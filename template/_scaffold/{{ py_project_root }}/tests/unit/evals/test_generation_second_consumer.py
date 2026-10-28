"""A second consumer of the generation-under-contract harness that is not
galactus — a fixed-width log-line formatter with a two-field contract.

This proves the harness's done-condition: a domain composes `runner`,
`cases`, `scripted`, `metrics`, and `results` and gets a scored run with a
non-degenerate spread, without importing anything from `galactus.*`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from evals.generation.cases import load_case_rows
from evals.generation.metrics import compute_metrics, is_grounded
from evals.generation.runner import ProducerOutcome, run_all, run_case
from evals.generation.scripted import StressProfile, scripted_provider_for

# ---------------------------------------------------------------------------
# The domain: a fixed-width log-line formatter.
# ---------------------------------------------------------------------------


@dataclass
class LogFieldSpec:
    """Satisfies the FieldSpec Protocol structurally — no import needed."""

    name: str
    kind: str = "text"
    max_words: int | None = None
    min_words: int | None = None
    max_chars: int | None = None


@dataclass
class LogLineContract:
    fields: list[LogFieldSpec]

    def field_by_name(self, name: str) -> LogFieldSpec:
        return next(f for f in self.fields if f.name == name)


LOG_CONTRACT = LogLineContract(
    fields=[
        LogFieldSpec(name="severity", max_chars=8),
        LogFieldSpec(name="message", max_words=10, max_chars=60),
    ]
)


@dataclass
class LogCase:
    case_id: str
    prompt: str
    source_lines: list[str] = field(default_factory=list)
    difficulty: str = "medium"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> LogCase:
        return cls(
            case_id=raw["case_id"],
            prompt=raw.get("prompt", ""),
            source_lines=raw.get("source_lines", []),
            difficulty=raw.get("difficulty", "medium"),
        )


def _contract_for(case: LogCase) -> LogLineContract:
    return LOG_CONTRACT


def _validate(output: dict[str, str], contract: LogLineContract) -> bool:
    for spec in contract.fields:
        value = output.get(spec.name, "")
        if spec.max_chars is not None and len(value) > spec.max_chars:
            return False
        if spec.max_words is not None and len(value.split()) > spec.max_words:
            return False
    return True


async def _produce(case: LogCase, contract: LogLineContract, provider: Any) -> ProducerOutcome:
    """Generate -> validate -> repair (max 2 attempts) -> fallback."""
    prompt = f"Format a log line for: {case.prompt}"
    schema = {"type": "object"}

    output = await provider.complete_structured(prompt, schema)
    first_pass_valid = _validate(output, contract)

    repair_attempts = 0
    used_fallback = False
    valid = first_pass_valid
    while not valid and repair_attempts < 2:
        repair_attempts += 1
        output = await provider.complete_structured(prompt, schema)
        valid = _validate(output, contract)

    if not valid:
        used_fallback = True
        output = {
            spec.name: (
                output.get(spec.name, "")[: spec.max_chars]
                if spec.max_chars
                else output.get(spec.name, "")
            )
            for spec in contract.fields
        }

    return ProducerOutcome(
        output=output,
        first_pass_valid=first_pass_valid,
        repair_attempts=repair_attempts,
        used_fallback=used_fallback,
        grounding_texts=case.source_lines,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


CASES = [
    LogCase(
        case_id="easy-1",
        prompt="disk usage warning",
        source_lines=["disk usage exceeded 90 percent"],
        difficulty="easy",
    ),
    LogCase(
        case_id="medium-1",
        prompt="connection reset",
        source_lines=["connection reset by peer"],
        difficulty="medium",
    ),
    LogCase(
        case_id="hard-1",
        prompt="unhandled exception",
        source_lines=["unhandled exception in worker pool"],
        difficulty="hard",
    ),
    LogCase(
        case_id="hard-stubborn",
        prompt="fatal crash",
        source_lines=["fatal crash during shutdown sequence"],
        difficulty="hard",
    ),
]

STRESS_PROFILES = {"hard-stubborn": StressProfile(stubborn=True)}


@pytest.mark.asyncio
async def test_second_consumer_runs_end_to_end_with_non_degenerate_spread() -> None:
    async def produce(case: LogCase, contract: LogLineContract, provider: Any) -> ProducerOutcome:
        return await _produce(case, contract, provider)

    results = []
    for case in CASES:
        provider = scripted_provider_for(case, LOG_CONTRACT.fields, STRESS_PROFILES)
        result = await run_case(
            case,
            contract_for=_contract_for,
            produce=produce,
            validate=_validate,
            is_grounded=is_grounded,
            provider=provider,
        )
        results.append(result)

    metrics = compute_metrics(results)

    # Non-degenerate spread: at least one first-pass pass, one repair, one fallback.
    assert any(r.first_pass_valid for r in results)
    assert any(r.repair_attempts > 0 for r in results)
    assert any(r.used_fallback for r in results)

    for key in (
        "contract_pass_rate",
        "repair_convergence",
        "fallback_rate",
        "grounding_rate",
        "contract_valid_rate",
    ):
        assert key in metrics


@pytest.mark.asyncio
async def test_dead_producer_scores_as_error_without_ending_the_run() -> None:
    async def dead_produce(
        case: LogCase, contract: LogLineContract, provider: Any
    ) -> ProducerOutcome:
        if case.case_id == "boom":
            raise RuntimeError("simulated producer failure")
        return await _produce(case, contract, provider)

    cases = [
        LogCase(case_id="boom", prompt="x", difficulty="medium"),
        LogCase(case_id="fine", prompt="y", difficulty="easy"),
    ]
    providers = {c.case_id: scripted_provider_for(c, LOG_CONTRACT.fields, {}) for c in cases}

    async def produce_with_provider(
        case: LogCase, contract: LogLineContract, _provider: Any
    ) -> ProducerOutcome:
        return await dead_produce(case, contract, providers[case.case_id])

    results = await run_all(
        cases,
        contract_for=_contract_for,
        produce=produce_with_provider,
        validate=_validate,
        is_grounded=is_grounded,
    )

    assert len(results) == 2
    assert results[0].case_id == "boom"
    assert results[0].error is not None
    assert "simulated producer failure" in results[0].error
    assert results[1].case_id == "fine"
    assert results[1].error is None


@pytest.mark.asyncio
async def test_run_all_preserves_case_order() -> None:
    async def produce(case: LogCase, contract: LogLineContract, provider: Any) -> ProducerOutcome:
        return await _produce(case, contract, provider)

    providers = {c.case_id: scripted_provider_for(c, LOG_CONTRACT.fields, {}) for c in CASES}

    async def produce_with_provider(
        case: LogCase, contract: LogLineContract, _provider: Any
    ) -> ProducerOutcome:
        return await produce(case, contract, providers[case.case_id])

    results = await run_all(
        CASES,
        contract_for=_contract_for,
        produce=produce_with_provider,
        validate=_validate,
        is_grounded=is_grounded,
    )

    assert [r.case_id for r in results] == [c.case_id for c in CASES]


class TestLoadCaseRows:
    def test_skips_blank_lines_and_rejects_duplicates(self, tmp_path: Path) -> None:
        good = tmp_path / "cases.jsonl"
        good.write_text('{"case_id": "a", "prompt": "x"}\n\n{"case_id": "b", "prompt": "y"}\n')
        rows = load_case_rows(good, LogCase.from_dict)
        assert [r.case_id for r in rows] == ["a", "b"]

        dup = tmp_path / "dup.jsonl"
        dup.write_text('{"case_id": "a", "prompt": "x"}\n{"case_id": "a", "prompt": "y"}\n')
        with pytest.raises(ValueError, match="duplicate case_id"):
            load_case_rows(dup, LogCase.from_dict)


class TestNoGalactusImport:
    def test_harness_modules_import_nothing_from_galactus(self) -> None:
        """The harness's own modules stay case-agnostic.

        This checks the production modules the second consumer composes
        (`cases`, `runner`) — not this test file itself, whose docstrings
        and assertions legitimately mention "galactus" by name to describe
        what they're proving.
        """
        import evals.generation.cases as cases_mod
        import evals.generation.runner as runner_mod

        for mod in (cases_mod, runner_mod):
            assert mod.__file__ is not None
            with open(mod.__file__) as f:
                assert "galactus" not in f.read()


@pytest.mark.asyncio
async def test_shared_provider_attributes_only_its_own_calls_to_each_case() -> None:
    """`run_all(provider=...)` is documented, but every test above hands each
    case its own provider — so a cumulative `provider.calls` read looked correct.

    On the shared path the counter never resets, so case N would report every
    call made since the run began: per-case counts climb 1, 2, 3 and the total
    grows quadratically while the run is behaving perfectly.
    """

    class CountingProvider:
        def __init__(self) -> None:
            self.calls = 0

        async def complete_structured(self, _prompt: str, _schema: Any) -> dict[str, str]:
            self.calls += 1
            return {"level": "INFO", "message": "ok"}

    shared = CountingProvider()

    async def produce_one_call(
        case: LogCase, contract: LogLineContract, provider: Any
    ) -> ProducerOutcome:
        output = await provider.complete_structured(case.prompt, None)
        return ProducerOutcome(
            output=output,
            first_pass_valid=True,
            repair_attempts=0,
            used_fallback=False,
            grounding_texts=[],
        )

    results = await run_all(
        CASES,
        contract_for=_contract_for,
        produce=produce_one_call,
        validate=_validate,
        is_grounded=is_grounded,
        provider=shared,
    )

    assert shared.calls == len(CASES), "fixture must make exactly one call per case"
    assert [r.llm_calls for r in results] == [1] * len(CASES), (
        "each case must report only the calls it made, not the run's running total"
    )
    assert sum(r.llm_calls for r in results) == shared.calls
