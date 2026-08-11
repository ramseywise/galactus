"""The repair loop, the schema builder, and the prompt builders.

Every test here runs against `FakeLLM` with scripted responses. No network, no
spend, and — more importantly — no flake: the three loop paths are exercised
deterministically, which a live model could not guarantee for the very reason
the loop exists.
"""

from __future__ import annotations

from typing import Any

import pytest
from galactus.generate import (
    build_prompt,
    build_repair_prompt,
    generate_collateral,
    schema_for,
)
from galactus.layout.validator import is_valid, validate
from galactus.models import Fact, PipelineState


class FakeLLM:
    """Returns scripted drafts in order, recording the prompts it was given.

    Satisfies `port.LLM` structurally — no inheritance, which is the point of
    the Protocol. The last scripted response repeats if the loop asks for more
    than were provided, so a test that scripts one bad draft gets a loop that
    keeps failing rather than an IndexError.
    """

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.prompts: list[str] = []
        self.schemas: list[dict[str, Any]] = []

    @property
    def call_count(self) -> int:
        return len(self.prompts)

    async def complete_structured(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.prompts.append(prompt)
        self.schemas.append(schema)
        index = min(len(self.prompts) - 1, len(self.responses) - 1)
        return dict(self.responses[index])


@pytest.fixture
def state() -> PipelineState:
    return PipelineState(job_id="job-1", prompt="Announce the logistics partnership.")


def _too_long(draft: dict[str, str]) -> dict[str, str]:
    """A copy of `draft` whose headline breaks the 9-word limit."""
    return {**draft, "headline": " ".join(["overlong"] * 20)}


# ---------------------------------------------------------------------------
# The three loop paths
# ---------------------------------------------------------------------------


async def test_clean_first_pass_makes_one_call(state, template, clean_draft):
    llm = FakeLLM([clean_draft])

    draft, used_fallback = await generate_collateral(state, template, llm)

    assert llm.call_count == 1
    assert used_fallback is False
    assert draft == clean_draft
    assert state.repair_attempts == 0
    assert state.used_fallback is False
    assert state.violations == []


async def test_repairs_then_succeeds(state, template, clean_draft):
    llm = FakeLLM([_too_long(clean_draft), clean_draft])

    draft, used_fallback = await generate_collateral(state, template, llm)

    assert llm.call_count == 2
    assert used_fallback is False
    assert draft == clean_draft
    assert state.repair_attempts == 1
    assert state.used_fallback is False


async def test_exhausts_budget_then_falls_back(state, template, clean_draft):
    bad = _too_long(clean_draft)
    llm = FakeLLM([bad])

    draft, used_fallback = await generate_collateral(state, template, llm, max_repairs=3)

    # One initial call plus three repairs.
    assert llm.call_count == 4
    assert used_fallback is True
    assert state.repair_attempts == 3
    assert state.used_fallback is True
    # The contract holds regardless — that is what makes the API unconditional.
    assert is_valid(draft, template)
    assert draft is not bad


async def test_fallback_draft_is_valid_even_from_garbage(state, template):
    llm = FakeLLM([{"headline": "x", "bogus_field": "y"}])

    draft, used_fallback = await generate_collateral(state, template, llm, max_repairs=1)

    assert used_fallback is True
    assert validate(draft, template) == []


async def test_zero_repair_budget_falls_back_immediately(state, template, clean_draft):
    llm = FakeLLM([_too_long(clean_draft)])

    draft, used_fallback = await generate_collateral(state, template, llm, max_repairs=0)

    assert llm.call_count == 1
    assert used_fallback is True
    assert is_valid(draft, template)


async def test_repair_budget_is_respected_exactly(state, template, clean_draft):
    llm = FakeLLM([_too_long(clean_draft)])

    await generate_collateral(state, template, llm, max_repairs=2)

    assert llm.call_count == 3
    assert state.repair_attempts == 2


async def test_state_records_the_returned_draft(state, template, clean_draft):
    llm = FakeLLM([clean_draft])

    draft, _ = await generate_collateral(state, template, llm)

    assert state.draft == draft


async def test_repair_prompt_carries_the_violation_hints(state, template, clean_draft):
    llm = FakeLLM([_too_long(clean_draft), clean_draft])

    await generate_collateral(state, template, llm)

    repair_prompt = llm.prompts[1]
    assert "headline" in repair_prompt
    assert "at most 9 words" in repair_prompt


async def test_late_success_still_reports_no_fallback(state, template, clean_draft):
    """A draft that only converges on the final allowed attempt is not degraded."""
    bad = _too_long(clean_draft)
    llm = FakeLLM([bad, bad, bad, clean_draft])

    draft, used_fallback = await generate_collateral(state, template, llm, max_repairs=3)

    assert llm.call_count == 4
    assert used_fallback is False
    assert draft == clean_draft
    assert state.repair_attempts == 3


# ---------------------------------------------------------------------------
# schema_for
# ---------------------------------------------------------------------------


def test_schema_closes_the_object(template):
    schema = schema_for(template)

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == template.field_names


def test_schema_types_every_field_as_a_string(template):
    schema = schema_for(template)

    assert set(schema["properties"]) == template.field_names
    assert all(prop["type"] == "string" for prop in schema["properties"].values())


def test_schema_carries_field_descriptions(template):
    schema = schema_for(template)

    assert "32pt" in schema["properties"]["headline"]["description"]


def test_schema_emits_char_ceilings_for_text_fields(template):
    schema = schema_for(template)

    assert schema["properties"]["headline"]["maxLength"] == 70
    # Non-text kinds have no length limit to express.
    assert "maxLength" not in schema["properties"]["hero_image"]


def test_a_clean_draft_matches_the_schema_key_set(template, clean_draft):
    schema = schema_for(template)

    assert set(clean_draft) == set(schema["properties"])


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


def test_prompt_states_every_numeric_limit(state, template):
    prompt = build_prompt(state, template)

    # The schema cannot bind these, so the prose must carry them.
    assert "3-9 words" in prompt
    assert "at most 70 characters" in prompt
    assert "60-95 words" in prompt


def test_prompt_lists_theme_colors_by_name(state, template):
    prompt = build_prompt(state, template)

    for color in template.theme_colors:
        assert f"`{color}`" in prompt


def test_prompt_includes_the_brief(state, template):
    prompt = build_prompt(state, template)

    assert "logistics partnership" in prompt


def test_prompt_includes_grounding_facts_when_present(template):
    state = PipelineState(
        job_id="job-2",
        sender_facts=[
            Fact(
                text="Cut delivery time by 18 percent",
                source_span="p2:120-160",
                page=2,
                confidence=0.9,
                origin="text",
            )
        ],
    )

    prompt = build_prompt(state, template)

    assert "Cut delivery time by 18 percent" in prompt
    assert "Source facts" in prompt


def test_prompt_omits_the_facts_section_when_there_are_none(state, template):
    prompt = build_prompt(state, template)

    assert "Source facts" not in prompt


def test_prompt_separates_sender_and_receiver_facts(template):
    state = PipelineState(
        job_id="job-3",
        sender_facts=[Fact(text="Sender claim", source_span="p1:0-12", page=1, origin="text")],
        receiver_facts=[Fact(text="Receiver claim", source_span="p1:0-14", page=1, origin="text")],
    )

    prompt = build_prompt(state, template)

    assert "## Sender" in prompt
    assert "## Receiver" in prompt
    assert prompt.index("## Sender") < prompt.index("## Receiver")


def test_repair_prompt_lists_one_line_per_violation(template, clean_draft):
    draft = _too_long(clean_draft)
    violations = validate(draft, template)

    prompt = build_repair_prompt(draft, violations, template)

    for violation in violations:
        assert violation.repair_hint in prompt


def test_repair_prompt_sends_the_whole_draft_back(template, clean_draft):
    draft = _too_long(clean_draft)

    prompt = build_repair_prompt(draft, validate(draft, template), template)

    for name in template.field_names:
        assert f"`{name}`" in prompt
