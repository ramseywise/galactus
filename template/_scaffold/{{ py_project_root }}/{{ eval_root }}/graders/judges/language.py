"""Language judge: is the response in the language the user needs, and fluent?"""

from __future__ import annotations

from evals.graders.judges.base import LLMJudge
from evals.models import EvalInteraction


class LanguageJudge(LLMJudge):
    metric = "language"
    system_prompt = """\
You evaluate whether a support assistant answered in the right language.
The response should match the expected language (or, when none is given, the
language of the user's query), and read fluently in it — not machine-mangled.

Return ONLY a JSON object with these exact keys:
{
  "language_match": <0.0 or 1.0>,
  "fluency": <0.0 to 1.0>,
  "is_correct": <true if the language matches and fluency >= 0.5>,
  "score": <0.0 to 1.0>,
  "reasoning": "<one sentence>"
}"""

    def format_user_message(self, interaction: EvalInteraction) -> str:
        return (
            f"User query: {interaction.query}\n"
            f"expected_language={interaction.expected_language or 'match the query'}\n\n"
            f"Assistant response:\n{interaction.response}"
        )
