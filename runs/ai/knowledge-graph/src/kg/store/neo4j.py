"""Neo4j `GraphStore`: per-page mention nodes, idempotent MERGE loads, bounded hops.

Same semantics as `SqliteStore` so the parity test can drive both through identical calls:

- A node is a *mention* `(key, page)`: the normalised surface form on one page. There is
  no cross-page merge in storage (uniqueness constraint on `(key, page)`).
- A relationship is `(build_id, relation)` between two mentions on one page, which is the
  SQLite canonical key `(build, subject_norm, relation, object_norm, page)`. Writing it again
  replaces its properties and never adds a second edge.
- Default reads see only `promoted` builds and only `accept` triples; `build_id=` reads that
  build whatever its status; `k` is refused outside `[1, HARD_MAX_K]`.
- Traversal follows the surface key, not the node, exactly as the SQLite CTE joins on
  `*_norm`: a surface repeated on two pages is one waypoint for reachability while the two
  mentions stay separate rows in storage. A single `*1..2` path match cannot cross pages
  (the two mentions are different nodes), so `hops()` expands one bounded level per query,
  at most `HARD_MAX_K` of them.

Credentials: `Settings` carries only `neo4j_uri`, so user, password and database come from
`NEO4J_USER` / `NEO4J_PASSWORD` / `NEO4J_DATABASE` here, defaulting to the values in
`docker-compose.yml`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import neo4j
from neo4j.exceptions import ConstraintError

from kg.config import Settings
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
from kg.store.sqlite import HARD_MAX_K

DEFAULT_USER = "neo4j"
DEFAULT_PASSWORD = "kg-local-dev-pw"
"""Matches the compose default. A local-dev convenience, not a secret."""

SCHEMA = (
    "CREATE CONSTRAINT mention_key_page IF NOT EXISTS "
    "FOR (m:Mention) REQUIRE (m.key, m.page) IS UNIQUE",
    "CREATE CONSTRAINT build_id IF NOT EXISTS FOR (b:Build) REQUIRE b.build_id IS UNIQUE",
    "CREATE CONSTRAINT page_build_path IF NOT EXISTS "
    "FOR (p:Page) REQUIRE (p.build_id, p.path) IS UNIQUE",
    "CREATE CONSTRAINT counter_name IF NOT EXISTS FOR (c:Counter) REQUIRE c.name IS UNIQUE",
    "CREATE FULLTEXT INDEX mention_surface IF NOT EXISTS FOR (m:Mention) ON EACH [m.surface]",
)

_WRITE_TRIPLE = """
MERGE (c:Counter {name: 'triple_seq'})
SET c.v = coalesce(c.v, 0) + 1
WITH c.v AS seq
MERGE (s:Mention {key: $s, page: $page}) ON CREATE SET s.surface = $s_surface
MERGE (o:Mention {key: $o, page: $page}) ON CREATE SET o.surface = $o_surface
MERGE (s)-[r:REL {type: $rel, build_id: $build}]->(o)
ON CREATE SET r.seq = seq
SET r.subject = $s_surface, r.subject_type = $s_type,
    r.object = $o_surface, r.object_type = $o_type,
    r.tier = $tier, r.score = $score, r.seat = $seat,
    r.label = $label, r.model = $model,
    r.quote = $quote, r.span_start = $span_start, r.span_end = $span_end,
    r.ev_page = $ev_page
"""

_EDGES = """
MATCH (a:Mention)-[r:REL]->(b:Mention)
WHERE r.build_id IN $builds AND r.tier IN $tiers
  AND (a.key IN $keys OR b.key IN $keys)
RETURN a.key AS a_key, b.key AS b_key, a.page AS page, properties(r) AS p
ORDER BY r.seq
"""


def _run_edges(tx: neo4j.ManagedTransaction, params: dict[str, Any]) -> list[neo4j.Record]:
    return list(tx.run(_EDGES, params))


class Neo4jStore:
    def __init__(
        self,
        uri: str,
        user: str | None = None,
        password: str | None = None,
        *,
        database: str | None = None,
        corpus_root: Path | None = None,
        driver: neo4j.Driver | None = None,
    ) -> None:
        self.corpus_root = corpus_root
        self.database = database or os.environ.get("NEO4J_DATABASE") or "neo4j"
        self._driver = driver or neo4j.GraphDatabase.driver(
            uri,
            auth=(
                user or os.environ.get("NEO4J_USER") or DEFAULT_USER,
                password or os.environ.get("NEO4J_PASSWORD") or DEFAULT_PASSWORD,
            ),
        )
        with self._session() as s:
            for stmt in SCHEMA:
                s.run(stmt).consume()

    @classmethod
    def from_settings(cls, settings: Settings, **kw: Any) -> Neo4jStore:
        """Refuses by name (`NEO4J_URI`) when the URI is unset."""
        return cls(settings.require_neo4j_uri(), **kw)

    def close(self) -> None:
        self._driver.close()

    # -- plumbing ----------------------------------------------------------------------

    def _session(self) -> neo4j.Session:
        return self._driver.session(database=self.database)

    @staticmethod
    def _build_row(tx: neo4j.ManagedTransaction, build_id: str) -> dict[str, Any]:
        rec = tx.run(
            "MATCH (b:Build {build_id: $b}) RETURN properties(b) AS p", b=build_id
        ).single()
        if rec is None:
            raise UnknownBuild(build_id)
        return dict(rec["p"])

    # -- writes ------------------------------------------------------------------------

    def open_build(self, build_id: str, pack_hash: str, profile_hash: str) -> None:
        def work(tx: neo4j.ManagedTransaction) -> None:
            tx.run(
                "CREATE (:Build {build_id: $b, pack_hash: $pack, profile_hash: $prof, "
                "status: 'building', created_at: toString(datetime())})",
                b=build_id,
                pack=pack_hash,
                prof=profile_hash,
            ).consume()

        with self._session() as s:
            try:
                s.execute_write(work)
            except ConstraintError:
                raise ValueError(f"build {build_id!r} already exists") from None

    def write_page_result(self, build_id: str, result: PageResult) -> None:
        def work(tx: neo4j.ManagedTransaction) -> None:
            self._build_row(tx, build_id)
            tx.run(
                "MERGE (p:Page {build_id: $b, path: $path}) "
                "SET p.status = $status, p.reason = $reason, p.n_candidates = $n",
                b=build_id,
                path=result.page_path,
                status=result.status,
                reason=result.reason,
                n=len(result.candidates),
            ).consume()

        with self._session() as s:
            s.execute_write(work)

    def write_triple(
        self, build_id: str, triple: Triple, evidence: Evidence, judgement: Judgement, tier: Tier
    ) -> None:
        """Upsert on the canonical key: re-writing the same key replaces, never duplicates."""
        s_norm, rel, o_norm, page = triple.key

        def work(tx: neo4j.ManagedTransaction) -> None:
            self._build_row(tx, build_id)
            tx.run(
                _WRITE_TRIPLE,
                s=s_norm,
                o=o_norm,
                page=page,
                rel=rel,
                build=build_id,
                s_surface=triple.subject,
                s_type=triple.subject_type,
                o_surface=triple.object,
                o_type=triple.object_type,
                tier=tier,
                score=judgement.score,
                seat=judgement.seat,
                label=judgement.label,
                model=judgement.model,
                quote=evidence.quote,
                span_start=evidence.span[0],
                span_end=evidence.span[1],
                ev_page=evidence.page_path,
            ).consume()

        with self._session() as s:
            s.execute_write(work)

    def set_build_status(self, build_id: str, status: BuildStatus) -> None:
        if status not in BUILD_STATUSES:
            raise ValueError(f"unknown build status {status!r}")

        def work(tx: neo4j.ManagedTransaction) -> None:
            self._build_row(tx, build_id)
            tx.run("MATCH (b:Build {build_id: $b}) SET b.status = $st", b=build_id, st=status)

        with self._session() as s:
            s.execute_write(work)

    def delete_build(self, build_id: str) -> None:
        """Remove this build's relationships, pages and node, and mentions left with none."""

        def work(tx: neo4j.ManagedTransaction) -> None:
            self._build_row(tx, build_id)
            tx.run("MATCH ()-[r:REL {build_id: $b}]->() DELETE r", b=build_id).consume()
            tx.run("MATCH (p:Page {build_id: $b}) DELETE p", b=build_id).consume()
            tx.run("MATCH (b:Build {build_id: $b}) DELETE b", b=build_id).consume()
            tx.run("MATCH (m:Mention) WHERE NOT (m)--() DELETE m").consume()

        with self._session() as s:
            s.execute_write(work)

    # -- reads -------------------------------------------------------------------------

    @staticmethod
    def _stored(page: str, p: dict[str, Any]) -> StoredTriple:
        return StoredTriple(
            triple=Triple(
                subject=p["subject"],
                subject_type=p["subject_type"],
                relation=p["type"],
                object=p["object"],
                object_type=p["object_type"],
                page_path=page,
            ),
            evidence=Evidence(
                quote=p["quote"], span=(p["span_start"], p["span_end"]), page_path=p["ev_page"]
            ),
            judgement=Judgement(
                seat=p["seat"], label=p["label"], score=p["score"], model=p.get("model")
            ),
            tier=p["tier"],
            build_id=p["build_id"],
        )

    def _hop_rows(
        self, entities: set[str], k: int, tiers: frozenset[Tier], build_id: str | None
    ) -> list[HopRow]:
        if not 1 <= k <= HARD_MAX_K:
            raise ValueError(f"k must be in [1, {HARD_MAX_K}], got {k}")
        if not entities or not tiers:
            return []
        with self._session() as s:

            def builds(tx: neo4j.ManagedTransaction) -> dict[str, str]:
                if build_id:
                    return {build_id: self._build_row(tx, build_id)["profile_hash"]}
                rows = tx.run(
                    "MATCH (b:Build {status: 'promoted'}) RETURN b.build_id AS id, "
                    "b.profile_hash AS ph"
                )
                return {r["id"]: r["ph"] for r in rows}

            profile_hashes = s.execute_read(builds)
            if not profile_hashes:
                return []
            reached = {norm_surface(e) for e in entities}
            seen: set[tuple[str, str, str, str, str]] = set()
            out: list[HopRow] = []
            for level in range(1, k + 1):
                frontier = set(reached)
                params = {
                    "builds": list(profile_hashes),
                    "tiers": sorted(tiers),
                    "keys": sorted(frontier),
                }
                records = s.execute_read(_run_edges, params)
                for rec in records:
                    a_key, b_key, p = rec["a_key"], rec["b_key"], rec["p"]
                    if a_key in frontier:
                        reached.add(b_key)
                    if b_key in frontier:
                        reached.add(a_key)
                    ident = (p["build_id"], a_key, p["type"], b_key, rec["page"])
                    if ident in seen:
                        continue
                    seen.add(ident)
                    out.append(
                        HopRow(
                            stored=self._stored(rec["page"], p),
                            hop=level,
                            build_profile_hash=profile_hashes[p["build_id"]],
                        )
                    )
        return out

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
        def work(tx: neo4j.ManagedTransaction) -> list[StoredTriple]:
            self._build_row(tx, build_id)
            rows = tx.run(
                "MATCH (a:Mention)-[r:REL {build_id: $b}]->(:Mention) "
                "RETURN a.page AS page, properties(r) AS p ORDER BY r.seq",
                b=build_id,
            )
            return [self._stored(r["page"], r["p"]) for r in rows]

        with self._session() as s:
            return s.execute_read(work)

    def stats(self, build_id: str) -> BuildStats:
        def work(tx: neo4j.ManagedTransaction) -> BuildStats:
            b = self._build_row(tx, build_id)
            pages = {
                r["k"]: r["n"]
                for r in tx.run(
                    "MATCH (p:Page {build_id: $b}) RETURN p.status AS k, count(*) AS n", b=build_id
                )
            }
            triples = {
                r["k"]: r["n"]
                for r in tx.run(
                    "MATCH ()-[r:REL {build_id: $b}]->() RETURN r.tier AS k, count(*) AS n",
                    b=build_id,
                )
            }
            return BuildStats(
                build_id=build_id,
                status=b["status"],
                pack_hash=b["pack_hash"],
                profile_hash=b["profile_hash"],
                pages=pages,
                triples=triples,
            )

        with self._session() as s:
            return s.execute_read(work)

    def search_surface(self, text: str, limit: int = 10) -> list[str]:
        """Distinct surface forms matching `text` in the full-text index (entry-point lookup)."""
        with self._session() as s:
            rows = s.run(
                "CALL db.index.fulltext.queryNodes('mention_surface', $q) YIELD node, score "
                "RETURN DISTINCT node.surface AS surface LIMIT $n",
                q=text,
                n=limit,
            )
            return [r["surface"] for r in rows]
