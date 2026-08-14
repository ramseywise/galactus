"""The eval harness: turns assertions into numbers.

Four metrics over the case file:

  - **contract pass rate** — % valid on the first generation, before any repair
  - **repair convergence** — mean repair attempts to reach a valid draft
  - **fallback rate** — % that exhausted the repair budget and were truncated
  - **grounding rate** — % of drafts whose content traces to an extracted fact

The distinction the first and last metrics draw is the whole argument. "It
handles constraints" is an assertion; "it satisfies the contract on 92% of first
passes and 100% after repair, with zero ungrounded drafts" is a measurement.

`--dry-run` runs the whole harness against a scripted adapter: no network, no
key, no spend. That is what makes this runnable in CI and on a laptop with no
credential, which is most of the time.

Usage:
    uv run python evals/run.py --dry-run
    uv run python evals/run.py                 # live, needs ANTHROPIC_API_KEY
    uv run python evals/run.py --json          # machine-readable
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from galactus.config import Settings
from galactus.generate import generate_collateral
from galactus.guardrails.validator import is_valid
from galactus.layout.contract import load_template_cached
from galactus.model.gateway import LLM
from galactus.models import Fact, LayoutTemplate, PipelineState
from galactus.observability import configure_structlog

CASES_PATH = Path(__file__).parent / "cases.jsonl"

MIN_GROUNDING_OVERLAP = 2
"""Distinctive tokens a draft must share with its facts to count as grounded.

A blunt proxy, and named as one. Real grounding verification happens in
`ingest.facts.verify_facts`, which re-reads the source span; this metric asks
the weaker question of whether the generated copy drew on the supplied facts at
all. One shared token would fire on a company name alone.
"""

_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "with",
        "we",
        "our",
        "their",
        "this",
        "these",
        "those",
        "will",
        "can",
        "more",
        "than",
        "over",
        "under",
    ]
)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9.%-]*")


# ---------------------------------------------------------------------------
# Case loading
# ---------------------------------------------------------------------------


@dataclass
class EvalCase:
    """One row of `cases.jsonl`."""

    case_id: str
    prompt: str
    template_id: str
    sender_facts: list[Fact] = field(default_factory=list)
    receiver_facts: list[Fact] = field(default_factory=list)
    difficulty: str = "medium"
    notes: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> EvalCase:
        return cls(
            case_id=raw["case_id"],
            prompt=raw.get("prompt", ""),
            template_id=raw.get("template_id", "two_column_brief"),
            sender_facts=[Fact(**f) for f in raw.get("sender_facts", [])],
            receiver_facts=[Fact(**f) for f in raw.get("receiver_facts", [])],
            difficulty=raw.get("difficulty", "medium"),
            notes=raw.get("notes", ""),
        )


def load_cases(path: Path = CASES_PATH) -> list[EvalCase]:
    """Read the case file, skipping blank lines."""
    cases = [
        EvalCase.from_dict(json.loads(line))
        for line in path.read_text().splitlines()
        if line.strip()
    ]

    seen = [c.case_id for c in cases]
    duplicates = {c for c in seen if seen.count(c) > 1}
    if duplicates:
        raise ValueError(f"duplicate case_id in {path.name}: {sorted(duplicates)}")

    return cases


# ---------------------------------------------------------------------------
# The dry-run adapter
# ---------------------------------------------------------------------------


class ScriptedEvalLLM:
    """A fake provider that behaves like a plausible model, deterministically.

    Not a stub returning one canned draft. It reads the requested limits out of
    the prompt and produces text that mostly fits, deliberately overshooting on
    the cases whose prompts fight the contract — so a dry run exercises the
    clean path, the repair path, and the fallback path rather than reporting a
    perfect score against a fixture that could never fail.

    Repair calls tighten toward the limit, which is what a real model does when
    handed a specific violation. `stubborn` cases never tighten, so the budget
    runs out and the fallback engages.
    """

    LOREM: ClassVar[list[str]] = [
        "meridian",
        "calder",
        "partnership",
        "shipments",
        "corridor",
        "network",
        "delivery",
        "freight",
        "logistics",
        "carriers",
        "routing",
        "terminals",
        "capacity",
        "coverage",
        "performance",
        "operations",
        "customers",
        "enterprise",
        "regional",
        "volume",
        "reliability",
        "service",
    ]

    def __init__(
        self,
        template: LayoutTemplate,
        *,
        overshoot: bool,
        stubborn: bool,
        stress_fields: frozenset[str] | None = None,
        bad_color: bool = False,
    ) -> None:
        self.template = template
        self.overshoot = overshoot
        self.stubborn = stubborn
        # None means every text field overshoots. A named set breaches only
        # those fields, so a case that stresses the headline does not also
        # report violations on the columns it never pressured.
        self.stress_fields = stress_fields
        self.bad_color = bad_color
        self.calls = 0

    async def complete_structured(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1

        # A repair prompt is the second call onward; the first is generation.
        repairing = self.calls > 1
        breaching = self.overshoot and (self.stubborn or not repairing)

        return {
            field.name: self._value_for(field, breaching=breaching)
            for field in self.template.fields
        }

    def _value_for(self, field: Any, *, breaching: bool) -> str:
        if field.kind == "image_placeholder":
            return f"{{{{{field.name}}}}}"
        if field.kind == "color_ref":
            # A hex literal where the contract requires a named theme color.
            return "#ff2d55" if breaching and self.bad_color else "accent"

        over = breaching and (self.stress_fields is None or field.name in self.stress_fields)

        # Aim just inside the word ceiling, or past it when overshooting.
        ceiling = field.max_words or 20
        floor = field.min_words or 1
        count = ceiling + 6 if over else max(floor, ceiling - 1)

        words = [self.LOREM[i % len(self.LOREM)] for i in range(count)]
        text = " ".join(words).capitalize()

        # Respect max_chars on the non-overshooting path by dropping whole
        # words — a mid-word cut would be a truncation the model would not make.
        if not over and field.max_chars is not None:
            while len(text) > field.max_chars and " " in text:
                text = text.rsplit(" ", 1)[0]

        return text


STRESS_PROFILES: dict[str, dict[str, Any]] = {
    "overlong-headline-pressure": {"stress_fields": frozenset({"headline"})},
    "verbose-column-pressure": {"stress_fields": frozenset({"column_left", "column_right"})},
    "color-reference-pressure": {"stress_fields": frozenset(), "bad_color": True},
    "quote-and-cta-pressure": {"stress_fields": frozenset({"pull_quote", "cta"})},
    "no-facts-at-all": {"stubborn": True},
}
"""Which contract each hard case actually breaches on its first attempt.

Without this every hard case would breach every field identically, and the
run would report the same twelve violations four times over — which would say
nothing about whether the repair loop handles a color reference differently
from a word count.
"""


def _scripted_llm(case: EvalCase, template: LayoutTemplate) -> ScriptedEvalLLM:
    """Give each case a scripted provider matched to its difficulty.

    Difficulty drives behaviour so the dry-run metrics have a real spread: easy
    and medium cases pass first time, hard cases need repair, and the case with
    no grounding at all is the one that exhausts the budget.
    """
    profile = STRESS_PROFILES.get(case.case_id, {})
    return ScriptedEvalLLM(
        template,
        overshoot=case.difficulty == "hard",
        stubborn=profile.get("stubborn", False),
        stress_fields=profile.get("stress_fields"),
        bad_color=profile.get("bad_color", False),
    )


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------


@dataclass
class CaseResult:
    """What one case produced. The metrics are computed from a list of these."""

    case_id: str
    difficulty: str
    first_pass_valid: bool
    repair_attempts: int
    used_fallback: bool
    grounded: bool
    contract_valid: bool
    llm_calls: int
    error: str | None = None


async def run_case(case: EvalCase, llm: LLM | None = None, *, model: str = "dry-run") -> CaseResult:
    """Run one case end to end and score it."""
    template = load_template_cached(case.template_id)
    provider = llm if llm is not None else _scripted_llm(case, template)

    state = PipelineState(
        job_id=f"eval-{case.case_id}",
        prompt=case.prompt,
        sender_facts=case.sender_facts,
        receiver_facts=case.receiver_facts,
    )

    try:
        draft, used_fallback = await generate_collateral(state, template, provider, model=model)
    except Exception as exc:  # noqa: BLE001 - one dead case must not end the run
        return CaseResult(
            case_id=case.case_id,
            difficulty=case.difficulty,
            first_pass_valid=False,
            repair_attempts=state.repair_attempts,
            used_fallback=False,
            grounded=False,
            contract_valid=False,
            llm_calls=getattr(provider, "calls", 0),
            error=f"{type(exc).__name__}: {exc}",
        )

    return CaseResult(
        case_id=case.case_id,
        difficulty=case.difficulty,
        first_pass_valid=bool(state.first_pass_valid),
        repair_attempts=state.repair_attempts,
        used_fallback=used_fallback,
        grounded=is_grounded(draft, case.sender_facts + case.receiver_facts),
        contract_valid=is_valid(draft, template),
        llm_calls=getattr(provider, "calls", 0),
    )


async def run_all(
    cases: list[EvalCase], llm: LLM | None = None, *, model: str = "dry-run"
) -> list[CaseResult]:
    """Run every case in order.

    Sequential rather than gathered: the live path costs money, and a serial run
    keeps the spend legible and the rate limits comfortable.
    """
    return [await run_case(case, llm, model=model) for case in cases]


# ---------------------------------------------------------------------------
# Grounding
# ---------------------------------------------------------------------------


def is_grounded(draft: dict[str, str], facts: list[Fact]) -> bool:
    """Whether a draft's copy traces back to the supplied facts.

    A case with no facts is never grounded — that is the honest reading, not a
    vacuous pass. Reporting 100% grounding on a run that included an ungrounded
    case would be the exact overclaim these metrics exist to prevent.
    """
    if not facts:
        return False

    fact_tokens = _distinctive_tokens(" ".join(f.text for f in facts))
    draft_tokens = _distinctive_tokens(" ".join(v for v in draft.values() if isinstance(v, str)))

    return len(fact_tokens & draft_tokens) >= MIN_GROUNDING_OVERLAP


def _distinctive_tokens(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(text.lower())
        if token not in _STOPWORDS and len(token) > 2
    }


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def compute_metrics(results: list[CaseResult]) -> dict[str, Any]:
    """The four numbers, plus the counts they were computed from.

    Denominators are reported alongside every rate. A pass rate without its `n`
    is not a claim anyone should act on.
    """
    total = len(results)
    if not total:
        raise ValueError("no cases to score")

    converged = [r for r in results if not r.used_fallback and not r.error]

    return {
        "cases": total,
        "contract_pass_rate": _rate(sum(r.first_pass_valid for r in results), total),
        "repair_convergence": (
            round(sum(r.repair_attempts for r in converged) / len(converged), 2)
            if converged
            else None
        ),
        "fallback_rate": _rate(sum(r.used_fallback for r in results), total),
        "grounding_rate": _rate(sum(r.grounded for r in results), total),
        "contract_valid_rate": _rate(sum(r.contract_valid for r in results), total),
        "errors": sum(1 for r in results if r.error),
        "total_llm_calls": sum(r.llm_calls for r in results),
    }


def _rate(count: int, total: int) -> float:
    return round(100.0 * count / total, 1) if total else 0.0


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def summarize_table(rows: list[dict[str, Any]]) -> str:
    """Render a list of dicts as a compact markdown table.

    Adapted from `cap-genai.md`'s `shared_tools.py` (copied, not imported — that
    module executes registry decorators on import). See docs/cap-reuse.md.
    """
    if not rows:
        return "_no rows_"

    headers = list(rows[0])
    widths = {h: max(len(h), *(len(str(row.get(h, ""))) for row in rows)) for h in headers}

    def line(values: list[str]) -> str:
        return (
            "| "
            + " | ".join(v.ljust(widths[h]) for h, v in zip(headers, values, strict=True))
            + " |"
        )

    out = [
        line(headers),
        "|" + "|".join("-" * (widths[h] + 2) for h in headers) + "|",
    ]
    out += [line([str(row.get(h, "")) for h in headers]) for row in rows]
    return "\n".join(out)


def format_report(results: list[CaseResult], metrics: dict[str, Any]) -> str:
    """The human-readable run summary — the four numbers over the case table."""
    rows = [
        {
            "case_id": r.case_id,
            "difficulty": r.difficulty,
            "first_pass": "yes" if r.first_pass_valid else "no",
            "repairs": r.repair_attempts,
            "fallback": "yes" if r.used_fallback else "no",
            "grounded": "yes" if r.grounded else "no",
            "valid": "yes" if r.contract_valid else "NO",
            "calls": r.llm_calls,
        }
        for r in results
    ]

    convergence = metrics["repair_convergence"]
    lines = [
        summarize_table(rows),
        "",
        f"Cases:                {metrics['cases']}",
        f"Contract pass rate:   {metrics['contract_pass_rate']}%  (valid on first generation)",
        (
            f"Repair convergence:   {convergence if convergence is not None else 'n/a'}"
            "  (mean attempts, converged cases)"
        ),
        f"Fallback rate:        {metrics['fallback_rate']}%  (deterministic truncation)",
        f"Grounding rate:       {metrics['grounding_rate']}%  (traceable to a source span)",
        "",
        f"Contract valid after repair+fallback: {metrics['contract_valid_rate']}%",
        f"Total provider calls: {metrics['total_llm_calls']}",
    ]

    errored = [r for r in results if r.error]
    if errored:
        lines += ["", "Errors:"] + [f"  {r.case_id}: {r.error}" for r in errored]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the galactus eval harness.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run against the scripted adapter. No network, no key, no spend.",
    )
    parser.add_argument("--json", action="store_true", help="Emit metrics as JSON.")
    parser.add_argument("--cases", type=Path, default=CASES_PATH, help="Path to the case file.")
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)

    if args.dry_run:
        llm: LLM | None = None
        model = "dry-run"
        # Spans are logged on both paths, so the dry run configures logging too
        # — otherwise structlog's default console renderer would emit a
        # different shape than production, and the format would go untested.
        configure_structlog(Settings.load().log_level)
    else:
        from galactus.model.gateway import AnthropicAdapter

        settings = Settings.load()
        settings.require_api_key()
        configure_structlog(settings.log_level)
        llm = AnthropicAdapter(settings)
        model = settings.model

    results = asyncio.run(run_all(cases, llm, model=model))
    metrics = compute_metrics(results)

    if args.json:
        print(json.dumps(metrics, indent=2))
    else:
        print(format_report(results, metrics))

    # A draft that fails the contract after repair and fallback is a broken
    # guarantee, not a low score — that is the one result worth a nonzero exit.
    return 0 if metrics["contract_valid_rate"] == 100.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
