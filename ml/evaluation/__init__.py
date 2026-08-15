"""Evaluation — splitting, metrics, calibration, and the decision rule.

The split comes first deliberately. Metrics computed over a leaky split are
precise measurements of nothing, so `splitting.py` is the module the rest of
this package depends on being correct.
"""

from __future__ import annotations

from ml.evaluation.calibration import (
    CalibrationReport,
    assess_calibration,
    calibrate_classifier,
    expected_calibration_error,
    recommend_method,
    reliability_curve,
)
from ml.evaluation.metrics import (
    ClassificationMetrics,
    ClusteringMetrics,
    CurvePoints,
    RegressionMetrics,
    classification_metrics,
    clustering_metrics,
    pr_curve,
    precision_at_k,
    regression_metrics,
    roc_curve_points,
)
from ml.evaluation.splitting import (
    DEFAULT_N_SPLITS,
    RANDOM_STATE,
    GroupLeakageError,
    SortedTimeSeriesSplit,
    SplitPlan,
    TemporalLeakageError,
    assert_no_group_leakage,
    assert_temporal_order,
    make_splitter,
)
from ml.evaluation.threshold import (
    ThresholdResult,
    choose_threshold,
    expected_cost,
    threshold_for_capacity,
)

__all__ = [
    "DEFAULT_N_SPLITS",
    "RANDOM_STATE",
    "CalibrationReport",
    "ClassificationMetrics",
    "ClusteringMetrics",
    "CurvePoints",
    "GroupLeakageError",
    "RegressionMetrics",
    "SortedTimeSeriesSplit",
    "SplitPlan",
    "TemporalLeakageError",
    "ThresholdResult",
    "assert_no_group_leakage",
    "assert_temporal_order",
    "assess_calibration",
    "calibrate_classifier",
    "choose_threshold",
    "classification_metrics",
    "clustering_metrics",
    "expected_calibration_error",
    "expected_cost",
    "make_splitter",
    "pr_curve",
    "precision_at_k",
    "recommend_method",
    "regression_metrics",
    "reliability_curve",
    "roc_curve_points",
    "threshold_for_capacity",
]
