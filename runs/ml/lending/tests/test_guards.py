"""Unit tests for `guards.py` — every guard has a tripping test AND a passing twin.

The positive path is what makes a guard real: a guard only proven by its trip could be
`raise` unconditionally and every tripping test would still pass. Toolkit-free — pandas,
sklearn, numpy only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from guards import (
    GuardError,
    assert_excluded_absent,
    final_metric_alarm,
    single_feature_auc_alarm,
)


def _clean_tiny_frame(n: int = 200, seed: int = 7) -> pd.DataFrame:
    """A small guard-clean frame: a weakly-informative feature and a noise feature."""
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < 0.2).astype(int)
    return pd.DataFrame(
        {
            "charged_off": y,
            # weak signal: shifted noise, nowhere near the 0.95 alarm line
            "loan_amnt": rng.normal(loc=10_000 + 500 * y, scale=5_000, size=n),
            "noise": rng.normal(size=n),
            "group_key": [f"g{i}" for i in range(n)],  # non-numeric: invisible to (b)
        }
    )


# --- guard (a): excluded columns --------------------------------------------------


def test_excluded_column_trips_naming_it():
    df = _clean_tiny_frame()
    df["recoveries"] = 0.0
    with pytest.raises(GuardError) as exc_info:
        assert_excluded_absent(df)
    assert "recoveries" in str(exc_info.value)


def test_clean_frame_passes_excluded_guard():
    assert_excluded_absent(_clean_tiny_frame())


# --- guard (b): single-feature AUC alarm ------------------------------------------


def test_target_copy_column_trips_auc_alarm():
    df = _clean_tiny_frame()
    # A near-copy of the label: the classic surviving-leak shape.
    df["settlement_ish"] = df["charged_off"] + 0.01 * np.random.default_rng(0).random(len(df))
    with pytest.raises(GuardError) as exc_info:
        single_feature_auc_alarm(df)
    assert "settlement_ish" in str(exc_info.value)


def test_inverse_predictor_trips_auc_alarm():
    """Direction-free: a perfect negative ranker separates just as well."""
    df = _clean_tiny_frame()
    df["inverse_leak"] = -df["charged_off"].astype(float)
    with pytest.raises(GuardError) as exc_info:
        single_feature_auc_alarm(df)
    assert "inverse_leak" in str(exc_info.value)


def test_allowlisted_column_passes_auc_alarm():
    df = _clean_tiny_frame()
    df["argued_legit"] = df["charged_off"].astype(float)
    single_feature_auc_alarm(df, allowlist=("argued_legit",))


def test_clean_frame_passes_auc_alarm():
    single_feature_auc_alarm(_clean_tiny_frame())


def test_all_nan_and_constant_columns_are_skipped_not_crashed():
    df = _clean_tiny_frame()
    df["all_nan"] = np.nan
    df["constant"] = 1.0
    single_feature_auc_alarm(df)


# --- guard (d): final metric alarm ------------------------------------------------


def test_metric_alarm_trips_at_096():
    with pytest.raises(GuardError) as exc_info:
        final_metric_alarm({"logistic": 0.71, "leaky_model": 0.96})
    assert "leaky_model" in str(exc_info.value)


def test_metric_alarm_passes_at_094():
    final_metric_alarm({"logistic": 0.71, "catboost": 0.94})


def test_metric_alarm_tolerates_missing_scores():
    """A model whose ROC-AUC is None (skipped, refused) must not crash the guard."""
    final_metric_alarm({"logistic": 0.71, "skipped_model": None})
