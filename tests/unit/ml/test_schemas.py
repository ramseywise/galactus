"""The typed stage boundaries.

These tests are mostly about what the types make *impossible*. A schema whose
invalid states are still constructible is documentation, not a contract — so each
test here asserts a rejection rather than an acceptance.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ml.schemas import (
    ColumnPlan,
    MetricValue,
    ModelReport,
    OperatingPoint,
    ParkedQuestion,
    RunConfig,
    SplitSpec,
    ThresholdPolicy,
)


def test_a_stage_contract_rejects_unknown_keys():
    """`extra="forbid"`: a typo'd field name must fail loudly, not be absorbed."""
    with pytest.raises(ValidationError):
        SplitSpec(kind="holdout", reason="quick check", n_splitz=3)


def test_a_stage_contract_is_frozen():
    """A downstream stage must not mutate an upstream stage's output."""
    spec = SplitSpec(kind="holdout", reason="quick check")
    with pytest.raises(ValidationError):
        spec.reason = "something else"


# ── ColumnPlan: the silent-drop guard ────────────────────────────────────────


def test_excluded_columns_carry_a_reason():
    plan = ColumnPlan(numeric=("age",), excluded={"borrower_id": "near-unique identifier"})
    assert plan.excluded["borrower_id"]


def test_a_column_cannot_be_both_a_feature_and_excluded():
    with pytest.raises(ValidationError, match="both a feature and excluded"):
        ColumnPlan(numeric=("age",), excluded={"age": "changed my mind"})


def test_a_column_cannot_sit_in_two_buckets():
    """Being both numeric and categorical is contradictory, and would silently
    double the column in `feature_names`."""
    with pytest.raises(ValidationError, match="more than one bucket"):
        ColumnPlan(numeric=("age",), categorical=("age",))


def test_feature_names_covers_every_bucket():
    plan = ColumnPlan(numeric=("a",), categorical=("b",), ordinal=("c",), high_cardinality=("d",))
    assert plan.feature_names == ("a", "b", "c", "d")


# ── SplitSpec: a split kind needs its column ─────────────────────────────────


def test_group_split_requires_a_group_column():
    with pytest.raises(ValidationError, match="requires group_col"):
        SplitSpec(kind="group_kfold", reason="one row per borrower is not independent")


def test_time_series_split_requires_a_time_column():
    with pytest.raises(ValidationError, match="requires time_col"):
        SplitSpec(kind="time_series", reason="forecasting")


def test_a_valid_grouped_split_is_accepted():
    spec = SplitSpec(
        kind="group_kfold", reason="repeat borrowers", group_col="borrower_id", n_splits=5
    )
    assert spec.group_col == "borrower_id"


# ── RunConfig: family/output coherence and parked questions ──────────────────


def test_output_must_match_family():
    with pytest.raises(ValidationError, match="not valid for family"):
        RunConfig(family="classification", output="continuous", target="y")


def test_a_coherent_run_config_is_accepted():
    config = RunConfig(family="prediction", output="continuous", target="amount")
    assert config.seed == 42


def test_a_parked_question_carries_its_trigger():
    """Parking discipline surviving into runtime is the whole point — a parked
    question without a trigger is just a note that never gets revisited."""
    config = RunConfig(
        family="classification",
        output="binary",
        target="default",
        parked=(
            ParkedQuestion(
                question="What is the cost ratio of a false negative?",
                trigger="when the collections team gives a number",
            ),
        ),
    )
    assert config.parked[0].trigger


# ── ModelReport: honesty fields ──────────────────────────────────────────────


def test_beats_baseline_distinguishes_unknown_from_false():
    """None means "no baseline existed"; False means "lost to one". Collapsing
    them to False would report a missing comparison as a defeat."""
    report = ModelReport(
        model_name="logistic",
        metrics=(MetricValue(name="pr_auc", mean=0.4),),
        split=SplitSpec(kind="holdout", reason="smoke test"),
    )
    assert report.beats_baseline is None


def test_a_failed_candidate_records_why():
    """The catboost failure mode: a candidate that vanishes from the table with
    no recorded reason."""
    report = ModelReport(
        model_name="catboost",
        metrics=(),
        split=SplitSpec(kind="holdout", reason="smoke test"),
        failed_with="only one of random_seed, random_state should be initialized",
    )
    assert "random_seed" in report.failed_with


def test_metric_lookup_returns_none_for_an_absent_metric():
    report = ModelReport(
        model_name="logistic",
        metrics=(MetricValue(name="pr_auc", mean=0.4, std=0.02),),
        split=SplitSpec(kind="holdout", reason="smoke test"),
    )
    assert report.metric("pr_auc").mean == 0.4
    assert report.metric("roc_auc") is None


def test_metric_std_cannot_be_negative():
    with pytest.raises(ValidationError):
        MetricValue(name="pr_auc", mean=0.4, std=-0.1)


# ── ThresholdPolicy ──────────────────────────────────────────────────────────


def test_selected_point_must_be_one_of_the_offered_points():
    offered = OperatingPoint(threshold=0.5, precision=0.6, recall=0.4, coverage=0.1)
    other = OperatingPoint(threshold=0.9, precision=0.9, recall=0.1, coverage=0.01)

    with pytest.raises(ValidationError, match="not among points"):
        ThresholdPolicy(points=(offered,), selected=other)


def test_a_threshold_outside_zero_one_is_rejected():
    with pytest.raises(ValidationError):
        OperatingPoint(threshold=1.5, precision=0.6, recall=0.4, coverage=0.1)


def test_an_operating_point_defaults_to_in_sample():
    """The caveat that a caller should not have to remember to add."""
    point = OperatingPoint(threshold=0.5, precision=0.6, recall=0.4, coverage=0.1)
    assert point.in_sample is True
