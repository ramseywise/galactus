"""Friction metric aggregation — heuristic flag rate vs judge friction scores."""

from __future__ import annotations

from evals.metrics._shared import summarize
from evals.models import GraderResult, MetricSummary


def summary(results: list[GraderResult]) -> MetricSummary:
    return summarize("friction", results)
