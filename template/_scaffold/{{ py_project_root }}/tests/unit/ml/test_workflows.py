"""Step 6 — end-to-end workflows.

The claims worth testing here are structural, not numerical. Whether a random
forest beats logistic regression on `breast_cancer` is a fact about the dataset;
whether every fitted object is a single Pipeline with no transform outside it is
a fact about this code, and it is the one that decides whether any reported
number means anything.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import load_breast_cancer, make_blobs, make_classification, make_regression
from sklearn.pipeline import Pipeline

from ml.evaluation.metrics import RegressionMetrics
from ml.evaluation.splitting import assert_no_group_leakage
from ml.transform.columns import ColumnPlan
from ml.workflows import run_classification, run_clustering, run_prediction
from ml.workflows.base import ModelResult, RunResult, TransformLeakageError

RANDOM_STATE = 42


@pytest.fixture(scope="module")
def cancer_frame() -> pd.DataFrame:
    """`breast_cancer` as a frame — 569 rows, 30 numeric features, binary target."""
    data = load_breast_cancer(as_frame=True)
    frame = data.frame.copy()
    return frame.rename(columns={"target": "malignant"})


@pytest.fixture(scope="module")
def imbalanced_frame() -> pd.DataFrame:
    x, y = make_classification(
        n_samples=600,
        n_features=10,
        n_informative=5,
        weights=[0.9, 0.1],
        random_state=RANDOM_STATE,
    )
    frame = pd.DataFrame(x, columns=[f"f{i}" for i in range(x.shape[1])])
    frame["target"] = y
    return frame


@pytest.fixture(scope="module")
def xor_frame() -> pd.DataFrame:
    """A label with no linear decision boundary, plus 5% label noise.

    Exists so the baseline-comparison test has a frame where the answer is
    structural rather than incidental: logistic regression cannot represent XOR
    at any coefficient, so it sits at chance while any tree splits it.
    """
    rng = np.random.default_rng(RANDOM_STATE)
    n = 600
    a, b = rng.normal(size=n), rng.normal(size=n)
    label = ((a > 0) ^ (b > 0)).astype(int)
    label = np.where(rng.random(n) < 0.05, 1 - label, label)
    return pd.DataFrame({"a": a, "b": b, "noise": rng.normal(size=n), "label": label})


@pytest.fixture(scope="module")
def mixed_frame() -> pd.DataFrame:
    """Numeric + categorical + boolean, so the transformer branch is exercised."""
    rng = np.random.default_rng(RANDOM_STATE)
    n = 400
    numeric = rng.normal(size=n)
    category = rng.choice(["north", "south", "east"], size=n)
    signal = numeric + (category == "north") * 1.5
    return pd.DataFrame(
        {
            "amount": numeric,
            "region": category,
            "is_active": rng.random(n) < 0.6,
            "label": (signal + rng.normal(0, 0.5, n) > 0.8).astype(int),
        }
    )


# ── classification ───────────────────────────────────────────────────────────


def test_breast_cancer_returns_a_populated_comparison(cancer_frame):
    """The Done-when: ≥3 models compared, logistic baseline present."""
    result = run_classification(cancer_frame, target="malignant", seed=RANDOM_STATE)

    assert len(result.models) >= 3, f"only {len(result.models)} models ran: {result.skipped}"
    assert result.baseline is not None, "the logistic baseline must always be present"
    assert result.baseline.name == "logistic"
    assert result.n_rows == len(cancer_frame)
    assert result.n_features == 30
    assert result.target == "malignant"

    for model in result.models:
        assert model.metrics.roc_auc is not None
        assert model.metrics.roc_auc > 0.8, f"{model.name} scored implausibly low on cancer"


def test_every_fitted_model_is_a_single_pipeline(cancer_frame):
    """The leakage guarantee, asserted.

    If preprocessing lived outside the pipeline it would be fitted on the whole
    frame before the split, and every cross-validated score above would be
    inflated by an amount nothing downstream can recover.
    """
    result = run_classification(cancer_frame, target="malignant", seed=RANDOM_STATE)

    result.assert_no_transform_outside_pipeline()  # raises on violation

    for model in result.models:
        assert isinstance(model.estimator, Pipeline)
        assert "preprocess" in model.estimator.named_steps
        assert "model" in model.estimator.named_steps


def test_assert_no_transform_outside_pipeline_actually_raises(cancer_frame):
    """The guard needs its failure path exercised, or it is a comment."""
    from sklearn.linear_model import LogisticRegression

    result = run_classification(
        cancer_frame, target="malignant", models=["logistic"], seed=RANDOM_STATE
    )
    result.models[0].estimator = LogisticRegression()  # a bare estimator, not a pipeline

    with pytest.raises(TransformLeakageError, match="not a Pipeline"):
        result.assert_no_transform_outside_pipeline()


def test_the_same_seed_produces_identical_metrics(cancer_frame):
    """Two runs, same seed, same numbers — otherwise a reported metric is not a
    fact about the model, it is a fact about that afternoon."""
    first = run_classification(
        cancer_frame, target="malignant", models=["logistic", "random_forest"], seed=RANDOM_STATE
    )
    second = run_classification(
        cancer_frame, target="malignant", models=["logistic", "random_forest"], seed=RANDOM_STATE
    )

    assert [m.name for m in first.models] == [m.name for m in second.models]
    for a, b in zip(first.models, second.models, strict=True):
        assert a.metrics.roc_auc == pytest.approx(b.metrics.roc_auc)
        assert a.metrics.average_precision == pytest.approx(b.metrics.average_precision)
        assert a.metrics.confusion == b.metrics.confusion


def test_imbalanced_run_reports_pr_auc_as_the_headline(imbalanced_frame):
    result = run_classification(imbalanced_frame, target="target", seed=RANDOM_STATE)

    best = result.best
    name, value = best.metrics.headline(imbalanced=True)
    assert name == "average_precision"
    assert value is not None
    assert result.class_balance["1"] < result.class_balance["0"]


def test_curves_are_attached_for_binary_runs(cancer_frame):
    result = run_classification(
        cancer_frame, target="malignant", models=["logistic"], seed=RANDOM_STATE
    )
    curves = result.models[0].curves

    assert set(curves) == {"pr", "roc"}
    assert curves["pr"].baseline == pytest.approx(cancer_frame["malignant"].mean())
    assert curves["roc"].baseline == 0.5


def test_costs_produce_a_threshold_and_their_absence_does_not(cancer_frame):
    """A threshold without a cost matrix is a guess wearing a number, so the
    default must be to recommend no operating point at all."""
    without = run_classification(
        cancer_frame, target="malignant", models=["logistic"], seed=RANDOM_STATE
    )
    assert without.models[0].threshold is None

    with_costs = run_classification(
        cancer_frame,
        target="malignant",
        models=["logistic"],
        cost_fp=1.0,
        cost_fn=10.0,
        seed=RANDOM_STATE,
    )
    chosen = with_costs.models[0].threshold
    assert chosen is not None
    assert 0.0 <= chosen.threshold <= 1.0
    assert chosen.expected_cost <= chosen.cost_at_default
    # The operating point is selected out-of-fold: each fold's threshold is
    # chosen on the other folds' rows, so the metrics carry no in-sample
    # optimism and need no caveat.
    assert chosen.in_sample is False
    assert chosen.selection_caveat is None
    assert len(chosen.fold_thresholds) == with_costs.split_plan.n_splits


def test_calibration_report_is_attached_when_requested(cancer_frame):
    result = run_classification(
        cancer_frame,
        target="malignant",
        models=["random_forest"],
        calibrate=True,
        seed=RANDOM_STATE,
    )
    report = result.models[0].calibration

    assert report is not None
    assert report.brier_before > 0 and report.brier_after > 0
    assert report.method in ("sigmoid", "isotonic")

    uncalibrated = run_classification(
        cancer_frame,
        target="malignant",
        models=["random_forest"],
        calibrate=False,
        seed=RANDOM_STATE,
    )
    assert uncalibrated.models[0].calibration is None


def test_mixed_dtypes_flow_through_the_transformer(mixed_frame):
    """Categorical and boolean columns must reach the model encoded, not dropped."""
    result = run_classification(mixed_frame, target="label", seed=RANDOM_STATE)

    assert "region" in result.column_plan.categorical
    assert "amount" in result.column_plan.numeric
    assert result.best.metrics.roc_auc > 0.7


def test_beats_baseline_is_none_when_the_baseline_wins(cancer_frame):
    """On `breast_cancer` the logistic baseline is genuinely the best model, so
    the comparison has nothing to report — and that is the useful answer.

    A well-separated 30-feature frame is close to linearly separable; the
    ensembles have nothing to add. `None` here means "no model beat the
    baseline", which is the result a reader needs to see rather than a fabricated
    True.
    """
    result = run_classification(cancer_frame, target="malignant", seed=RANDOM_STATE)

    assert result.best is result.baseline, "logistic is expected to win on this frame"
    assert result.beats_baseline() is None


def test_beats_baseline_is_true_when_a_model_actually_wins(xor_frame):
    """The True branch, on a frame where the baseline provably cannot win.

    XOR has no linear decision boundary, so logistic regression sits at chance
    while a tree splits it trivially. This is not a fixture chosen because the
    forest happened to edge ahead — it is one where the comparison has a
    guaranteed answer.
    """
    result = run_classification(
        xor_frame, target="label", models=["logistic", "random_forest"], seed=RANDOM_STATE
    )

    assert result.best.name == "random_forest"
    assert result.baseline.name == "logistic"
    assert result.beats_baseline() is True
    assert result.baseline.metrics.roc_auc < 0.6, "logistic is at chance on XOR"
    assert result.best.metrics.roc_auc > 0.9


def test_beats_baseline_is_none_without_a_comparison(cancer_frame):
    baseline_only = run_classification(
        cancer_frame, target="malignant", models=["logistic"], seed=RANDOM_STATE
    )
    assert baseline_only.beats_baseline() is None, "nothing to compare against itself"


def _two_model_result(best_score: float, baseline_score: float) -> RunResult:
    """A `RunResult` with two models at chosen R² values.

    Hand-built rather than fitted: the tie band is arithmetic over two numbers,
    and pinning a real fit to a margin of exactly 0.0002 would be a fixture
    fighting the optimiser rather than a test of the property.
    """
    return RunResult(
        family="prediction",
        output="continuous",
        target="y",
        models=[
            ModelResult(
                name="candidate",
                estimator=Pipeline([("preprocess", "passthrough"), ("model", "passthrough")]),
                metrics=RegressionMetrics(
                    rmse=0.0, mae=0.0, mape=None, r2=best_score, n_samples=100
                ),
            ),
            ModelResult(
                name="baseline",
                estimator=Pipeline([("preprocess", "passthrough"), ("model", "passthrough")]),
                metrics=RegressionMetrics(
                    rmse=0.0, mae=0.0, mape=None, r2=baseline_score, n_samples=100
                ),
                is_baseline=True,
            ),
        ],
        column_plan=ColumnPlan(),
        split_plan=None,
        n_rows=100,
        n_features=3,
        seed=RANDOM_STATE,
    )


def test_a_near_tie_is_not_a_win():
    """The finding this band exists for: a 0.0002 margin is noise, and a strict
    `>` called it a victory. Inside the band the answer is `None` — no verdict —
    not `False`, because the baseline did not win either."""
    result = _two_model_result(best_score=0.7002, baseline_score=0.7000)

    assert result.beats_baseline() is None
    assert result.baseline_margin == pytest.approx(0.0002)


def test_a_margin_outside_the_band_is_still_a_win():
    result = _two_model_result(best_score=0.80, baseline_score=0.70)

    assert result.beats_baseline() is True
    assert result.baseline_margin == pytest.approx(0.10)


def test_the_tolerance_band_is_callable_down_to_strict_comparison():
    """`tolerance=0` recovers the old strict `>`, so a project that genuinely
    wants every margin adjudicated can still ask for that."""
    result = _two_model_result(best_score=0.7002, baseline_score=0.7000)

    assert result.beats_baseline(tolerance=0) is True
    assert result.beats_baseline(tolerance=0.5) is None


def test_a_negative_tolerance_is_rejected():
    result = _two_model_result(best_score=0.80, baseline_score=0.70)

    with pytest.raises(ValueError, match="non-negative"):
        result.beats_baseline(tolerance=-0.1)


def test_a_grouped_run_keeps_the_group_column_out_of_the_features():
    """The leak this fix closes: `group_col` had to be a feature for the split to
    resolve it, and at near-unique cardinality the transformer target-encoded
    borrower identity against the label."""
    rng = np.random.default_rng(RANDOM_STATE)
    n_entities, per_entity = 40, 5
    n = n_entities * per_entity
    frame = pd.DataFrame(
        {
            # Near-unique, exactly the shape that lands in `high_cardinality`.
            "entity": np.repeat([f"e{i}" for i in range(n_entities)], per_entity),
            "f0": rng.normal(size=n),
            "label": rng.integers(0, 2, size=n),
        }
    )

    result = run_classification(
        frame, target="label", group_col="entity", models=["logistic"], seed=RANDOM_STATE
    )

    plan = result.column_plan
    assert "entity" not in plan.features
    assert "entity" not in plan.high_cardinality, "the group column must not be target-encoded"
    assert plan.excluded == ("entity",)
    assert result.split_plan.group_col == "entity"


def test_a_grouped_run_still_keeps_groups_off_the_fold_boundary():
    """Excluding the column from the features must not cost the guarantee it was
    there for — no entity may span a fold."""
    rng = np.random.default_rng(RANDOM_STATE)
    n_entities, per_entity = 40, 5
    n = n_entities * per_entity
    entities = np.repeat([f"e{i}" for i in range(n_entities)], per_entity)
    frame = pd.DataFrame(
        {"entity": entities, "f0": rng.normal(size=n), "value": rng.normal(size=n)}
    )

    result = run_prediction(frame, target="value", group_col="entity", n_splits=4)

    assert "entity" not in result.column_plan.features
    x = frame[list(result.column_plan.features)]
    for train_idx, test_idx in result.split_plan.split(x, frame["value"], frame=frame):
        assert_no_group_leakage(train_idx, test_idx, entities)


def test_comparison_frame_has_one_row_per_model(cancer_frame):
    result = run_classification(cancer_frame, target="malignant", seed=RANDOM_STATE)
    frame = result.comparison_frame()

    assert len(frame) == len(result.models)
    assert list(frame["model"]) == [m.name for m in result.models]
    assert frame["baseline"].sum() == 1


def test_missing_target_raises(cancer_frame):
    with pytest.raises(KeyError, match="absent"):
        run_classification(cancer_frame, target="absent")


def test_binary_output_on_a_multiclass_target_raises():
    x, y = make_classification(
        n_samples=200, n_features=6, n_informative=4, n_classes=3, random_state=RANDOM_STATE
    )
    frame = pd.DataFrame(x, columns=[f"f{i}" for i in range(6)])
    frame["target"] = y

    with pytest.raises(ValueError, match="output='binary'"):
        run_classification(frame, target="target", output="binary")


def test_single_valued_target_raises(cancer_frame):
    frame = cancer_frame.copy()
    frame["malignant"] = 1
    with pytest.raises(ValueError, match="at least 2"):
        run_classification(frame, target="malignant")


def test_multiclass_run_produces_per_class_metrics():
    x, y = make_classification(
        n_samples=400,
        n_features=8,
        n_informative=5,
        n_classes=3,
        random_state=RANDOM_STATE,
    )
    frame = pd.DataFrame(x, columns=[f"f{i}" for i in range(8)])
    frame["target"] = y

    result = run_classification(frame, target="target", output="multiclass", seed=RANDOM_STATE)

    assert result.output == "multiclass"
    assert set(result.best.metrics.per_class) == {"0", "1", "2"}
    assert result.best.curves == {}, "PR/ROC curves are binary-only"


# ── clustering ───────────────────────────────────────────────────────────────


def test_clustering_finds_the_planted_structure():
    x, _ = make_blobs(n_samples=300, centers=4, cluster_std=0.8, random_state=RANDOM_STATE)
    frame = pd.DataFrame(x, columns=["a", "b"])

    result = run_clustering(frame, n_clusters=4, seed=RANDOM_STATE)

    assert result.family == "clustering"
    assert result.target is None
    assert result.split_plan is None, "there is no held-out split without a target"
    assert len(result.models) >= 3

    best = result.best
    assert best.metrics.silhouette > 0.4, "well-separated blobs should score highly"
    assert best.metrics.n_clusters >= 2


def test_clustering_honours_n_clusters_where_the_algorithm_takes_one():
    x, _ = make_blobs(n_samples=200, centers=3, random_state=RANDOM_STATE)
    frame = pd.DataFrame(x, columns=["a", "b"])

    result = run_clustering(frame, models=["kmeans"], n_clusters=5, seed=RANDOM_STATE)
    assert result.models[0].metrics.n_clusters == 5


def test_clustering_models_are_pipelines_too():
    x, _ = make_blobs(n_samples=200, centers=3, random_state=RANDOM_STATE)
    frame = pd.DataFrame(x, columns=["a", "b"])

    result = run_clustering(frame, seed=RANDOM_STATE)
    result.assert_no_transform_outside_pipeline()


# ── prediction ───────────────────────────────────────────────────────────────


def test_prediction_recovers_a_linear_signal():
    x, y = make_regression(
        n_samples=400, n_features=6, n_informative=4, noise=8.0, random_state=RANDOM_STATE
    )
    frame = pd.DataFrame(x, columns=[f"f{i}" for i in range(6)])
    frame["value"] = y

    result = run_prediction(frame, target="value", seed=RANDOM_STATE)

    assert result.family == "prediction"
    assert result.baseline is not None and result.baseline.name == "linear"
    assert result.best.metrics.r2 > 0.9, "a linear signal should be recovered nearly exactly"
    assert result.best.metrics.rmse > 0
    result.assert_no_transform_outside_pipeline()


def test_prediction_uses_kfold_not_stratified_for_a_continuous_target():
    """Stratification is undefined for a continuous target — it would try to
    balance folds by distinct float value."""
    x, y = make_regression(n_samples=200, n_features=4, random_state=RANDOM_STATE)
    frame = pd.DataFrame(x, columns=[f"f{i}" for i in range(4)])
    frame["value"] = y

    result = run_prediction(frame, target="value", seed=RANDOM_STATE)
    assert result.split_plan.kind == "kfold"
    assert "stratification is undefined" in result.split_plan.reason


def test_prediction_on_a_categorical_target_raises(cancer_frame):
    frame = cancer_frame.copy()
    frame["label"] = frame["malignant"].map({0: "benign", 1: "malignant"})

    with pytest.raises(TypeError, match="not numeric"):
        run_prediction(frame, target="label")


def test_prediction_respects_a_group_column():
    """Grouped rows must not span the fold boundary — the splitter choice has to
    survive the trip through the workflow, not just exist in isolation."""
    rng = np.random.default_rng(RANDOM_STATE)
    n_entities, per_entity = 20, 10
    frame = pd.DataFrame(
        {
            "entity": np.repeat([f"e{i}" for i in range(n_entities)], per_entity),
            "f0": rng.normal(size=n_entities * per_entity),
            "value": rng.normal(size=n_entities * per_entity),
        }
    )

    result = run_prediction(
        frame, target="value", group_col="entity", n_splits=4, seed=RANDOM_STATE
    )
    assert result.split_plan.kind == "group"
    assert result.split_plan.group_col == "entity"
