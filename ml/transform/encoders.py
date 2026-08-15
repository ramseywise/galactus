"""Encoders and the `ColumnTransformer` builder.

Everything here is an sklearn transformer, which is the point: the whole
preprocessing stack goes *inside* the `Pipeline` so that cross-validation refits
it per fold. Preprocessing fitted once, outside the split, is the most common
way a tabular model reports a score it cannot reproduce in production.

`TargetEncoder` is the sharp edge. Target encoding replaces a category with a
statistic *of the label*, so fitting it on rows that later appear in validation
leaks the answer directly. This implementation is safe by construction in a
Pipeline — `fit` sees only the fold's training rows — and `test_transform.py`
asserts that property rather than trusting it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (
    FunctionTransformer,
    MinMaxScaler,
    OneHotEncoder,
    OrdinalEncoder,
    RobustScaler,
    StandardScaler,
)

from ml.transform.columns import ColumnPlan

_SCALERS = {
    "standard": StandardScaler,
    "minmax": MinMaxScaler,
    "robust": RobustScaler,
    "none": None,
}


class TargetEncoder(BaseEstimator, TransformerMixin):
    """Replace each category with a smoothed mean of the target for that category.

    Smoothing shrinks rare categories toward the global mean, so a category seen
    twice does not get the same confidence as one seen ten thousand times:

        encoded = (count * category_mean + smoothing * global_mean)
                  / (count + smoothing)

    Unseen categories at transform time fall back to the global mean rather than
    raising — an unknown level in production is normal, not exceptional.

    Fold safety: this class holds no reference to any data beyond the mapping
    learned in `fit`. Placed inside a `Pipeline`, sklearn refits it per fold, so
    the statistics never see the rows they are scoring.
    """

    def __init__(self, smoothing: float = 10.0):
        self.smoothing = smoothing

    def fit(self, x: pd.DataFrame | np.ndarray, y=None):
        if y is None:
            raise ValueError(
                "TargetEncoder needs the target to fit. It is a supervised "
                "encoder — use OrdinalEncoder or one-hot if no target is available."
            )
        x = self._as_frame(x)
        y = pd.Series(np.asarray(y)).reset_index(drop=True)

        self.global_mean_ = float(y.mean())
        self.mappings_: dict[str, dict] = {}
        self.feature_names_in_ = list(x.columns)

        for col in x.columns:
            values = x[col].reset_index(drop=True).astype("object")
            grouped = y.groupby(values)
            counts = grouped.count()
            means = grouped.mean()
            smoothed = (counts * means + self.smoothing * self.global_mean_) / (
                counts + self.smoothing
            )
            self.mappings_[col] = smoothed.to_dict()

        return self

    def transform(self, x: pd.DataFrame | np.ndarray) -> np.ndarray:
        x = self._as_frame(x)
        out = np.empty((len(x), len(self.feature_names_in_)), dtype=np.float64)
        for i, col in enumerate(self.feature_names_in_):
            mapping = self.mappings_[col]
            column = x[col].astype("object")
            out[:, i] = column.map(mapping).fillna(self.global_mean_).to_numpy(dtype=np.float64)
        return out

    def get_feature_names_out(self, input_features=None) -> np.ndarray:
        names = input_features if input_features is not None else self.feature_names_in_
        return np.asarray([f"{name}_target_enc" for name in names], dtype=object)

    @staticmethod
    def _as_frame(x) -> pd.DataFrame:
        if isinstance(x, pd.DataFrame):
            return x
        return pd.DataFrame(np.asarray(x))


class DatetimeFeatures(BaseEstimator, TransformerMixin):
    """Decompose datetime columns into calendar parts a tree model can split on.

    Emits year, month, day, day-of-week, day-of-year, quarter, and an
    is-weekend flag per input column. The raw timestamp itself is dropped — an
    epoch integer invites the model to memorise a cutoff rather than learn
    seasonality.
    """

    _PARTS = ("year", "month", "day", "dayofweek", "dayofyear", "quarter", "is_weekend")

    def fit(self, x: pd.DataFrame | np.ndarray, y=None):
        self.feature_names_in_ = list(TargetEncoder._as_frame(x).columns)
        return self

    def transform(self, x: pd.DataFrame | np.ndarray) -> np.ndarray:
        frame = TargetEncoder._as_frame(x)
        columns: list[np.ndarray] = []
        for col in self.feature_names_in_:
            series = pd.to_datetime(frame[col], errors="coerce")
            dt = series.dt
            columns.extend(
                [
                    dt.year.to_numpy(dtype=np.float64),
                    dt.month.to_numpy(dtype=np.float64),
                    dt.day.to_numpy(dtype=np.float64),
                    dt.dayofweek.to_numpy(dtype=np.float64),
                    dt.dayofyear.to_numpy(dtype=np.float64),
                    dt.quarter.to_numpy(dtype=np.float64),
                    (dt.dayofweek >= 5).to_numpy(dtype=np.float64),
                ]
            )
        stacked = np.column_stack(columns) if columns else np.empty((len(frame), 0))
        return np.nan_to_num(stacked, nan=-1.0)

    def get_feature_names_out(self, input_features=None) -> np.ndarray:
        names = input_features if input_features is not None else self.feature_names_in_
        return np.asarray(
            [f"{name}_{part}" for name in names for part in self._PARTS], dtype=object
        )


def _bools_to_float(x):
    """Cast a boolean block to float, preserving NaN.

    Module-level rather than a lambda so the fitted transformer stays picklable —
    a model that cannot be serialised cannot be deployed.
    """
    frame = TargetEncoder._as_frame(x)
    return frame.astype("float64").to_numpy()


def _numeric_pipeline(strategy: str, add_missing_indicators: bool) -> Pipeline:
    if strategy not in _SCALERS:
        raise ValueError(f"unknown numeric strategy {strategy!r}; valid: {sorted(_SCALERS)}")

    steps: list[tuple[str, object]] = [
        # add_indicator preserves not-missing-at-random signal: "this field was
        # blank" is frequently predictive in its own right, and imputing it away
        # destroys that before the model ever sees it.
        ("impute", SimpleImputer(strategy="median", add_indicator=add_missing_indicators)),
    ]
    scaler_cls = _SCALERS[strategy]
    if scaler_cls is not None:
        steps.append(("scale", scaler_cls()))
    return Pipeline(steps)


def _categorical_pipeline(strategy: str) -> Pipeline:
    steps: list[tuple[str, object]] = [
        ("impute", SimpleImputer(strategy="constant", fill_value="__missing__")),
    ]
    if strategy == "onehot":
        steps.append(("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False)))
    elif strategy == "ordinal":
        steps.append(
            (
                "encode",
                OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
            )
        )
    elif strategy == "target":
        steps.append(("encode", TargetEncoder()))
    else:
        raise ValueError(
            f"unknown categorical strategy {strategy!r}; valid: onehot, ordinal, target"
        )
    return Pipeline(steps)


def build_transformer(
    plan: ColumnPlan,
    *,
    numeric: str = "standard",
    categorical: str = "onehot",
    high_cardinality: str = "target",
    add_missing_indicators: bool = True,
) -> ColumnTransformer:
    """Assemble a `ColumnTransformer` from a `ColumnPlan`.

    High-cardinality columns get their own strategy (target encoding by default)
    so that a 200-level column does not silently explode into 200 one-hot
    columns. The result is meant to be the first step of a `Pipeline` — never
    fitted standalone on the full frame, which is precisely the leak the split
    exists to prevent.
    """
    transformers: list[tuple[str, object, list[str]]] = []

    if plan.numeric:
        transformers.append(
            ("numeric", _numeric_pipeline(numeric, add_missing_indicators), list(plan.numeric))
        )
    if plan.boolean:
        # SimpleImputer rejects bool dtype outright, so cast to float before it
        # runs. A nullable-boolean column arrives as object and imputes fine, but
        # a plain numpy bool column would raise.
        transformers.append(
            (
                "boolean",
                Pipeline(
                    [
                        (
                            "to_float",
                            FunctionTransformer(
                                _bools_to_float, feature_names_out="one-to-one"
                            ),
                        ),
                        ("impute", SimpleImputer(strategy="most_frequent")),
                    ]
                ),
                list(plan.boolean),
            )
        )
    if plan.categorical:
        transformers.append(
            ("categorical", _categorical_pipeline(categorical), list(plan.categorical))
        )
    if plan.high_cardinality:
        transformers.append(
            (
                "high_cardinality",
                _categorical_pipeline(high_cardinality),
                list(plan.high_cardinality),
            )
        )
    if plan.datetime:
        transformers.append(("datetime", DatetimeFeatures(), list(plan.datetime)))

    if not transformers:
        raise ValueError(
            "ColumnPlan has no usable feature columns — every column was bucketed "
            f"as unused: {plan.unused}"
        )

    # remainder='drop' is deliberate: `plan.unused` columns are excluded by an
    # explicit decision recorded in the plan, not by accident.
    return ColumnTransformer(transformers=transformers, remainder="drop")
