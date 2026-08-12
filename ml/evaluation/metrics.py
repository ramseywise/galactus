"""Classification, clustering, and regression metrics.

The opinionated part of this module is that **PR-AUC leads and ROC-AUC follows**
for imbalanced binary problems. ROC-AUC is computed over the true-positive and
false-positive rates, and the false-positive rate divides by the count of the
majority class. On a 95/5 frame that denominator is so large that hundreds of
false positives barely move it, so a model can look excellent while the precision
an operator actually experiences is dismal. Average precision divides by the
predicted-positive count instead, which is the number the operator feels.

`precision_at_k` exists for the same reason: when capacity is fixed — an agent
can make 200 calls a day — the question is not "how good is the ranking overall"
but "of the top 200, how many pay". That is a different number and often a much
less flattering one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    calinski_harabasz_score,
    confusion_matrix,
    davies_bouldin_score,
    f1_score,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    precision_recall_curve,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    roc_curve,
    silhouette_score,
)


@dataclass(frozen=True)
class CurvePoints:
    """Points for one curve, kept as plain lists so the reporting layer can draw
    SVG paths without importing a plotting library."""

    x: list[float]
    y: list[float]
    label: str
    x_label: str
    y_label: str
    baseline: float | None = None
    """The no-skill reference: prevalence for a PR curve, 0.5 for ROC."""


@dataclass(frozen=True)
class ClassificationMetrics:
    """Every headline number for one fitted classifier."""

    average_precision: float | None = None
    roc_auc: float | None = None
    brier: float | None = None
    log_loss: float | None = None
    accuracy: float = 0.0
    balanced_accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    precision_at_k: dict[int, float] = field(default_factory=dict)
    per_class: dict[str, dict[str, float]] = field(default_factory=dict)
    confusion: list[list[int]] = field(default_factory=list)
    prevalence: float | None = None
    n_samples: int = 0

    @property
    def brier_score(self) -> float | None:
        """Alias for `brier`. Reports reach for the full name, and a `getattr`
        miss returns `None` — which is indistinguishable from "not computed"."""
        return self.brier

    def headline(self, imbalanced: bool = True) -> tuple[str, float | None]:
        """The metric to lead a report with. PR-AUC under imbalance, else ROC-AUC."""
        if imbalanced and self.average_precision is not None:
            return "average_precision", self.average_precision
        if self.roc_auc is not None:
            return "roc_auc", self.roc_auc
        return "f1", self.f1


def precision_at_k(y_true, y_prob, k: int) -> float:
    """Precision among the `k` highest-scored rows — the fixed-capacity metric.

    `k` above the row count is clamped rather than raising: a capacity larger
    than the queue is a real situation, and the honest answer is the precision
    over everything.
    """
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")
    k = min(k, len(y_true))
    top = np.argsort(y_prob)[::-1][:k]
    return float(np.mean(y_true[top]))


def classification_metrics(
    y_true,
    y_pred,
    y_prob=None,
    *,
    labels: list[Any] | None = None,
    k_values: tuple[int, ...] = (10, 50, 100),
    positive_label: Any = 1,
) -> ClassificationMetrics:
    """Compute the full metric set for one classifier.

    `y_prob` is the positive-class probability for binary problems, or the full
    `(n_samples, n_classes)` matrix for multiclass. Probability-dependent metrics
    are `None` when it is absent rather than silently zero — a missing number and
    a bad number must not look the same in a report.
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    classes = labels if labels is not None else sorted(set(y_true.tolist()))
    is_binary = len(classes) <= 2

    average = "binary" if is_binary else "macro"
    kwargs: dict[str, Any] = {"average": average, "zero_division": 0}
    if is_binary:
        kwargs["pos_label"] = positive_label

    metrics: dict[str, Any] = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, **kwargs)),
        "recall": float(recall_score(y_true, y_pred, **kwargs)),
        "f1": float(f1_score(y_true, y_pred, **kwargs)),
        "confusion": confusion_matrix(y_true, y_pred, labels=classes).tolist(),
        "n_samples": int(len(y_true)),
    }

    if is_binary:
        metrics["prevalence"] = float(np.mean(y_true == positive_label))

    if y_prob is not None:
        prob = np.asarray(y_prob)
        if is_binary:
            positive = prob if prob.ndim == 1 else prob[:, -1]
            binary_true = (y_true == positive_label).astype(int)
            metrics["average_precision"] = float(average_precision_score(binary_true, positive))
            metrics["roc_auc"] = float(roc_auc_score(binary_true, positive))
            metrics["brier"] = float(brier_score_loss(binary_true, positive))
            metrics["log_loss"] = float(log_loss(binary_true, positive, labels=[0, 1]))
            metrics["precision_at_k"] = {
                k: precision_at_k(binary_true, positive, k) for k in k_values if k <= len(y_true)
            }
        elif prob.ndim == 2 and prob.shape[1] == len(classes):
            metrics["roc_auc"] = float(
                roc_auc_score(y_true, prob, multi_class="ovr", average="macro", labels=classes)
            )
            metrics["log_loss"] = float(log_loss(y_true, prob, labels=classes))

    if not is_binary:
        per_class: dict[str, dict[str, float]] = {}
        for cls in classes:
            mask_true = y_true == cls
            mask_pred = y_pred == cls
            tp = float(np.sum(mask_true & mask_pred))
            per_class[str(cls)] = {
                "precision": tp / float(np.sum(mask_pred)) if np.sum(mask_pred) else 0.0,
                "recall": tp / float(np.sum(mask_true)) if np.sum(mask_true) else 0.0,
                "support": float(np.sum(mask_true)),
            }
        metrics["per_class"] = per_class

    return ClassificationMetrics(**metrics)


def pr_curve(y_true, y_prob, *, positive_label: Any = 1) -> CurvePoints:
    """Precision-recall curve, with prevalence as the no-skill baseline."""
    y_true = np.asarray(y_true)
    binary_true = (y_true == positive_label).astype(int)
    precision, recall, _ = precision_recall_curve(binary_true, np.asarray(y_prob))
    return CurvePoints(
        x=recall.tolist(),
        y=precision.tolist(),
        label="precision-recall",
        x_label="recall",
        y_label="precision",
        baseline=float(np.mean(binary_true)),
    )


def roc_curve_points(y_true, y_prob, *, positive_label: Any = 1) -> CurvePoints:
    """ROC curve, with the 0.5 diagonal as the no-skill baseline."""
    y_true = np.asarray(y_true)
    binary_true = (y_true == positive_label).astype(int)
    fpr, tpr, _ = roc_curve(binary_true, np.asarray(y_prob))
    return CurvePoints(
        x=fpr.tolist(),
        y=tpr.tolist(),
        label="ROC",
        x_label="false positive rate",
        y_label="true positive rate",
        baseline=0.5,
    )


@dataclass(frozen=True)
class RegressionMetrics:
    rmse: float
    mae: float
    mape: float | None
    r2: float
    n_samples: int


def regression_metrics(y_true, y_pred) -> RegressionMetrics:
    """RMSE/MAE/MAPE/R². MAPE is `None` when any true value is zero — dividing by
    it would produce an infinity that poisons the mean silently."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    mape: float | None = None
    if not np.any(y_true == 0):
        mape = float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100)

    return RegressionMetrics(
        rmse=float(np.sqrt(mean_squared_error(y_true, y_pred))),
        mae=float(mean_absolute_error(y_true, y_pred)),
        mape=mape,
        r2=float(r2_score(y_true, y_pred)),
        n_samples=int(len(y_true)),
    )


@dataclass(frozen=True)
class ClusteringMetrics:
    silhouette: float | None
    davies_bouldin: float | None
    calinski_harabasz: float | None
    n_clusters: int
    n_noise: int
    cluster_sizes: dict[str, int]


def clustering_metrics(x, labels) -> ClusteringMetrics:
    """Internal cluster-quality metrics.

    DBSCAN labels noise as -1; those rows are excluded from the quality scores
    (they belong to no cluster) but counted in `n_noise`, because "most of the
    frame was called noise" is the single most useful diagnostic for a DBSCAN run
    and averaging it away would hide it.
    """
    labels = np.asarray(labels)
    x = np.asarray(x)

    n_noise = int(np.sum(labels == -1))
    signal = labels != -1
    unique = sorted({int(label) for label in labels[signal]})
    sizes = {str(label): int(np.sum(labels == label)) for label in unique}

    silhouette = davies_bouldin = calinski = None
    # Every internal metric needs at least two populated clusters to be defined.
    if len(unique) >= 2 and np.sum(signal) > len(unique):
        silhouette = float(silhouette_score(x[signal], labels[signal]))
        davies_bouldin = float(davies_bouldin_score(x[signal], labels[signal]))
        calinski = float(calinski_harabasz_score(x[signal], labels[signal]))

    return ClusteringMetrics(
        silhouette=silhouette,
        davies_bouldin=davies_bouldin,
        calinski_harabasz=calinski,
        n_clusters=len(unique),
        n_noise=n_noise,
        cluster_sizes=sizes,
    )
