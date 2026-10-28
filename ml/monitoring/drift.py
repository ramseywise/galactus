"""Drift detection — has the world moved away from the training data?

Two tests, because they disagree in useful ways:

* **PSI** (population stability index) bins the reference distribution and
  measures how much probability mass moved between bins. It is the industry
  convention, it is interpretable, and its thresholds (0.1 / 0.25) are
  conventional rather than derived — treat them as a prompt to look, not a
  verdict.
* **KS** (two-sample Kolmogorov-Smirnov) is a real hypothesis test with a
  p-value, but its power scales with sample size: at a million rows it flags
  differences too small to change any decision.

Reading them together is the point. PSI high and KS low means a shift big enough
to matter but noisy; KS low p-value with negligible PSI usually means "you have
a lot of rows", not "retrain".

Prediction drift is tracked separately and matters most: features can shift a
long way without changing what the model outputs, and the output is what
downstream decisions consume.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

DEFAULT_BINS = 10
PSI_MINOR = 0.1
PSI_MAJOR = 0.25
KS_ALPHA = 0.05
# A fraction of a bin's worth of mass, substituted for an empty bin so the log
# does not blow up. Zero mass in a reference bin is an artefact of binning, not
# evidence of infinite drift.
EPSILON = 1e-6


@dataclass(frozen=True)
class FeatureDrift:
    """One feature's drift, by both tests."""

    feature: str
    psi: float
    ks_statistic: float | None
    ks_pvalue: float | None
    kind: str  # "numeric" | "categorical"
    reference_missing: float = 0.0
    current_missing: float = 0.0

    @property
    def severity(self) -> str:
        if self.psi >= PSI_MAJOR:
            return "major"
        if self.psi >= PSI_MINOR:
            return "minor"
        return "stable"

    @property
    def drifted(self) -> bool:
        return self.psi >= PSI_MINOR

    @property
    def significant(self) -> bool:
        """KS says the two samples are unlikely to share a distribution."""
        return self.ks_pvalue is not None and self.ks_pvalue < KS_ALPHA


@dataclass
class DriftReport:
    """Per-feature drift plus the one question a caller actually asks."""

    features: list[FeatureDrift]
    n_reference: int
    n_current: int
    prediction_drift: FeatureDrift | None = None
    missing_features: list[str] = field(default_factory=list)
    new_features: list[str] = field(default_factory=list)

    @property
    def drifted(self) -> list[FeatureDrift]:
        return sorted((f for f in self.features if f.drifted), key=lambda f: f.psi, reverse=True)

    @property
    def major(self) -> list[FeatureDrift]:
        return [f for f in self.features if f.severity == "major"]

    @property
    def max_psi(self) -> float:
        return max((f.psi for f in self.features), default=0.0)

    @property
    def retrain_recommended(self) -> bool:
        """Any major feature shift, any prediction shift, or a schema change.

        Deliberately a low bar for *recommending* — the cost of looking is an
        afternoon and the cost of not looking is a model that has been quietly
        wrong for a quarter. It recommends; it does not retrain.
        """
        if self.missing_features:
            return True
        if self.major:
            return True
        return self.prediction_drift is not None and self.prediction_drift.drifted

    @property
    def reason(self) -> str:
        if self.missing_features:
            return (
                f"{len(self.missing_features)} training feature(s) absent from the current "
                f"frame: {self.missing_features[:5]}"
            )
        if self.prediction_drift is not None and self.prediction_drift.drifted:
            return (
                f"the model's own output distribution shifted (PSI "
                f"{self.prediction_drift.psi:.3g}) — downstream decisions have already changed"
            )
        if self.major:
            names = ", ".join(f"{f.feature} ({f.psi:.3g})" for f in self.major[:5])
            return f"{len(self.major)} feature(s) past the major threshold: {names}"
        if self.drifted:
            return f"{len(self.drifted)} feature(s) show minor drift; watch, do not retrain yet"
        return "no feature exceeded the minor drift threshold"

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "feature": f.feature,
                    "psi": f.psi,
                    "ks_statistic": f.ks_statistic,
                    "ks_pvalue": f.ks_pvalue,
                    "severity": f.severity,
                    "kind": f.kind,
                }
                for f in sorted(self.features, key=lambda f: f.psi, reverse=True)
            ]
        )


def population_stability_index(
    reference: Sequence[float], current: Sequence[float], *, bins: int = DEFAULT_BINS
) -> float:
    """PSI between two numeric samples, using reference quantile edges.

    Quantile edges, not equal-width: equal-width bins on a skewed feature put
    99% of both samples in one bin and report a PSI of ~0 for any shift inside
    it. The edges come from the *reference* sample because the reference is the
    fixed thing being compared against.
    """
    ref = np.asarray(reference, dtype=float)
    cur = np.asarray(current, dtype=float)
    ref = ref[~np.isnan(ref)]
    cur = cur[~np.isnan(cur)]
    if ref.size == 0 or cur.size == 0:
        return 0.0

    quantiles = np.linspace(0, 100, bins + 1)
    edges = np.unique(np.percentile(ref, quantiles))
    if edges.size < 2:  # a constant reference feature cannot drift by this measure
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf

    ref_counts, _ = np.histogram(ref, bins=edges)
    cur_counts, _ = np.histogram(cur, bins=edges)

    ref_pct = np.maximum(ref_counts / ref.size, EPSILON)
    cur_pct = np.maximum(cur_counts / cur.size, EPSILON)
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def categorical_psi(reference: Sequence[Any], current: Sequence[Any]) -> float:
    """PSI over category shares. Categories unseen in the reference count as drift."""
    ref = pd.Series(list(reference)).dropna().astype(str)
    cur = pd.Series(list(current)).dropna().astype(str)
    if ref.empty or cur.empty:
        return 0.0

    categories = sorted(set(ref) | set(cur))
    ref_pct = np.maximum(
        ref.value_counts().reindex(categories, fill_value=0).to_numpy() / len(ref), EPSILON
    )
    cur_pct = np.maximum(
        cur.value_counts().reindex(categories, fill_value=0).to_numpy() / len(cur), EPSILON
    )
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def compute_drift(
    reference_df: pd.DataFrame,
    current_df: pd.DataFrame,
    *,
    features: Sequence[str] | None = None,
    bins: int = DEFAULT_BINS,
    reference_predictions: Sequence[float] | None = None,
    current_predictions: Sequence[float] | None = None,
) -> DriftReport:
    """Compare two frames feature by feature.

    `features` defaults to the columns common to both frames. Pass the training
    feature list explicitly in production — then a column that vanished shows up
    in `missing_features` instead of being silently excluded from the comparison,
    which is the difference between a report that catches a schema break and one
    that does not.
    """
    if features is None:
        features = [c for c in reference_df.columns if c in current_df.columns]

    missing = [c for c in features if c not in current_df.columns]
    absent_from_reference = [c for c in features if c not in reference_df.columns]
    new = [c for c in current_df.columns if c not in reference_df.columns]

    results: list[FeatureDrift] = []
    for column in features:
        if column in missing or column in absent_from_reference:
            continue
        try:
            results.append(
                _one_feature(reference_df[column], current_df[column], name=column, bins=bins)
            )
        except Exception as exc:
            logger.warning("drift for %s could not be computed: %s", column, exc)

    prediction_drift = None
    if reference_predictions is not None and current_predictions is not None:
        prediction_drift = _one_feature(
            pd.Series(list(reference_predictions)),
            pd.Series(list(current_predictions)),
            name="prediction",
            bins=bins,
        )

    return DriftReport(
        features=results,
        n_reference=len(reference_df),
        n_current=len(current_df),
        prediction_drift=prediction_drift,
        missing_features=missing + absent_from_reference,
        new_features=new,
    )


def _one_feature(reference: pd.Series, current: pd.Series, *, name: str, bins: int) -> FeatureDrift:
    numeric = pd.api.types.is_numeric_dtype(reference) and pd.api.types.is_numeric_dtype(current)

    ref_missing = float(reference.isna().mean())
    cur_missing = float(current.isna().mean())

    if numeric:
        ref = reference.dropna().to_numpy(dtype=float)
        cur = current.dropna().to_numpy(dtype=float)
        psi = population_stability_index(ref, cur, bins=bins)
        ks_stat: float | None = None
        ks_p: float | None = None
        if ref.size > 1 and cur.size > 1:
            result = stats.ks_2samp(ref, cur)
            ks_stat, ks_p = float(result.statistic), float(result.pvalue)
        kind = "numeric"
    else:
        psi = categorical_psi(reference, current)
        # KS is defined on continuous distributions; running it on category codes
        # would produce a number whose ordering is an artefact of encoding order.
        ks_stat = ks_p = None
        kind = "categorical"

    return FeatureDrift(
        feature=name,
        psi=psi,
        ks_statistic=ks_stat,
        ks_pvalue=ks_p,
        kind=kind,
        reference_missing=ref_missing,
        current_missing=cur_missing,
    )
