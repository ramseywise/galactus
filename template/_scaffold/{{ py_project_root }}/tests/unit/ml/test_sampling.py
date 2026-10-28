from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.sampling import (
    ClassWeightSampler,
    SamplingLeakageError,
    build_sampler,
    compute_class_weights,
    detect_outliers,
    is_validation,
    mark_validation,
    remove_outliers,
    resample_fold,
)

RANDOM_STATE = 42


@pytest.fixture
def imbalanced():
    """A synthetic 95/5 frame — the shape every strategy is judged on."""
    rng = np.random.default_rng(RANDOM_STATE)
    n = 1000
    n_minority = 50
    y = pd.Series([0] * (n - n_minority) + [1] * n_minority)
    x = pd.DataFrame(
        {
            "f1": rng.normal(0, 1, n) + y * 1.5,
            "f2": rng.normal(0, 1, n),
            "f3": rng.normal(0, 1, n) - y * 0.8,
        }
    )
    return x, y


@pytest.fixture
def imbalanced_with_categorical(imbalanced):
    x, y = imbalanced
    rng = np.random.default_rng(RANDOM_STATE)
    x = x.copy()
    # Ordinal-encoded categorical: SMOTENC must take the neighbourhood mode
    # rather than interpolating to a category that does not exist.
    x["region"] = rng.integers(0, 4, len(x)).astype(float)
    return x, y


def _minority_fraction(y) -> float:
    counts = pd.Series(np.asarray(y)).value_counts(normalize=True)
    return float(counts.min())


def test_baseline_frame_really_is_95_5(imbalanced):
    _, y = imbalanced

    assert _minority_fraction(y) == pytest.approx(0.05)


@pytest.mark.parametrize("strategy", ["smote", "under", "over", "smote_tomek"])
def test_each_resampling_strategy_rebalances_the_frame(imbalanced, strategy):
    pytest.importorskip("imblearn")
    x, y = imbalanced

    x_out, y_out, weights = resample_fold(x, y, strategy=strategy, random_state=RANDOM_STATE)

    assert _minority_fraction(y_out) > 0.4, f"{strategy} did not rebalance the frame"
    assert weights is None, "resampling strategies rebalance by rows, not weights"
    assert len(x_out) == len(y_out)


def test_smotenc_handles_categoricals(imbalanced_with_categorical):
    pytest.importorskip("imblearn")
    x, y = imbalanced_with_categorical
    categorical_index = list(x.columns).index("region")

    x_out, y_out, _ = resample_fold(
        x, y, strategy="smotenc", categorical_indices=[categorical_index]
    )

    assert _minority_fraction(y_out) > 0.4
    synthesised = set(np.asarray(x_out)[:, categorical_index])
    assert synthesised <= set(x["region"].unique()), (
        "SMOTENC must take existing category values, never interpolate between them"
    )


def test_smotenc_without_categorical_indices_raises():
    with pytest.raises(ValueError, match="categorical_indices"):
        build_sampler("smotenc")


def test_class_weight_is_the_default_and_reweights_without_copying_rows(imbalanced):
    x, y = imbalanced

    sampler = build_sampler()
    x_out, _ = sampler.fit_resample(x, y)

    assert isinstance(sampler, ClassWeightSampler)
    assert len(x_out) == len(x), "class weighting must not invent or drop rows"
    assert sampler.class_weight_[1] > sampler.class_weight_[0], (
        "the minority class must carry the larger weight"
    )


def test_class_weights_are_balanced(imbalanced):
    _, y = imbalanced
    weights = compute_class_weights(y)

    # n_samples / (n_classes * count): 1000/(2*950) and 1000/(2*50)
    assert weights[0] == pytest.approx(1000 / (2 * 950))
    assert weights[1] == pytest.approx(1000 / (2 * 50))


def test_none_strategy_is_a_real_passthrough(imbalanced):
    x, y = imbalanced

    x_out, y_out, weights = resample_fold(x, y, strategy="none")

    assert len(x_out) == len(x)
    assert weights is None
    assert _minority_fraction(y_out) == pytest.approx(0.05)


def test_unknown_strategy_raises():
    with pytest.raises(ValueError, match="unknown strategy"):
        build_sampler("magic")


@pytest.mark.parametrize("strategy", ["none", "class_weight", "smote", "under", "over"])
def test_applying_a_sampler_to_validation_data_raises(imbalanced, strategy):
    x, y = imbalanced
    validation = mark_validation(x)

    sampler = build_sampler(strategy)
    with pytest.raises(SamplingLeakageError, match="held-out"):
        sampler.fit_resample(validation, y)


def test_the_marker_survives_the_slicing_a_fold_does(imbalanced):
    x, _ = imbalanced
    validation = mark_validation(x)

    assert is_validation(validation.iloc[:10]), (
        "a fold indexes into the frame; the marker must survive or the guard is trivially bypassed"
    )


def test_marking_does_not_mutate_the_callers_frame(imbalanced):
    x, _ = imbalanced
    mark_validation(x)

    assert not is_validation(x), "marking returns a marked copy, it does not stamp in place"


def test_unmarked_training_data_passes_the_guard(imbalanced):
    x, y = imbalanced

    x_out, _ = build_sampler("class_weight").fit_resample(x, y)

    assert len(x_out) == len(x)


def test_absent_imbalanced_learn_degrades_to_class_weights(imbalanced, monkeypatch, caplog):
    x, y = imbalanced
    monkeypatch.setattr("ml.sampling.resample._imblearn_available", lambda: False)

    with caplog.at_level("WARNING"):
        sampler = build_sampler("smote")

    assert isinstance(sampler, ClassWeightSampler), (
        "a missing optional dep must degrade, not raise ImportError"
    )
    assert any("imbalanced-learn" in record.getMessage() for record in caplog.records)

    _, _, weights = resample_fold(x, y, strategy="smote")
    assert weights is not None, "the degraded path still rebalances, via weights"


def test_degraded_path_still_enforces_the_leakage_guard(imbalanced, monkeypatch):
    x, y = imbalanced
    monkeypatch.setattr("ml.sampling.resample._imblearn_available", lambda: False)

    with pytest.raises(SamplingLeakageError):
        build_sampler("smote").fit_resample(mark_validation(x), y)


def test_seeded_resampling_is_reproducible(imbalanced):
    pytest.importorskip("imblearn")
    x, y = imbalanced

    first, _, _ = resample_fold(x, y, strategy="smote", random_state=RANDOM_STATE)
    second, _, _ = resample_fold(x, y, strategy="smote", random_state=RANDOM_STATE)

    np.testing.assert_allclose(np.asarray(first, dtype=float), np.asarray(second, dtype=float))


@pytest.fixture
def frame_with_outliers():
    rng = np.random.default_rng(RANDOM_STATE)
    values = rng.normal(50, 5, 200)
    values[:4] = [500.0, 600.0, -400.0, 700.0]
    return pd.DataFrame({"amount": values, "score": rng.normal(0, 1, 200)})


@pytest.mark.parametrize("method", ["iqr", "zscore", "isolation_forest"])
def test_each_outlier_method_flags_the_planted_extremes(frame_with_outliers, method):
    threshold = 3.0 if method == "zscore" else 1.5
    mask = detect_outliers(frame_with_outliers, ["amount"], method, threshold=threshold)

    assert mask.iloc[:4].all(), f"{method} missed the planted extreme values"
    assert not mask.iloc[4:].all(), f"{method} flagged everything, which flags nothing"


def test_remove_outliers_returns_the_cleaned_frame_and_the_mask(frame_with_outliers):
    cleaned, mask = remove_outliers(frame_with_outliers, ["amount"], "iqr")

    assert len(cleaned) == len(frame_with_outliers) - int(mask.sum())
    assert cleaned["amount"].max() < 500.0


def test_remove_outliers_refuses_to_drop_a_large_fraction(frame_with_outliers):
    with pytest.raises(ValueError, match="ceiling"):
        remove_outliers(frame_with_outliers, ["amount"], "zscore", threshold=0.01)


def test_outlier_detection_refuses_validation_data(frame_with_outliers):
    with pytest.raises(SamplingLeakageError):
        detect_outliers(mark_validation(frame_with_outliers), ["amount"], "iqr")


def test_outlier_detection_needs_numeric_columns():
    df = pd.DataFrame({"label": ["a", "b", "c"]})

    with pytest.raises(ValueError, match="no numeric columns"):
        detect_outliers(df)


def test_unknown_outlier_method_raises(frame_with_outliers):
    with pytest.raises(ValueError, match="unknown method"):
        detect_outliers(frame_with_outliers, ["amount"], "vibes")
