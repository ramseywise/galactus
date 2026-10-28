"""The four generation-under-contract metrics, plus the grounding heuristic.

  - **contract pass rate** — % valid on the first generation, before any repair
  - **repair convergence** — mean repair attempts to reach a valid output
  - **fallback rate** — % that exhausted the repair budget and were truncated
  - **grounding rate** — % of outputs whose content traces to a source text

The distinction the first and last metrics draw is the whole argument. "It
handles constraints" is an assertion; "it satisfies the contract on 92% of
first passes and 100% after repair, with zero ungrounded outputs" is a
measurement.
"""

from __future__ import annotations

import re
from typing import Any

from .results import CaseResult

MIN_GROUNDING_OVERLAP = 2
"""Distinctive tokens an output must share with its grounding texts to count
as grounded.

A blunt proxy, and named as one. Real grounding verification would re-read
the source span directly; this metric asks the weaker question of whether
the generated content drew on the supplied source texts at all. One shared
token would fire on a proper noun alone.
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


def is_grounded(output: dict[str, str], grounding_texts: list[str]) -> bool:
    """Whether an output's content traces back to the supplied source texts.

    A case with no grounding texts is never grounded — that is the honest
    reading, not a vacuous pass. Reporting 100% grounding on a run that
    included an ungrounded case would be the exact overclaim these metrics
    exist to prevent.
    """
    if not grounding_texts:
        return False

    fact_tokens = _distinctive_tokens(" ".join(grounding_texts))
    draft_tokens = _distinctive_tokens(" ".join(v for v in output.values() if isinstance(v, str)))

    return len(fact_tokens & draft_tokens) >= MIN_GROUNDING_OVERLAP


def _distinctive_tokens(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(text.lower())
        if token not in _STOPWORDS and len(token) > 2
    }


def compute_metrics(results: list[CaseResult]) -> dict[str, Any]:
    """The four numbers, plus the counts they were computed from.

    Denominators are reported alongside every rate. A pass rate without its
    `n` is not a claim anyone should act on.
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
