"""Monitoring — what happens to a model after it stops being a notebook.

Today this is drift: has the incoming data moved away from the data the model
was fitted on, far enough that its predictions should stop being trusted.
"""

from __future__ import annotations

from ml.monitoring.drift import (
    DriftReport,
    FeatureDrift,
    categorical_psi,
    compute_drift,
    population_stability_index,
)

__all__ = [
    "DriftReport",
    "FeatureDrift",
    "categorical_psi",
    "compute_drift",
    "population_stability_index",
]
