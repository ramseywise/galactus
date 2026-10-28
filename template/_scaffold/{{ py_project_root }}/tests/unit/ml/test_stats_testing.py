from __future__ import annotations

import numpy as np

from ml.stats_testing.ab_test import (
    bootstrap_cliffs_delta,
    cliffs_delta,
    cliffs_delta_strength,
    mann_whitney_test,
    proportion_ci,
    required_sample_size,
)


def test_required_sample_size_decreases_with_larger_effect():
    n_small_effect = required_sample_size(effect_size=0.1)
    n_large_effect = required_sample_size(effect_size=0.5)
    assert n_small_effect > n_large_effect > 0


def test_proportion_ci_contains_point_estimate():
    result = proportion_ci(count=34, nobs=58)
    assert result.ci_low <= result.proportion <= result.ci_high
    assert abs(result.proportion - 34 / 58) < 1e-9


def test_mann_whitney_detects_real_difference():
    rng = np.random.default_rng(0)
    group_a = rng.normal(10, 2, 100)
    group_b = rng.normal(20, 2, 100)  # clearly shifted
    result = mann_whitney_test(group_a, group_b)
    assert result.significant
    assert result.p_value < 0.05


def test_cliffs_delta_identical_groups_near_zero():
    rng = np.random.default_rng(1)
    group = rng.normal(0, 1, 200)
    delta = cliffs_delta(group, group.copy())
    assert abs(delta) < 1e-9
    assert cliffs_delta_strength(delta) == "negligible"


def test_cliffs_delta_fully_separated_groups_is_large():
    group_a = np.arange(0, 50)
    group_b = np.arange(100, 150)
    delta = cliffs_delta(group_a, group_b)
    assert delta == -1.0
    assert cliffs_delta_strength(delta) == "large"


def test_bootstrap_cliffs_delta_ci_brackets_point_estimate():
    rng = np.random.default_rng(2)
    group_a = rng.normal(10, 3, 60)
    group_b = rng.normal(15, 3, 60)
    result = bootstrap_cliffs_delta(group_a, group_b, n_resamples=500, seed=3)
    assert result.ci_low <= result.delta <= result.ci_high
    assert len(result.deltas) == 500
