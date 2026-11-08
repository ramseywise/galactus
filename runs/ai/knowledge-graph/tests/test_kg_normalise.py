"""Normalisation: frontmatter, wikilinks and comments are stripped; prose survives."""

from __future__ import annotations

from pathlib import Path

from kg.profile import NORMALISATION_RULE_HASH, norm_surface, normalise
from kg.profile.normalise import CANONICAL_LINK_TYPES

FIXTURES = Path(__file__).parent / "fixtures" / "pages"


def test_frontmatter_is_stripped() -> None:
    body = normalise((FIXTURES / "normal.md").read_text(encoding="utf-8"))
    assert "Frontmatter says" not in body
    assert "title:" not in body
    assert body.startswith("# Judge Calibration")


def test_wikilinks_reduce_to_display_or_target() -> None:
    assert normalise("see [[Expected Calibration Error|ECE]] here") == "see ECE here"
    assert normalise("the [[Gold Set]] holds labels") == "the Gold Set holds labels"
    assert normalise("see [[Gold Set#Schema]]") == "see Gold Set"


def test_typed_link_suffix_dropped_for_canonical_types_only() -> None:
    for t in CANONICAL_LINK_TYPES:
        assert normalise(f"- [[Gold Set]] — {t}") == "- Gold Set"
    assert normalise("- [[Pairwise Judging]] — related (same family)") == (
        "- Pairwise Judging (same family)"
    )
    # Prose after a dash is not a link type and keeps its dash.
    assert normalise("[[Gold Set]] — a labelled sample") == "Gold Set — a labelled sample"
    # A canonical type as a word prefix is not a match.
    assert normalise("[[X]] — relatedness matters") == "X — relatedness matters"


def test_html_comments_are_stripped() -> None:
    assert normalise("before <!-- auto-linked --> after") == "before after"


def test_hard_wraps_collapse_but_paragraphs_stay() -> None:
    raw = "line one\nwraps here\n\n\n  second   paragraph\t\n"
    assert normalise(raw) == "line one wraps here\n\nsecond paragraph"


def test_nfc() -> None:
    decomposed = "café"
    assert normalise(decomposed) == "café"


def test_frontmatter_only_page_is_empty() -> None:
    assert normalise((FIXTURES / "empty.md").read_text(encoding="utf-8")) == ""


def test_dashes_inside_body_are_not_frontmatter() -> None:
    assert normalise("text\n---\nmore") == "text --- more"


def test_norm_surface() -> None:
    assert norm_surface("  Position  BIAS ") == "position bias"


def test_rule_hash_is_sha256_hex() -> None:
    assert len(NORMALISATION_RULE_HASH) == 64
    int(NORMALISATION_RULE_HASH, 16)
