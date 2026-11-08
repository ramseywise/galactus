"""SQLite `GraphStore`: one file, recursive-CTE hops, promoted builds only by default."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from kg.models import ACCEPT_ONLY, Evidence, Judgement, PageResult, Tier, Triple
from kg.profile.normalise import norm_surface, normalise
from kg.store.passages import HopRow, graph_to_passages
from kg.store.protocol import (
    BUILD_STATUSES,
    BuildStats,
    BuildStatus,
    Passage,
    StoredTriple,
    UnknownBuild,
)

BUSY_TIMEOUT_MS = 5000
"""How long a connection waits on a locked database before raising (mirrors
marketing-comms `store.py`): a build writes while a query reads, and without a busy
handler that contention surfaces as an immediate `database is locked`."""

HARD_MAX_K = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS builds (
    build_id     TEXT PRIMARY KEY,
    pack_hash    TEXT NOT NULL,
    profile_hash TEXT NOT NULL,
    status       TEXT NOT NULL
                 CHECK (status IN ('building', 'complete', 'halted', 'promoted')),
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS pages (
    build_id     TEXT NOT NULL REFERENCES builds(build_id),
    page_path    TEXT NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('proposed', 'no_candidates', 'not_run')),
    reason       TEXT,
    n_candidates INTEGER NOT NULL,
    PRIMARY KEY (build_id, page_path)
);
CREATE TABLE IF NOT EXISTS mentions (
    build_id    TEXT NOT NULL REFERENCES builds(build_id),
    page_path   TEXT NOT NULL,
    norm        TEXT NOT NULL,
    surface     TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    PRIMARY KEY (build_id, page_path, norm, entity_type)
);
CREATE TABLE IF NOT EXISTS triples (
    id           INTEGER PRIMARY KEY,
    build_id     TEXT NOT NULL REFERENCES builds(build_id),
    subject      TEXT NOT NULL,
    subject_norm TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    relation     TEXT NOT NULL,
    object       TEXT NOT NULL,
    object_norm  TEXT NOT NULL,
    object_type  TEXT NOT NULL,
    page_path    TEXT NOT NULL,
    tier         TEXT NOT NULL CHECK (tier IN ('accept', 'review', 'reject')),
    score        REAL NOT NULL,
    seat         TEXT NOT NULL,
    UNIQUE (build_id, subject_norm, relation, object_norm, page_path)
);
CREATE INDEX IF NOT EXISTS idx_triples_subject ON triples (subject_norm);
CREATE INDEX IF NOT EXISTS idx_triples_object ON triples (object_norm);
CREATE TABLE IF NOT EXISTS evidence (
    triple_id  INTEGER PRIMARY KEY REFERENCES triples(id) ON DELETE CASCADE,
    quote      TEXT NOT NULL,
    span_start INTEGER NOT NULL,
    span_end   INTEGER NOT NULL,
    page_path  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS judgements (
    triple_id INTEGER NOT NULL REFERENCES triples(id) ON DELETE CASCADE,
    seat      TEXT NOT NULL,
    label     TEXT NOT NULL CHECK (label IN ('supported', 'not_supported', 'unclear')),
    score     REAL NOT NULL,
    model     TEXT,
    PRIMARY KEY (triple_id, seat)
);
"""

# `eligible` is the only place build status and tier are filtered; every read goes through it.
_HOPS_SQL = """
WITH RECURSIVE
eligible AS (
    SELECT t.* , b.profile_hash AS build_profile_hash
    FROM triples t JOIN builds b ON b.build_id = t.build_id
    WHERE {build_filter}
      AND t.tier IN (SELECT value FROM json_each(:tiers))
),
reach(node, hop) AS (
    SELECT value, 0 FROM json_each(:seeds)
    UNION
    SELECT CASE WHEN e.subject_norm = r.node THEN e.object_norm ELSE e.subject_norm END,
           r.hop + 1
    FROM reach r JOIN eligible e ON e.subject_norm = r.node OR e.object_norm = r.node
    WHERE r.hop + 1 < :k
)
SELECT e.*, MIN(r.hop) + 1 AS hop
FROM eligible e JOIN reach r ON e.subject_norm = r.node OR e.object_norm = r.node
GROUP BY e.id
ORDER BY hop, e.id
"""

_ROW_SQL = """
SELECT t.*, ev.quote, ev.span_start, ev.span_end, ev.page_path AS ev_page,
       j.seat AS j_seat, j.label, j.score AS j_score, j.model
FROM ({inner}) t
JOIN evidence ev ON ev.triple_id = t.id
JOIN judgements j ON j.triple_id = t.id AND j.seat = t.seat
ORDER BY {order}
"""


class SqliteStore:
    def __init__(self, db_path: Path, *, corpus_root: Path | None = None) -> None:
        self.db_path = db_path
        self.corpus_root = corpus_root
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    # -- plumbing ----------------------------------------------------------------------

    def _new_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = self._new_connection()
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _require_build(conn: sqlite3.Connection, build_id: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM builds WHERE build_id = ?", (build_id,)).fetchone()
        if row is None:
            raise UnknownBuild(build_id)
        return row

    # -- writes ------------------------------------------------------------------------

    def open_build(self, build_id: str, pack_hash: str, profile_hash: str) -> None:
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO builds (build_id, pack_hash, profile_hash, status) "
                    "VALUES (?, ?, ?, 'building')",
                    (build_id, pack_hash, profile_hash),
                )
            except sqlite3.IntegrityError:
                raise ValueError(f"build {build_id!r} already exists") from None

    def write_page_result(self, build_id: str, result: PageResult) -> None:
        with self._connect() as conn:
            self._require_build(conn, build_id)
            conn.execute(
                "INSERT INTO pages (build_id, page_path, status, reason, n_candidates) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT (build_id, page_path) DO UPDATE SET "
                "status = excluded.status, reason = excluded.reason, "
                "n_candidates = excluded.n_candidates",
                (build_id, result.page_path, result.status, result.reason, len(result.candidates)),
            )

    def write_triple(
        self, build_id: str, triple: Triple, evidence: Evidence, judgement: Judgement, tier: Tier
    ) -> None:
        """Upsert on the canonical key: re-writing the same key replaces, never duplicates."""
        s_norm, rel, o_norm, page = triple.key
        with self._connect() as conn:
            self._require_build(conn, build_id)
            (triple_id,) = conn.execute(
                "INSERT INTO triples (build_id, subject, subject_norm, subject_type, relation, "
                "object, object_norm, object_type, page_path, tier, score, seat) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (build_id, subject_norm, relation, object_norm, page_path) "
                "DO UPDATE SET subject = excluded.subject, subject_type = excluded.subject_type, "
                "object = excluded.object, object_type = excluded.object_type, "
                "tier = excluded.tier, score = excluded.score, seat = excluded.seat "
                "RETURNING id",
                (
                    build_id,
                    triple.subject,
                    s_norm,
                    triple.subject_type,
                    rel,
                    triple.object,
                    o_norm,
                    triple.object_type,
                    page,
                    tier,
                    judgement.score,
                    judgement.seat,
                ),
            ).fetchone()
            conn.execute(
                "INSERT OR REPLACE INTO evidence VALUES (?, ?, ?, ?, ?)",
                (triple_id, evidence.quote, *evidence.span, evidence.page_path),
            )
            conn.execute(
                "INSERT OR REPLACE INTO judgements VALUES (?, ?, ?, ?, ?)",
                (triple_id, judgement.seat, judgement.label, judgement.score, judgement.model),
            )
            for surface, etype in (
                (triple.subject, triple.subject_type),
                (triple.object, triple.object_type),
            ):
                conn.execute(
                    "INSERT OR IGNORE INTO mentions VALUES (?, ?, ?, ?, ?)",
                    (build_id, page, norm_surface(surface), surface, etype),
                )

    def set_build_status(self, build_id: str, status: BuildStatus) -> None:
        if status not in BUILD_STATUSES:
            raise ValueError(f"unknown build status {status!r}")
        with self._connect() as conn:
            self._require_build(conn, build_id)
            conn.execute("UPDATE builds SET status = ? WHERE build_id = ?", (status, build_id))

    def delete_build(self, build_id: str) -> None:
        """Remove this build's rows and no others (the undo for a bad promote, fog FA-005)."""
        with self._connect() as conn:
            self._require_build(conn, build_id)
            ids = "SELECT id FROM triples WHERE build_id = :b"
            conn.execute(f"DELETE FROM evidence WHERE triple_id IN ({ids})", {"b": build_id})
            conn.execute(f"DELETE FROM judgements WHERE triple_id IN ({ids})", {"b": build_id})
            for table in ("triples", "mentions", "pages", "builds"):
                conn.execute(f"DELETE FROM {table} WHERE build_id = ?", (build_id,))

    # -- reads -------------------------------------------------------------------------

    @staticmethod
    def _stored(row: sqlite3.Row) -> StoredTriple:
        return StoredTriple(
            triple=Triple(
                subject=row["subject"],
                subject_type=row["subject_type"],
                relation=row["relation"],
                object=row["object"],
                object_type=row["object_type"],
                page_path=row["page_path"],
            ),
            evidence=Evidence(
                quote=row["quote"],
                span=(row["span_start"], row["span_end"]),
                page_path=row["ev_page"],
            ),
            judgement=Judgement(
                seat=row["j_seat"], label=row["label"], score=row["j_score"], model=row["model"]
            ),
            tier=row["tier"],
            build_id=row["build_id"],
        )

    def _hop_rows(
        self, entities: set[str], k: int, tiers: frozenset[Tier], build_id: str | None
    ) -> list[HopRow]:
        if not 1 <= k <= HARD_MAX_K:
            raise ValueError(f"k must be in [1, {HARD_MAX_K}], got {k}")
        if not entities or not tiers:
            return []
        build_filter = "t.build_id = :build_id" if build_id else "b.status = 'promoted'"
        inner = _HOPS_SQL.format(build_filter=build_filter)
        sql = _ROW_SQL.format(inner=inner, order="t.hop, t.id")
        params = {
            "seeds": json.dumps(sorted({norm_surface(e) for e in entities})),
            "tiers": json.dumps(sorted(tiers)),
            "k": k,
            "build_id": build_id,
        }
        with self._connect() as conn:
            if build_id:
                self._require_build(conn, build_id)
            rows = conn.execute(sql, params).fetchall()
        return [
            HopRow(stored=self._stored(r), hop=r["hop"], build_profile_hash=r["build_profile_hash"])
            for r in rows
        ]

    def hops(
        self,
        entities: set[str],
        k: int,
        tiers: frozenset[Tier] = ACCEPT_ONLY,
        *,
        build_id: str | None = None,
    ) -> list[Triple]:
        return [r.stored.triple for r in self._hop_rows(entities, k, tiers, build_id)]

    def _body(self, page_path: str) -> str | None:
        if self.corpus_root is None:
            return None
        f = self.corpus_root / page_path
        return normalise(f.read_text(encoding="utf-8")) if f.is_file() else None

    def passages(
        self,
        entities: set[str],
        k: int,
        tiers: frozenset[Tier] = ACCEPT_ONLY,
        *,
        build_id: str | None = None,
        current_profile_hash: str | None = None,
    ) -> list[Passage]:
        return graph_to_passages(
            self._hop_rows(entities, k, tiers, build_id),
            current_profile_hash=current_profile_hash,
            body_lookup=self._body,
        )

    def triples(self, build_id: str) -> list[StoredTriple]:
        inner = "SELECT * FROM triples WHERE build_id = :build_id"
        with self._connect() as conn:
            self._require_build(conn, build_id)
            rows = conn.execute(
                _ROW_SQL.format(inner=inner, order="t.id"), {"build_id": build_id}
            ).fetchall()
        return [self._stored(r) for r in rows]

    def stats(self, build_id: str) -> BuildStats:
        with self._connect() as conn:
            b = self._require_build(conn, build_id)
            pages = dict(
                conn.execute(
                    "SELECT status, COUNT(*) FROM pages WHERE build_id = ? GROUP BY status",
                    (build_id,),
                ).fetchall()
            )
            triples = dict(
                conn.execute(
                    "SELECT tier, COUNT(*) FROM triples WHERE build_id = ? GROUP BY tier",
                    (build_id,),
                ).fetchall()
            )
        return BuildStats(
            build_id=build_id,
            status=b["status"],
            pack_hash=b["pack_hash"],
            profile_hash=b["profile_hash"],
            pages=pages,
            triples=triples,
        )
