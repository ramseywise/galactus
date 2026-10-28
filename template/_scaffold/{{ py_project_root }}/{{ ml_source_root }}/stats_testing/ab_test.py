"""A/B test statistics: power analysis, proportion confidence intervals,
Mann-Whitney U (for skewed, non-normal metrics), and bootstrap Cliff's delta
effect size.

Adapted from a real production support-team A/B test — genericized (dropped
hardcoded CSV paths and German-language comments/prints; the statistical
methodology is unchanged).

Usage:
    n = required_sample_size(effect_size=0.2)  # groups need >= n rows each
    ci = proportion_ci(count=34, nobs=58)
    result = mann_whitney_test(group_a, group_b)
    delta = bootstrap_cliffs_delta(group_a, group_b)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def required_sample_size(
    effect_size: float,
    alpha: float = 0.05,
    power: float = 0.8,
) -> int:
    """Minimum per-group sample size for a two-sided, two-independent-groups
    t-test to detect `effect_size` (Cohen's d) at the given alpha/power."""
    from statsmodels.stats.power import tt_ind_solve_power

    n = tt_ind_solve_power(
        effect_size=effect_size, alpha=alpha, power=power, alternative="two-sided"
    )
    return int(np.ceil(n))


@dataclass
class ProportionCI:
    proportion: float
    ci_low: float
    ci_high: float
    method: str


def proportion_ci(
    count: int, nobs: int, alpha: float = 0.05, method: str = "wilson"
) -> ProportionCI:
    """Confidence interval for a binomial proportion (e.g. "how many customers
    gave a top rating"). Wilson's method (the default) behaves well even for
    small samples or proportions near 0/1, unlike the normal approximation."""
    from statsmodels.stats.proportion import proportion_confint

    ci_low, ci_high = proportion_confint(count=count, nobs=nobs, alpha=alpha, method=method)
    return ProportionCI(proportion=count / nobs, ci_low=ci_low, ci_high=ci_high, method=method)


@dataclass
class MannWhitneyResult:
    u_statistic: float
    p_value: float
    significant: bool  # at alpha=0.05


def mann_whitney_test(a: np.ndarray, b: np.ndarray) -> MannWhitneyResult:
    """Two-sided Mann-Whitney U test — a non-parametric alternative to the
    t-test, appropriate for skewed or ordinal metrics (e.g. response times,
    ratings) where normality can't be assumed."""
    from scipy.stats import mannwhitneyu

    result = mannwhitneyu(a, b, alternative="two-sided")
    # scipy's stub types this return value too generically to expose
    # .statistic/.pvalue — real attributes at runtime (SignificanceResult).
    u_stat = float(result.statistic)  # type: ignore[attr-defined]
    p_value = float(result.pvalue)  # type: ignore[attr-defined]
    return MannWhitneyResult(u_statistic=u_stat, p_value=p_value, significant=p_value < 0.05)


def cliffs_delta(a: np.ndarray, b: np.ndarray) -> float:
    """Cliff's delta: a rank-based, distribution-free effect size in [-1, 1].
    0 means the two groups are stochastically identical; |delta| close to 1
    means one group's values are almost always larger than the other's."""
    a = np.asarray(a)
    b = np.asarray(b)
    # Vectorized: for each element of a, count how many of b it exceeds/is
    # exceeded by, summed — equivalent to the naive O(n*m) double loop but
    # using numpy broadcasting instead of a Python-level loop per element.
    diff = a[:, None] - b[None, :]
    ranks = int(np.sum(diff > 0)) - int(np.sum(diff < 0))
    return ranks / (len(a) * len(b))


def cliffs_delta_strength(delta: float) -> str:
    """Effect-size labels per Romano et al. (2006)."""
    abs_delta = abs(delta)
    if abs_delta < 0.147:
        return "negligible"
    elif abs_delta < 0.33:
        return "small"
    elif abs_delta < 0.474:
        return "medium"
    return "large"


@dataclass
class BootstrapCliffsDeltaResult:
    delta: float
    strength: str
    ci_low: float
    ci_high: float
    deltas: np.ndarray  # the full bootstrap distribution, for plotting


def bootstrap_cliffs_delta(
    a: np.ndarray,
    b: np.ndarray,
    n_resamples: int = 10000,
    seed: int | None = None,
) -> BootstrapCliffsDeltaResult:
    """Bootstrap a 95% CI for Cliff's delta by resampling both groups with
    replacement `n_resamples` times."""
    a = np.asarray(a)
    b = np.asarray(b)
    rng = np.random.default_rng(seed)

    deltas = np.empty(n_resamples)
    for i in range(n_resamples):
        sample_a = rng.choice(a, size=len(a), replace=True)
        sample_b = rng.choice(b, size=len(b), replace=True)
        deltas[i] = cliffs_delta(sample_a, sample_b)

    point_delta = cliffs_delta(a, b)
    ci_low, ci_high = np.percentile(deltas, [2.5, 97.5])
    return BootstrapCliffsDeltaResult(
        delta=point_delta,
        strength=cliffs_delta_strength(point_delta),
        ci_low=float(ci_low),
        ci_high=float(ci_high),
        deltas=deltas,
    )
