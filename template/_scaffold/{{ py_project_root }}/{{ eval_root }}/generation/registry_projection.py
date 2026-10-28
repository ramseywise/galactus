"""Project harness metrics into the shape Phase 1's run registry accepts.

Phase 1's eval adapter deliberately takes a plain metrics map rather than a
typed eval result, so that Phase 1 could not be blocked on this extraction.
That decoupling is preserved here: this module knows the registry's shape
(`dict[str, float | NotApplicable]` plus an explicit `headline_metric`); the
registry knows nothing about this harness. Nothing here imports from `runs`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from experiments.record import NotApplicable

HEADLINE_METRIC = "contract_pass_rate"
"""Matches Phase 1's own worked example. `RunRecord.__post_init__` validates
that the declared headline names a key actually present in the projected
map, so this must stay in sync with `to_run_record_metrics` below."""

NON_FLOAT_KEYS = ("cases", "errors", "total_llm_calls")
"""`compute_metrics` reports these as `int` counts; the registry wants `float`."""


def to_run_record_metrics(
    metrics: Mapping[str, Any],
) -> tuple[dict[str, float | NotApplicable], str]:
    """Project harness metrics into the registry's dict + headline shape.

    Handles the two shape mismatches `compute_metrics` produces:
    `cases`/`errors`/`total_llm_calls` are `int` and coerce to `float`;
    `repair_convergence` may be `None` when no case converged, and maps to
    `NotApplicable("no case converged")` — never to `0.0`, which would read
    as "converged instantly" and is the exact brier/getattr failure Phase
    1's registry exists to prevent.
    """
    projected: dict[str, float | NotApplicable] = {}
    for key, value in metrics.items():
        if key in NON_FLOAT_KEYS:
            projected[key] = float(value)
        elif value is None:
            projected[key] = NotApplicable("no case converged")
        else:
            projected[key] = float(value)

    return projected, HEADLINE_METRIC
