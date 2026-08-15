"""ARIMA / SARIMA forecasting with explicit assumption checking and diagnostics.

ARIMA assumptions (all must hold — violation degrades or invalidates the model):
  1. Stationarity after d differences (unit root removed — ADF test)
  2. No autocorrelation in residuals (Ljung-Box test)
  3. Homoskedastic residuals (ARCH test)
  4. Normally distributed residuals (Jarque-Bera; needed for valid prediction intervals)
  5. Sufficient history: at least 4x the seasonal period (so 52+ obs for weekly)

Auto mode uses `statsforecast`'s AutoARIMA (searches (p,d,q)(P,D,Q)[s] space via
information criterion); manual mode uses `statsmodels` with an explicit order,
after running `check_assumptions()`. Falls back to a naive seasonal forecast if
neither library succeeds.

Usage:
    model = ARIMAForecaster(series_id="revenue")
    model.check_assumptions(train_values)   # prints a diagnostic report
    model.fit(train_values)
    result = model.predict(horizon=30)
    print(result.comparison_vs_naive())
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ml.timeseries.preprocessing import (
    StationarityReport,
    check_stationarity,
    difference_series,
)


@dataclass
class AssumptionReport:
    """Full diagnostic output from assumption checking."""

    series_id: str
    n_obs: int
    stationarity: StationarityReport
    ljung_box_passed: bool | None  # None if statsmodels unavailable
    ljung_box_pvalue: float | None
    heteroskedasticity_passed: bool | None
    arch_pvalue: float | None
    normality_passed: bool | None  # Jarque-Bera
    jb_pvalue: float | None
    min_obs_met: bool
    seasonal_period_detected: int | None
    violations: list[str]
    warnings: list[str]
    recommendation: str


def check_arima_assumptions(
    values: np.ndarray,
    series_id: str = "unknown",
    min_obs_multiplier: int = 4,
    seasonal_period: int = 7,
) -> AssumptionReport:
    """Run all ARIMA pre-fit assumption checks and return a structured report."""
    violations: list[str] = []
    warnings: list[str] = []
    n = len(values)

    stat = check_stationarity(values, series_id=series_id)
    if not stat.adf_stationary:
        violations.append(
            f"Non-stationary (ADF p={stat.adf_pvalue:.3f}). "
            f"Apply d={stat.recommended_d} differencing before fitting."
        )

    min_obs = min_obs_multiplier * seasonal_period
    min_obs_met = n >= min_obs
    if not min_obs_met:
        violations.append(
            f"Insufficient history: {n} obs < {min_obs} (4 x seasonal period {seasonal_period}). "
            "ARIMA estimates will be unreliable."
        )

    ljung_passed = ljung_pval = arch_pval = hetero_passed = jb_passed = jb_pval = None

    # N811 below: statsmodels' ARIMA is a class, not a constant — aliased to
    # avoid colliding with this module's own ARIMA.
    try:
        from scipy.stats import jarque_bera
        from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch
        from statsmodels.tsa.arima.model import ARIMA as StatsARIMA  # noqa: N811

        d = stat.recommended_d
        work = difference_series(values, d) if d > 0 else values
        work = work[~np.isnan(work)]

        try:
            fit = StatsARIMA(work, order=(1, 0, 0)).fit()
            resid = fit.resid

            lb = acorr_ljungbox(resid, lags=[10], return_df=True)
            ljung_pval = float(lb["lb_pvalue"].iloc[0])
            ljung_passed = ljung_pval > 0.05
            if not ljung_passed:
                violations.append(
                    f"Residual autocorrelation (Ljung-Box p={ljung_pval:.3f}). "
                    "Increase AR/MA order."
                )

            arch_test = het_arch(resid, nlags=5)
            arch_pval = float(arch_test[1])
            hetero_passed = arch_pval > 0.05
            if not hetero_passed:
                warnings.append(
                    f"Heteroskedastic residuals (ARCH p={arch_pval:.3f}). "
                    "Consider log transform or GARCH. Prediction intervals may be unreliable."
                )

            jb_result = jarque_bera(resid)
            jb_pval = float(jb_result[1])  # type: ignore[arg-type]
            jb_passed = jb_pval > 0.05
            if not jb_passed:
                warnings.append(
                    f"Non-normal residuals (JB p={jb_pval:.3f}). "
                    "Prediction intervals are approximate — use bootstrap PI."
                )
        except Exception:
            warnings.append("Could not fit diagnostic AR(1) — skipping residual tests")
    except ImportError:
        warnings.append("statsmodels/scipy not available — skipping residual diagnostics")

    detected_period = _detect_seasonal_period(values)
    if detected_period and detected_period != seasonal_period:
        warnings.append(
            f"Detected seasonal period {detected_period} differs from specified {seasonal_period}. "
            "Consider SARIMA with the correct s parameter."
        )

    if not violations:
        rec = f"Assumptions met for ARIMA(p,{stat.recommended_d},q). Safe to fit."
    elif len(violations) == 1 and not stat.adf_stationary:
        rec = f"Apply d={stat.recommended_d} differencing, then fit ARIMA."
    else:
        rec = (
            "Multiple assumption violations. Consider: "
            "(1) log transform for heteroskedasticity, "
            "(2) higher d for non-stationarity, "
            "(3) a non-parametric model as an alternative."
        )

    return AssumptionReport(
        series_id=series_id,
        n_obs=n,
        stationarity=stat,
        ljung_box_passed=ljung_passed,
        ljung_box_pvalue=ljung_pval,
        heteroskedasticity_passed=hetero_passed,
        arch_pvalue=arch_pval,
        normality_passed=jb_passed,
        jb_pvalue=jb_pval,
        min_obs_met=min_obs_met,
        seasonal_period_detected=detected_period,
        violations=violations,
        warnings=warnings,
        recommendation=rec,
    )


def _detect_seasonal_period(values: np.ndarray, max_period: int = 52) -> int | None:
    """Heuristic: find the dominant period via autocorrelation peak."""
    n = len(values)
    if n < 2 * max_period:
        return None
    work = values - np.mean(values)
    autocorr = np.correlate(work, work, mode="full")[n - 1 :]
    autocorr = autocorr[1 : max_period + 1] / (autocorr[0] + 1e-8)
    if len(autocorr) == 0:
        return None
    period = int(np.argmax(autocorr)) + 1
    return period if autocorr[period - 1] > 0.3 else None


@dataclass
class ARIMAForecastResult:
    series_id: str
    model_spec: str  # e.g. "ARIMA(2,1,1)" or "AutoARIMA"
    point_forecast: list[float]
    lower_80: list[float]
    upper_80: list[float]
    aic: float | None
    bic: float | None
    horizon: int
    assumption_report: AssumptionReport | None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def comparison_vs_naive(self, actuals: np.ndarray | None = None) -> str:
        """Quick text summary for comparison output."""
        lines = [
            f"Model: {self.model_spec}",
            f"Horizon: {self.horizon} steps",
            f"AIC: {self.aic:.1f}" if self.aic else "AIC: N/A",
            f"Forecast range: [{min(self.point_forecast):.0f}, {max(self.point_forecast):.0f}]",
        ]
        if actuals is not None and len(actuals) >= self.horizon:
            act = np.array(actuals[: self.horizon])
            preds = np.array(self.point_forecast)
            mae = np.mean(np.abs(act - preds))
            naive = np.mean(np.abs(np.diff(act)))
            mase = mae / (naive + 1e-8)
            lines.append(f"MASE vs naive: {mase:.3f}")
        return "\n".join(lines)


class ARIMAForecaster:
    """ARIMA / SARIMA / AutoARIMA wrapper with assumption diagnostics.

    Fits one model per series_id. For multi-series forecasting, instantiate one
    ARIMAForecaster per series (stateful — holds the fitted model).

    Auto mode (auto=True): uses statsforecast's AutoARIMA — fastest path.
    Manual mode: specify (p, d, q) explicitly after running check_assumptions().
    """

    def __init__(
        self,
        series_id: str,
        auto: bool = True,
        order: tuple[int, int, int] = (1, 1, 1),
        seasonal_order: tuple[int, int, int, int] = (0, 0, 0, 0),  # (P, D, Q, s)
        exog_cols: list[str] | None = None,
    ):
        self.series_id = series_id
        self.auto = auto
        self.order = order
        self.seasonal_order = seasonal_order
        self.exog_cols = exog_cols or []
        self._fitted_model: Any = None
        self._last_train_values: np.ndarray | None = None

    def check_assumptions(self, values: np.ndarray, seasonal_period: int = 7) -> AssumptionReport:
        """Run the full assumption check and print a human-readable report."""
        report = check_arima_assumptions(
            values, series_id=self.series_id, seasonal_period=seasonal_period
        )
        _print_assumption_report(report)
        return report

    def fit(
        self,
        values: np.ndarray,
        exog: np.ndarray | None = None,
        seasonal_period: int = 7,
    ) -> AssumptionReport | None:
        """Fit ARIMA or AutoARIMA on training values.

        Returns an assumption report if auto=False (skipped for AutoARIMA speed).
        """
        self._last_train_values = values.copy()
        assumption_report = None

        if self.auto:
            self._fitted_model = self._fit_auto(values, exog, seasonal_period)
        else:
            assumption_report = check_arima_assumptions(
                values, self.series_id, seasonal_period=seasonal_period
            )
            self._fitted_model = self._fit_manual(values, exog)

        return assumption_report

    def predict(
        self,
        horizon: int = 30,
        exog_future: np.ndarray | None = None,
        level: int = 80,
    ) -> ARIMAForecastResult:
        """Generate point + interval forecasts."""
        if self._fitted_model is None:
            raise RuntimeError("Call fit() before predict()")

        point, lower, upper, aic, bic, spec = self._generate_forecast(horizon, exog_future, level)

        return ARIMAForecastResult(
            series_id=self.series_id,
            model_spec=spec,
            point_forecast=[max(0.0, p) for p in point],
            lower_80=[max(0.0, low) for low in lower],
            upper_80=[max(0.0, up) for up in upper],
            aic=aic,
            bic=bic,
            horizon=horizon,
            assumption_report=None,
        )

    def _fit_auto(self, values: np.ndarray, exog: np.ndarray | None, seasonal_period: int) -> Any:
        try:
            import pandas as pd
            from statsforecast import StatsForecast
            from statsforecast.models import AutoARIMA

            n = len(values)
            df_sf = pd.DataFrame(
                {
                    "unique_id": [self.series_id] * n,
                    "ds": pd.date_range("2020-01-01", periods=n, freq="D"),
                    "y": values.tolist(),
                }
            )
            sf = StatsForecast(
                models=[AutoARIMA(season_length=seasonal_period, approximation=True)],
                freq="D",
                n_jobs=1,
            )
            sf.fit(df_sf)
            return ("statsforecast", sf, df_sf)
        except ImportError:
            return self._fit_manual(values, exog)

    def _fit_manual(self, values: np.ndarray, exog: np.ndarray | None) -> Any:
        try:
            # N811: see the note in _fit_auto — class alias, not a constant.
            from statsmodels.tsa.arima.model import ARIMA as StatsARIMA  # noqa: N811

            p, d, q = self.order
            model = StatsARIMA(values, order=(p, d, q), exog=exog).fit()
            return ("statsmodels", model)
        except Exception:
            return ("naive", values.copy())

    def _generate_forecast(
        self,
        horizon: int,
        exog_future: np.ndarray | None,
        level: int,
    ) -> tuple[list[float], list[float], list[float], float | None, float | None, str]:
        backend, *rest = self._fitted_model

        if backend == "statsforecast":
            sf, _df_sf = rest
            pred = sf.predict(h=horizon, level=[level])
            col = "AutoARIMA"
            point = pred[col].tolist()
            lower = pred[f"{col}-lo-{level}"].tolist()
            upper = pred[f"{col}-hi-{level}"].tolist()
            return point, lower, upper, None, None, "AutoARIMA(seasonal)"

        elif backend == "statsmodels":
            model = rest[0]
            fc = model.get_forecast(steps=horizon, exog=exog_future)
            ci = fc.conf_int(alpha=1 - level / 100)
            point = list(fc.predicted_mean)
            # conf_int() returns a DataFrame when fit on a pandas Series, but a
            # plain ndarray when fit on a raw numpy array (our case) — handle both.
            ci_arr = ci.to_numpy() if hasattr(ci, "to_numpy") else np.asarray(ci)
            lower = ci_arr[:, 0].tolist()
            upper = ci_arr[:, 1].tolist()
            p, d, q = self.order
            return (
                point,
                lower,
                upper,
                float(model.aic),
                float(model.bic),
                f"ARIMA({p},{d},{q})",
            )

        else:
            vals = rest[0]
            last7 = vals[-7:] if len(vals) >= 7 else vals
            point = list(np.tile(last7, math.ceil(horizon / len(last7)))[:horizon])
            lower = [p * 0.85 for p in point]
            upper = [p * 1.15 for p in point]
            return point, lower, upper, None, None, "NaiveSeasonal(lag-7)"


def _print_assumption_report(report: AssumptionReport) -> None:
    print(f"\n=== ARIMA Assumptions: {report.series_id} ===")
    print(
        f"Stationarity: {'PASS' if report.stationarity.adf_stationary else 'FAIL'} "
        f"(d={report.stationarity.recommended_d})"
    )
    for v in report.violations:
        print(f"  VIOLATION: {v}")
    for w in report.warnings:
        print(f"  WARNING: {w}")
    print(f"Recommendation: {report.recommendation}")
