"""Serving edge — applying a threshold policy to incoming rows.

The claims worth pinning are refusals: serving without a chosen operating point,
and applying a probability threshold to a model that emits only hard labels. Both
are silent-wrong-answer bugs if allowed through.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC

from ml.api import Decision, ScoringService, artifact_path
from ml.schemas import OperatingPoint, ThresholdPolicy

SEED = 42


@pytest.fixture
def fitted_estimator():
    rng = np.random.default_rng(SEED)
    x = pd.DataFrame({"a": np.concatenate([rng.normal(0, 1, 50), rng.normal(4, 1, 50)])})
    y = pd.Series([0] * 50 + [1] * 50)
    return LogisticRegression(max_iter=1000).fit(x, y), x


@pytest.fixture
def policy():
    point = OperatingPoint(threshold=0.5, precision=0.8, recall=0.7, coverage=0.5)
    return ThresholdPolicy(method="sigmoid", points=(point,), selected=point)


def test_serving_requires_a_selected_operating_point(fitted_estimator):
    """Calibration must choose before the model can serve — a service with no
    threshold would have to invent one."""
    estimator, _ = fitted_estimator

    with pytest.raises(ValueError, match="no selected operating point"):
        ScoringService(estimator, ThresholdPolicy())


def test_scoring_applies_the_selected_threshold(fitted_estimator, policy):
    estimator, x = fitted_estimator

    decisions = ScoringService(estimator, policy, model_version="v1").score(x)

    assert len(decisions) == len(x)
    assert all(isinstance(d, Decision) for d in decisions)
    assert all(d.flagged == (d.probability >= 0.5) for d in decisions)


def test_a_decision_records_the_threshold_that_made_it(fitted_estimator, policy):
    """A stored boolean whose threshold is unknown cannot be audited after the
    policy changes."""
    estimator, x = fitted_estimator

    decision = ScoringService(estimator, policy, model_version="v2").score(x.head(1))[0]

    assert decision.threshold == 0.5
    assert decision.model_version == "v2"


def test_a_hard_label_model_is_refused(policy):
    """A threshold applied to a 0/1 label is meaningless — better to refuse than
    to silently compare a label against 0.5."""
    rng = np.random.default_rng(SEED)
    x = pd.DataFrame({"a": rng.normal(0, 1, 40)})
    y = pd.Series([0] * 20 + [1] * 20)
    estimator = SVC(probability=False).fit(x, y)

    with pytest.raises(TypeError, match="predict_proba"):
        ScoringService(estimator, policy).score(x)


def test_a_stricter_threshold_flags_no_more_rows(fitted_estimator):
    """Monotonicity — raising the bar cannot flag more rows. Cheap to state,
    and it catches an inverted comparison."""
    estimator, x = fitted_estimator

    def flagged_at(threshold: float) -> int:
        point = OperatingPoint(threshold=threshold, precision=0.8, recall=0.7, coverage=0.5)
        service = ScoringService(estimator, ThresholdPolicy(points=(point,), selected=point))
        return sum(d.flagged for d in service.score(x))

    assert flagged_at(0.9) <= flagged_at(0.5) <= flagged_at(0.1)


def test_artifact_path_is_versioned(monkeypatch):
    """Two runs must not overwrite each other's artifacts."""
    monkeypatch.setenv("ML_MODEL_VERSION", "v9")

    path = artifact_path("model.joblib", version="v9")

    assert "v9" in str(path)
    assert path.name == "model.joblib"
