"""Persistence for uploaded PDFs and generation jobs.

Two tables, SQLite. The schema is deliberately document-shaped — a row is an id
plus a JSON blob plus a couple of indexed scalars — because the production
target is Firestore, and a store built around joins would not survive the
migration. Swapping the backend means reimplementing this module's six
functions, not rewriting the callers.

Job state is the reason this exists at all. The generation endpoint returns 202
immediately and does the work in the background, so the result has to live
somewhere the polling endpoint can find it.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

JobStatus = Literal["queued", "running", "succeeded", "failed"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS pdfs (
    pdf_id     TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    role       TEXT NOT NULL,
    filename   TEXT NOT NULL,
    content    BLOB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pdfs_company ON pdfs (company_id);

CREATE TABLE IF NOT EXISTS jobs (
    job_id     TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    status     TEXT NOT NULL,
    payload    TEXT NOT NULL
);
"""
"""`payload` holds the whole job document as JSON.

Result shape changes with the template, so columns would mean a migration every
time a designer adds a field. The scalars that are promoted to real columns are
exactly the ones queried on.
"""


class Store:
    """A SQLite-backed store for PDFs and jobs.

    Connections are opened per operation rather than held. SQLite objects are
    bound to the thread that created them, and FastAPI runs sync handlers in a
    worker pool — a shared connection would fail intermittently under exactly
    the concurrency this API is built for.
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        # A bare ":memory:" database is private to its connection, so the
        # per-operation connections below would each get an empty one. The
        # shared-cache URI form gives every connection the same database while
        # keeping them per-thread, which is what SQLite requires: FastAPI runs
        # sync handlers in a worker pool, and a connection reused across
        # threads raises.
        self._in_memory = str(path) == ":memory:"
        if self._in_memory:
            self.path = f"file:galactus-{uuid.uuid4().hex}?mode=memory&cache=shared"
        else:
            self.path = str(path)

        # An in-memory database lives only as long as one connection remains
        # open, so hold one aside purely to keep it alive. It is never used for
        # queries — every operation opens its own.
        self._keepalive = self._new_connection() if self._in_memory else None
        self._init_schema()

    def _new_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, uri=self._in_memory)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = self._new_connection()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def close(self) -> None:
        if self._keepalive is not None:
            self._keepalive.close()
            self._keepalive = None

    # -- PDFs ---------------------------------------------------------------

    def put_pdf(self, company_id: str, role: str, filename: str, content: bytes) -> str:
        """Store an uploaded PDF and return its generated id."""
        pdf_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO pdfs (pdf_id, company_id, role, filename, content) "
                "VALUES (?, ?, ?, ?, ?)",
                (pdf_id, company_id, role, filename, content),
            )
        return pdf_id

    def get_pdfs(
        self, company_id: str, role: str | None = None
    ) -> list[dict[str, Any]]:
        """Return every stored PDF for a company, optionally filtered by role."""
        sql = "SELECT * FROM pdfs WHERE company_id = ?"
        params: list[Any] = [company_id]
        if role is not None:
            sql += " AND role = ?"
            params.append(role)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [dict(row) for row in rows]

    # -- Jobs ---------------------------------------------------------------

    def create_job(self, company_id: str, payload: dict[str, Any]) -> str:
        """Record a queued job and return its id."""
        job_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs (job_id, company_id, status, payload) "
                "VALUES (?, ?, ?, ?)",
                (job_id, company_id, "queued", json.dumps(payload)),
            )
        return job_id

    def update_job(self, job_id: str, status: JobStatus, **fields: Any) -> None:
        """Set a job's status, merging `fields` into its payload."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"no such job: {job_id}")

            payload = json.loads(row["payload"])
            payload.update(fields)

            conn.execute(
                "UPDATE jobs SET status = ?, payload = ? WHERE job_id = ?",
                (status, json.dumps(payload), job_id),
            )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Return a job document, or None if the id is unknown."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()

        if row is None:
            return None

        return {
            "job_id": row["job_id"],
            "company_id": row["company_id"],
            "status": row["status"],
            **json.loads(row["payload"]),
        }
