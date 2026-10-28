"""End-to-end workflows — frame in, scored comparison out.

One function per family. Each takes a DataFrame and returns a `RunResult` that
the reporting layer turns into HTML, with every intermediate decision (column
types, splitter, sampler, threshold) made explicitly and recorded on the result
rather than left implicit in the caller's notebook.
"""

from __future__ import annotations

from ml.workflows.base import (
    ModelResult,
    RunResult,
    TransformLeakageError,
    build_pipeline,
)
from ml.workflows.classification import run_classification
from ml.workflows.clustering import run_clustering
from ml.workflows.prediction import run_prediction

__all__ = [
    "ModelResult",
    "RunResult",
    "TransformLeakageError",
    "build_pipeline",
    "run_classification",
    "run_clustering",
    "run_prediction",
]
