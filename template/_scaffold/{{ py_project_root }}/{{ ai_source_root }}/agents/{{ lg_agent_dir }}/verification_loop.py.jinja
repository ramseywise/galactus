"""Verification loop wrapper for the LangGraph agent.

Runs the compiled graph once, passes the output to a grader (reuses the
eval-pillar's GraderResult interface — no duplication), and retries up to
``max_retries`` times if the grade fails.  The retry cap is independent of
the graph's own ``recursion_limit`` / ``checkpointer`` step cap so the inner
loop can hit its own ceiling without burning the outer retry budget.

Usage::

    from agents.{{ lg_agent_dir }}.verification_loop import run_with_verification
    from agents.{{ lg_agent_dir }}.graph import build_graph

    graph = build_graph()
    result, attempts = await run_with_verification(graph, state, config, grader=my_grader)

``grader`` is optional — when omitted the loop runs exactly once (no grading).
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from evals.graders.judges.base import LLMJudge
from evals.models import EvalInteraction, GraderResult

log = logging.getLogger(__name__)

_MAX_RETRIES_DEFAULT = 3


async def run_with_verification(
    graph,
    initial_state: dict[str, Any],
    config: RunnableConfig,
    *,
    grader: LLMJudge | None = None,
    max_retries: int = _MAX_RETRIES_DEFAULT,
    pass_threshold: float = 0.7,
) -> tuple[dict[str, Any], int]:
    """Run the graph with optional grader-gated retries.

    Parameters
    ----------
    graph:
        A compiled LangGraph graph (returned by ``build_graph()``).
    initial_state:
        The initial state dict to pass to ``graph.ainvoke``.
    config:
        LangGraph ``RunnableConfig`` (contains ``thread_id`` etc.).
    grader:
        An ``LLMJudge`` instance whose ``grade()`` method returns a
        ``GraderResult``.  When ``None`` the loop runs once with no grading.
    max_retries:
        Maximum number of attempts (first run + retries).  Independently
        capped from the graph's own ``recursion_limit``.
    pass_threshold:
        Minimum ``GraderResult.score`` to accept as a passing response.
        Defaults to 0.7 (same as ``JudgeVerdict.from_response_text``).

    Returns
    -------
    tuple[dict, int]
        The final state dict and the number of attempts made (1 = no retry).
    """
    if max_retries < 1:
        raise ValueError(f"max_retries must be >= 1, got {max_retries}")

    state = initial_state
    last_result: dict[str, Any] = {}
    last_grade: GraderResult | None = None

    for attempt in range(1, max_retries + 1):
        last_result = await graph.ainvoke(state, config)

        if grader is None:
            log.debug("verification-loop no-grader attempt=%d", attempt)
            return last_result, attempt

        interaction = EvalInteraction(
            id=config.get("configurable", {}).get("thread_id", "unknown"),
            query=str(initial_state.get("message", "")),
            response=str(last_result.get("answer", "")),
        )
        last_grade = grader.grade(interaction)

        if last_grade is None:
            log.warning(
                "verification-loop grader returned None (API/parse failure) "
                "attempt=%d — accepting response",
                attempt,
            )
            return last_result, attempt

        log.debug(
            "verification-loop attempt=%d score=%.3f pass=%s",
            attempt,
            last_grade.score,
            last_grade.is_correct,
        )

        if last_grade.score >= pass_threshold:
            return last_result, attempt

        if attempt < max_retries:
            # Feed failure context back so the next attempt can improve.
            feedback = (
                f"[verification-loop] Previous response did not meet quality threshold "
                f"(score={last_grade.score:.2f}). Reasoning: {last_grade.reasoning}. "
                "Please try again with a more accurate answer."
            )
            state = {**initial_state, "verification_feedback": feedback}
            log.info(
                "verification-loop retry attempt=%d/%d score=%.3f",
                attempt,
                max_retries,
                last_grade.score,
            )

    log.warning(
        "verification-loop exhausted retries max_retries=%d final_score=%.3f",
        max_retries,
        last_grade.score if last_grade else 0.0,
    )
    return last_result, max_retries
