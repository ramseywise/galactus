"""The runner seam — drives generate -> validate against three injected callables.

`run_case` knows nothing about a domain's contract type, its producer, or its
validator: it takes them as callables and scores whatever they return. A
consumer wires its own `contract_for`/`produce`/`validate` and gets
`CaseResult` rows and the four metrics for free.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from .ports import LLM
from .results import CaseResult


class GenerationCase(Protocol):
    """The three attributes the runner needs from a case, regardless of domain."""

    case_id: str
    difficulty: str
    prompt: str


@dataclass
class ProducerOutcome:
    """What a producer returns: the artifact plus the process facts about how
    it was produced.

    Contract pass rate is measured on the FIRST generation, before repair,
    and is not reconstructable afterwards: a run with `repair_attempts == 0`
    could equally be a clean first pass or a run given no repair budget. The
    producer must report these facts explicitly rather than the runner
    inferring them.
    """

    output: dict[str, str]
    first_pass_valid: bool
    repair_attempts: int
    used_fallback: bool
    grounding_texts: list[str]


async def run_case(
    case: GenerationCase,
    *,
    contract_for: Callable[[GenerationCase], Any],
    produce: Callable[[GenerationCase, Any, LLM | None], Awaitable[ProducerOutcome]],
    validate: Callable[[dict[str, str], Any], bool],
    is_grounded: Callable[[dict[str, str], list[str]], bool],
    provider: LLM | None = None,
) -> CaseResult:
    """Run one case end to end and score it.

    A dead producer must not end the run — a bug or a provider failure on one
    case scores that case as `error` and lets the rest of the batch continue.
    """
    contract = contract_for(case)

    # `provider.calls` is cumulative for the provider's lifetime, so a bare read
    # attributes every earlier case's calls to this one when a single provider is
    # shared across a run (the documented run_all(provider=...) path). Record the
    # delta across this case instead; with a fresh provider per case the baseline
    # is 0 and the delta is identical to the old reading.
    calls_before = getattr(provider, "calls", 0)

    try:
        outcome = await produce(case, contract, provider)
    except Exception as exc:  # one dead case must not end the run
        return CaseResult(
            case_id=case.case_id,
            difficulty=case.difficulty,
            first_pass_valid=False,
            repair_attempts=0,
            used_fallback=False,
            grounded=False,
            contract_valid=False,
            llm_calls=getattr(provider, "calls", 0) - calls_before,
            error=f"{type(exc).__name__}: {exc}",
        )

    return CaseResult(
        case_id=case.case_id,
        difficulty=case.difficulty,
        first_pass_valid=outcome.first_pass_valid,
        repair_attempts=outcome.repair_attempts,
        used_fallback=outcome.used_fallback,
        grounded=is_grounded(outcome.output, outcome.grounding_texts),
        contract_valid=validate(outcome.output, contract),
        llm_calls=getattr(provider, "calls", 0) - calls_before,
    )


async def run_all(
    cases: list[GenerationCase],
    *,
    contract_for: Callable[[GenerationCase], Any],
    produce: Callable[[GenerationCase, Any, LLM | None], Awaitable[ProducerOutcome]],
    validate: Callable[[dict[str, str], Any], bool],
    is_grounded: Callable[[dict[str, str], list[str]], bool],
    provider: LLM | None = None,
) -> list[CaseResult]:
    """Run every case in order.

    Sequential rather than gathered: the live path may cost money, and a
    serial run keeps the spend legible and the rate limits comfortable.
    """
    return [
        await run_case(
            case,
            contract_for=contract_for,
            produce=produce,
            validate=validate,
            is_grounded=is_grounded,
            provider=provider,
        )
        for case in cases
    ]
