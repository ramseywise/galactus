"""Step 4 gate: the deterministic validator.

Done-when: every constraint kind in FieldConstraint has a passing violation test
and a passing clean-draft test. Table-driven where the cases are homogeneous.
"""

from __future__ import annotations

import pytest
from galactus.layout.validator import count_words, is_valid, validate
from galactus.models import FieldConstraint, LayoutTemplate

# ---------------------------------------------------------------------------
# The clean case — the baseline every other test mutates away from
# ---------------------------------------------------------------------------


def test_clean_draft_has_no_violations(clean_draft, template):
    assert validate(clean_draft, template) == []
    assert is_valid(clean_draft, template)


# ---------------------------------------------------------------------------
# One violation per constraint kind, table-driven
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field_name", "bad_value", "expected_constraint"),
    [
        ("headline", " ".join(["word"] * 20), "max_words"),
        ("column_left", "far too short", "min_words"),
        ("subheadline", "x" * 200, "max_chars"),
        ("hero_image", "https://example.com/hero.png", "image_placeholder"),
        ("accent_color", "#e07a3f", "color_ref"),
    ],
)
def test_each_constraint_kind_is_violated(
    clean_draft, template, field_name, bad_value, expected_constraint
):
    clean_draft[field_name] = bad_value
    violations = validate(clean_draft, template)

    matching = [
        v
        for v in violations
        if v.field == field_name and v.constraint == expected_constraint
    ]
    assert len(matching) == 1, f"expected one {expected_constraint} on {field_name}"
    assert matching[0].repair_hint


def test_missing_field_is_required_violation(clean_draft, template):
    del clean_draft["cta"]
    violations = validate(clean_draft, template)
    assert [(v.field, v.constraint) for v in violations] == [("cta", "required")]


def test_unknown_field_is_reported(clean_draft, template):
    clean_draft["footer_note"] = "not in the template"
    violations = validate(clean_draft, template)
    assert [(v.field, v.constraint) for v in violations] == [
        ("footer_note", "unknown_field")
    ]


# ---------------------------------------------------------------------------
# Violations carry machine-readable repair context
# ---------------------------------------------------------------------------


def test_max_words_violation_reports_actual_and_limit(clean_draft, template):
    clean_draft["headline"] = " ".join(["word"] * 15)
    violation = next(
        v for v in validate(clean_draft, template) if v.field == "headline"
    )
    assert violation.actual == 15
    assert violation.limit == 9
    assert "15" in violation.repair_hint and "9" in violation.repair_hint


def test_min_words_hint_explains_the_whitespace_reason(clean_draft, template):
    clean_draft["column_right"] = "too short"
    violation = next(
        v for v in validate(clean_draft, template) if v.constraint == "min_words"
    )
    assert "whitespace" in violation.repair_hint


def test_color_ref_hint_lists_valid_choices(clean_draft, template):
    clean_draft["accent_color"] = "chartreuse"
    violation = next(
        v for v in validate(clean_draft, template) if v.constraint == "color_ref"
    )
    assert "primary" in violation.limit
    assert "accent" in violation.repair_hint


def test_image_placeholder_hint_names_the_expected_token(clean_draft, template):
    clean_draft["sender_logo"] = "the company logo, top left"
    violation = next(
        v
        for v in validate(clean_draft, template)
        if v.constraint == "image_placeholder"
    )
    assert "{{sender_logo}}" in violation.repair_hint


# ---------------------------------------------------------------------------
# Reporting behaviour — all violations at once, not just the first
# ---------------------------------------------------------------------------


def test_all_violations_reported_in_one_pass(clean_draft, template):
    """The repair loop needs the full set; one-at-a-time would cost N LLM calls."""
    clean_draft["headline"] = " ".join(["word"] * 30)
    clean_draft["accent_color"] = "not_a_theme_color"
    del clean_draft["cta"]
    clean_draft["stray"] = "x"

    constraints = {(v.field, v.constraint) for v in validate(clean_draft, template)}
    assert constraints == {
        ("headline", "max_words"),
        ("headline", "max_chars"),
        ("accent_color", "color_ref"),
        ("cta", "required"),
        ("stray", "unknown_field"),
    }


def test_one_field_can_break_two_constraints(clean_draft, template):
    clean_draft["pull_quote"] = " ".join(["antidisestablishmentarianism"] * 30)
    violations = [v for v in validate(clean_draft, template) if v.field == "pull_quote"]
    assert {v.constraint for v in violations} == {"max_words", "max_chars"}


def test_empty_draft_reports_every_field_as_required(template):
    violations = validate({}, template)
    assert len(violations) == len(template.fields)
    assert all(v.constraint == "required" for v in violations)


# ---------------------------------------------------------------------------
# Boundary conditions — off-by-one is the whole point of this module
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("word_count", [3, 9])
def test_word_limits_are_inclusive(clean_draft, template, word_count):
    """min_words=3 and max_words=9 on headline: both bounds are allowed values."""
    clean_draft["headline"] = " ".join(["w"] * word_count)
    assert [v for v in validate(clean_draft, template) if v.field == "headline"] == []


@pytest.mark.parametrize(
    ("word_count", "constraint"), [(2, "min_words"), (10, "max_words")]
)
def test_one_past_each_word_bound_violates(
    clean_draft, template, word_count, constraint
):
    clean_draft["headline"] = " ".join(["w"] * word_count)
    violations = [v for v in validate(clean_draft, template) if v.field == "headline"]
    assert [v.constraint for v in violations] == [constraint]


def test_max_chars_is_inclusive():
    template = LayoutTemplate(
        template_id="t",
        fields=[FieldConstraint(name="a", max_chars=5)],
        theme_colors={"primary": "#000"},
    )
    assert validate({"a": "12345"}, template) == []
    assert validate({"a": "123456"}, template)[0].constraint == "max_chars"


def test_empty_string_is_present_but_may_break_min_words(template):
    """Empty is not the same as missing: it is a min_words problem, not required."""
    violations = [
        v for v in validate({"column_left": ""}, template) if v.field == "column_left"
    ]
    assert [v.constraint for v in violations] == ["min_words"]


def test_whitespace_only_text_counts_as_zero_words(template):
    violations = [
        v
        for v in validate({"column_left": "   \n\t  "}, template)
        if v.field == "column_left"
    ]
    assert [v.constraint for v in violations] == ["min_words"]
    assert violations[0].actual == 0


# ---------------------------------------------------------------------------
# Fields with no constraints declared
# ---------------------------------------------------------------------------


def test_unconstrained_text_field_accepts_anything():
    template = LayoutTemplate(
        template_id="t",
        fields=[FieldConstraint(name="notes")],
        theme_colors={"primary": "#000"},
    )
    assert validate({"notes": "x" * 10_000}, template) == []


# ---------------------------------------------------------------------------
# Placeholder / color-ref accepted forms
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["{{hero_image}}", "{{img_2}}"])
def test_valid_placeholder_tokens_accepted(value):
    template = LayoutTemplate(
        template_id="t",
        fields=[FieldConstraint(name="img", kind="image_placeholder")],
        theme_colors={"primary": "#000"},
    )
    assert validate({"img": value}, template) == []


@pytest.mark.parametrize(
    "value", ["{{Hero}}", "{hero}", "hero_image", "{{hero image}}", "", "{{}}"]
)
def test_malformed_placeholder_tokens_rejected(value):
    template = LayoutTemplate(
        template_id="t",
        fields=[FieldConstraint(name="img", kind="image_placeholder")],
        theme_colors={"primary": "#000"},
    )
    assert validate({"img": value}, template)[0].constraint == "image_placeholder"


def test_every_theme_color_key_is_an_accepted_color_ref(clean_draft, template):
    for key in template.theme_colors:
        clean_draft["accent_color"] = key
        assert [
            v for v in validate(clean_draft, template) if v.field == "accent_color"
        ] == []


# ---------------------------------------------------------------------------
# count_words — the shared definition
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", 0),
        ("   ", 0),
        ("one", 1),
        ("two words", 2),
        ("  leading and trailing  ", 3),
        ("multiple   internal    spaces", 3),
        ("line\nbreaks\tand\ttabs", 4),
        ("hyphenated-word counts once", 3),
    ],
)
def test_count_words(text, expected):
    assert count_words(text) == expected


# ---------------------------------------------------------------------------
# Purity — no mutation of the caller's data
# ---------------------------------------------------------------------------


def test_validate_does_not_mutate_the_draft(clean_draft, template):
    clean_draft["headline"] = " ".join(["word"] * 40)
    before = dict(clean_draft)
    validate(clean_draft, template)
    assert clean_draft == before


def test_validate_is_deterministic(clean_draft, template):
    clean_draft["headline"] = " ".join(["word"] * 40)
    first = validate(clean_draft, template)
    second = validate(clean_draft, template)
    assert first == second
