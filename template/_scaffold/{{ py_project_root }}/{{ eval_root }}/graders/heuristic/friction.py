"""Friction heuristic: deterministic UX-friction flags on the response text.

Counts hedging phrases, questions bounced back at the user, overlong or empty
responses. Cheap and always-on; the LLM friction judge scores the same rows
with reasoning, and pipelines/calibration.py measures how well these flags
track it.
"""

from __future__ import annotations

from evals.models import EvalInteraction, GraderResult

_HEDGE_PHRASES = (
    "i'm not sure",
    "i am not sure",
    "it depends",
    "i cannot say",
    "as an ai",
    "i apologize, but i",
    "unfortunately, i can't",
)

# A response longer than this (chars) is flagged — direct answers to support
# questions rarely need more.
_OVERLONG_CHARS = 1200
_MAX_FLAGS_FOR_PASS = 1


def grade(interaction: EvalInteraction) -> GraderResult:
    text = interaction.response.lower()
    flags: dict[str, float] = {}

    hedges = sum(text.count(phrase) for phrase in _HEDGE_PHRASES)
    if hedges:
        flags["hedging"] = float(hedges)
    questions_back = interaction.response.count("?")
    if questions_back >= 2:
        flags["questions_back"] = float(questions_back)
    if len(interaction.response) > _OVERLONG_CHARS:
        flags["overlong"] = 1.0
    if not interaction.response.strip():
        flags["empty_response"] = 1.0

    flag_count = len(flags)
    return GraderResult(
        interaction_id=interaction.id,
        metric="friction",
        grader="heuristic",
        is_correct=flag_count <= _MAX_FLAGS_FOR_PASS,
        score=max(0.0, 1.0 - flag_count / 3.0),
        reasoning=f"{flag_count} friction flag(s): {sorted(flags)}"
        if flags
        else "no friction flags",
        dimensions=flags,
    )
