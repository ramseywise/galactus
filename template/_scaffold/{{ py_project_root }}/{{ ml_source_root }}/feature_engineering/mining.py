"""Cross-sectional feature extractions — the entity-level vocabulary.

`features.py` is time-series oriented: lags, rolling windows, EWMs, calendar
parts on a single series. This module covers the other half of a tabular
problem — collapsing many transaction rows into one row per entity, which is the
shape a debtor-level or customer-level model actually consumes.

Every function here takes a frame and returns a new frame; none mutate their
input. The recurring hazard is temporal: an aggregate computed over an entity's
whole history includes rows that had not happened yet at scoring time, so
`add_rfm_features` takes an explicit `as_of` cutoff and drops everything after
it. That is a hard filter, not a caller's responsibility.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_AGGS: tuple[str, ...] = ("mean", "std", "count")


def add_group_aggregates(
    df: pd.DataFrame,
    group_col: str,
    value_cols: Sequence[str],
    aggs: Sequence[str] = DEFAULT_AGGS,
    *,
    prefix: str | None = None,
) -> pd.DataFrame:
    """Broadcast per-group statistics back onto every row.

    Produces `{group_col}_{value_col}_{agg}` columns — e.g. a row's amount
    alongside the mean amount for its debtor, which is what lets a model express
    "unusually large *for this entity*" rather than "large in absolute terms".

    Note the leakage shape here: these statistics are computed over whatever rows
    the frame contains. Compute them on the training slice, or on a window that
    closes before the prediction point — never on train and validation together.
    """
    missing = [col for col in [group_col, *value_cols] if col not in df.columns]
    if missing:
        raise KeyError(f"columns not in frame: {missing}")

    stem = prefix if prefix is not None else group_col
    out = df.copy()
    grouped = df.groupby(group_col)[list(value_cols)]

    for agg in aggs:
        try:
            aggregated = grouped.transform(agg)
        except (AttributeError, ValueError) as exc:
            raise ValueError(f"unsupported aggregation {agg!r}") from exc
        renamed = {col: f"{stem}_{col}_{agg}" for col in value_cols}
        out = out.join(aggregated.rename(columns=renamed))

    return out


def add_rfm_features(
    df: pd.DataFrame,
    entity_col: str,
    date_col: str,
    amount_col: str,
    as_of: str | pd.Timestamp,
) -> pd.DataFrame:
    """Recency / frequency / monetary, one row per entity, as of a cutoff.

    Returns columns `recency_days`, `frequency`, `monetary`, `monetary_mean`,
    and `tenure_days`, indexed by `entity_col`.

    **Rows dated after `as_of` are dropped before anything is computed.** An RFM
    table built over an entity's full history is the classic temporal leak: the
    "frequency" a model trains on already counts transactions from after the
    moment it is meant to be predicting, so the model looks excellent in
    backtest and useless in production. The cutoff is required for that reason —
    there is no default.
    """
    missing = [col for col in (entity_col, date_col, amount_col) if col not in df.columns]
    if missing:
        raise KeyError(f"columns not in frame: {missing}")

    cutoff = pd.Timestamp(as_of)
    dates = pd.to_datetime(df[date_col])

    historical = df.loc[dates <= cutoff].copy()
    n_dropped = len(df) - len(historical)
    if n_dropped:
        logger.info(
            "RFM: excluded %d of %d rows dated after the %s cutoff",
            n_dropped,
            len(df),
            cutoff.date(),
        )
    if historical.empty:
        raise ValueError(
            f"no rows on or before the as_of cutoff {cutoff.date()} — every "
            "transaction is in the future relative to it"
        )

    historical[date_col] = pd.to_datetime(historical[date_col])
    grouped = historical.groupby(entity_col)

    rfm = pd.DataFrame(
        {
            "recency_days": (cutoff - grouped[date_col].max()).dt.days,
            "frequency": grouped[date_col].count(),
            "monetary": grouped[amount_col].sum(),
            "monetary_mean": grouped[amount_col].mean(),
            "tenure_days": (cutoff - grouped[date_col].min()).dt.days,
        }
    )
    return rfm


def collapse_rare_categories(
    df: pd.DataFrame,
    cols: Sequence[str],
    min_freq: float = 0.01,
    *,
    other_label: str = "__other__",
) -> pd.DataFrame:
    """Fold categories below `min_freq` into a single `other_label` level.

    A level seen three times in a hundred thousand rows cannot support an
    estimate; kept as its own one-hot column it is noise the model can overfit,
    and at scoring time it mostly appears as an unseen value anyway. Collapsing
    trades an unusable distinction for a usable one.
    """
    missing = [col for col in cols if col not in df.columns]
    if missing:
        raise KeyError(f"columns not in frame: {missing}")
    if not 0.0 <= min_freq < 1.0:
        raise ValueError(f"min_freq must be in [0, 1), got {min_freq}")

    out = df.copy()
    for col in cols:
        frequencies = out[col].value_counts(normalize=True)
        rare = set(frequencies[frequencies < min_freq].index)
        if not rare:
            continue
        logger.info("collapsing %d rare levels in %r into %r", len(rare), col, other_label)
        out[col] = out[col].where(~out[col].isin(rare), other_label)

    return out


def add_ratio_features(
    df: pd.DataFrame,
    pairs: Sequence[tuple[str, str]],
    *,
    epsilon: float = 1e-9,
) -> pd.DataFrame:
    """Add `{numerator}_over_{denominator}` for each pair.

    Ratios express relationships a linear model cannot reach on its own — a
    balance-to-income ratio is predictive where neither column alone is.
    `epsilon` guards division by zero; the result is finite everywhere, since an
    inf column silently breaks most estimators downstream.
    """
    out = df.copy()
    for numerator, denominator in pairs:
        missing = [col for col in (numerator, denominator) if col not in df.columns]
        if missing:
            raise KeyError(f"columns not in frame: {missing}")
        out[f"{numerator}_over_{denominator}"] = out[numerator] / (
            out[denominator].replace(0, np.nan).fillna(epsilon)
        )
    return out


def add_interaction_features(
    df: pd.DataFrame,
    pairs: Sequence[tuple[str, str]],
) -> pd.DataFrame:
    """Add `{a}_x_{b}` products for each pair.

    Explicit interactions only — a full polynomial expansion over a wide frame
    produces more columns than rows, and every one of them is a chance to overfit.
    """
    out = df.copy()
    for left, right in pairs:
        missing = [col for col in (left, right) if col not in df.columns]
        if missing:
            raise KeyError(f"columns not in frame: {missing}")
        out[f"{left}_x_{right}"] = out[left] * out[right]
    return out


def add_binned_features(
    df: pd.DataFrame,
    cols: Sequence[str],
    n_bins: int = 5,
    strategy: Literal["quantile", "uniform"] = "quantile",
    *,
    suffix: str = "_bin",
) -> pd.DataFrame:
    """Discretise numeric columns into `{col}{suffix}` integer bins.

    Quantile binning gives equally-populated bins, which is the safer default on
    a skewed column — uniform width on a long tail puts almost every row in the
    first bin. Bins are returned as integer codes; NaN inputs become -1 rather
    than propagating.
    """
    missing = [col for col in cols if col not in df.columns]
    if missing:
        raise KeyError(f"columns not in frame: {missing}")
    if n_bins < 2:
        raise ValueError(f"n_bins must be at least 2, got {n_bins}")

    out = df.copy()
    for col in cols:
        if strategy == "quantile":
            binned = pd.qcut(out[col], q=n_bins, labels=False, duplicates="drop")
        elif strategy == "uniform":
            binned = pd.cut(out[col], bins=n_bins, labels=False)
        else:
            raise ValueError(f"unknown strategy {strategy!r}; valid: quantile, uniform")
        out[f"{col}{suffix}"] = pd.Series(binned, index=out.index).fillna(-1).astype(int)

    return out
