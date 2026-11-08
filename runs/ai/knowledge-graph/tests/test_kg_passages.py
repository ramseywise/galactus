"""Passages: quote + following sentence, tier/build/hop stamped, tri-state freshness."""

from __future__ import annotations

from pathlib import Path

import pytest
from kg_store_helpers import promoted, put

from kg.profile import normalise
from kg.store import SqliteStore

BODY = (
    "Intro line. Swapping answer order mitigates position bias in pairwise judging. "
    "It costs one extra call. Unrelated tail."
)
QUOTE = "Swapping answer order mitigates position bias in pairwise judging."


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    (root / "eval").mkdir(parents=True)
    (root / "eval" / "p.md").write_text(BODY, encoding="utf-8")
    return root


def _store(tmp_path: Path, corpus: Path) -> SqliteStore:
    store = SqliteStore(tmp_path / "kg.db", corpus_root=corpus)
    promoted(store, "b1", profile_hash="p-build")
    body = normalise(BODY)
    start = body.index(QUOTE)
    from kg.models import Evidence, Judgement, Triple

    t = Triple(
        subject="Swapping answer order",
        subject_type="Method",
        relation="mitigates",
        object="position bias",
        object_type="FailureMode",
        page_path="eval/p.md",
    )
    store.write_triple(
        "b1",
        t,
        Evidence(quote=QUOTE, span=(start, start + len(QUOTE)), page_path="eval/p.md"),
        Judgement(seat="judge-a", label="supported", score=0.95),
        "accept",
    )
    return store


def test_fresh_passage_carries_quote_plus_next_sentence(tmp_path: Path, corpus: Path) -> None:
    store = _store(tmp_path, corpus)
    [p] = store.passages({"position bias"}, 1, current_profile_hash="p-build")
    assert p.freshness == "fresh"
    assert p.text == QUOTE + " It costs one extra call."
    assert (p.tier, p.build_id, p.source_path, p.hop) == ("accept", "b1", "eval/p.md", 1)


def test_differing_profile_hash_reports_unverified(tmp_path: Path, corpus: Path) -> None:
    store = _store(tmp_path, corpus)
    [p] = store.passages({"position bias"}, 1, current_profile_hash="p-now")
    assert p.freshness == "unverified"
    assert p.text == QUOTE


def test_no_current_hash_is_unverified_never_fresh(tmp_path: Path, corpus: Path) -> None:
    store = _store(tmp_path, corpus)
    [p] = store.passages({"position bias"}, 1)
    assert p.freshness == "unverified"


def test_quote_gone_from_current_body_is_stale(tmp_path: Path, corpus: Path) -> None:
    store = _store(tmp_path, corpus)
    (corpus / "eval" / "p.md").write_text("Rewritten entirely.", encoding="utf-8")
    [p] = store.passages({"position bias"}, 1, current_profile_hash="p-now")
    assert p.freshness == "stale"


def test_review_tier_never_in_default_passages(tmp_path: Path, corpus: Path) -> None:
    store = _store(tmp_path, corpus)
    put(store, "b1", "position bias", "produces", "Judge Drift", tier="review")
    assert {p.triple.object for p in store.passages({"position bias"}, 1)} == {"position bias"}
    widened = store.passages({"position bias"}, 1, frozenset({"accept", "review"}))
    assert {p.tier for p in widened} == {"accept", "review"}


def test_second_hop_passage_is_stamped_hop_two(tmp_path: Path, corpus: Path) -> None:
    store = _store(tmp_path, corpus)
    put(store, "b1", "position bias", "instance-of", "Judge Bias")
    hops = {p.triple.object: p.hop for p in store.passages({"Swapping answer order"}, 2)}
    assert hops == {"position bias": 1, "Judge Bias": 2}
