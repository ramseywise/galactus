"""SQLite and Neo4j answer identical `hops()` / `passages()` on one fixture (spec F6).

The fixture repeats one surface form ("Position Bias") on two pages and puts a review-tier
edge, an unpromoted build and a three-edge chain beside it, so a store that merged mentions
across pages, ignored tier, or ignored build status would diverge from the other.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from conftest import NEO4J_SKIP_REASON, TEST_BUILD_PREFIX
from kg_store_helpers import promoted, put

from kg.models import ALL_TIERS
from kg.store import SqliteStore

pytestmark = pytest.mark.skipif(not os.environ.get("NEO4J_URI"), reason=NEO4J_SKIP_REASON)

LIVE = f"{TEST_BUILD_PREFIX}live"
DRAFT = f"{TEST_BUILD_PREFIX}draft"
P1, P2 = "eval/p1.md", "eval/p2.md"


def _load(store) -> None:
    promoted(store, LIVE)
    put(store, LIVE, "Position Bias", "mitigates", "Judge Drift", page=P1)
    put(store, LIVE, "Judge Drift", "requires", "Calibration", page=P1)
    put(store, LIVE, "Position Bias", "causes", "Order Effect", page=P2)  # same surface, page 2
    put(store, LIVE, "Order Effect", "degrades", "Recall", page=P2)
    put(store, LIVE, "Recall", "measured_by", "Hit Rate", page=P2)
    put(store, LIVE, "Position Bias", "relates_to", "Noise", page=P2, tier="review")
    store.open_build(DRAFT, "pack0", "p0")
    put(store, DRAFT, "Position Bias", "causes", "Ghost", page=P1)


@pytest.fixture
def stores(tmp_path: Path, neo4j_store):
    sqlite = SqliteStore(tmp_path / "kg.db")
    _load(sqlite)
    _load(neo4j_store)
    return sqlite, neo4j_store


def _keys(triples) -> set[tuple[str, str, str, str]]:
    return {(t.subject, t.relation, t.object, t.page_path) for t in triples}


@pytest.mark.parametrize("seed", ["Position Bias", "Judge Drift", "Recall", "position  bias"])
@pytest.mark.parametrize("k", [1, 2])
@pytest.mark.parametrize("tiers", [None, ALL_TIERS], ids=["accept", "all"])
def test_hops_identical(stores, seed: str, k: int, tiers) -> None:
    sqlite, neo = stores
    args = (tiers,) if tiers else ()
    a = sqlite.hops({seed}, k, *args)
    b = neo.hops({seed}, k, *args)
    assert _keys(a) == _keys(b)
    assert _keys(a)  # a vacuous empty==empty would prove nothing


def test_hops_cross_page_waypoint(stores) -> None:
    """Judge Drift reaches page 2 through the shared "Position Bias" key at hop 2."""
    _, neo = stores
    got = _keys(neo.hops({"Judge Drift"}, 2))
    assert ("Position Bias", "causes", "Order Effect", P2) in got
    assert ("Position Bias", "causes", "Ghost", P1) not in got  # unpromoted build


def test_passages_identical_with_hop_and_tier(stores) -> None:
    sqlite, neo = stores

    def view(ps):
        return {(*_keys([p.triple]).pop(), p.hop, p.tier, p.build_id, p.freshness) for p in ps}

    for k in (1, 2):
        assert view(sqlite.passages({"Position Bias"}, k)) == view(
            neo.passages({"Position Bias"}, k)
        )


def test_explicit_build_identical(stores) -> None:
    sqlite, neo = stores
    assert _keys(sqlite.hops({"Position Bias"}, 1, build_id=DRAFT)) == _keys(
        neo.hops({"Position Bias"}, 1, build_id=DRAFT)
    )
    assert _keys(sqlite.triples(LIVE) and [s.triple for s in sqlite.triples(LIVE)]) == _keys(
        [s.triple for s in neo.triples(LIVE)]
    )
    assert sqlite.stats(LIVE).triples == neo.stats(LIVE).triples
