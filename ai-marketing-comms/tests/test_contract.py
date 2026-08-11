"""Step 3 gate: the shipped template validates, and the state model is sound."""

from __future__ import annotations

import json

import pytest
from galactus.layout.contract import (
    TemplateNotFoundError,
    available_templates,
    default_template_dir,
    load_template,
    load_template_file,
)
from galactus.models import (
    Fact,
    FieldConstraint,
    LayoutTemplate,
    PipelineState,
    Violation,
)
from pydantic import ValidationError

# --------------------------------------------------------------------------
# The shipped template
# --------------------------------------------------------------------------


def test_two_column_brief_validates_from_disk():
    path = default_template_dir() / "two_column_brief.json"
    template = LayoutTemplate.model_validate(json.load(path.open(encoding="utf-8")))
    assert template.template_id == "two_column_brief"


def test_two_column_brief_loads_by_id():
    template = load_template("two_column_brief")
    assert len(template.fields) == 9
    assert template.field_names == {
        "headline",
        "subheadline",
        "column_left",
        "column_right",
        "pull_quote",
        "cta",
        "hero_image",
        "sender_logo",
        "accent_color",
    }


def test_shipped_template_covers_every_field_kind():
    """Step 4's validator dispatches on kind — the fixture must exercise all of them."""
    kinds = {f.kind for f in load_template("two_column_brief").fields}
    assert kinds == {"text", "image_placeholder", "color_ref"}


def test_shipped_template_is_listed():
    assert "two_column_brief" in available_templates()


def test_missing_template_raises():
    with pytest.raises(TemplateNotFoundError):
        load_template("no_such_template")


def test_template_id_mismatch_raises(tmp_path):
    (tmp_path / "claimed_id.json").write_text(
        json.dumps(
            {
                "template_id": "actual_id",
                "fields": [{"name": "a"}],
                "theme_colors": {"primary": "#fff"},
            }
        )
    )
    with pytest.raises(ValueError, match="template id mismatch"):
        load_template("claimed_id", template_dir=tmp_path)


def test_malformed_template_fails_at_load(tmp_path):
    (tmp_path / "bad.json").write_text(json.dumps({"template_id": "bad"}))
    with pytest.raises(ValidationError):
        load_template_file(tmp_path / "bad.json")


# --------------------------------------------------------------------------
# Template schema rules
# --------------------------------------------------------------------------


def test_template_rejects_duplicate_field_names():
    with pytest.raises(ValidationError, match="duplicate field names"):
        LayoutTemplate(
            template_id="t",
            fields=[FieldConstraint(name="dup"), FieldConstraint(name="dup")],
            theme_colors={"primary": "#000"},
        )


def test_template_rejects_empty_field_list():
    with pytest.raises(ValidationError, match="at least one field"):
        LayoutTemplate(template_id="t", fields=[], theme_colors={"primary": "#000"})


def test_template_rejects_non_hex_theme_color():
    with pytest.raises(ValidationError, match="must be hex"):
        LayoutTemplate(
            template_id="t",
            fields=[FieldConstraint(name="a")],
            theme_colors={"primary": "navy"},
        )


def test_template_accepts_three_and_six_digit_hex():
    template = LayoutTemplate(
        template_id="t",
        fields=[FieldConstraint(name="a")],
        theme_colors={"short": "#fff", "long": "#1f3a5f"},
    )
    assert template.theme_colors["short"] == "#fff"


def test_template_rejects_unknown_keys():
    with pytest.raises(ValidationError):
        LayoutTemplate(
            template_id="t",
            fields=[FieldConstraint(name="a")],
            theme_colors={"primary": "#000"},
            typo_field="oops",
        )


def test_field_by_name_returns_none_for_unknown():
    template = load_template("two_column_brief")
    assert template.field_by_name("headline") is not None
    assert template.field_by_name("nope") is None


# --------------------------------------------------------------------------
# FieldConstraint rules
# --------------------------------------------------------------------------


def test_field_rejects_min_above_max_words():
    with pytest.raises(ValidationError, match="exceeds max_words"):
        FieldConstraint(name="a", min_words=20, max_words=10)


def test_field_rejects_blank_name():
    with pytest.raises(ValidationError, match="must not be blank"):
        FieldConstraint(name="   ")


def test_field_defaults_to_text_kind():
    assert FieldConstraint(name="a").kind == "text"


# --------------------------------------------------------------------------
# State model
# --------------------------------------------------------------------------


def test_pipeline_state_defaults_are_independent():
    a = PipelineState(job_id="a")
    b = PipelineState(job_id="b")
    a.sender_facts.append(Fact(text="t", source_span="s"))
    assert b.sender_facts == []
    assert a.draft is None
    assert a.repair_attempts == 0
    assert a.used_fallback is False


def test_pipeline_state_roundtrips_through_json():
    state = PipelineState(
        job_id="j1",
        prompt="write a brief",
        sender_facts=[Fact(text="founded 2014", source_span="p1:120-140", page=1)],
        draft={"headline": "hello"},
        violations=[
            Violation(
                field="headline",
                constraint="max_words",
                actual=12,
                limit=9,
                repair_hint="shorten it",
            )
        ],
        repair_attempts=2,
    )
    restored = PipelineState.model_validate_json(state.model_dump_json())
    assert restored == state


def test_violation_requires_known_constraint_name():
    with pytest.raises(ValidationError):
        Violation(field="a", constraint="not_a_real_constraint", repair_hint="x")


def test_fact_defaults_to_text_origin():
    assert Fact(text="t", source_span="s").origin == "text"
