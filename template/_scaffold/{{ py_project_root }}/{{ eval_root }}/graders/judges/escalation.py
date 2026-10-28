"""Escalation judge: was a hand-off warranted, and did the assistant execute it?"""

from __future__ import annotations

from evals.graders.judges.base import LLMJudge
from evals.models import EvalInteraction


class EscalationJudge(LLMJudge):
    metric = "escalation"
    system_prompt = """\
You evaluate whether a support assistant correctly escalated (handed off to a
human) — escalating when the query is beyond its scope, and NOT escalating
when it could answer directly.

Return ONLY a JSON object with these exact keys:
{
  "escalation_warranted": <0.0 or 1.0>,
  "escalation_executed": <0.0 or 1.0>,
  "is_correct": <true if warranted == executed, else false>,
  "score": <1.0 if correct, else 0.0>,
  "reasoning": "<one sentence>"
}"""

    def format_user_message(self, interaction: EvalInteraction) -> str:
        return (
            f"User query: {interaction.query}\n"
            f"escalated={interaction.escalated}\n"
            f"escalation_expected={interaction.escalation_expected}\n\n"
            f"Assistant response:\n{interaction.response}"
        )
