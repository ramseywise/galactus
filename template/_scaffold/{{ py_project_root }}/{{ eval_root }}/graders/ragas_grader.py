"""Ragas-based LLM-judge grading — faithfulness/answer-relevancy/context-precision
scores for a single (question, contexts, answer, ground_truth) row.

KNOWN ISSUE (verified 2026-07-14): the current ``ragas`` release on PyPI (0.4.3)
has a broken top-level import — ``ragas.llms.base`` unconditionally imports
``langchain_community.chat_models.vertexai.ChatVertexAI``, a submodule that no
longer exists in current ``langchain-community`` releases (moved to the
separate ``langchain-google-vertexai`` package, which doesn't help — the
submodule path itself is gone). ``uv sync``/``pip install ragas`` succeeds
since dependency *resolution* is fine, but ``import ragas`` crashes — this is
an upstream packaging bug in ragas itself, confirmed by installing it fresh and
reproducing the crash, not something fixable from this side.
``grade_with_ragas`` below catches this and returns ``None`` (skipping ragas
scoring for the row, not crashing the whole eval run) rather than papering over
it — check whether a newer ``ragas`` release has fixed this before expecting
real scores here.
"""

from __future__ import annotations

from evals.graders.judges.base import judge_model


def grade_with_ragas(
    question: str, contexts: list[str], answer: str, ground_truth: str
) -> dict[str, float] | None:
    """Returns ``{"faithfulness": ..., "answer_relevancy": ..., "context_precision": ...}``,
    or ``None`` if ragas isn't usable in this environment (see module docstring)."""
    try:
        from datasets import Dataset
        from langchain_anthropic import ChatAnthropic
        from ragas import evaluate
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import answer_relevancy, context_precision, faithfulness
    except Exception as exc:
        print(f"Warning: ragas unavailable, skipping ragas grading for this row: {exc}")
        return None

    dataset = Dataset.from_dict(
        {
            "question": [question],
            "contexts": [contexts],
            "answer": [answer],
            "ground_truth": [ground_truth],
        }
    )
    judge_llm = LangchainLLMWrapper(ChatAnthropic(model=judge_model()))
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision],
        llm=judge_llm,
    )
    row = result.to_pandas().iloc[0]
    return {
        "faithfulness": float(row["faithfulness"]),
        "answer_relevancy": float(row["answer_relevancy"]),
        "context_precision": float(row["context_precision"]),
    }
