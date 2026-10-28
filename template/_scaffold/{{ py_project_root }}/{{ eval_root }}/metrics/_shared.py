"""Shared aggregation helpers for interaction metrics (metrics/<metric>.py)."""

from __future__ import annotations

from evals.models import GraderResult, MetricSummary


def pass_rate(results: list[GraderResult]) -> float | None:
    if not results:
        return None
    return sum(1 for r in results if r.is_correct) / len(results)


def mean_score(results: list[GraderResult]) -> float | None:
    if not results:
        return None
    return sum(r.score for r in results) / len(results)


def summarize(metric: str, results: list[GraderResult]) -> MetricSummary:
    """Aggregate one metric's grader results, split by grader type."""
    heuristic = [r for r in results if r.metric == metric and r.grader == "heuristic"]
    judge = [r for r in results if r.metric == metric and r.grader == "judge"]
    return MetricSummary(
        metric=metric,
        n_heuristic=len(heuristic),
        n_judge=len(judge),
        heuristic_pass_rate=pass_rate(heuristic),
        judge_pass_rate=pass_rate(judge),
        judge_mean_score=mean_score(judge),
    )
