"""SQLite GraphStore: promoted-only default reads, tier filter, bounded hops, scoped delete."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from kg_store_helpers import promoted, put

from kg.models import ALL_TIERS, PageResult
from kg.store import BUSY_TIMEOUT_MS, GraphStore, SqliteStore, UnknownBuild


@pytest.fixture
def store(tmp_path: Path) -> SqliteStore:
    return SqliteStore(tmp_path / "kg.db")


def _edges(triples) -> set[tuple[str, str]]:
    return {(t.subject, t.object) for t in triples}


def test_satisfies_protocol(store: SqliteStore) -> None:
    assert isinstance(store, GraphStore)


def test_busy_timeout_and_wal(store: SqliteStore) -> None:
    conn = store._new_connection()
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == BUSY_TIMEOUT_MS
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    finally:
        conn.close()


def test_two_hop_closure_on_five_node_chain(store: SqliteStore) -> None:
    promoted(store, "b1")
    for s, o in [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E")]:
        put(store, "b1", s, "requires", o)
    assert _edges(store.hops({"A"}, 1)) == {("A", "B")}
    assert _edges(store.hops({"A"}, 2)) == {("A", "B"), ("B", "C")}
    assert _edges(store.hops({"C"}, 1)) == {("B", "C"), ("C", "D")}


def test_hops_match_seed_case_insensitively(store: SqliteStore) -> None:
    promoted(store, "b1")
    put(store, "b1", "Position Bias", "mitigates", "Judge Drift")
    assert len(store.hops({"position  BIAS"}, 1)) == 1


@pytest.mark.parametrize("k", [0, 3])
def test_k_out_of_bounds_refused(store: SqliteStore, k: int) -> None:
    with pytest.raises(ValueError, match="k must be"):
        store.hops({"A"}, k)


@pytest.mark.parametrize("status", ["building", "halted", "complete"])
def test_unpromoted_build_contributes_nothing_by_default(store: SqliteStore, status) -> None:
    store.open_build("b1", "pack0", "p0")
    store.set_build_status("b1", status)
    put(store, "b1", "A", "requires", "B", tier="accept")
    assert store.hops({"A"}, 2) == []
    assert store.passages({"A"}, 2) == []
    # An explicit build_id still reads it, for inspection before promote.
    assert len(store.hops({"A"}, 2, build_id="b1")) == 1


def test_review_tier_excluded_by_default(store: SqliteStore) -> None:
    promoted(store, "b1")
    put(store, "b1", "A", "requires", "B", tier="accept")
    put(store, "b1", "A", "produces", "C", tier="review")
    put(store, "b1", "A", "measures", "D", tier="reject")
    assert _edges(store.hops({"A"}, 1)) == {("A", "B")}
    assert {p.tier for p in store.passages({"A"}, 1)} == {"accept"}
    assert _edges(store.hops({"A"}, 1, frozenset({"accept", "review"}))) == {
        ("A", "B"),
        ("A", "C"),
    }
    assert len(store.hops({"A"}, 1, ALL_TIERS)) == 3


def test_review_edge_does_not_bridge_hops(store: SqliteStore) -> None:
    promoted(store, "b1")
    put(store, "b1", "A", "requires", "B", tier="review")
    put(store, "b1", "B", "requires", "C", tier="accept")
    assert store.hops({"A"}, 2) == []


def test_rewriting_same_key_is_idempotent(store: SqliteStore) -> None:
    promoted(store, "b1")
    put(store, "b1", "A", "requires", "B", score=0.6, tier="review")
    put(store, "b1", "a", "requires", "b", score=0.9, tier="accept")
    rows = store.triples("b1")
    assert len(rows) == 1
    assert rows[0].tier == "accept"
    assert rows[0].judgement.score == 0.9
    assert store.stats("b1").triples == {"accept": 1}


def test_delete_build_removes_only_that_build(tmp_path: Path, store: SqliteStore) -> None:
    promoted(store, "keep")
    promoted(store, "drop")
    put(store, "keep", "A", "requires", "B")
    put(store, "drop", "A", "requires", "B")
    put(store, "drop", "X", "requires", "Y")
    store.write_page_result("drop", PageResult(page_path="eval/p.md", status="no_candidates"))
    store.delete_build("drop")

    conn = sqlite3.connect(tmp_path / "kg.db")
    for table in ("triples", "mentions", "pages", "builds"):
        builds = {r[0] for r in conn.execute(f"SELECT build_id FROM {table}")}
        assert "drop" not in builds, table
    (n_ev,) = conn.execute("SELECT COUNT(*) FROM evidence").fetchone()
    (n_j,) = conn.execute("SELECT COUNT(*) FROM judgements").fetchone()
    conn.close()
    assert n_ev == n_j == 1
    assert len(store.triples("keep")) == 1
    with pytest.raises(UnknownBuild):
        store.stats("drop")


def test_stats_counts_pages_and_tiers(store: SqliteStore) -> None:
    store.open_build("b1", "pack0", "p0")
    store.write_page_result("b1", PageResult(page_path="a.md", status="no_candidates"))
    store.write_page_result("b1", PageResult(page_path="b.md", status="not_run", reason="api"))
    put(store, "b1", "A", "requires", "B", tier="review")
    s = store.stats("b1")
    assert s.status == "building"
    assert s.pages == {"no_candidates": 1, "not_run": 1}
    assert s.triples == {"review": 1}


def test_unknown_build_and_status_refused(store: SqliteStore) -> None:
    with pytest.raises(UnknownBuild):
        put(store, "nope", "A", "requires", "B")
    store.open_build("b1", "pack0", "p0")
    with pytest.raises(ValueError, match="unknown build status"):
        store.set_build_status("b1", "shipped")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="already exists"):
        store.open_build("b1", "pack0", "p0")
