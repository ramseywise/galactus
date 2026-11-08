"""Weak gold from typed wikilinks: resolution, filtering, hand-row preservation, real corpus."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kg.config import Settings
from kg.retrieve.weak_gold import title_index, weak_gold, write_rows


def page(root: Path, rel: str, title: str | None, body: str) -> None:
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    head = f"---\ntitle: {title}\n---\n\n" if title else ""
    f.write_text(head + body, encoding="utf-8")


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    page(
        tmp_path,
        "eval/a.md",
        "Alpha Page",
        "# Alpha Page\n\n- [[Beta Page]] — extends (why)\n"
        "- [[Gamma Thing]] — related\n- [[Nowhere]] — related\n- [[Alpha Page]] — related\n",
    )
    page(tmp_path, "eval/b.md", "Beta Page", "No typed links, only prose [[Alpha Page]].\n")
    page(tmp_path, "patterns/g.md", None, "# Gamma Thing\n\nbody\n")
    return tmp_path


def test_titles_resolve_from_frontmatter_h1_and_stem(corpus: Path) -> None:
    idx = title_index(corpus)
    assert idx["alpha page"] == "eval/a.md"
    assert idx["gamma thing"] == "patterns/g.md"
    assert idx["g"] == "patterns/g.md"


def test_rows_carry_resolved_neighbours_and_drop_self_and_unresolved(corpus: Path) -> None:
    res = weak_gold(corpus)
    assert len(res.rows) == 1  # b.md has only a prose link, so it yields no row
    row = res.rows[0]
    assert row["source"] == "weak" and row["from_page"] == "eval/a.md"
    assert row["expected"] == ["eval/b.md", "patterns/g.md"]
    assert "Alpha Page" in str(row["question"])
    assert (res.links_seen, res.links_unresolved) == (4, 1)


def test_write_rows_replaces_weak_and_keeps_hand_rows(corpus: Path, tmp_path: Path) -> None:
    out = tmp_path / "q.jsonl"
    hand = {"id": "h1", "source": "hand", "question": "q?", "expected": ["eval/a.md"]}
    out.write_text(json.dumps(hand) + "\n" + json.dumps({"id": "old", "source": "weak"}) + "\n")
    write_rows(weak_gold(corpus).rows, out)
    rows = [json.loads(x) for x in out.read_text().splitlines()]
    assert [r["source"] for r in rows] == ["hand", "weak"] and rows[0] == hand


def test_real_eval_corpus_yields_at_least_30_rows() -> None:
    root = Settings.load(use_dotenv=False).corpus_root
    if not (root / "eval").is_dir():
        pytest.skip("corpus absent")
    res = weak_gold(root)
    assert len(res.rows) >= 30
    assert all(r["expected"] and r["from_page"] != r["expected"] for r in res.rows)
