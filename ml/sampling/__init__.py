"""Sampling — imbalance strategies and outlier handling, both fold-safe.

Everything here refuses to operate on data marked by `mark_validation`. See
`resample.py` for why that guard is a runtime failure rather than a comment.
"""

from __future__ import annotations

from ml.sampling.outliers import detect_outliers, remove_outliers
from ml.sampling.resample import (
    RANDOM_STATE,
    ClassWeightSampler,
    PassthroughSampler,
    SamplingLeakageError,
    build_sampler,
    compute_class_weights,
    is_validation,
    mark_validation,
    resample_fold,
)

__all__ = [
    "RANDOM_STATE",
    "ClassWeightSampler",
    "PassthroughSampler",
    "SamplingLeakageError",
    "build_sampler",
    "compute_class_weights",
    "detect_outliers",
    "is_validation",
    "mark_validation",
    "remove_outliers",
    "resample_fold",
]
