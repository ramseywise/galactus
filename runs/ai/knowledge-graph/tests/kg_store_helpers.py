"""Shared builders for the store tests: one triple + evidence + judgement in one call."""

from __future__ import annotations

from kg.models import Evidence, Judgement, Tier, Triple
from kg.store import SqliteStore


def put(
    store: SqliteStore,
    build_id: str,
    s: str,
    rel: str,
    o: str,
    *,
    page: str = "eval/p.md",
    tier: Tier = "accept",
    quote: str | None = None,
    score: float = 0.9,
) -> Triple:
    quote = quote or f"{s} {rel} {o} in this sentence."
    t = Triple(
        subject=s,
        subject_type="Method",
        relation=rel,
        object=o,
        object_type="Metric",
        page_path=page,
    )
    ev = Evidence(quote=quote, span=(0, len(quote)), page_path=page)
    j = Judgement(seat="judge-a", label="supported", score=score, model="fake")
    store.write_triple(build_id, t, ev, j, tier)
    return t


def promoted(store: SqliteStore, build_id: str, profile_hash: str = "p0") -> str:
    store.open_build(build_id, "pack0", profile_hash)
    store.set_build_status(build_id, "promoted")
    return build_id
