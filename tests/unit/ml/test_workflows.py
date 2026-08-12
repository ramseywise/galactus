"""Step 15 — the classification workflow that composes every prior step.

`run_classification` is the only entry point a run script calls. Everything below
it — column inference, sampling, splitting, calibration, threshold choice — is
already tested in isolation; what is untested until here is whether they compose
without a seam leaking.

The guard test is the reason this module exists rather than being inlined into a
run script: a transformer fitted outside the CV pipeline inflates every score in
the report, and it does so silently. `assert_no_transform_outside_pipeline` is
asserted rather than trusted, so it needs a case where it actually raises.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.evaluation.splitting import make_splitter
from ml.workflows.classification import BASELINE_TOLERANCE, run_classification

RANDOM_STATE = 42


@pytest.fixture
def imbalanced_frame() -> pd.DataFrame:
    """600 rows at ~15% minority, with signal a linear model can find.

    Deliberately imbalanced: the headline metric under imbalance is PR-AUC, and a
    frame at 50/50 would let a run pass while reporting the wrong number.
    """
    rng = np.random.default_rng(RANDOM_STATE)
    n = 600
    signal = rng.normal(size=n)
    noise = rng.normal(size=n)
    logit = 2.2 * signal - 2.0
    prob = 1.0 / (1.0 + np.exp(-logit))
    target = (rng.uniform(size=n) < prob).astype(int)
    return pd.DataFrame(
        {
            "signal": signal,
            "noise": noise,
            "category": rng.choice(["a", "b", "c"], size=n),
            "charged_off": target,
        }
    )


# --- Test 1: happy path. The whole chain runs and reports the surface a run
# script consumes. Named fields, not just "it returned something" — the run
# script reads `.metrics.average_precision` and a result missing it fails at the
# report, thousands of rows after the fit.
def test_run_classification_reports_the_full_consumed_surface(imbalanced_frame):
    result = run_classification(
        imbalanced_frame,
        target="charged_off",
        output="binary",
        models=["logistic"],
        sampling="class_weight",
        splitter=make_splitter(n_splits=3, random_state=RANDOM_STATE),
        calibrate=True,
        cost_fp=1.0,
        cost_fn=4.0,
        seed=RANDOM_STATE,
    )

    assert result.n_rows == len(imbalanced_frame)
    assert result.n_features > 0
    assert result.sampling == "class_weight"
    assert result.split_plan.n_splits == 3
    assert result.baseline is not None, "a run with no floor cannot claim to beat one"
    assert result.best is not None
    assert isinstance(result.beats_baseline, bool)

    for model in result.models:
        assert model.metrics.average_precision is not None, (
            "PR-AUC is the headline under imbalance; a missing value and a bad "
            "value must not look the same in the report"
        )
        assert model.threshold is not None, "cost_fn was supplied, so a threshold is owed"
        assert model.fit_seconds >= 0


# --- Test 2: the failure mode this module exists to catch. A transformer fitted
# on the full frame before splitting sees the validation rows, so every fold
# score is inflated by an unmeasured amount.
# WHAT MAKES THIS FAIL: an implementation that fits its preprocessor once, outside
# the per-fold pipeline, and then reports the resulting scores as clean. That run
# passes test 1 identically — the numbers are simply, silently, too good.
def test_transform_outside_pipeline_is_asserted_not_trusted(imbalanced_frame):
    result = run_classification(
        imbalanced_frame,
        target="charged_off",
        output="binary",
        models=["logistic"],
        sampling="class_weight",
        splitter=make_splitter(n_splits=3, random_state=RANDOM_STATE),
        seed=RANDOM_STATE,
    )

    # Clean run: the guard is silent.
    result.assert_no_transform_outside_pipeline()

    # Now claim a transform escaped, and the same guard must raise rather than
    # letting the inflated scores through.
    result.models[0].transform_in_pipeline = False
    with pytest.raises(Exception, match="pipeline"):
        result.assert_no_transform_outside_pipeline()


# --- Test 3: the boundary. `beats_baseline` on a frame with no learnable signal.
# WHAT MAKES THIS FAIL: a strict `>` with no tolerance band, which calls a
# 0.0002 PR-AUC margin a win. On pure noise no model beats the prevalence floor,
# and reporting one that does is how a null result gets shipped as a finding.
def test_no_signal_does_not_beat_the_baseline():
    rng = np.random.default_rng(RANDOM_STATE)
    n = 400
    frame = pd.DataFrame(
        {
            "noise_a": rng.normal(size=n),
            "noise_b": rng.normal(size=n),
            "charged_off": (rng.uniform(size=n) < 0.2).astype(int),
        }
    )

    # random_forest, not logistic: the baseline cannot beat itself, so a
    # single-model run would pass this assertion no matter what the comparison
    # does. A second, non-baseline candidate is what makes the test real.
    result = run_classification(
        frame,
        target="charged_off",
        output="binary",
        models=["random_forest"],
        sampling="class_weight",
        splitter=make_splitter(n_splits=3, random_state=RANDOM_STATE),
        seed=RANDOM_STATE,
    )

    assert result.best is not result.baseline, (
        "the fixture is only meaningful if a non-baseline model outscored the "
        "baseline — otherwise this asserts nothing about the tolerance band"
    )
    margin = result.best.headline - result.baseline.headline
    assert 0 < margin < BASELINE_TOLERANCE, (
        f"expected a positive margin inside the noise band, got {margin:.4f}"
    )
    assert result.beats_baseline is False, (
        "features are pure noise — a margin this small is fold-to-fold variance "
        "being reported as signal"
    )
