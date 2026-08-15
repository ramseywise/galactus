"""Feature engineering (lag/rolling/EWM/calendar/Fourier) and feature-importance
analysis (mutual information, correlation, permutation importance) for tabular
time-series ML (gradient boosting, etc.).

Adapted from a real production forecasting pipeline — rewritten from polars to
pandas (more standard for a general-purpose ml toolkit) and, for the
lag/rolling/EWM builders, from the original's manual per-series Python loops to
vectorized `groupby().shift()`/`.rolling()`/`.ewm()` calls — same feature
semantics, meaningfully faster on real data. Dropped `add_company_level_features`
entirely (cash-flow/customer-specific — inflow/outflow ratios, "cash runway" —
not generic).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

LAG_PERIODS: list[int] = [1, 7, 14, 28, 30]
ROLL_WINDOWS: list[int] = [7, 14, 30, 90]


def add_lag_features(
    df: pd.DataFrame,
    value_col: str = "value",
    series_col: str = "series_id",
    date_col: str = "date",
    lags: list[int] = LAG_PERIODS,
) -> pd.DataFrame:
    """Add lag features per series (no cross-series leakage) — each series is
    shifted independently via groupby, sorted by date first."""
    df = df.sort_values([series_col, date_col])
    grouped = df.groupby(series_col)[value_col]
    for lag in lags:
        df[f"lag_{lag}"] = grouped.shift(lag)
    return df


def add_rolling_features(
    df: pd.DataFrame,
    value_col: str = "value",
    series_col: str = "series_id",
    date_col: str = "date",
    windows: list[int] = ROLL_WINDOWS,
) -> pd.DataFrame:
    """Rolling mean/std/min/max per series, computed on [i-window+1 .. i]
    (no lookahead — pandas' default rolling window is trailing)."""
    df = df.sort_values([series_col, date_col])
    grouped = df.groupby(series_col)[value_col]
    for w in windows:
        rolling = grouped.rolling(window=w, min_periods=w)
        df[f"roll_mean_{w}"] = rolling.mean().reset_index(level=0, drop=True)
        df[f"roll_std_{w}"] = rolling.std().reset_index(level=0, drop=True)
        df[f"roll_min_{w}"] = rolling.min().reset_index(level=0, drop=True)
        df[f"roll_max_{w}"] = rolling.max().reset_index(level=0, drop=True)
    return df


def add_ewm_features(
    df: pd.DataFrame,
    value_col: str = "value",
    series_col: str = "series_id",
    date_col: str = "date",
    spans: list[int] | None = None,
) -> pd.DataFrame:
    """Exponentially weighted mean per series, per span — more responsive to
    recent changes than a simple rolling mean, useful for catching trend
    shifts early."""
    if spans is None:
        spans = [7, 14, 30]
    df = df.sort_values([series_col, date_col])
    grouped = df.groupby(series_col)[value_col]
    for span in spans:
        df[f"ewm_{span}"] = grouped.transform(
            lambda s, sp=span: s.ewm(span=sp, adjust=False).mean()
        )
    return df


def add_calendar_features(
    df: pd.DataFrame,
    date_col: str = "date",
    include_fourier: bool = True,
) -> pd.DataFrame:
    """Calendar features (day-of-week, month-end, quarter-end, ...) plus
    optional Fourier terms (sin/cos harmonics for weekly/monthly/annual
    seasonality) — lets a model capture smooth seasonality without a
    dummy-variable explosion. Use k=1..2 harmonics per period."""
    dates = pd.to_datetime(df[date_col])
    df = df.copy()
    df["day_of_week"] = dates.dt.dayofweek
    df["day_of_month"] = dates.dt.day
    df["month"] = dates.dt.month
    df["quarter"] = dates.dt.quarter
    df["day_of_year"] = dates.dt.dayofyear
    df["is_month_end"] = dates.dt.is_month_end.astype(int)
    df["is_quarter_end"] = dates.dt.is_quarter_end.astype(int)
    df["is_year_end"] = dates.dt.is_year_end.astype(int)
    df["days_to_month_end"] = (dates + pd.offsets.MonthEnd(0) - dates).dt.days

    if include_fourier:
        dow = df["day_of_week"].to_numpy(dtype=float)
        dom = df["day_of_month"].to_numpy(dtype=float)
        doy = df["day_of_year"].to_numpy(dtype=float)
        for k in (1, 2):
            df[f"weekly_sin_{k}"] = np.sin(2 * np.pi * k * dow / 7)
            df[f"weekly_cos_{k}"] = np.cos(2 * np.pi * k * dow / 7)
            df[f"monthly_sin_{k}"] = np.sin(2 * np.pi * k * dom / 30.44)
            df[f"monthly_cos_{k}"] = np.cos(2 * np.pi * k * dom / 30.44)
            df[f"annual_sin_{k}"] = np.sin(2 * np.pi * k * doy / 365.25)
            df[f"annual_cos_{k}"] = np.cos(2 * np.pi * k * doy / 365.25)

    return df


def build_feature_matrix(
    df: pd.DataFrame,
    value_col: str = "value",
    series_col: str = "series_id",
    date_col: str = "date",
    include_fourier: bool = True,
    include_ewm: bool = True,
    lags: list[int] = LAG_PERIODS,
    roll_windows: list[int] = ROLL_WINDOWS,
) -> pd.DataFrame:
    """One-shot feature builder: lag + rolling + ewm + calendar + Fourier.

    Returns a DataFrame ready for ML models. NaN rows (early history, before
    enough lag/rolling context exists) are retained — drop them before fitting.
    """
    df = add_lag_features(df, value_col, series_col, date_col, lags)
    df = add_rolling_features(df, value_col, series_col, date_col, roll_windows)
    if include_ewm:
        df = add_ewm_features(df, value_col, series_col, date_col)
    df = add_calendar_features(df, date_col, include_fourier)
    return df


@dataclass
class FeatureImportanceResult:
    method: str
    importances: dict[str, float]  # feature_name -> score
    ranked: list[tuple[str, float]]  # sorted desc by score

    def top_k(self, k: int = 15) -> list[tuple[str, float]]:
        return self.ranked[:k]

    def as_dataframe(self) -> pd.DataFrame:
        names, scores = zip(*self.ranked, strict=False) if self.ranked else ([], [])
        return pd.DataFrame({"feature": list(names), "importance": list(scores)})


def mutual_information_importance(
    x: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    discrete_features: bool = False,
) -> FeatureImportanceResult:
    """Mutual information between each feature and the target — model-agnostic
    (works before any model is fitted) and captures nonlinear dependencies,
    unlike correlation."""
    try:
        from sklearn.feature_selection import mutual_info_regression

        # discrete_features accepts bool at runtime (sklearn docs) even though
        # the bundled type stub only declares "auto" | array-like — stub gap,
        # not a real type error.
        scores = mutual_info_regression(x, y, discrete_features=discrete_features, random_state=42)  # type: ignore[arg-type]
        importance = dict(zip(feature_names, scores.tolist(), strict=False))
        ranked = sorted(importance.items(), key=lambda item: item[1], reverse=True)
        return FeatureImportanceResult("mutual_information", importance, ranked)
    except ImportError:
        return correlation_importance(x, y, feature_names)


def correlation_importance(
    x: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    method: Literal["pearson", "spearman"] = "pearson",
) -> FeatureImportanceResult:
    """|Pearson| or |Spearman| correlation of each feature with the target.
    Spearman is more robust to monotonic nonlinear relationships and outliers.
    Useful for lag selection: correlation of lag_k vs. target across k reveals
    the dominant autocorrelation lag."""
    scores: dict[str, float] = {}
    for i, name in enumerate(feature_names):
        col = x[:, i]
        valid = ~(np.isnan(col) | np.isnan(y))
        if valid.sum() < 10:
            scores[name] = 0.0
            continue
        if method == "pearson":
            c = float(np.corrcoef(col[valid], y[valid])[0, 1])
        else:
            from scipy.stats import spearmanr

            # Same scipy stub gap as mannwhitneyu — .statistic is real at runtime.
            c = float(spearmanr(col[valid], y[valid]).statistic)  # type: ignore[attr-defined]
        scores[name] = abs(c) if not np.isnan(c) else 0.0

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return FeatureImportanceResult(f"{method}_correlation", scores, ranked)


def permutation_importance(
    model,  # any fitted model exposing .predict(X)
    x: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    n_repeats: int = 10,
    scoring_fn=None,  # callable(y_true, y_pred) -> float, higher = better
    random_state: int = 42,
) -> FeatureImportanceResult:
    """Shuffle each feature, measure the performance drop — works for any
    fitted model (sklearn, XGBoost, LightGBM). A negative "drop" means the
    feature was actually hurting the model."""
    rng = np.random.default_rng(random_state)

    def default_neg_mae(y_true, y_pred):
        return -float(np.mean(np.abs(y_true - y_pred)))

    score_fn = scoring_fn or default_neg_mae
    baseline_score = score_fn(y, model.predict(x))

    importances: dict[str, float] = {}
    for i, name in enumerate(feature_names):
        drops: list[float] = []
        for _ in range(n_repeats):
            x_perm = x.copy()
            x_perm[:, i] = rng.permutation(x_perm[:, i])
            perm_score = score_fn(y, model.predict(x_perm))
            drops.append(baseline_score - perm_score)
        importances[name] = float(np.mean(drops))

    ranked = sorted(importances.items(), key=lambda item: item[1], reverse=True)
    return FeatureImportanceResult("permutation", importances, ranked)
