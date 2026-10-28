"""Escalation metric aggregation — heuristic appropriateness vs judge scores.

Extend here for project-specific rollups (e.g. missed-escalation rate split
from over-escalation rate); keep the ``summary`` signature stable — the
registry and reports call it.
"""

from __future__ import annotations

from evals.metrics._shared import summarize
from evals.models import GraderResult, MetricSummary


def summary(results: list[GraderResult]) -> MetricSummary:
    return summarize("escalation", results)
