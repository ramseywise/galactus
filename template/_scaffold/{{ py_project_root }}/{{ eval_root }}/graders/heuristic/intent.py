"""Intent heuristic: did the system route/classify the query as expected?"""

from __future__ import annotations

from evals.models import EvalInteraction, GraderResult


def grade(interaction: EvalInteraction) -> GraderResult | None:
    if interaction.routed_to is None or interaction.expected_intent is None:
        return None
    correct = interaction.routed_to.strip().lower() == interaction.expected_intent.strip().lower()
    return GraderResult(
        interaction_id=interaction.id,
        metric="intent",
        grader="heuristic",
        is_correct=correct,
        score=1.0 if correct else 0.0,
        reasoning=f"routed_to={interaction.routed_to!r} vs expected={interaction.expected_intent!r}",
        dimensions={"intent_match": float(correct)},
    )
