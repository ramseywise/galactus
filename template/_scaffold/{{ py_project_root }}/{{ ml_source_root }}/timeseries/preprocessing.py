"""Time-series preprocessing primitives: outlier detection/treatment,
stationarity testing (ADF/KPSS), differencing, and scaling.

Adapted from a real production forecasting pipeline. Trimmed to the
numpy-level primitives — the original also had a polars-DataFrame-level
`Preprocessor`/`fill_gaps` orchestration wrapper for multi-series panels,
which is pipeline glue you'd customize per-project anyway; these functions
are the reusable core.

Usage:
    stat = check_stationarity(values, series_id="revenue")
    if not stat.adf_stationary:
        values = difference_series(values, d=stat.recommended_d)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np


@dataclass
class StationarityReport:
    """ADF + KPSS test results for a single series."""

    series_id: str
    adf_statistic: float
    adf_pvalue: float
    adf_stationary: bool  # True if ADF rejects unit root (p < 0.05)
    kpss_statistic: float | None  # None if statsmodels unavailable
    kpss_pvalue: float | None
    kpss_stationary: bool | None  # True if KPSS fails to reject stationarity
    recommended_d: int  # suggested order of differencing
    conclusion: str


@dataclass
class OutlierReport:
    series_id: str
    method: str
    n_outliers: int
    outlier_indices: list[int]
    treatment: str  # "winsorise" | "interpolate" | "flag_only"


def detect_outliers(
    values: np.ndarray,
    method: Literal["iqr", "zscore", "both"] = "iqr",
    iqr_multiplier: float = 3.0,
    zscore_threshold: float = 3.5,
) -> np.ndarray:
    """Return boolean mask of outlier positions.

    IQR method: beyond Q1 - k*IQR or Q3 + k*IQR (robust to heavy tails).
    Z-score (modified, median-based): |z| > threshold (assumes approximate
    normality). "both": union of the two masks.
    """
    mask = np.zeros(len(values), dtype=bool)

    if method in ("iqr", "both"):
        q1, q3 = np.percentile(values, [25, 75])
        iqr = q3 - q1
        mask |= (values < q1 - iqr_multiplier * iqr) | (values > q3 + iqr_multiplier * iqr)

    if method in ("zscore", "both"):
        med = np.median(values)
        mad = np.median(np.abs(values - med))
        if mad > 1e-8:
            mod_z = 0.6745 * (values - med) / mad
            mask |= np.abs(mod_z) > zscore_threshold

    return mask


def treat_outliers(
    values: np.ndarray,
    outlier_mask: np.ndarray,
    treatment: Literal["winsorise", "interpolate", "flag_only"] = "winsorise",
    winsorise_pct: float = 0.01,
) -> np.ndarray:
    """Apply outlier treatment.

    winsorise: clip to [p1, p99] percentiles — preserves shape, reduces extremes.
    interpolate: replace with linear interpolation of neighbours.
    flag_only: return unchanged (outliers remain; caller uses mask externally).
    """
    out = values.copy()

    if treatment == "winsorise":
        lo = np.percentile(values[~outlier_mask], winsorise_pct * 100)
        hi = np.percentile(values[~outlier_mask], (1 - winsorise_pct) * 100)
        out = np.clip(out, lo, hi)
    elif treatment == "interpolate":
        idx = np.arange(len(values))
        good = ~outlier_mask
        if good.sum() >= 2:
            out[outlier_mask] = np.interp(idx[outlier_mask], idx[good], values[good])

    return out


def check_stationarity(
    values: np.ndarray,
    series_id: str = "unknown",
    max_d: int = 2,
) -> StationarityReport:
    """ADF + KPSS tests. Recommends a differencing order d.

    ADF null = unit root (non-stationary). Reject -> stationary.
    KPSS null = stationary. Reject -> non-stationary.
    Conflicting results signal trend-stationary vs. difference-stationary.
    """
    try:
        from statsmodels.tsa.stattools import adfuller, kpss

        # adfuller's stub can't statically disambiguate its overloads based on
        # our kwargs, so it reports a union of tuple sizes here — real return
        # is always a 6-tuple without regresults=True (which we never pass).
        adf_stat, adf_p, _, _, _, _ = adfuller(values, autolag="AIC")  # type: ignore[misc]
        adf_stationary = bool(adf_p < 0.05)

        try:
            kpss_result = kpss(values, regression="c", nlags="auto", store=False)
            kpss_stat, kpss_p = kpss_result[0], kpss_result[1]
            kpss_stationary = bool(kpss_p > 0.05)
        except Exception:
            kpss_stat, kpss_p, kpss_stationary = None, None, None

        d = 0
        working = values.copy()
        while d < max_d:
            _, p, *_ = adfuller(working, autolag="AIC")
            if p < 0.05:
                break
            working = np.diff(working)
            d += 1

        if adf_stationary and (kpss_stationary is None or kpss_stationary):
            conclusion = "Stationary — no differencing needed (d=0)"
        elif not adf_stationary and kpss_stationary is False:
            conclusion = f"Non-stationary — recommend d={d} (difference-stationary)"
        elif adf_stationary and kpss_stationary is False:
            conclusion = "Trend-stationary — consider detrending or d=1"
        else:
            conclusion = f"Uncertain — recommend d={d}, verify residuals post-fit"

        return StationarityReport(
            series_id=series_id,
            adf_statistic=float(adf_stat),
            adf_pvalue=float(adf_p),
            adf_stationary=adf_stationary,
            kpss_statistic=float(kpss_stat) if kpss_stat is not None else None,
            kpss_pvalue=float(kpss_p) if kpss_p is not None else None,
            kpss_stationary=kpss_stationary,
            recommended_d=d,
            conclusion=conclusion,
        )
    except ImportError:
        mid = len(values) // 2
        var_ratio = np.var(values[mid:]) / (np.var(values[:mid]) + 1e-8)
        stationary = bool(0.5 < var_ratio < 2.0)
        return StationarityReport(
            series_id=series_id,
            adf_statistic=float("nan"),
            adf_pvalue=float("nan"),
            adf_stationary=stationary,
            kpss_statistic=None,
            kpss_pvalue=None,
            kpss_stationary=None,
            recommended_d=0 if stationary else 1,
            conclusion="statsmodels unavailable — variance-ratio heuristic used",
        )


def difference_series(values: np.ndarray, d: int = 1) -> np.ndarray:
    """Apply d-th order differencing. Prepends a NaN to preserve intent (length
    shrinks by 1 per order, matching np.diff's semantics)."""
    out = values.astype(float).copy()
    for _ in range(d):
        out = np.diff(out)
    return out


def undifference_series(
    diff_values: np.ndarray, last_originals: np.ndarray, d: int = 1
) -> np.ndarray:
    """Invert differencing for forecast output.

    last_originals: the last d values from the training series (needed as
    starting points for cumulative sum reconstruction).
    """
    out = diff_values.copy()
    for i in range(d):
        out = np.concatenate([[last_originals[-(d - i)]], out]).cumsum()[1:]
    return out


@dataclass
class ScalerParams:
    method: str
    mean: float = 0.0
    std: float = 1.0
    min_val: float = 0.0
    max_val: float = 1.0
    log_transform: bool = False


def fit_scaler(
    values: np.ndarray,
    method: Literal["standard", "minmax", "log1p", "none"] = "log1p",
) -> ScalerParams:
    """Fit scaler parameters on training data.

    log1p is a good default for right-skewed, always-positive series (e.g.
    counts, cash flows). Standard scaling after log1p is a common combined path.
    """
    use_log = method == "log1p"
    work = np.log1p(np.clip(values, 0.0, None)) if use_log else values

    return ScalerParams(
        method=method,
        mean=float(np.mean(work)),
        std=float(np.std(work)) or 1.0,
        min_val=float(np.min(work)),
        max_val=float(np.max(work)),
        log_transform=use_log,
    )


def apply_scaler(values: np.ndarray, params: ScalerParams) -> np.ndarray:
    work = np.log1p(np.clip(values, 0.0, None)) if params.log_transform else values.copy()
    if params.method in ("log1p", "standard"):
        return (work - params.mean) / params.std
    elif params.method == "minmax":
        rng = params.max_val - params.min_val
        return (work - params.min_val) / (rng if rng > 1e-8 else 1.0)
    return work


def inverse_scaler(values: np.ndarray, params: ScalerParams) -> np.ndarray:
    work = values.copy()
    if params.method in ("log1p", "standard"):
        work = work * params.std + params.mean
    elif params.method == "minmax":
        rng = params.max_val - params.min_val
        work = work * (rng if rng > 1e-8 else 1.0) + params.min_val
    if params.log_transform:
        work = np.expm1(work)
    return np.clip(work, 0.0, None)
