"""Intent judge: independently classifies the query's intent and checks the routing."""

from __future__ import annotations

from evals.graders.judges.base import LLMJudge
from evals.models import EvalInteraction


class IntentJudge(LLMJudge):
    metric = "intent"
    system_prompt = """\
You evaluate intent routing for a support assistant. Given the user's query,
the intent the system routed it to, and the expected intent, judge whether the
routing was correct — and whether the response actually addresses the query's
real intent (a lucky wrong route that still answers well is noted in
reasoning but scored on the routing).

Return ONLY a JSON object with these exact keys:
{
  "routing_correct": <0.0 or 1.0>,
  "is_correct": <true|false>,
  "score": <0.0 to 1.0>,
  "reasoning": "<one sentence>"
}"""

    def format_user_message(self, interaction: EvalInteraction) -> str:
        return (
            f"User query: {interaction.query}\n"
            f"routed_to={interaction.routed_to}\n"
            f"expected_intent={interaction.expected_intent}\n\n"
            f"Assistant response:\n{interaction.response}"
        )
