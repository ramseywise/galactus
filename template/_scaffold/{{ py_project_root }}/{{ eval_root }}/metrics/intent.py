"""Intent metric aggregation — routing accuracy from heuristic and judge grades."""

from __future__ import annotations

from evals.metrics._shared import summarize
from evals.models import GraderResult, MetricSummary


def summary(results: list[GraderResult]) -> MetricSummary:
    return summarize("intent", results)
