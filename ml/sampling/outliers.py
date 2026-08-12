"""Outlier detection — IQR, z-score, and IsolationForest.

Detection is separated from removal on purpose. `detect_outliers` returns a
boolean mask so the caller can inspect what would be dropped before dropping it;
on a debtor-level problem the extreme rows are frequently the cases the model
exists to find, and silently discarding them optimises the metric while
destroying the use case.

The same fold discipline as `resample` applies: thresholds are learned on
training rows. A z-score computed over train and validation together lets the
validation distribution influence which training rows survive.
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np
import pandas as pd

from ml.sampling.resample import _reject_validation

logger = logging.getLogger(__name__)

RANDOM_STATE = 42

Method = Literal["iqr", "zscore", "isolation_forest"]


def detect_outliers(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    method: Method = "iqr",
    *,
    threshold: float = 1.5,
    contamination: float = 0.05,
    random_state: int = RANDOM_STATE,
) -> pd.Series:
    """Return a boolean Series: True where the row is an outlier.

    `threshold` is the IQR multiplier (1.5 is the conventional fence) for
    `method="iqr"`, and the absolute z-score cutoff for `method="zscore"` — pass
    3.0 there rather than the IQR default. `contamination` is the expected
    outlier fraction for IsolationForest.

    IQR and z-score flag a row when *any* considered column is extreme;
    IsolationForest judges the row jointly, which catches combinations that are
    unremarkable one column at a time.
    """
    _reject_validation(df)

    numeric = df[columns] if columns else df.select_dtypes(include=[np.number])
    if numeric.empty:
        raise ValueError("no numeric columns to check for outliers")

    if method == "iqr":
        q1 = numeric.quantile(0.25)
        q3 = numeric.quantile(0.75)
        iqr = q3 - q1
        low = q1 - threshold * iqr
        high = q3 + threshold * iqr
        mask = ((numeric < low) | (numeric > high)).any(axis=1)
    elif method == "zscore":
        std = numeric.std(ddof=0).replace(0.0, np.nan)
        scores = (numeric - numeric.mean()).abs() / std
        mask = (scores > threshold).any(axis=1)
    elif method == "isolation_forest":
        from sklearn.ensemble import IsolationForest

        forest = IsolationForest(contamination=contamination, random_state=random_state)
        predictions = forest.fit_predict(numeric.fillna(numeric.median()))
        mask = pd.Series(predictions == -1, index=df.index)
    else:
        raise ValueError(
            f"unknown method {method!r}; valid: iqr, zscore, isolation_forest"
        )

    return mask.fillna(False).astype(bool)


def remove_outliers(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    method: Method = "iqr",
    *,
    max_removed_fraction: float = 0.1,
    **kwargs,
) -> tuple[pd.DataFrame, pd.Series]:
    """Drop detected outliers. Returns `(cleaned_frame, mask_of_removed_rows)`.

    Refuses to remove more than `max_removed_fraction` of the frame. A method
    that wants to drop a third of the data has not found outliers, it has found
    that the distribution is not what the method assumes — and dropping that much
    silently is how a model ends up trained on a population that no longer
    resembles the one it scores.
    """
    mask = detect_outliers(df, columns, method, **kwargs)
    fraction = float(mask.mean())

    if fraction > max_removed_fraction:
        raise ValueError(
            f"{method} flagged {fraction:.1%} of rows as outliers, above the "
            f"{max_removed_fraction:.1%} ceiling. Either the threshold is too "
            "tight or the distribution is genuinely heavy-tailed — inspect the "
            "mask from detect_outliers() before removing anything."
        )

    if fraction:
        logger.info("removing %d outlier rows (%.1f%%) via %s", mask.sum(), fraction * 100, method)
    return df.loc[~mask], mask
