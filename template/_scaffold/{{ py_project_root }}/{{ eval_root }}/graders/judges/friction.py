"""Friction judge: rates UX friction in a response (0 = smooth, 1 = high friction)."""

from __future__ import annotations

from evals.graders.judges.base import LLMJudge
from evals.models import EvalInteraction, GraderResult


class FrictionJudge(LLMJudge):
    metric = "friction"
    system_prompt = """\
You are a user-friction evaluator for a support assistant.

High friction means the response makes the user's experience worse:
unnecessary hedging, burying the answer in caveats, asking for information the
user already provided, or a vague non-answer when a direct one was possible.
Low friction means: direct, accurate, easy to follow.

Return ONLY a JSON object with these exact keys:
{
  "friction_score": <0.0 (no friction) to 1.0 (high friction)>,
  "primary_cause": "<main cause of friction, or 'none'>",
  "reasoning": "<one sentence>"
}"""

    # Mirrors the heuristic's bar: a response passes when judged friction is low.
    _PASS_BELOW = 0.4

    def grade(self, interaction: EvalInteraction) -> GraderResult | None:
        result = super().grade(interaction)
        if result is None:
            return None
        friction = result.dimensions.get("friction_score", 1.0 - result.score)
        result.is_correct = friction < self._PASS_BELOW
        result.score = round(1.0 - friction, 3)
        return result
