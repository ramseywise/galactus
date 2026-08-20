"""Persistence for uploaded PDFs and generation jobs.

Two tables, SQLite. The schema is deliberately document-shaped — a row is an id
plus a JSON blob plus a couple of indexed scalars — because the production
target is Firestore, and a store built around joins would not survive the
migration. Swapping the backend means reimplementing this module's functions,
not rewriting the callers.

Job state is the reason this exists at all. The generation endpoint returns 202
immediately and does the work in the background, so the result has to live
somewhere the polling endpoint can find it. `dedup_key` carries the idempotency
guarantee from the cloud design: the datastore, not the queue, is what makes a
redelivered or double-submitted request one billed generation instead of two.
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

BUSY_TIMEOUT_MS = 5000
"""How long a connection waits on a locked database before raising.

The API polls jobs from a sync route (worker thread) while the background task
commits updates from the event loop thread — without a busy handler that
contention surfaces as an immediate `database is locked` 500 instead of a
few-millisecond wait.
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS pdfs (
    pdf_id     TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    role       TEXT NOT NULL,
    filename   TEXT NOT NULL,
    content    BLOB NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_pdfs_company ON pdfs (company_id);

CREATE TABLE IF NOT EXISTS jobs (
    job_id     TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    status     TEXT NOT NULL,
    dedup_key  TEXT,
    payload    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs (company_id);
"""
"""`payload` holds the whole job document as JSON.

Result shape changes with the template, so columns would mean a migration every
time a designer adds a field. The scalars that are promoted to real columns are
exactly the ones queried on: `company_id` for listings, `dedup_key` for the
idempotency lookup, `created_at` so the retention sweep can age rows out.
"""

DEDUP_INDEX = """
DROP INDEX IF EXISTS idx_jobs_dedup;
CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_dedup_active
ON jobs (dedup_key) WHERE dedup_key IS NOT NULL AND status != 'failed';
"""
"""One active job per dedup key, enforced by the database.

The API's check-then-insert (`find_active_job` then `create_job`) is a race:
two identical requests interleaving between the check and the insert used to
produce two billed generations — the exact double spend the dedup key exists
to prevent. The partial index makes the loser's insert fail instead; its WHERE
clause mirrors `find_active_job`, so a failed job releases its key and a
resubmission generates rather than replaying the error.

Kept out of SCHEMA because creating it can fail on a database that predates it
(duplicate active rows already present) — `_init_schema` resolves those first.
The DROP clears this index's non-unique predecessor.
"""


class DuplicateJobError(Exception):
    """An active job already holds this dedup key.

    Raised from `create_job` when the unique index rejects the insert — the
    caller lost a submission race and should re-read the winning job.
    """


class Store:
    """A SQLite-backed store for PDFs and jobs.

    Connections are opened per operation rather than held. SQLite objects are
    bound to the thread that created them, and FastAPI runs sync handlers in a
    worker pool — a shared connection would fail intermittently under exactly
    the concurrency this API is built for.
    """

    def __init__(self, path: str | Path | None = ":memory:") -> None:
        # A bare ":memory:" database is private to its connection, so the
        # per-operation connections below would each get an empty one. The
        # shared-cache URI form gives every connection the same database while
        # keeping them per-thread, which is what SQLite requires: FastAPI runs
        # sync handlers in a worker pool, and a connection reused across
        # threads raises.
        self._in_memory = path is None or str(path) == ":memory:"
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
        conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        if not self._in_memory:
            # WAL lets the polling reads proceed while a job update commits.
            # Not applicable to shared-cache in-memory databases.
            conn.execute("PRAGMA journal_mode = WAL")
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
            try:
                conn.executescript(DEDUP_INDEX)
            except sqlite3.IntegrityError:
                # A database from before the unique index can hold duplicate
                # active rows. Keep the newest per key and fail the rest —
                # failing is honest (each duplicate was a real double spend)
                # and frees the key for the index to build.
                self._fail_duplicate_active_jobs(conn)
                conn.executescript(DEDUP_INDEX)

    @staticmethod
    def _fail_duplicate_active_jobs(conn: sqlite3.Connection) -> None:
        message = "duplicate of a newer job with the same dedup key; superseded at migration"
        rows = conn.execute(
            "SELECT job_id, payload FROM jobs WHERE dedup_key IS NOT NULL "
            "AND status != 'failed' AND rowid NOT IN ("
            "  SELECT max(rowid) FROM jobs WHERE dedup_key IS NOT NULL "
            "  AND status != 'failed' GROUP BY dedup_key)"
        ).fetchall()
        for row in rows:
            payload = json.loads(row["payload"])
            payload["error"] = message
            conn.execute(
                "UPDATE jobs SET status = 'failed', payload = ? WHERE job_id = ?",
                (json.dumps(payload), row["job_id"]),
            )

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

    def get_pdfs(self, company_id: str, role: str | None = None) -> list[dict[str, Any]]:
        """Return every stored PDF for a company, optionally filtered by role."""
        sql = "SELECT * FROM pdfs WHERE company_id = ?"
        params: list[Any] = [company_id]
        if role is not None:
            sql += " AND role = ?"
            params.append(role)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [dict(row) for row in rows]

    def list_pdfs(self, company_id: str) -> list[dict[str, Any]]:
        """PDF metadata for a company — no content BLOBs.

        The listing endpoint exists so a bad upload can be found and deleted
        instead of silently poisoning every later generation; shipping the
        full document bytes back for that would be absurd.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT pdf_id, company_id, role, filename, length(content) AS size_bytes, "
                "created_at FROM pdfs WHERE company_id = ?",
                (company_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_pdf(self, company_id: str, pdf_id: str) -> bool:
        """Delete one PDF. Returns False if it did not exist for this company.

        Scoped by company as well as id so a caller cannot delete another
        company's context by guessing ids.
        """
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM pdfs WHERE company_id = ? AND pdf_id = ?",
                (company_id, pdf_id),
            )
            return cursor.rowcount > 0

    # -- Jobs ---------------------------------------------------------------

    def create_job(
        self, company_id: str, payload: dict[str, Any], dedup_key: str | None = None
    ) -> str:
        """Record a queued job and return its id.

        Raises `DuplicateJobError` when an active job already holds
        `dedup_key` — the unique index decides, so two racing submissions
        cannot both insert.
        """
        job_id = str(uuid.uuid4())
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO jobs (job_id, company_id, status, dedup_key, payload) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (job_id, company_id, "queued", dedup_key, json.dumps(payload)),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateJobError(
                    f"an active job already holds dedup key {dedup_key}"
                ) from exc
        return job_id

    def find_active_job(self, dedup_key: str) -> dict[str, Any] | None:
        """The newest non-failed job for this dedup key, or None.

        Failed jobs do not count as duplicates on purpose: resubmitting a
        request whose last attempt died should generate, not replay the error.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE dedup_key = ? AND status != 'failed' "
                "ORDER BY created_at DESC LIMIT 1",
                (dedup_key,),
            ).fetchone()

        return self._job_document(row)

    def update_job(self, job_id: str, status: JobStatus, **fields: Any) -> None:
        """Set a job's status, merging `fields` into its payload."""
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
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
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()

        return self._job_document(row)

    def fail_stale_jobs(self) -> int:
        """Mark every queued/running job as failed. Returns how many were.

        Called at process startup: `BackgroundTasks` dies with the process, so
        a job still non-terminal at boot is one whose worker no longer exists.
        Failing it loudly turns "the client polls forever" into an explicit
        error the client can act on.
        """
        message = "process restarted before this job finished; resubmit the request"
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT job_id, payload FROM jobs WHERE status IN ('queued', 'running')"
            ).fetchall()
            for row in rows:
                payload = json.loads(row["payload"])
                payload["error"] = message
                conn.execute(
                    "UPDATE jobs SET status = 'failed', payload = ? WHERE job_id = ?",
                    (json.dumps(payload), row["job_id"]),
                )
        return len(rows)

    def sweep_expired(self, retention_days: int) -> tuple[int, int]:
        """Delete finished jobs and uploaded PDFs older than `retention_days`.

        Returns (jobs deleted, pdfs deleted). Only terminal jobs are swept: a
        queued/running row either belongs to a live worker or gets failed
        loudly at the next boot — deleting it under the worker would resurrect
        the stuck-job problem. PDFs age out unconditionally; context is
        re-uploadable, and keeping client documents forever is the liability
        retention exists to bound. A swept succeeded job also releases its
        dedup key, so the idempotency window is at most the retention window.

        The cutoff is computed by SQLite against the same clock and in the
        same format `created_at` defaults use, so the comparison can never
        drift on formatting.
        """
        if retention_days <= 0:
            raise ValueError(f"retention_days must be positive, got {retention_days}")

        modifier = f"-{retention_days} days"
        cutoff_sql = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now', ?)"
        with self._connect() as conn:
            jobs = conn.execute(
                "DELETE FROM jobs WHERE status IN ('succeeded', 'failed') "
                f"AND created_at < {cutoff_sql}",
                (modifier,),
            ).rowcount
            pdfs = conn.execute(
                f"DELETE FROM pdfs WHERE created_at < {cutoff_sql}",
                (modifier,),
            ).rowcount
        return jobs, pdfs

    @staticmethod
    def _job_document(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "job_id": row["job_id"],
            "company_id": row["company_id"],
            "status": row["status"],
            "created_at": row["created_at"],
            **json.loads(row["payload"]),
        }
