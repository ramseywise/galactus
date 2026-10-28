"""Unit tests for the dry-run scripted adapter
(evals/generation/scripted.py).

No LLM calls, no galactus/ml/agents imports — the provider is exercised
directly against plain field-spec stand-ins.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from evals.generation.scripted import (
    GenerationCase,
    ScriptedProvider,
    StressProfile,
    scripted_provider_for,
)


@dataclass
class _Field:
    name: str
    kind: str = "text"
    max_words: int | None = 12
    min_words: int | None = None
    max_chars: int | None = None


@dataclass
class _Case:
    case_id: str
    difficulty: str


def _case(case_id: str = "c-1", difficulty: str = "medium") -> GenerationCase:
    return _Case(case_id=case_id, difficulty=difficulty)  # type: ignore[return-value]


class TestOvershoot:
    @pytest.mark.asyncio
    async def test_hard_case_overshoots_on_first_call(self) -> None:
        fields = [_Field(name="headline", max_words=5)]
        provider = scripted_provider_for(_case(difficulty="hard"), fields, {})
        out = await provider.complete_structured("prompt", {})
        word_count = len(out["headline"].split())
        assert word_count > 5

    @pytest.mark.asyncio
    async def test_non_hard_case_never_overshoots(self) -> None:
        fields = [_Field(name="headline", max_words=5)]
        for difficulty in ["easy", "medium"]:
            provider = scripted_provider_for(_case(difficulty=difficulty), fields, {})
            out = await provider.complete_structured("prompt", {})
            assert len(out["headline"].split()) <= 5


class TestStressFields:
    @pytest.mark.asyncio
    async def test_stress_fields_breach_only_named_fields(self) -> None:
        fields = [
            _Field(name="headline", max_words=5),
            _Field(name="body", max_words=5),
        ]
        profile = StressProfile(stress_fields=frozenset({"headline"}))
        provider = scripted_provider_for(
            _case(case_id="c-stress", difficulty="hard"),
            fields,
            {"c-stress": profile},
        )
        out = await provider.complete_structured("prompt", {})
        assert len(out["headline"].split()) > 5
        assert len(out["body"].split()) <= 5


class TestBadColor:
    @pytest.mark.asyncio
    async def test_bad_color_emits_hex_literal(self) -> None:
        fields = [_Field(name="accent_color", kind="color_ref")]
        profile = StressProfile(bad_color=True)
        provider = scripted_provider_for(
            _case(case_id="c-color", difficulty="hard"),
            fields,
            {"c-color": profile},
        )
        out = await provider.complete_structured("prompt", {})
        assert out["accent_color"].startswith("#")

    @pytest.mark.asyncio
    async def test_without_bad_color_emits_named_reference(self) -> None:
        fields = [_Field(name="accent_color", kind="color_ref")]
        provider = scripted_provider_for(_case(difficulty="medium"), fields, {})
        out = await provider.complete_structured("prompt", {})
        assert not out["accent_color"].startswith("#")


class TestStubborn:
    @pytest.mark.asyncio
    async def test_stubborn_never_tightens(self) -> None:
        fields = [_Field(name="headline", max_words=5)]
        profile = StressProfile(stubborn=True)
        provider = scripted_provider_for(
            _case(case_id="c-stub", difficulty="hard"), fields, {"c-stub": profile}
        )
        await provider.complete_structured("prompt", {})
        second = await provider.complete_structured("prompt", {})
        assert len(second["headline"].split()) > 5

    @pytest.mark.asyncio
    async def test_non_stubborn_tightens_on_second_call(self) -> None:
        fields = [_Field(name="headline", max_words=5)]
        provider = scripted_provider_for(_case(case_id="c-normal", difficulty="hard"), fields, {})
        await provider.complete_structured("prompt", {})
        second = await provider.complete_structured("prompt", {})
        assert len(second["headline"].split()) <= 5


class TestCallCount:
    @pytest.mark.asyncio
    async def test_calls_increments_per_call(self) -> None:
        fields = [_Field(name="headline")]
        provider = ScriptedProvider(fields, overshoot=False, stubborn=False)
        assert provider.calls == 0
        await provider.complete_structured("prompt", {})
        assert provider.calls == 1
        await provider.complete_structured("prompt", {})
        assert provider.calls == 2


class TestNoGalactusImport:
    def test_module_imports_nothing_from_galactus(self) -> None:
        import evals.generation.scripted as mod

        source = mod.__file__
        assert source is not None
        with open(source) as f:
            contents = f.read()
        assert "galactus" not in contents
