"""Language metric aggregation — response-language match rate."""

from __future__ import annotations

from evals.metrics._shared import summarize
from evals.models import GraderResult, MetricSummary


def summary(results: list[GraderResult]) -> MetricSummary:
    return summarize("language", results)
