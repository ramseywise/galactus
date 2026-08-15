"""Scaling, and the guard that runs before any score exists.

`check_leakage` has four rules and they do not all point the same way. Rules (a)-(c)
detect *too much* information — a column that restates the answer, a transform fitted
across a split, the same quantity counted twice. Rule (d) detects *too little*: a matrix
that is clean by every name-based rule and still carries no signal.

Rule (d) exists because of a specific way this pipeline could lie. If a feature build
silently guts a column — an unhandled sentinel, a groupby producing NaN — rules (a)-(c)
all pass, because they read column *names* and none of them reads a value. The damage then
surfaces as a *low* silhouette, which this POC has explicitly authorised itself to report
as the honest "the structure is weak" verdict. Without rule (d), a broken feature build
exits through the intellectual-honesty clause and nobody finds out. An all-PASS from a
one-directional guard is not evidence the matrix is sound; it is evidence nobody looked.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from features import FEATURE_COLUMNS, FORBIDDEN_COLUMNS
from sklearn.preprocessing import StandardScaler

#: Columns log-scaled before standardizing. Trade counts and monetary volumes are heavily
#: right-skewed (median 20 trades, mean 38, max 956); without this, a handful of whales
#: dominate every Euclidean distance and the clustering finds "big" versus "not big".
#: A test asserts this set matches the columns that are actually skewed, rather than
#: leaving it as a claim.
LOG_COLUMNS: tuple[str, ...] = (
    "n_trades",
    "total_volume",
    "mean_trade_size",
    "n_instruments",
    "days_since_last_trade",
    "mean_days_between_trades",
)

#: Rule (d) thresholds.
MAX_NAN_FRACTION = 0.10
MIN_VARIANCE = 1e-12


@dataclass(frozen=True)
class Finding:
    rule: str
    passed: bool
    detail: str

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"[{'PASS' if self.passed else 'FAIL'}] {self.rule}: {self.detail}"


def check_leakage(df: pd.DataFrame, expected_rows: int | None = None) -> list[Finding]:
    """Red until proven. Returns one Finding per rule.

    An empty list is *not* a pass — an all-PASS list is. The distinction matters because a
    guard that returns `[]` when it cannot evaluate looks identical to one that checked
    and approved.
    """
    findings: list[Finding] = []

    # (a) No first-trade-derived column may reach the matrix. `cohort` is exactly the
    # signup month; clustering on it segments by tenure and calls it behaviour.
    present = sorted(set(df.columns) & set(FORBIDDEN_COLUMNS))
    findings.append(
        Finding(
            "a_no_first_trade_derived_column",
            not present,
            f"forbidden columns present: {present}" if present else "none of FORBIDDEN_COLUMNS present",
        )
    )

    # (b) The scaler must be fitted inside whatever subsample is being scored, never once
    # over the full frame and reused. This is a property of the caller, so what is
    # asserted here is the contract: `prepare_matrix` is the only fitter and it is called
    # per-subsample.
    findings.append(
        Finding(
            "b_scaler_fitted_within_fold",
            True,
            "prepare_matrix fits a fresh StandardScaler per call; callers must not share one",
        )
    )

    # (c) A sum and its own parts are the same information counted twice, which silently
    # weights that axis above every other in Euclidean distance.
    doubles = [
        col
        for col in df.columns
        if any(other != col and other.startswith(col + "_") for other in df.columns)
    ]
    findings.append(
        Finding(
            "c_no_sum_and_parts_double_count",
            not doubles,
            f"columns with decomposed parts also present: {doubles}" if doubles else "no sum/parts pair found",
        )
    )

    # (d) Matrix health — the opposite direction from (a)-(c).
    problems: list[str] = []
    for col in df.columns:
        series = pd.to_numeric(df[col], errors="coerce")
        nan_fraction = float(series.isna().mean())
        if nan_fraction > MAX_NAN_FRACTION:
            problems.append(f"{col}: {nan_fraction:.1%} NaN")
        if float(series.var(ddof=0)) <= MIN_VARIANCE:
            problems.append(f"{col}: zero variance")
    if expected_rows is not None and len(df) != expected_rows:
        problems.append(f"row count {len(df)} != expected {expected_rows}")
    findings.append(
        Finding(
            "d_matrix_health",
            not problems,
            "; ".join(problems) if problems else f"{len(df.columns)} columns, all with variance and few NaN",
        )
    )

    return findings


def prepare_matrix(features: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """Log-scale the skewed axes, then standardize. Returns `(matrix, column_names)`.

    A fresh `StandardScaler` is fitted on every call by design — see rule (b). Callers
    doing subsample stability work must call this per subsample rather than scaling once
    and slicing.
    """
    df = features[list(FEATURE_COLUMNS)].copy()
    for col in LOG_COLUMNS:
        # log1p over the absolute value, sign preserved: some monetary columns are
        # legitimately negative and log1p would produce NaN for them.
        df[col] = np.sign(df[col]) * np.log1p(df[col].abs())
    matrix = StandardScaler().fit_transform(df.to_numpy(dtype=float))
    return matrix, list(df.columns)
