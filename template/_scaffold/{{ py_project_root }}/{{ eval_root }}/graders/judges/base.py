"""LLM-as-judge base: format prompt → call Claude → parse JSON → GraderResult.

Graceful-degradation contract (same as the retrieval pipeline's answer-overlap
grading): requires ANTHROPIC_API_KEY; without it — or on any API/parse error —
``grade()`` returns None and the pipeline continues heuristic-only.
"""

from __future__ import annotations

import logging
import os

from evals.graders.judges.schema import JudgeVerdict
from evals.models import EvalInteraction, GraderResult

log = logging.getLogger(__name__)

DEFAULT_JUDGE_MODEL = "claude-opus-4-8"


def judge_model() -> str:
    return os.environ.get("EVAL_JUDGE_MODEL", DEFAULT_JUDGE_MODEL)


def judges_available() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


class LLMJudge:
    """Subclasses set ``metric`` and ``system_prompt``; override
    ``format_user_message`` to surface metric-specific fields to the judge."""

    metric: str = "llm_judge"
    system_prompt: str = "You are an evaluator. Return only a JSON object."

    def __init__(self, model: str | None = None) -> None:
        self.model = model or judge_model()

    def format_user_message(self, interaction: EvalInteraction) -> str:
        return f"User query: {interaction.query}\n\nAssistant response:\n{interaction.response}"

    def grade(self, interaction: EvalInteraction) -> GraderResult | None:
        try:
            import anthropic

            client = anthropic.Anthropic()
            response = client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=self.system_prompt,
                messages=[{"role": "user", "content": self.format_user_message(interaction)}],
            )
            text = next(block.text for block in response.content if block.type == "text")
            verdict = JudgeVerdict.from_response_text(text)
        except Exception:
            log.debug("llm-judge-failed metric=%s", self.metric, exc_info=True)
            return None
        return GraderResult(
            interaction_id=interaction.id,
            metric=self.metric,
            grader="judge",
            is_correct=verdict.is_correct,
            score=verdict.score,
            reasoning=verdict.reasoning,
            dimensions=verdict.dimensions,
        )
