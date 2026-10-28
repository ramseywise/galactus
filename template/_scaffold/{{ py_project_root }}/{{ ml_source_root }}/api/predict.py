"""Serving edge — the seam where a fitted model meets a request.

Deliberately thin, and deliberately not a web framework. Per naming.md §1 rule 1,
`api/` never holds business logic: this module loads an artifact, applies the
`ThresholdPolicy` that `calibration/` produced, and returns a decision. Choosing
the threshold is not its job; neither is fitting anything.

The concrete transport (FastAPI route, Lambda handler, batch job) wraps
`ScoringService` rather than reimplementing it, so the decision logic is testable
without standing up a server. Deployment itself — Docker, Elastic Beanstalk, the
AWS arc — is a later phase; this is the seam it will attach to.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from ml.config import settings
from ml.schemas import ThresholdPolicy


@dataclass(frozen=True)
class Decision:
    """One scored row: the probability, the decision, and the point that made it.

    Carries `threshold` alongside `flagged` so a logged decision remains
    interpretable after the policy is changed — a stored boolean whose threshold
    is unknown cannot be audited later.
    """

    probability: float
    flagged: bool
    threshold: float
    model_version: str


class ScoringService:
    """Applies a fitted estimator plus a threshold policy to incoming rows."""

    def __init__(
        self,
        estimator: Any,
        policy: ThresholdPolicy,
        model_version: str | None = None,
    ):
        if policy.selected is None:
            raise ValueError(
                "ThresholdPolicy has no selected operating point — calibration/ must "
                "choose one before the model can serve decisions."
            )
        self.estimator = estimator
        self.policy = policy
        self.model_version = model_version or settings.model_version

    @property
    def threshold(self) -> float:
        assert self.policy.selected is not None  # enforced in __init__
        return self.policy.selected.threshold

    def score(self, frame: pd.DataFrame) -> list[Decision]:
        """Score a frame. Raises if the estimator cannot produce probabilities —
        a decision threshold applied to a raw label is meaningless."""
        if not hasattr(self.estimator, "predict_proba"):
            raise TypeError(
                f"{type(self.estimator).__name__} has no predict_proba; a "
                "ThresholdPolicy cannot be applied to hard labels."
            )
        probabilities = self.estimator.predict_proba(frame)[:, 1]
        return [
            Decision(
                probability=float(p),
                flagged=bool(p >= self.threshold),
                threshold=self.threshold,
                model_version=self.model_version,
            )
            for p in probabilities
        ]


def artifact_path(name: str = "model.joblib", version: str | None = None) -> Path:
    """Where a versioned artifact lives, per `config.settings`.

    Centralised so training, serving, and monitoring resolve the same path rather
    than three hardcoded strings that drift apart.
    """
    base = settings.artifact_dir / (version or settings.model_version)
    return base / name
