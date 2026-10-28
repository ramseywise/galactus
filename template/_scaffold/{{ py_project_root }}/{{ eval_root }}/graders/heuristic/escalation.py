"""Escalation heuristic: did the assistant hand off when it should (and only then)?"""

from __future__ import annotations

from evals.models import EvalInteraction, GraderResult

# Phrases that signal a hand-off; used only when the interaction record does
# not carry an explicit `escalated` field.
_ESCALATION_PHRASES = (
    "contact support",
    "contact our support",
    "escalat",
    "human agent",
    "reach out to our team",
    "support team",
)


def inferred_escalated(interaction: EvalInteraction) -> bool:
    response = interaction.response.lower()
    return any(phrase in response for phrase in _ESCALATION_PHRASES)


def grade(interaction: EvalInteraction) -> GraderResult | None:
    if interaction.escalation_expected is None:
        return None
    escalated = (
        interaction.escalated
        if interaction.escalated is not None
        else inferred_escalated(interaction)
    )
    correct = escalated == interaction.escalation_expected
    return GraderResult(
        interaction_id=interaction.id,
        metric="escalation",
        grader="heuristic",
        is_correct=correct,
        score=1.0 if correct else 0.0,
        reasoning=(
            f"escalated={escalated} vs expected={interaction.escalation_expected}"
            + ("" if interaction.escalated is not None else " (inferred from response phrasing)")
        ),
        dimensions={
            "escalation_expected": float(interaction.escalation_expected),
            "escalation_executed": float(escalated),
        },
    )
