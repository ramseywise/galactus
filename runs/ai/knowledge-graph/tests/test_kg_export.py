"""Exports: JSONL round-trips exactly; markdown writes one wikilinked page per subject."""

from __future__ import annotations

from pathlib import Path

from kg_store_helpers import promoted, put

from kg.store import SqliteStore, export_jsonl, export_markdown, read_jsonl


def _store(tmp_path: Path) -> SqliteStore:
    store = SqliteStore(tmp_path / "kg.db")
    promoted(store, "b1")
    put(store, "b1", "Pairwise Judging", "requires", "Gold Set", tier="accept")
    put(store, "b1", "Pairwise Judging", "measures", "ECE", tier="review")
    put(store, "b1", "Answer Swap", "mitigates", "Position Bias", page="eval/q.md")
    return store


def test_jsonl_round_trips(tmp_path: Path) -> None:
    store = _store(tmp_path)
    out = tmp_path / "out" / "b1.jsonl"
    assert export_jsonl(store, "b1", out) == 3
    assert read_jsonl(out) == store.triples("b1")


def test_markdown_one_page_per_subject_with_wikilinks(tmp_path: Path) -> None:
    store = _store(tmp_path)
    pages = export_markdown(store, "b1", tmp_path / "md")
    assert sorted(p.name for p in pages) == ["Answer Swap.md", "Pairwise Judging.md"]
    text = (tmp_path / "md" / "Pairwise Judging.md").read_text(encoding="utf-8")
    assert "- requires [[Gold Set]] (accept)" in text
    assert "- measures [[ECE]] (review)" in text
    assert "source: `eval/p.md`" in text
    assert "type: Method" in text
