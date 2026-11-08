"""Neo4j GraphStore: same semantics as SQLite, plus idempotent loads. Needs `NEO4J_URI`."""

from __future__ import annotations

import os

import pytest
from conftest import NEO4J_SKIP_REASON, TEST_BUILD_PREFIX
from kg_store_helpers import promoted, put

from kg.config import ConfigError, Settings
from kg.models import ALL_TIERS, PageResult
from kg.store import GraphStore, UnknownBuild

pytestmark = pytest.mark.skipif(not os.environ.get("NEO4J_URI"), reason=NEO4J_SKIP_REASON)

B = f"{TEST_BUILD_PREFIX}b1"


def _edges(triples) -> set[tuple[str, str]]:
    return {(t.subject, t.object) for t in triples}


def test_satisfies_protocol(neo4j_store) -> None:
    assert isinstance(neo4j_store, GraphStore)


def test_loading_twice_yields_same_counts(neo4j_store) -> None:
    store = neo4j_store
    promoted(store, B)
    store.write_page_result(B, PageResult(page_path="eval/p.md", status="no_candidates"))
    edges = [("A", "B"), ("B", "C"), ("C", "D")]
    for s, o in edges:
        put(store, B, s, "requires", o)
    first = store.stats(B)
    with store._session() as s:
        n_nodes = s.run("MATCH (m:Mention) RETURN count(m) AS n").single()["n"]
    for s, o in edges:  # the second load
        put(store, B, s, "requires", o)
    assert store.stats(B) == first
    assert first.triples == {"accept": 3}
    assert len(store.triples(B)) == 3
    with store._session() as s:
        assert s.run("MATCH (m:Mention) RETURN count(m) AS n").single()["n"] == n_nodes


def test_rewrite_replaces_not_duplicates(neo4j_store) -> None:
    store = neo4j_store
    promoted(store, B)
    put(store, B, "A", "requires", "B", tier="review", score=0.5)
    put(store, B, "A", "requires", "B", tier="accept", score=0.9)
    (st,) = store.triples(B)
    assert st.tier == "accept" and st.judgement.score == 0.9


def test_two_hop_closure_on_chain(neo4j_store) -> None:
    store = neo4j_store
    promoted(store, B)
    for s, o in [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E")]:
        put(store, B, s, "requires", o)
    assert _edges(store.hops({"A"}, 1)) == {("A", "B")}
    assert _edges(store.hops({"A"}, 2)) == {("A", "B"), ("B", "C")}
    assert _edges(store.hops({"C"}, 1)) == {("B", "C"), ("C", "D")}
    assert len(store.hops({"position  BIAS"}, 1)) == 0


@pytest.mark.parametrize("k", [0, 3])
def test_k_out_of_bounds_refused(neo4j_store, k: int) -> None:
    with pytest.raises(ValueError, match="k must be"):
        neo4j_store.hops({"A"}, k)


@pytest.mark.parametrize("status", ["building", "halted", "complete"])
def test_unpromoted_build_contributes_nothing_by_default(neo4j_store, status) -> None:
    store = neo4j_store
    store.open_build(B, "pack0", "p0")
    put(store, B, "A", "requires", "B")
    store.set_build_status(B, status)
    assert store.hops({"A"}, 1) == []
    assert len(store.hops({"A"}, 1, build_id=B)) == 1
    store.set_build_status(B, "promoted")
    assert len(store.hops({"A"}, 1)) == 1


def test_tier_filter_default_accept_only(neo4j_store) -> None:
    store = neo4j_store
    promoted(store, B)
    put(store, B, "A", "requires", "B", tier="accept")
    put(store, B, "A", "requires", "C", tier="review")
    assert _edges(store.hops({"A"}, 1)) == {("A", "B")}
    assert _edges(store.hops({"A"}, 1, ALL_TIERS)) == {("A", "B"), ("A", "C")}


def test_same_surface_on_two_pages_stays_two_mentions(neo4j_store) -> None:
    store = neo4j_store
    promoted(store, B)
    put(store, B, "Bias", "causes", "X", page="eval/p1.md")
    put(store, B, "Bias", "causes", "Y", page="eval/p2.md")
    with store._session() as s:
        n = s.run("MATCH (m:Mention {key: 'bias'}) RETURN count(m) AS n").single()["n"]
    assert n == 2
    assert _edges(store.hops({"Bias"}, 1)) == {("Bias", "X"), ("Bias", "Y")}


def test_delete_build_leaves_other_builds(neo4j_store) -> None:
    store = neo4j_store
    promoted(store, B)
    promoted(store, f"{TEST_BUILD_PREFIX}b2")
    put(store, B, "A", "requires", "B")
    put(store, f"{TEST_BUILD_PREFIX}b2", "A", "requires", "B")
    store.delete_build(B)
    with pytest.raises(UnknownBuild):
        store.stats(B)
    (t,) = store.hops({"A"}, 1)
    assert t.subject == "A"


def test_fulltext_index_finds_surface(neo4j_store) -> None:
    store = neo4j_store
    promoted(store, B)
    put(store, B, "Position Bias", "mitigates", "Judge Drift")
    # the index is eventually consistent for a moment after a write
    with store._session() as s:
        s.run("CALL db.awaitIndexes(30)").consume()
    assert "Position Bias" in store.search_surface("position")


def test_missing_uri_refuses_by_name(clean_env) -> None:
    with pytest.raises(ConfigError, match="NEO4J_URI"):
        Settings.load(use_dotenv=False).require_neo4j_uri()
