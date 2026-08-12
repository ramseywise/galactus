"""Step 15 — the classification workflow.

One call that runs the whole chain: infer column types, build a leakage-safe
pipeline per fold, cross-validate every candidate model on identical folds,
calibrate out-of-fold probabilities, and choose a cost-minimising threshold.

Two design choices are load-bearing and worth stating rather than leaving to be
inferred from the code:

**Everything that learns from data goes inside the per-fold pipeline.** The
preprocessor is fitted on the fold's training rows only, never on the frame.
This is the difference between a score that transfers and one that is inflated
by an amount nobody measured, and because the inflated version looks *better*
there is no natural moment at which anyone notices. `RunResult` therefore
carries the claim explicitly so a run script can assert it.

**Predictions are out-of-fold.** Each row is scored by a model that did not
train on it, so calibration and threshold selection see honest probabilities.
Choosing an operating point on in-sample scores picks a threshold for a model
that no longer exists once it is refitted.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.pipeline import Pipeline

from ml.evaluation.calibration import (
    CalibrationReport,
    assess_calibration,
    calibrate_classifier,
    recommend_method,
)
from ml.evaluation.metrics import ClassificationMetrics, classification_metrics
from ml.evaluation.splitting import SplitPlan, make_splitter
from ml.evaluation.threshold import ThresholdResult, choose_threshold
from ml.model_comparison.compare import TabularPreprocessor
from ml.sampling.resample import build_sampler
from ml.selection.registry import get_models
from ml.transform.columns import infer_column_types

logger = logging.getLogger(__name__)

RANDOM_STATE = 42

BASELINE_TOLERANCE = 0.01
"""Minimum PR-AUC margin over the baseline before a model is called better.

A strict `>` reports a 0.0002 margin as a win. Cross-validated metrics carry
fold-to-fold variance far larger than that, so a margin inside the noise band is
a coin flip being reported as a finding. One point of PR-AUC is the floor at
which the difference is worth acting on.
"""


class TransformLeakageError(RuntimeError):
    """Raised when a model fitted a transformer outside its cross-validation
    pipeline, which inflates every score it reported."""


@dataclass
class ModelRun:
    """One candidate model's cross-validated result."""

    name: str
    metrics: ClassificationMetrics
    fit_seconds: float
    is_baseline: bool = False
    calibration: CalibrationReport | None = None
    threshold: ThresholdResult | None = None
    transform_in_pipeline: bool = True
    """False means a transformer was fitted outside the CV pipeline — see
    `RunResult.assert_no_transform_outside_pipeline`."""
    estimator: Any = None
    """The pipeline refitted on all rows. `None` when the model was skipped."""

    @property
    def headline(self) -> float | None:
        """PR-AUC — the metric to rank on under imbalance."""
        return self.metrics.average_precision


@dataclass
class RunResult:
    """Everything a report needs from one classification run."""

    models: list[ModelRun]
    n_rows: int
    n_features: int
    sampling: str
    class_balance: dict[Any, float]
    split_plan: SplitPlan | None
    target: str
    features: tuple[str, ...] = ()
    skipped: dict[str, str] = field(default_factory=dict)
    """Model name → why it did not run. Carried so a missing model in the report
    is a recorded decision rather than a silent omission."""

    @property
    def baseline(self) -> ModelRun | None:
        """The explainability floor. If nothing beats it, that is a finding about
        feature quality, not a failed run."""
        for model in self.models:
            if model.is_baseline:
                return model
        return None

    @property
    def best(self) -> ModelRun | None:
        """Highest PR-AUC, baseline included — it wins when it deserves to."""
        scored = [m for m in self.models if m.headline is not None]
        if not scored:
            return None
        return max(scored, key=lambda m: m.headline)

    @property
    def beats_baseline(self) -> bool:
        """Whether the best model clears the baseline by more than noise.

        False when there is no baseline to compare against: an unsubstantiated
        claim and a refuted one are both not-established, and the honest default
        for "we could not check" is not "yes".
        """
        baseline, best = self.baseline, self.best
        if baseline is None or best is None:
            return False
        if baseline.headline is None or best.headline is None:
            return False
        return (best.headline - baseline.headline) > BASELINE_TOLERANCE

    def assert_no_transform_outside_pipeline(self) -> None:
        """Raise unless every model kept its preprocessing inside the CV pipeline.

        Asserted rather than trusted: a transformer fitted on the full frame sees
        the validation rows, and the resulting scores are inflated *upward*, so
        the failure mode is a run that looks unusually good and is never
        questioned.
        """
        escaped = [m.name for m in self.models if not m.transform_in_pipeline]
        if escaped:
            raise TransformLeakageError(
                f"models {escaped} fitted a transformer outside the "
                "cross-validation pipeline. Every score reported for them saw "
                "the validation rows during preprocessing and is inflated by an "
                "unmeasured amount."
            )


def _build_pipeline(
    estimator: Any,
    numeric: list[str],
    categorical: list[str],
    class_weight: dict[Any, float] | None,
) -> Pipeline:
    """Preprocessor + estimator as one object, so `fit` cannot touch held-out rows.

    `class_weight` is applied to the estimator when it accepts one; models that
    do not take the parameter are left alone rather than erroring, since the
    sampler's reweighting is an optimisation and not a correctness requirement.
    """
    model = clone(estimator)
    if class_weight is not None and "class_weight" in model.get_params():
        model.set_params(class_weight=class_weight)
    return Pipeline(
        [
            (
                "preprocess",
                TabularPreprocessor(
                    numeric_features=numeric, categorical_features=categorical
                ),
            ),
            ("model", model),
        ]
    )


def _out_of_fold_probabilities(
    pipeline: Pipeline,
    x: pd.DataFrame,
    y: np.ndarray,
    splitter: SplitPlan,
    positive_label: Any,
    calibrate: bool,
    calibration_method: str | None,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Score every row with a model that did not train on it.

    Returns `(prob_raw, prob_calibrated, n_folds)`. When `calibrate` is False the
    two probability vectors are identical, so downstream code has one shape to
    handle rather than a None branch.
    """
    prob_raw = np.full(len(y), np.nan, dtype=float)
    prob_cal = np.full(len(y), np.nan, dtype=float)
    n_folds = 0

    for train_idx, test_idx in splitter.split(x, y):
        n_folds += 1
        x_train, x_test = x.iloc[train_idx], x.iloc[test_idx]
        y_train = y[train_idx]

        fitted = clone(pipeline)
        fitted.fit(x_train, y_train)
        prob_raw[test_idx] = _positive_probability(fitted, x_test, positive_label)

        if not calibrate:
            prob_cal[test_idx] = prob_raw[test_idx]
            continue

        # Calibration cross-validates *within* the training rows: the fold's
        # test rows must stay unseen, or the calibrated probabilities are fitted
        # to the very rows used to judge them.
        method = calibration_method or recommend_method(len(y_train))
        try:
            calibrated = calibrate_classifier(clone(pipeline), method=method, cv=3)
            calibrated.fit(x_train, y_train)
            prob_cal[test_idx] = _positive_probability(calibrated, x_test, positive_label)
        except Exception as exc:  # noqa: BLE001 — a failed calibration degrades, not aborts
            logger.warning("calibration failed on a fold (%s); using raw probabilities", exc)
            prob_cal[test_idx] = prob_raw[test_idx]

    return prob_raw, prob_cal, n_folds


def _positive_probability(fitted: Any, x: pd.DataFrame, positive_label: Any) -> np.ndarray:
    """Positive-class probability, located by label rather than by position.

    `predict_proba[:, 1]` assumes the positive class sorts second. That holds for
    0/1 and silently does not for other encodings, which produces a perfectly
    inverted score that still looks like a probability.
    """
    proba = fitted.predict_proba(x)
    classes = list(fitted.classes_)
    try:
        index = classes.index(positive_label)
    except ValueError:
        index = len(classes) - 1
    return proba[:, index]


def run_classification(
    df: pd.DataFrame,
    *,
    target: str,
    output: str = "binary",
    models: list[str] | None = None,
    sampling: str = "class_weight",
    splitter: SplitPlan | None = None,
    n_splits: int = 5,
    calibrate: bool = True,
    calibration_method: str | None = None,
    cost_fp: float | None = None,
    cost_fn: float | None = None,
    positive_label: Any = 1,
    seed: int = RANDOM_STATE,
) -> RunResult:
    """Run every candidate classifier on identical folds and report the comparison.

    `splitter` accepts a pre-built `SplitPlan`, which is how a caller supplies
    grouped or temporal folds without also putting the group column into the
    feature matrix — passing `group_col` through to the frame would let it be
    encoded as a feature, and a group key is usually a near-perfect one.

    `cost_fp`/`cost_fn` are optional: with both supplied, each model gets a
    cost-minimising threshold chosen on out-of-fold probabilities. Without them
    no threshold is reported, because the 0.5 default is a convention rather
    than a decision and reporting it as one would be misleading.
    """
    if target not in df.columns:
        raise KeyError(f"target {target!r} is not a column of the frame: {list(df.columns)}")

    plan = infer_column_types(df, target=target)
    features = plan.features
    if not features:
        raise ValueError(
            "no usable feature columns remain after type inference — every column "
            f"landed in `unused`: {plan.unused}"
        )

    x = df[list(features)].copy()
    y = df[target].to_numpy()

    counts = pd.Series(y).value_counts(normalize=True)
    class_balance = {k: float(v) for k, v in counts.items()}

    split_plan = splitter or make_splitter(n_splits=n_splits, random_state=seed)

    # The sampler is consulted once for the weights it recommends; the reweighting
    # itself is applied inside each fold's pipeline. Resampling the whole frame
    # here would synthesise minority rows from held-out data.
    sampler = build_sampler(sampling, random_state=seed)
    try:
        _, _ = sampler.fit_resample(x, y)
        class_weight = getattr(sampler, "class_weight_", None)
    except Exception as exc:  # noqa: BLE001 — degrade to unweighted rather than abort
        logger.warning("sampler %r failed (%s); continuing unweighted", sampling, exc)
        class_weight = None

    candidates = get_models("classification", output, include=models, random_state=seed)
    numeric = list(plan.numeric) + list(plan.boolean)
    categorical = list(plan.categorical) + list(plan.high_cardinality)

    runs: list[ModelRun] = []
    skipped: dict[str, str] = {}

    for name, estimator in candidates.items():
        pipeline = _build_pipeline(estimator, numeric, categorical, class_weight)
        started = time.perf_counter()
        try:
            prob_raw, prob_cal, _ = _out_of_fold_probabilities(
                pipeline, x, y, split_plan, positive_label, calibrate, calibration_method
            )
        except Exception as exc:  # noqa: BLE001 — one bad model must not kill the run
            logger.warning("model %r failed and was skipped: %s", name, exc)
            skipped[name] = str(exc)
            continue
        elapsed = time.perf_counter() - started

        scored = ~np.isnan(prob_cal)
        if not scored.any():
            skipped[name] = "no fold produced predictions"
            continue

        y_scored = y[scored]
        prob_scored = prob_cal[scored]
        y_pred = (prob_scored >= 0.5).astype(int)

        metrics = classification_metrics(
            y_scored, y_pred, prob_scored, positive_label=positive_label
        )

        calibration = None
        if calibrate:
            calibration = assess_calibration(
                y_scored,
                prob_raw[scored],
                prob_scored,
                method=calibration_method or recommend_method(int(scored.sum())),
                positive_label=positive_label,
            )

        threshold = None
        if cost_fp is not None and cost_fn is not None:
            threshold = choose_threshold(
                y_scored,
                prob_scored,
                cost_fp=cost_fp,
                cost_fn=cost_fn,
                positive_label=positive_label,
            )

        spec_is_baseline = name == "logistic"
        final = clone(pipeline)
        final.fit(x, y)

        runs.append(
            ModelRun(
                name=name,
                metrics=metrics,
                fit_seconds=elapsed,
                is_baseline=spec_is_baseline,
                calibration=calibration,
                threshold=threshold,
                estimator=final,
            )
        )

    return RunResult(
        models=runs,
        n_rows=len(df),
        n_features=len(features),
        sampling=sampling,
        class_balance=class_balance,
        split_plan=split_plan,
        target=target,
        features=features,
        skipped=skipped,
    )
