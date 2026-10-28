"""Binary and multiclass classification, end to end.

One call takes a frame and a target name and returns a scored comparison across
every available model. The steps in between — infer column types, choose a
leakage-safe splitter, build a transformer, wrap everything in a Pipeline,
cross-validate, calibrate, pick a threshold — are the steps a person does by
hand every time and gets subtly wrong roughly one time in five.

The ordering is the load-bearing part:

1. Column types are inferred from the **training frame only** conceptually, but
   in practice from the whole frame's *dtypes and cardinality* — which is
   metadata, not signal. Nothing here is fitted outside the fold.
2. The splitter is chosen before anything is fitted, so no transform can precede
   the split.
3. Every transform lives inside the Pipeline, so `cross_val_predict` refits it
   per fold.

Out-of-fold predictions come from `cross_val_predict`, not from a single
train/test split. Every row gets a prediction from a model that never saw it,
which gives metrics computed over the whole frame instead of over one arbitrary
30% slice.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import pandas as pd
from sklearn.base import clone
from sklearn.model_selection import cross_val_predict

from ml.evaluation.calibration import assess_calibration, calibrate_classifier, recommend_method
from ml.evaluation.metrics import classification_metrics, pr_curve, roc_curve_points
from ml.evaluation.splitting import RANDOM_STATE, SplitPlan, make_splitter, split_columns
from ml.evaluation.threshold import choose_threshold_out_of_fold
from ml.sampling.resample import build_sampler
from ml.selection.registry import get_models, get_spec
from ml.transform.columns import infer_column_types
from ml.transform.encoders import build_transformer
from ml.workflows.base import ModelResult, RunResult, _score, build_pipeline

logger = logging.getLogger(__name__)

IMBALANCE_THRESHOLD = 0.35
"""Minority-class fraction below which a run is treated as imbalanced — PR-AUC
leads the report and class weighting is worth applying."""


def run_classification(
    df: pd.DataFrame,
    *,
    target: str,
    output: str = "binary",
    models: list[str] | None = None,
    sampling: str = "class_weight",
    splitter: SplitPlan | None = None,
    group_col: str | None = None,
    time_col: str | None = None,
    n_splits: int = 5,
    calibrate: bool = True,
    cost_fp: float | None = None,
    cost_fn: float | None = None,
    seed: int = RANDOM_STATE,
) -> RunResult:
    """Fit and compare every available classifier on `df`.

    `models=None` runs everything registered for this family/output pair whose
    optional dependency is installed; the baseline is always included so the
    comparison has a floor. Models are returned ordered best-first by PR-AUC
    under imbalance, ROC-AUC otherwise.

    `cost_fp`/`cost_fn` are optional: supplying both adds a cost-optimal
    threshold to each binary result. Without them the models are scored but no
    operating point is recommended, which is the honest default — a threshold
    without a cost matrix is a guess wearing a number.
    """
    if target not in df.columns:
        raise KeyError(f"target {target!r} is not a column in the frame: {list(df.columns)}")

    # The group and time columns are split metadata: they steer the folds and
    # must not reach the feature matrix. A group column is entity identity —
    # near-unique, so it would land in `high_cardinality` and be target-encoded,
    # which is the label leaking back in through the grouping contract.
    split_cols = [c for c in split_columns(splitter, group_col, time_col) if c in df.columns]
    plan = infer_column_types(df, target=target, exclude=split_cols)
    features = list(plan.features)
    if not features:
        raise ValueError(
            f"no usable feature columns were inferred from {len(df.columns)} columns. "
            "Every column was classified as unused — check dtypes and cardinality."
        )

    x = df[features]
    y = df[target]

    classes = sorted(y.dropna().unique().tolist())
    if len(classes) < 2:
        raise ValueError(
            f"target {target!r} has {len(classes)} distinct value(s); classification "
            "needs at least 2."
        )
    is_binary = len(classes) == 2
    if output == "binary" and not is_binary:
        raise ValueError(
            f"output='binary' was requested but target {target!r} has {len(classes)} "
            "classes. Pass output='multiclass'."
        )

    counts = y.value_counts()
    balance = {str(k): int(v) for k, v in counts.items()}
    minority_fraction = float(counts.min() / counts.sum())
    imbalanced = minority_fraction < IMBALANCE_THRESHOLD
    positive_label = classes[-1] if is_binary else None

    split_plan = splitter or make_splitter(
        n_splits=n_splits,
        group_col=group_col,
        time_col=time_col,
        # A temporal split cannot also be stratified; make_splitter raises on the
        # contradiction, so the flag has to follow the declared structure.
        stratify=time_col is None,
        random_state=seed,
    )

    transformer = build_transformer(plan)
    specs = get_models(family="classification", output=output, include=models)

    results: list[ModelResult] = []
    skipped: dict[str, str] = {}

    for name, estimator in specs.items():
        try:
            result = _fit_one(
                name=name,
                estimator=estimator,
                transformer=transformer,
                x=x,
                y=y,
                frame=df,
                split_plan=split_plan,
                sampling=sampling,
                plan=plan,
                classes=classes,
                is_binary=is_binary,
                imbalanced=imbalanced,
                positive_label=positive_label,
                calibrate=calibrate,
                cost_fp=cost_fp,
                cost_fn=cost_fn,
                seed=seed,
            )
        except Exception as exc:
            logger.warning("model %s failed and was skipped: %s", name, exc)
            skipped[name] = f"{type(exc).__name__}: {exc}"
            continue
        results.append(result)

    results.sort(key=_score, reverse=True)

    return RunResult(
        family="classification",
        output=output,
        target=target,
        models=results,
        column_plan=plan,
        split_plan=split_plan,
        n_rows=len(df),
        n_features=len(features),
        seed=seed,
        sampling=sampling,
        class_balance=balance,
        skipped=skipped,
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
    sampling: str,
    plan: Any,
    classes: list[Any],
    is_binary: bool,
    imbalanced: bool,
    positive_label: Any,
    calibrate: bool,
    cost_fp: float | None,
    cost_fn: float | None,
    seed: int,
) -> ModelResult:
    """Cross-validate one model and assemble its `ModelResult`."""
    spec = get_spec(name)
    started = time.perf_counter()

    sampler = _make_sampler(sampling, plan=plan, x=x, seed=seed)
    # clone() so the registry's instance is never fitted — a shared fitted
    # estimator across calls would make the second run's "fresh" model stale.
    pipeline = build_pipeline(clone(transformer), clone(estimator), sampler=sampler)

    # `frame=` so the splitter reads its group/time columns from the source frame;
    # `x` no longer carries them. The yielded indices are positional and the two
    # frames share row order, so they stay valid against `x`.
    cv = list(split_plan.split(x, y, frame=frame))
    y_pred = cross_val_predict(pipeline, x, y, cv=cv, method="predict")

    y_prob = None
    if hasattr(estimator, "predict_proba"):
        probabilities = cross_val_predict(pipeline, x, y, cv=cv, method="predict_proba")
        y_prob = probabilities[:, -1] if is_binary else probabilities

    metrics = classification_metrics(
        y,
        y_pred,
        y_prob,
        labels=classes,
        positive_label=positive_label if is_binary else 1,
    )

    curves: dict[str, Any] = {}
    calibration = None
    threshold = None

    if is_binary and y_prob is not None:
        curves["pr"] = pr_curve(y, y_prob, positive_label=positive_label)
        curves["roc"] = roc_curve_points(y, y_prob, positive_label=positive_label)

        if calibrate:
            calibration = _calibrate(
                pipeline=pipeline,
                x=x,
                y=y,
                cv=cv,
                raw_prob=y_prob,
                positive_label=positive_label,
            )

        if cost_fp is not None and cost_fn is not None:
            # `y_prob` is out-of-fold, and the threshold selection is too: each
            # fold's operating point is chosen on the other folds' rows and
            # scored on its own, so precision/recall/expected_cost describe
            # rows the sweep never saw. The returned threshold itself is the
            # deployable full-data choice; `fold_thresholds` shows its
            # stability across folds.
            threshold = choose_threshold_out_of_fold(
                y,
                y_prob,
                cv,
                cost_fp=cost_fp,
                cost_fn=cost_fn,
                positive_label=positive_label,
            )

    # Fit on the full frame last: the metrics above are out-of-fold, and the
    # returned estimator is the one to persist and serve.
    pipeline.fit(x, y)

    return ModelResult(
        name=name,
        estimator=pipeline,
        metrics=metrics,
        is_baseline=spec.is_baseline,
        curves=curves,
        calibration=calibration,
        threshold=threshold,
        fit_seconds=time.perf_counter() - started,
        notes=spec.notes,
    )


def _make_sampler(sampling: str, *, plan: Any, x: pd.DataFrame, seed: int) -> Any:
    """Build the fold-level sampler, or `None` for the weight-only strategies.

    `class_weight` and `none` need no pipeline step — the first is handled by the
    estimator's own weighting and the second is a no-op — so returning `None`
    keeps the pipeline one step shorter rather than inserting a passthrough.
    """
    if sampling in ("none", "class_weight"):
        return None

    categorical = set(plan.categorical) | set(plan.high_cardinality)
    indices = [i for i, col in enumerate(x.columns) if col in categorical]
    return build_sampler(
        sampling,
        categorical_indices=indices or None,
        random_state=seed,
    )


def _calibrate(*, pipeline: Any, x: pd.DataFrame, y: pd.Series, cv: list, raw_prob, positive_label):
    """Cross-validate a calibrated copy and report the before/after."""
    method = recommend_method(len(y))
    try:
        calibrated = calibrate_classifier(clone(pipeline), method=method, cv=3)
        adjusted = cross_val_predict(calibrated, x, y, cv=cv, method="predict_proba")[:, -1]
    except Exception as exc:
        logger.warning("calibration failed, reporting uncalibrated probabilities: %s", exc)
        return None

    return assess_calibration(y, raw_prob, adjusted, method=method, positive_label=positive_label)
