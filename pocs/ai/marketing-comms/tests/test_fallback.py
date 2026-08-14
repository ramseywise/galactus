"""Step 5 gate: the deterministic truncation fallback.

Done-when: `validate(fallback(bad_draft, template), template) == []` holds for
every fixture — the fallback provably always satisfies the contract.
"""

from __future__ import annotations

import pytest

from galactus.guardrails.fallback import (
    FILLER_WORD,
    fallback,
    fallback_report,
    was_degraded,
)
from guardrails.validator import count_words, validate
from models import FieldConstraint, LayoutTemplate

_LONG = " ".join(["overlong"] * 200)


def _bad_drafts(clean: dict[str, str]) -> dict[str, dict[str, str]]:
    """Every way a draft can breach the contract, keyed by a readable name."""
    return {
        "empty": {},
        "over_words_headline": {**clean, "headline": _LONG},
        "over_chars_subheadline": {**clean, "subheadline": "x" * 500},
        "under_words_column": {**clean, "column_left": "far too short"},
        "empty_string_column": {**clean, "column_left": ""},
        "whitespace_column": {**clean, "column_right": "   \n  "},
        "missing_cta": {k: v for k, v in clean.items() if k != "cta"},
        "url_hero_image": {**clean, "hero_image": "https://example.com/x.png"},
        "prose_logo": {**clean, "sender_logo": "the logo, top-left"},
        "hex_accent_color": {**clean, "accent_color": "#e07a3f"},
        "unknown_color_name": {**clean, "accent_color": "chartreuse"},
        "unknown_field": {**clean, "footer": "not in template"},
        "everything_wrong": {
            "headline": _LONG,
            "subheadline": "y" * 400,
            "column_left": "tiny",
            "pull_quote": _LONG,
            "hero_image": "not-a-token",
            "accent_color": "#123456",
            "stray_one": "x",
            "stray_two": "y",
        },
        "all_fields_blank": {
            "headline": "",
            "subheadline": "",
            "column_left": "",
            "column_right": "",
            "pull_quote": "",
            "cta": "",
            "hero_image": "",
            "sender_logo": "",
            "accent_color": "",
        },
        "single_giant_word": {**clean, "headline": "x" * 300},
        "no_sentence_boundary": {**clean, "column_left": " ".join(["word"] * 300)},
        "many_sentences": {
            **clean,
            "column_left": "One two three four five six. " * 40,
        },
    }


# ---------------------------------------------------------------------------
# The invariant — the whole point of this module
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_name", list(_bad_drafts({}).keys()))
def test_fallback_output_always_satisfies_the_contract(clean_draft, template, case_name):
    bad = _bad_drafts(clean_draft)[case_name]
    repaired = fallback(bad, template)
    assert validate(repaired, template) == [], (
        f"case {case_name!r} left violations: {validate(repaired, template)}"
    )


def test_fallback_is_idempotent(clean_draft, template):
    """Repairing a repaired draft changes nothing — no oscillation."""
    for bad in _bad_drafts(clean_draft).values():
        once = fallback(bad, template)
        assert fallback(once, template) == once


def test_fallback_preserves_an_already_valid_draft(clean_draft, template):
    assert fallback(clean_draft, template) == clean_draft


def test_fallback_never_raises_on_hostile_input(template):
    for draft in ({}, {"headline": ""}, {"unknown": "x"}, {"accent_color": "\n"}):
        assert validate(fallback(draft, template), template) == []


def test_fallback_survives_a_template_with_no_theme_colors():
    """The one path that must not fail must not fail on a malformed template.

    A `color_ref` field with an empty `theme_colors` is malformed and nothing
    ships that way — but the fallback is the escape hatch the contract
    guarantee rests on, and raising here would fail the request at exactly the
    moment the fallback exists to rescue it. Degrading to a reported violation
    is acceptable; an exception is not.
    """
    malformed = LayoutTemplate(
        template_id="no_colors",
        description="A template that declares a color field but no colors.",
        theme_colors={},
        fields=[FieldConstraint(name="accent_color", kind="color_ref")],
    )

    result = fallback({"accent_color": "primary"}, malformed)

    assert result == {"accent_color": ""}


def test_fallback_does_not_mutate_the_input(clean_draft, template):
    bad = {**clean_draft, "headline": _LONG, "stray": "x"}
    before = dict(bad)
    fallback(bad, template)
    assert bad == before


# ---------------------------------------------------------------------------
# Truncation quality — valid is the floor, not the whole requirement
# ---------------------------------------------------------------------------


def test_truncation_never_splits_a_word(clean_draft, template):
    clean_draft["subheadline"] = " ".join(["encyclopaedia"] * 40)
    result = fallback(clean_draft, template)["subheadline"]
    assert all(word == "encyclopaedia" for word in result.split())


def test_truncation_prefers_a_sentence_boundary(clean_draft, template):
    clean_draft["pull_quote"] = (
        "This sentence fits inside the limit. And this trailing clause does not "
        "belong because it runs well past the ceiling for the field."
    )
    result = fallback(clean_draft, template)["pull_quote"]
    assert result.endswith(".")
    assert result == "This sentence fits inside the limit."


def test_sentence_boundary_skipped_when_it_would_discard_most_content(clean_draft, template):
    """A period after two words must not shrink a 95-word column to two words."""
    clean_draft["column_left"] = "Yes. " + " ".join(["substantive"] * 300)
    result = fallback(clean_draft, template)["column_left"]
    assert count_words(result) > 47


def test_over_limit_text_is_cut_to_the_maximum_not_below(clean_draft, template):
    clean_draft["column_left"] = " ".join(["word"] * 300)
    result = fallback(clean_draft, template)["column_left"]
    field = template.field_by_name("column_left")
    assert count_words(result) == field.max_words


def test_char_ceiling_respected_even_when_word_count_passes(clean_draft, template):
    clean_draft["subheadline"] = " ".join(["encyclopaedias"] * 15)
    result = fallback(clean_draft, template)["subheadline"]
    field = template.field_by_name("subheadline")
    assert len(result) <= field.max_chars
    assert count_words(result) <= field.max_words


def test_single_word_longer_than_char_ceiling_is_hard_cut():
    template = LayoutTemplate(
        template_id="t",
        fields=[FieldConstraint(name="a", max_chars=10)],
        theme_colors={"primary": "#000"},
    )
    result = fallback({"a": "x" * 50}, template)
    assert result["a"] == "x" * 10
    assert validate(result, template) == []


# ---------------------------------------------------------------------------
# Padding under-length fields
# ---------------------------------------------------------------------------


def test_short_field_is_padded_to_the_floor(clean_draft, template):
    clean_draft["column_left"] = "three words here"
    result = fallback(clean_draft, template)["column_left"]
    field = template.field_by_name("column_left")
    assert count_words(result) >= field.min_words
    assert result.startswith("three words here")


def test_padding_uses_neutral_filler_not_invented_content(clean_draft, template):
    clean_draft["column_left"] = "seed"
    result = fallback(clean_draft, template)["column_left"]
    padding = result.split()[1:]
    assert set(padding) == {FILLER_WORD}


def test_missing_text_field_is_synthesized_valid(clean_draft, template):
    del clean_draft["column_right"]
    result = fallback(clean_draft, template)
    assert count_words(result["column_right"]) >= template.field_by_name("column_right").min_words


# ---------------------------------------------------------------------------
# Non-text kinds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_value", ["https://example.com/x.png", "logo.png", "the logo", "", "{{Bad}}"]
)
def test_bad_image_placeholder_becomes_the_field_token(clean_draft, template, bad_value):
    clean_draft["hero_image"] = bad_value
    assert fallback(clean_draft, template)["hero_image"] == "{{hero_image}}"


def test_valid_placeholder_is_left_alone(clean_draft, template):
    clean_draft["hero_image"] = "{{custom_slot}}"
    assert fallback(clean_draft, template)["hero_image"] == "{{custom_slot}}"


@pytest.mark.parametrize("bad_value", ["#e07a3f", "chartreuse", "", "primary "])
def test_bad_color_ref_falls_back_to_a_theme_color(clean_draft, template, bad_value):
    clean_draft["accent_color"] = bad_value
    result = fallback(clean_draft, template)["accent_color"]
    assert result in template.theme_colors


def test_valid_color_ref_is_left_alone(clean_draft, template):
    clean_draft["accent_color"] = "secondary"
    assert fallback(clean_draft, template)["accent_color"] == "secondary"


def test_unknown_fields_are_dropped(clean_draft, template):
    result = fallback({**clean_draft, "footer": "x", "sidebar": "y"}, template)
    assert set(result) == template.field_names


# ---------------------------------------------------------------------------
# Degradation reporting — the caller must be able to say quality dropped
# ---------------------------------------------------------------------------


def test_report_lists_changed_fields(clean_draft, template):
    bad = {**clean_draft, "headline": _LONG, "accent_color": "#000", "stray": "x"}
    repaired, changed = fallback_report(bad, template)
    assert changed == ["accent_color", "headline", "stray"]
    assert validate(repaired, template) == []


def test_report_is_empty_for_a_clean_draft(clean_draft, template):
    repaired, changed = fallback_report(clean_draft, template)
    assert changed == []
    assert repaired == clean_draft


def test_was_degraded_matches_validation(clean_draft, template):
    assert not was_degraded(clean_draft, template)
    assert was_degraded({**clean_draft, "headline": _LONG}, template)


# ---------------------------------------------------------------------------
# Template sanity — the fallback's guarantee depends on satisfiable ranges
# ---------------------------------------------------------------------------


def test_no_template_field_has_an_unsatisfiable_range(template):
    """min_words padding must fit under max_chars, or no output could be valid.

    Guards the one case `_pad_to_words` cannot repair: a floor that cannot be
    reached without breaching the character ceiling.
    """
    for field in template.fields:
        if field.min_words is None or field.max_chars is None:
            continue
        shortest = len(" ".join([FILLER_WORD] * field.min_words))
        assert shortest <= field.max_chars, (
            f"field {field.name!r}: min_words={field.min_words} cannot fit in "
            f"max_chars={field.max_chars}"
        )
