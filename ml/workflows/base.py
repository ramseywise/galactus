"""Shared result types and the leakage-safe pipeline assembly.

Every workflow in this package returns a `RunResult`, and every fitted object
inside one is a single `sklearn.Pipeline`. That second constraint is the design:
if the imputer, the scaler, and the encoder live inside the pipeline, then
`cross_val_predict` refits them per fold and leakage is structurally impossible.
If any of them ran over the whole frame first, no amount of careful splitting
downstream recovers the honest number — the scaler already saw the validation
rows' means.

So `build_pipeline` is the only sanctioned way to assemble an estimator here,
and `RunResult.assert_no_transform_outside_pipeline` is the assertion a test can
make about the result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from sklearn.pipeline import Pipeline

from ml.evaluation.calibration import CalibrationReport
from ml.evaluation.metrics import (
    ClassificationMetrics,
    ClusteringMetrics,
    CurvePoints,
    RegressionMetrics,
)
from ml.evaluation.splitting import SplitPlan
from ml.evaluation.threshold import ThresholdResult
from ml.transform.columns import ColumnPlan

Metrics = ClassificationMetrics | RegressionMetrics | ClusteringMetrics

DEFAULT_TIE_TOLERANCE = 0.005
"""Headline-metric margin below which a model and the baseline are called a tie.

Half a point of PR-AUC or R² is comfortably inside the fold-to-fold spread of a
5-fold comparison on a few thousand rows, so a smaller gap is not evidence of a
better model. Deliberately a named constant rather than a magic number: a project
whose metric is tighter or noisier than that should override it at the call site
and be able to point at what it changed."""


class TransformLeakageError(RuntimeError):
    """Raised when a model fitted a transformer outside its cross-validation
    pipeline, which inflates every score it reported.

    A distinct type rather than `TypeError`: leakage is a result-validity
    failure, and a caller that wants to catch it must not have to catch every
    other type error alongside it.
    """


@dataclass
class ModelResult:
    """One fitted model and everything measured about it."""

    name: str
    estimator: Pipeline
    metrics: Metrics
    is_baseline: bool = False
    curves: dict[str, CurvePoints] = field(default_factory=dict)
    calibration: CalibrationReport | None = None
    threshold: ThresholdResult | None = None
    fit_seconds: float = 0.0
    notes: str = ""


@dataclass
class RunResult:
    """The full output of one workflow call — everything a report needs.

    Deliberately a data object with no rendering on it. The reporting layer reads
    this; it does not reach back into the models. That keeps `write_report`
    testable against a hand-built `RunResult` and keeps a workflow runnable
    without ever producing HTML.
    """

    family: str
    output: str
    target: str | None
    models: list[ModelResult]
    column_plan: ColumnPlan
    split_plan: SplitPlan | None
    n_rows: int
    n_features: int
    seed: int
    sampling: str = "none"
    class_balance: dict[str, int] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)
    """model name -> why it was not run (missing optional dep, reserved, error)."""

    @property
    def best(self) -> ModelResult | None:
        """The top model by the family's headline metric.

        Ties and near-ties are not adjudicated here — a report should show the
        comparison, not just the winner, which is why `models` stays ordered.
        """
        return self.models[0] if self.models else None

    @property
    def baseline(self) -> ModelResult | None:
        return next((m for m in self.models if m.is_baseline), None)

    @property
    def baseline_margin(self) -> float | None:
        """Headline score of the best model minus the baseline's.

        `None` when there is nothing to compare. Exposed alongside the verdict
        because the size of the gap is the part a reader can actually judge — a
        boolean hides whether the win was 0.30 or 0.0002.
        """
        best, base = self.best, self.baseline
        if best is None or base is None or best is base:
            return None
        return _score(best) - _score(base)

    def beats_baseline(self, tolerance: float = DEFAULT_TIE_TOLERANCE) -> bool | None:
        """Whether the best model improves on the baseline by more than `tolerance`.

        `None` when there is no baseline to compare against, **and also** when the
        margin falls inside the band — a near-tie is not a `False` (the baseline
        did not win either), it is the absence of a verdict. The question is worth
        asking explicitly: a gradient-boosted ensemble that ties logistic
        regression is a result, and usually the wrong model to ship.

        A strict `>` would call a 0.0002 margin a win. That margin is noise —
        smaller than the fold-to-fold spread of the same comparison rerun with a
        different seed — and a near-tie is the single most common real outcome of
        a model comparison, so the default band makes the common case reportable.
        Pass `tolerance=0` for the raw strict comparison, or read
        `baseline_margin` and decide with a domain-specific band.
        """
        if tolerance < 0:
            raise ValueError(f"tolerance must be non-negative, got {tolerance}")

        margin = self.baseline_margin
        if margin is None:
            return None
        if abs(margin) <= tolerance:
            return None
        return margin > 0

    def assert_no_transform_outside_pipeline(self) -> None:
        """Raise unless every fitted model is a single `Pipeline`.

        The structural guarantee against leakage, stated as an assertion so a
        test can hold the workflow to it rather than trusting the docstring.
        """
        for model in self.models:
            if not isinstance(model.estimator, Pipeline):
                raise TransformLeakageError(
                    f"model {model.name!r} is a {type(model.estimator).__name__}, not a "
                    "Pipeline. Preprocessing outside the pipeline is fitted on the whole "
                    "frame, so every cross-validated score it produces is inflated."
                )
            steps = dict(model.estimator.named_steps)
            if "preprocess" not in steps:
                raise TransformLeakageError(
                    f"model {model.name!r} has no 'preprocess' step; its transformer was "
                    "fitted somewhere the CV split cannot reach."
                )

    def comparison_frame(self) -> pd.DataFrame:
        """The model comparison as a frame — what a report tabulates."""
        rows = []
        for model in self.models:
            row: dict[str, Any] = {"model": model.name, "baseline": model.is_baseline}
            metrics = model.metrics
            for key in (
                "average_precision",
                "roc_auc",
                "brier",
                "f1",
                "balanced_accuracy",
                "rmse",
                "mae",
                "r2",
                "silhouette",
                "davies_bouldin",
                "n_clusters",
            ):
                if hasattr(metrics, key):
                    row[key] = getattr(metrics, key)
            row["fit_seconds"] = round(model.fit_seconds, 3)
            rows.append(row)
        return pd.DataFrame(rows)


def _score(model: ModelResult) -> float:
    """The single number models are ranked by, per family."""
    metrics = model.metrics
    if isinstance(metrics, ClassificationMetrics):
        _, value = metrics.headline(imbalanced=True)
        return value if value is not None else metrics.f1
    if isinstance(metrics, RegressionMetrics):
        return metrics.r2
    if isinstance(metrics, ClusteringMetrics):
        return metrics.silhouette if metrics.silhouette is not None else float("-inf")
    return float("-inf")


def build_pipeline(transformer: Any, estimator: Any, *, sampler: Any = None) -> Pipeline:
    """Wrap a transformer and an estimator into one `Pipeline`.

    The step is named `preprocess` unconditionally so downstream code — the
    assertion above, the reporting layer's feature-name lookup — has a stable
    handle rather than positional guessing.

    A sampler, when imbalanced-learn is installed, must sit *between* the two and
    must be run by an imblearn `Pipeline`, whose `fit` calls `fit_resample` on
    intermediate steps and whose `predict` skips them. A plain sklearn Pipeline
    would call `transform` at predict time and resample production rows, which is
    train/serve skew of the most literal kind.
    """
    if sampler is None:
        return Pipeline([("preprocess", transformer), ("model", estimator)])

    try:
        from imblearn.pipeline import Pipeline as ImbPipeline
    except ImportError:  # pragma: no cover - exercised only on stripped installs
        return Pipeline([("preprocess", transformer), ("model", estimator)])

    return ImbPipeline([("preprocess", transformer), ("sample", sampler), ("model", estimator)])
