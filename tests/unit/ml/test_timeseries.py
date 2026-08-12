from __future__ import annotations

import numpy as np

from ml.timeseries.arima import ARIMAForecaster, check_arima_assumptions
from ml.timeseries.preprocessing import (
    apply_scaler,
    check_stationarity,
    detect_outliers,
    difference_series,
    fit_scaler,
    inverse_scaler,
    treat_outliers,
)


def _trending_series(n: int = 120, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    trend = np.linspace(100, 200, n)
    noise = rng.normal(0, 5, n)
    return trend + noise


def test_check_stationarity_detects_trend():
    series = _trending_series()
    report = check_stationarity(series, series_id="test")
    assert report.series_id == "test"
    # A clear linear trend should not be flagged stationary at d=0.
    assert report.recommended_d >= 1


def test_difference_series_removes_trend():
    series = _trending_series()
    diffed = difference_series(series, d=1)
    assert len(diffed) == len(series) - 1
    # Differencing a linear trend should collapse the mean drift.
    assert abs(np.mean(diffed) - np.mean(np.diff(series))) < 1e-6


def test_detect_and_treat_outliers():
    rng = np.random.default_rng(0)
    values = rng.normal(50, 2, 100)
    values[10] = 500.0  # inject a real outlier
    mask = detect_outliers(values, method="iqr")
    assert mask[10]
    treated = treat_outliers(values, mask, treatment="winsorise")
    assert treated[10] < 500.0


def test_scaler_roundtrip():
    values = np.array([10.0, 20.0, 30.0, 40.0])
    params = fit_scaler(values, method="standard")
    scaled = apply_scaler(values, params)
    restored = inverse_scaler(scaled, params)
    assert np.allclose(restored, values, atol=1e-6)


def test_check_arima_assumptions_returns_report():
    series = _trending_series()
    report = check_arima_assumptions(series, series_id="test", seasonal_period=7)
    assert report.n_obs == len(series)
    assert isinstance(report.violations, list)


def test_arima_forecaster_fit_predict():
    series = _trending_series(n=60)
    model = ARIMAForecaster(series_id="test", auto=False, order=(1, 1, 0))
    model.fit(series)
    result = model.predict(horizon=5)
    assert result.horizon == 5
    assert len(result.point_forecast) == 5
    assert all(p >= 0.0 for p in result.point_forecast)
