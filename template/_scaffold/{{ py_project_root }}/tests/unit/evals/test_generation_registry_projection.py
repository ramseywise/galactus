"""Step 7 — the projection from harness metrics into Phase 1's registry shape.

The claim under test: a projected metric map contains only `float` values or
explicit `NotApplicable` sentinels, never a bare `0.0` standing in for "no
case converged" — that substitution is the exact brier/getattr failure
Phase 1's registry exists to prevent.
"""

from __future__ import annotations

from evals.generation.registry_projection import (
    HEADLINE_METRIC,
    to_run_record_metrics,
)
from experiments.record import NotApplicable


def _metrics(**overrides: object) -> dict[str, object]:
    base = {
        "cases": 4,
        "contract_pass_rate": 50.0,
        "repair_convergence": 1.5,
        "fallback_rate": 25.0,
        "grounding_rate": 75.0,
        "contract_valid_rate": 100.0,
        "errors": 0,
        "total_llm_calls": 9,
    }
    base.update(overrides)
    return base


def test_headline_metric_defaults_to_contract_pass_rate() -> None:
    _, headline = to_run_record_metrics(_metrics())
    assert headline == "contract_pass_rate"
    assert headline == HEADLINE_METRIC


def test_headline_metric_is_always_a_key_in_the_projected_map() -> None:
    projected, headline = to_run_record_metrics(_metrics())
    assert headline in projected


def test_int_counts_coerce_to_float() -> None:
    projected, _ = to_run_record_metrics(_metrics(cases=4, errors=1, total_llm_calls=9))
    for key in ("cases", "errors", "total_llm_calls"):
        assert isinstance(projected[key], float)
        assert not isinstance(projected[key], bool)


def test_all_other_values_are_float() -> None:
    projected, _ = to_run_record_metrics(_metrics())
    non_sentinel_keys = set(projected) - {"repair_convergence"}
    for key in non_sentinel_keys:
        assert isinstance(projected[key], float)


def test_none_repair_convergence_maps_to_not_applicable_with_a_reason() -> None:
    projected, _ = to_run_record_metrics(_metrics(repair_convergence=None))
    convergence = projected["repair_convergence"]
    assert isinstance(convergence, NotApplicable)
    assert convergence.reason
    assert convergence != 0.0


def test_none_repair_convergence_never_becomes_zero() -> None:
    """The brier/getattr failure mode: 0.0 reads as 'converged instantly',
    not as 'no case converged'. These must never be conflated."""
    projected, _ = to_run_record_metrics(_metrics(repair_convergence=None))
    assert projected["repair_convergence"] != 0.0
    assert not isinstance(projected["repair_convergence"], float)


def test_a_real_repair_convergence_value_is_preserved_as_float() -> None:
    projected, _ = to_run_record_metrics(_metrics(repair_convergence=2.0))
    assert projected["repair_convergence"] == 2.0
    assert isinstance(projected["repair_convergence"], float)
