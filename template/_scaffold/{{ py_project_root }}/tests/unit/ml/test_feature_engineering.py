from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from ml.feature_engineering.features import (
    add_calendar_features,
    add_ewm_features,
    add_lag_features,
    add_rolling_features,
    build_feature_matrix,
    correlation_importance,
    mutual_information_importance,
    permutation_importance,
)


def _panel_df(n: int = 100) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    rng = np.random.default_rng(0)
    values = np.linspace(10, 50, n) + rng.normal(0, 1, n)
    return pd.DataFrame({"date": dates, "series_id": "s1", "value": values})


def test_add_lag_features_shifts_correctly():
    df = _panel_df()
    out = add_lag_features(df, lags=[1, 7])
    assert "lag_1" in out.columns and "lag_7" in out.columns
    # lag_1 at row i should equal value at row i-1
    assert np.isclose(out["lag_1"].iloc[10], out["value"].iloc[9])


def test_add_rolling_features_no_lookahead():
    df = _panel_df()
    out = add_rolling_features(df, windows=[7])
    # roll_mean_7 at row i should be the mean of value[i-6:i+1]
    expected = df["value"].iloc[10 - 6 : 11].mean()
    assert np.isclose(out["roll_mean_7"].iloc[10], expected)


def test_add_ewm_features_produces_smoothed_series():
    df = _panel_df()
    out = add_ewm_features(df, spans=[7])
    assert "ewm_7" in out.columns
    assert out["ewm_7"].notna().all()


def test_add_calendar_features_and_fourier():
    df = _panel_df()
    out = add_calendar_features(df, include_fourier=True)
    assert "day_of_week" in out.columns
    assert "weekly_sin_1" in out.columns
    assert out["weekly_sin_1"].between(-1, 1).all()


def test_build_feature_matrix_end_to_end():
    df = _panel_df()
    out = build_feature_matrix(df)
    assert "lag_1" in out.columns
    assert "roll_mean_7" in out.columns
    assert "weekly_sin_1" in out.columns


def test_correlation_and_mutual_information_importance():
    rng = np.random.default_rng(1)
    n = 200
    x1 = rng.normal(0, 1, n)
    x2 = rng.normal(0, 1, n)
    y = 3 * x1 + rng.normal(0, 0.1, n)  # y strongly depends on x1, not x2
    x = np.column_stack([x1, x2])

    corr = correlation_importance(x, y, feature_names=["x1", "x2"])
    assert corr.ranked[0][0] == "x1"

    mi = mutual_information_importance(x, y, feature_names=["x1", "x2"])
    assert mi.ranked[0][0] == "x1"


def test_permutation_importance_ranks_informative_feature_first():
    rng = np.random.default_rng(2)
    n = 300
    x1 = rng.normal(0, 1, n)
    x2 = rng.normal(0, 1, n)
    y = 5 * x1 + rng.normal(0, 0.1, n)
    x = np.column_stack([x1, x2])

    model = LinearRegression().fit(x, y)
    result = permutation_importance(model, x, y, feature_names=["x1", "x2"], n_repeats=5)
    assert result.ranked[0][0] == "x1"
