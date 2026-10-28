"""Continuous-target prediction.

Structurally the same as classification minus the probability machinery: no
calibration (there is nothing to calibrate), no threshold (there is no decision
boundary), no sampling (there are no classes to balance). What remains is the
part that matters — every transform inside the Pipeline, out-of-fold predictions
from `cross_val_predict`, and R² reported next to RMSE rather than instead of it.

R² alone is misleading in the direction people rarely check: it is scale-free, so
a model with an R² of 0.85 can still be off by an amount that makes the
prediction useless for the decision it feeds. RMSE is in the target's units,
which is the number to hand a stakeholder.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import pandas as pd
from sklearn.base import clone
from sklearn.model_selection import KFold, cross_val_predict

from ml.evaluation.metrics import regression_metrics
from ml.evaluation.splitting import RANDOM_STATE, SplitPlan, make_splitter, split_columns
from ml.selection.registry import get_models, get_spec
from ml.transform.columns import infer_column_types
from ml.transform.encoders import build_transformer
from ml.workflows.base import ModelResult, RunResult, _score, build_pipeline

logger = logging.getLogger(__name__)


def run_prediction(
    df: pd.DataFrame,
    target: str,
    *,
    models: list[str] | None = None,
    splitter: SplitPlan | None = None,
    group_col: str | None = None,
    time_col: str | None = None,
    n_splits: int = 5,
    seed: int = RANDOM_STATE,
) -> RunResult:
    """Fit and compare every available regressor on `df`. Ranked by R²."""
    if target not in df.columns:
        raise KeyError(f"target {target!r} is not a column in the frame: {list(df.columns)}")

    # Group and time columns steer the folds; they are not features. See
    # `infer_column_types(exclude=...)` for why letting them through leaks.
    split_cols = [c for c in split_columns(splitter, group_col, time_col) if c in df.columns]
    plan = infer_column_types(df, target=target, exclude=split_cols)
    features = list(plan.features)
    if not features:
        raise ValueError(f"no usable feature columns were inferred from {len(df.columns)} columns.")

    x = df[features]
    y = df[target]
    if not pd.api.types.is_numeric_dtype(y):
        raise TypeError(
            f"target {target!r} has dtype {y.dtype}, which is not numeric. Use "
            "run_classification for a categorical target."
        )

    split_plan = splitter or _default_splitter(
        group_col=group_col, time_col=time_col, n_splits=n_splits, seed=seed
    )

    transformer = build_transformer(plan)
    specs = get_models(family="prediction", output="continuous", include=models)

    results: list[ModelResult] = []
    skipped: dict[str, str] = {}

    for name, estimator in specs.items():
        try:
            results.append(
                _fit_one(
                    name=name,
                    estimator=estimator,
                    transformer=transformer,
                    x=x,
                    y=y,
                    frame=df,
                    split_plan=split_plan,
                )
            )
        except Exception as exc:
            logger.warning("model %s failed and was skipped: %s", name, exc)
            skipped[name] = f"{type(exc).__name__}: {exc}"

    results.sort(key=_score, reverse=True)

    return RunResult(
        family="prediction",
        output="continuous",
        target=target,
        models=results,
        column_plan=plan,
        split_plan=split_plan,
        n_rows=len(df),
        n_features=len(features),
        seed=seed,
        skipped=skipped,
    )


def _default_splitter(
    *, group_col: str | None, time_col: str | None, n_splits: int, seed: int
) -> SplitPlan:
    """Choose a splitter for a continuous target.

    `make_splitter` handles the declared-structure cases, but its unstructured
    fallback is `StratifiedKFold`, which is undefined for a continuous target —
    it would try to balance folds by distinct float value. Plain k-fold is the
    honest answer when no structure was declared.
    """
    if group_col is not None or time_col is not None:
        return make_splitter(
            n_splits=n_splits,
            group_col=group_col,
            time_col=time_col,
            stratify=False,
            random_state=seed,
        )

    return SplitPlan(
        splitter=KFold(n_splits=n_splits, shuffle=True, random_state=seed),
        kind="kfold",
        reason=(
            "continuous target with no group or time structure declared — plain "
            "k-fold; stratification is undefined for a continuous target."
        ),
        n_splits=n_splits,
    )


def _fit_one(
    *,
    name: str,
    estimator: Any,
    transformer: Any,
    x: pd.DataFrame,
    y: pd.Series,
    frame: pd.DataFrame,
    split_plan: SplitPlan,
) -> ModelResult:
    spec = get_spec(name)
    started = time.perf_counter()

    pipeline = build_pipeline(clone(transformer), clone(estimator))
    # `frame=` so the group/time columns resolve off the source frame rather than
    # having to be features. Indices are positional; the row order is shared.
    cv = list(split_plan.split(x, y, frame=frame))
    y_pred = cross_val_predict(pipeline, x, y, cv=cv, method="predict")

    metrics = regression_metrics(y, y_pred)
    pipeline.fit(x, y)

    return ModelResult(
        name=name,
        estimator=pipeline,
        metrics=metrics,
        is_baseline=spec.is_baseline,
        fit_seconds=time.perf_counter() - started,
        notes=spec.notes,
    )
