"""The `GraphStore` seam: what any store (SQLite now, Neo4j in Phase B) must answer.

Default reads see only `promoted` builds and only `accept`-tier triples. A halted or
crashed build never serves its partial accepts (fog FA-001), and a `review` triple never
reaches a passage unless the caller asks for that tier by name (spec F1).
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from kg.models import ACCEPT_ONLY, Evidence, Judgement, PageResult, Tier, Triple

BuildStatus = Literal["building", "complete", "halted", "promoted"]
BUILD_STATUSES: frozenset[str] = frozenset({"building", "complete", "halted", "promoted"})

Freshness = Literal["fresh", "stale", "unverified"]
"""`fresh`: the build's profile hash equals the current corpus profile. `stale`: a check
ran against the current body and the quote is no longer there. `unverified`: the hashes
differ (or no current hash was given) and nothing has re-checked, so "not checked" never
reads as "fresh" (fog FA-007)."""


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StoredTriple(_Frozen):
    triple: Triple
    evidence: Evidence
    judgement: Judgement
    tier: Tier
    build_id: str


class Passage(_Frozen):
    text: str
    tier: Tier
    build_id: str
    source_path: str
    hop: int
    freshness: Freshness
    triple: Triple


class BuildStats(_Frozen):
    build_id: str
    status: BuildStatus
    pack_hash: str
    profile_hash: str
    pages: dict[str, int]
    triples: dict[str, int]


class UnknownBuild(KeyError):  # noqa: N818 — reads as the condition it names
    """No build with that id."""


@runtime_checkable
class GraphStore(Protocol):
    def open_build(self, build_id: str, pack_hash: str, profile_hash: str) -> None: ...
    def write_page_result(self, build_id: str, result: PageResult) -> None: ...
    def write_triple(
        self, build_id: str, triple: Triple, evidence: Evidence, judgement: Judgement, tier: Tier
    ) -> None: ...
    def hops(
        self,
        entities: set[str],
        k: int,
        tiers: frozenset[Tier] = ACCEPT_ONLY,
        *,
        build_id: str | None = None,
    ) -> list[Triple]: ...
    def passages(
        self,
        entities: set[str],
        k: int,
        tiers: frozenset[Tier] = ACCEPT_ONLY,
        *,
        build_id: str | None = None,
        current_profile_hash: str | None = None,
    ) -> list[Passage]: ...
    def triples(self, build_id: str) -> list[StoredTriple]: ...
    def stats(self, build_id: str) -> BuildStats: ...
    def set_build_status(self, build_id: str, status: BuildStatus) -> None: ...
    def delete_build(self, build_id: str) -> None: ...
