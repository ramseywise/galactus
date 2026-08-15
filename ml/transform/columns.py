"""Column-type inference — deciding what each column *is* before deciding what
to do with it.

The plan a `ColumnPlan` carries is deliberately inspectable: `ml-transform`
recommends a treatment per column and an operator approves it, so the inference
result has to be readable, not just correct. Every column lands in exactly one
bucket, and `unused` is explicit rather than implied by absence — a column that
silently vanished between profiling and fitting is the kind of gap that only
surfaces as a train/serve schema mismatch much later.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
from pandas.api import types as ptypes

DEFAULT_HIGH_CARD_THRESHOLD = 50
"""Above this many distinct values, one-hot encoding stops being reasonable and
the column is routed to target encoding or rare-category collapsing instead."""


@dataclass(frozen=True)
class ColumnPlan:
    """What each column is, and what the transformer should therefore do with it."""

    numeric: tuple[str, ...] = ()
    categorical: tuple[str, ...] = ()
    high_cardinality: tuple[str, ...] = ()
    """Categorical, but too many levels to one-hot — encoded separately."""
    datetime: tuple[str, ...] = ()
    boolean: tuple[str, ...] = ()
    unused: tuple[str, ...] = ()
    """Constant columns, all-null columns, and free text — carried explicitly so
    a dropped column is a recorded decision rather than a silent omission."""
    target: str | None = None
    cardinality: dict[str, int] = field(default_factory=dict)
    missing_fraction: dict[str, float] = field(default_factory=dict)
    reasons: dict[str, str] = field(default_factory=dict)
    """Why each column landed where it did — what `ml-transform` shows the operator."""

    @property
    def features(self) -> tuple[str, ...]:
        """Every column the transformer will actually consume."""
        return (
            self.numeric
            + self.categorical
            + self.high_cardinality
            + self.datetime
            + self.boolean
        )

    def describe(self) -> pd.DataFrame:
        """One row per column: bucket, cardinality, missingness, and the reason."""
        rows = []
        buckets = {
            "numeric": self.numeric,
            "categorical": self.categorical,
            "high_cardinality": self.high_cardinality,
            "datetime": self.datetime,
            "boolean": self.boolean,
            "unused": self.unused,
        }
        for bucket, cols in buckets.items():
            for col in cols:
                rows.append(
                    {
                        "column": col,
                        "bucket": bucket,
                        "n_unique": self.cardinality.get(col),
                        "missing_fraction": self.missing_fraction.get(col),
                        "reason": self.reasons.get(col, ""),
                    }
                )
        return pd.DataFrame(rows)


def infer_column_types(
    df: pd.DataFrame,
    target: str | None = None,
    high_card_threshold: int = DEFAULT_HIGH_CARD_THRESHOLD,
) -> ColumnPlan:
    """Bucket every column of `df` by dtype and cardinality.

    The target column, when named, is excluded from every feature bucket — the
    single most direct form of target leakage is leaving the label in `X`.
    """
    if target is not None and target not in df.columns:
        raise KeyError(f"target {target!r} is not a column of the frame: {list(df.columns)}")

    numeric: list[str] = []
    categorical: list[str] = []
    high_cardinality: list[str] = []
    datetime_cols: list[str] = []
    boolean: list[str] = []
    unused: list[str] = []
    cardinality: dict[str, int] = {}
    missing_fraction: dict[str, float] = {}
    reasons: dict[str, str] = {}

    n_rows = len(df)

    for col in df.columns:
        if col == target:
            continue

        series = df[col]
        n_unique = int(series.nunique(dropna=True))
        cardinality[col] = n_unique
        missing_fraction[col] = float(series.isna().mean()) if n_rows else 0.0

        if missing_fraction[col] == 1.0:
            unused.append(col)
            reasons[col] = "all values missing"
            continue
        if n_unique <= 1:
            unused.append(col)
            reasons[col] = f"constant ({n_unique} distinct value)"
            continue

        if ptypes.is_bool_dtype(series):
            boolean.append(col)
            reasons[col] = "boolean dtype"
        elif ptypes.is_datetime64_any_dtype(series):
            datetime_cols.append(col)
            reasons[col] = "datetime dtype — decomposed into calendar parts"
        elif ptypes.is_numeric_dtype(series):
            numeric.append(col)
            reasons[col] = f"numeric dtype, {n_unique} distinct"
        elif n_unique > high_card_threshold:
            high_cardinality.append(col)
            reasons[col] = (
                f"{n_unique} distinct values exceeds the one-hot threshold "
                f"({high_card_threshold}) — target encoding or rare-collapse instead"
            )
        else:
            categorical.append(col)
            reasons[col] = f"object/category dtype, {n_unique} distinct"

    return ColumnPlan(
        numeric=tuple(numeric),
        categorical=tuple(categorical),
        high_cardinality=tuple(high_cardinality),
        datetime=tuple(datetime_cols),
        boolean=tuple(boolean),
        unused=tuple(unused),
        target=target,
        cardinality=cardinality,
        missing_fraction=missing_fraction,
        reasons=reasons,
    )
