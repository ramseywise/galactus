"""Step 9b — drift detection.

The Done-when is "PSI flags a synthetically shifted feature", but a detector
that fires on a shift proves only half of what matters. The other half — that it
stays quiet on two samples drawn from the same distribution — gets equal weight
here, because a drift monitor that alarms every week is a drift monitor someone
turns off.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.monitoring import (
    DriftReport,
    categorical_psi,
    compute_drift,
    population_stability_index,
)
from ml.monitoring.drift import KS_ALPHA, PSI_MAJOR, PSI_MINOR
from ml.selection.registry import RANDOM_STATE

N = 4000


@pytest.fixture(scope="module")
def reference() -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_STATE)
    return pd.DataFrame(
        {
            "amount": rng.normal(100.0, 15.0, N),
            "age": rng.integers(18, 80, N).astype(float),
            "region": rng.choice(["north", "south", "east", "west"], N, p=[0.4, 0.3, 0.2, 0.1]),
            "tier": rng.choice(["free", "paid"], N, p=[0.7, 0.3]),
        }
    )


@pytest.fixture(scope="module")
def stable(reference: pd.DataFrame) -> pd.DataFrame:
    """A second draw from the same generative process — nothing actually moved."""
    rng = np.random.default_rng(RANDOM_STATE + 1)
    return pd.DataFrame(
        {
            "amount": rng.normal(100.0, 15.0, N),
            "age": rng.integers(18, 80, N).astype(float),
            "region": rng.choice(["north", "south", "east", "west"], N, p=[0.4, 0.3, 0.2, 0.1]),
            "tier": rng.choice(["free", "paid"], N, p=[0.7, 0.3]),
        }
    )


@pytest.fixture(scope="module")
def shifted(stable: pd.DataFrame) -> pd.DataFrame:
    """`amount` moved by two reference standard deviations; everything else held."""
    frame = stable.copy()
    frame["amount"] = frame["amount"] + 30.0
    return frame


# --------------------------------------------------------------------------- #
# The Done-when: PSI flags a synthetically shifted feature.
# --------------------------------------------------------------------------- #


def test_psi_flags_a_shifted_numeric_feature(reference, shifted):
    report = compute_drift(reference, shifted)
    amount = next(f for f in report.features if f.feature == "amount")

    assert amount.psi > PSI_MAJOR
    assert amount.severity == "major"
    assert amount.drifted
    assert report.retrain_recommended
    assert "amount" in report.reason


def test_psi_stays_quiet_on_two_draws_from_the_same_distribution(reference, stable):
    """The false-positive half. A monitor that always alarms is not a monitor."""
    report = compute_drift(reference, stable)

    assert not report.retrain_recommended, report.reason
    assert report.major == []
    assert report.max_psi < PSI_MINOR, report.to_frame().to_string()
    assert "no feature exceeded" in report.reason


def test_only_the_shifted_feature_is_flagged(reference, shifted):
    report = compute_drift(reference, shifted)
    assert [f.feature for f in report.drifted] == ["amount"]


def test_psi_grows_with_the_size_of_the_shift():
    rng = np.random.default_rng(RANDOM_STATE)
    ref = rng.normal(0.0, 1.0, N)
    psis = [population_stability_index(ref, ref + delta) for delta in (0.0, 0.5, 1.0, 2.0)]
    assert psis == sorted(psis), psis
    assert psis[0] < PSI_MINOR
    assert psis[-1] > PSI_MAJOR


def test_psi_is_zero_for_a_sample_against_itself():
    rng = np.random.default_rng(RANDOM_STATE)
    values = rng.normal(size=1000)
    assert population_stability_index(values, values) == pytest.approx(0.0, abs=1e-9)


def test_psi_uses_quantile_edges_so_a_skewed_feature_still_registers():
    """Equal-width bins would put ~everything in bin 0 and report no drift."""
    rng = np.random.default_rng(RANDOM_STATE)
    ref = rng.exponential(1.0, N)
    cur = rng.exponential(2.0, N)
    assert population_stability_index(ref, cur) > PSI_MAJOR


def test_psi_survives_a_constant_reference_feature():
    """A feature that never varied cannot drift by this measure — it must not divide by zero."""
    assert population_stability_index(np.ones(500), np.ones(500) * 3.0) == 0.0


def test_psi_survives_empty_input():
    assert population_stability_index([], [1.0, 2.0]) == 0.0
    assert population_stability_index([1.0, 2.0], []) == 0.0


# --------------------------------------------------------------------------- #
# Categorical drift
# --------------------------------------------------------------------------- #


def test_categorical_psi_flags_a_changed_mix(reference):
    rng = np.random.default_rng(RANDOM_STATE + 2)
    moved = rng.choice(["north", "south", "east", "west"], N, p=[0.1, 0.2, 0.3, 0.4])
    assert categorical_psi(reference["region"], moved) > PSI_MAJOR


def test_categorical_psi_is_quiet_on_the_same_mix(reference, stable):
    assert categorical_psi(reference["region"], stable["region"]) < PSI_MINOR


def test_a_brand_new_category_counts_as_drift(reference):
    """A category the model never saw is drift, not a rounding error."""
    invaded = pd.Series(["central"] * (N // 2) + list(reference["region"][: N // 2]))
    assert categorical_psi(reference["region"], invaded) > PSI_MAJOR


def test_categorical_features_get_no_ks_statistic(reference, stable):
    """KS on category codes measures encoding order, not distribution distance."""
    report = compute_drift(reference, stable)
    region = next(f for f in report.features if f.feature == "region")
    assert region.kind == "categorical"
    assert region.ks_statistic is None
    assert region.ks_pvalue is None
    assert region.significant is False


# --------------------------------------------------------------------------- #
# KS alongside PSI
# --------------------------------------------------------------------------- #


def test_ks_agrees_with_psi_on_a_real_shift(reference, shifted):
    report = compute_drift(reference, shifted)
    amount = next(f for f in report.features if f.feature == "amount")
    assert amount.ks_pvalue is not None
    assert amount.ks_pvalue < KS_ALPHA
    assert amount.significant


def test_ks_reports_a_pvalue_for_every_numeric_feature(reference, stable):
    report = compute_drift(reference, stable)
    for feature in report.features:
        if feature.kind == "numeric":
            assert feature.ks_statistic is not None
            assert 0.0 <= feature.ks_pvalue <= 1.0


# --------------------------------------------------------------------------- #
# Schema changes and prediction drift
# --------------------------------------------------------------------------- #


def test_a_dropped_training_feature_is_reported_not_silently_skipped(reference, stable):
    """Defaulting to shared columns would hide exactly this."""
    narrowed = stable.drop(columns=["amount"])
    report = compute_drift(reference, narrowed, features=list(reference.columns))

    assert "amount" in report.missing_features
    assert report.retrain_recommended
    assert "absent" in report.reason


def test_default_feature_set_is_the_intersection(reference, stable):
    wider = stable.copy()
    wider["new_signal"] = 1.0
    report = compute_drift(reference, wider)
    assert "new_signal" in report.new_features
    assert "new_signal" not in [f.feature for f in report.features]


def test_prediction_drift_is_tracked_separately_and_recommends_retraining(reference, stable):
    """Features can move without changing output; output moving is what breaks decisions."""
    rng = np.random.default_rng(RANDOM_STATE)
    before = rng.beta(2.0, 8.0, N)
    after = rng.beta(8.0, 2.0, N)

    report = compute_drift(
        reference,
        stable,
        reference_predictions=before,
        current_predictions=after,
    )
    assert report.major == [], "features are stable — only the output moved"
    assert report.prediction_drift is not None
    assert report.prediction_drift.drifted
    assert report.retrain_recommended
    assert "output distribution shifted" in report.reason


def test_stable_predictions_do_not_trigger_a_retrain(reference, stable):
    rng = np.random.default_rng(RANDOM_STATE)
    report = compute_drift(
        reference,
        stable,
        reference_predictions=rng.beta(2.0, 8.0, N),
        current_predictions=rng.beta(2.0, 8.0, N),
    )
    assert not report.retrain_recommended, report.reason


# --------------------------------------------------------------------------- #
# Report shape
# --------------------------------------------------------------------------- #


def test_report_counts_both_frames(reference, shifted):
    report = compute_drift(reference, shifted)
    assert report.n_reference == len(reference)
    assert report.n_current == len(shifted)


def test_to_frame_is_sorted_worst_first(reference, shifted):
    frame = compute_drift(reference, shifted).to_frame()
    assert list(frame.columns) == [
        "feature",
        "psi",
        "ks_statistic",
        "ks_pvalue",
        "severity",
        "kind",
    ]
    assert frame["psi"].is_monotonic_decreasing
    assert frame.iloc[0]["feature"] == "amount"


def test_missing_values_are_recorded(reference, stable):
    holed = stable.copy()
    holed.loc[holed.index[: N // 4], "age"] = np.nan
    report = compute_drift(reference, holed)
    age = next(f for f in report.features if f.feature == "age")
    assert age.reference_missing == pytest.approx(0.0)
    assert age.current_missing == pytest.approx(0.25, abs=0.01)


def test_severity_thresholds_partition_cleanly():
    from ml.monitoring.drift import FeatureDrift

    def make(psi: float) -> FeatureDrift:
        return FeatureDrift(feature="x", psi=psi, ks_statistic=None, ks_pvalue=None, kind="numeric")

    assert make(0.0).severity == "stable"
    assert make(PSI_MINOR).severity == "minor"
    assert make(PSI_MAJOR).severity == "major"
    assert not make(PSI_MINOR - 1e-9).drifted
    assert make(PSI_MINOR).drifted


def test_an_empty_report_recommends_nothing():
    report = DriftReport(features=[], n_reference=0, n_current=0)
    assert not report.retrain_recommended
    assert report.max_psi == 0.0
