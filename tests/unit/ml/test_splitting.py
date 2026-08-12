"""Step 5 — leakage-safe splitting.

Every invariant in this module has a test that asserts it *raises*. A guard whose
failure path is never exercised is indistinguishable from a comment: it passes
the happy-path test either way, and only stops being real when someone needs it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold, StratifiedKFold

from ml.evaluation.splitting import (
    GroupLeakageError,
    SortedTimeSeriesSplit,
    TemporalLeakageError,
    assert_no_group_leakage,
    assert_temporal_order,
    make_splitter,
)

RANDOM_STATE = 42


@pytest.fixture
def grouped_frame() -> pd.DataFrame:
    """40 rows across 8 entities — every entity holds exactly 5 rows, so a random
    split would place each on both sides with near-certainty."""
    rng = np.random.default_rng(RANDOM_STATE)
    n_entities, per_entity = 8, 5
    return pd.DataFrame(
        {
            "entity": np.repeat([f"debtor_{i}" for i in range(n_entities)], per_entity),
            "feature": rng.normal(size=n_entities * per_entity),
            "target": rng.integers(0, 2, size=n_entities * per_entity),
        }
    )


@pytest.fixture
def timed_frame() -> pd.DataFrame:
    """60 rows over 60 consecutive days, deliberately shuffled so that a
    position-based split is *not* a temporal split unless the splitter sorts."""
    rng = np.random.default_rng(RANDOM_STATE)
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=60, freq="D"),
            "feature": rng.normal(size=60),
            "target": rng.integers(0, 2, size=60),
        }
    )
    return frame.sample(frac=1.0, random_state=RANDOM_STATE).reset_index(drop=True)


# ── the refusals ─────────────────────────────────────────────────────────────
# These are the reason the module exists. Each asserts the guard fires.


def test_time_col_with_stratify_raises():
    """The headline invariant: declaring time and asking for a random/stratified
    split is contradictory, and the contradiction is a hard failure."""
    with pytest.raises(TemporalLeakageError) as excinfo:
        make_splitter(time_col="date", stratify=True)

    message = str(excinfo.value)
    assert "date" in message, "the error must name the offending column"
    assert "stratify=False" in message, "the error must state the way forward"


def test_time_col_with_group_col_raises():
    """No grouped temporal splitter exists in sklearn; silently honouring one
    constraint and dropping the other is the failure mode being prevented."""
    with pytest.raises(TemporalLeakageError) as excinfo:
        make_splitter(time_col="date", group_col="entity", stratify=False)

    assert "date" in str(excinfo.value)
    assert "entity" in str(excinfo.value)


def test_assert_no_group_leakage_raises_on_overlap():
    groups = np.array(["a", "a", "b", "b", "c", "c"])
    # Row 0 and row 1 are both group "a" — split across the boundary.
    with pytest.raises(GroupLeakageError) as excinfo:
        assert_no_group_leakage(train_idx=[0, 2], test_idx=[1, 3], groups=groups)

    assert "both train and test" in str(excinfo.value)


def test_assert_temporal_order_raises_when_train_follows_test():
    times = np.arange(10)
    # Train on the late rows, test on the early ones — the exact inversion.
    with pytest.raises(TemporalLeakageError) as excinfo:
        assert_temporal_order(train_idx=[7, 8, 9], test_idx=[0, 1, 2], times=times)

    assert "not earlier" in str(excinfo.value)


def test_unparseable_time_column_raises(timed_frame):
    """A timestamp that does not parse sorts unpredictably, which would produce a
    non-temporal split while still looking like a temporal one."""
    frame = timed_frame.copy()
    frame["date"] = frame["date"].astype(str)
    frame.loc[0, "date"] = "not-a-date"

    splitter = SortedTimeSeriesSplit(time_col="date", n_splits=3)
    with pytest.raises(ValueError, match="do not parse"):
        list(splitter.split(frame))


def test_missing_time_column_raises(timed_frame):
    splitter = SortedTimeSeriesSplit(time_col="absent", n_splits=3)
    with pytest.raises(KeyError, match="absent"):
        list(splitter.split(timed_frame))


def test_time_split_on_array_raises_with_a_usable_message():
    splitter = SortedTimeSeriesSplit(time_col="date", n_splits=3)
    with pytest.raises(TypeError, match="DataFrame"):
        list(splitter.split(np.zeros((10, 2))))


def test_n_splits_below_two_raises():
    with pytest.raises(ValueError, match="at least 2"):
        make_splitter(n_splits=1)


# ── the properties the splitters must hold ───────────────────────────────────


def test_group_split_never_places_a_group_on_both_sides(grouped_frame):
    plan = make_splitter(group_col="entity", stratify=False, n_splits=4)
    assert isinstance(plan.splitter, GroupKFold)

    folds = 0
    for train_idx, test_idx in plan.split(
        grouped_frame, grouped_frame["target"], grouped_frame["entity"]
    ):
        # The assertion helper raises on overlap; calling it *is* the check.
        assert_no_group_leakage(train_idx, test_idx, grouped_frame["entity"].to_numpy())
        folds += 1
    assert folds == 4


def test_stratified_group_split_also_holds_the_group_property(grouped_frame):
    plan = make_splitter(group_col="entity", stratify=True, n_splits=4)
    assert isinstance(plan.splitter, StratifiedGroupKFold)

    for train_idx, test_idx in plan.split(
        grouped_frame, grouped_frame["target"], grouped_frame["entity"]
    ):
        assert_no_group_leakage(train_idx, test_idx, grouped_frame["entity"].to_numpy())


def test_split_plan_fills_groups_from_the_frame(grouped_frame):
    """The plan knows its own group column, so a caller who forgets to pass
    `groups` still gets a grouped split rather than a silent exception."""
    plan = make_splitter(group_col="entity", stratify=False, n_splits=4)

    for train_idx, test_idx in plan.split(grouped_frame, grouped_frame["target"]):
        assert_no_group_leakage(train_idx, test_idx, grouped_frame["entity"].to_numpy())


def test_time_split_never_trains_on_the_future(timed_frame):
    """The frame is shuffled, so this fails unless the splitter sorts by time
    before splitting — which is the whole reason SortedTimeSeriesSplit exists."""
    plan = make_splitter(time_col="date", stratify=False, n_splits=4)
    times = timed_frame["date"].to_numpy()

    folds = 0
    for train_idx, test_idx in plan.split(timed_frame, timed_frame["target"]):
        assert_temporal_order(train_idx, test_idx, times)
        folds += 1
    assert folds == 4


def test_time_split_indices_address_the_original_unsorted_frame(timed_frame):
    """Indices are mapped back to the caller's row order — a fold index must
    select the row the caller thinks it selects."""
    plan = make_splitter(time_col="date", stratify=False, n_splits=3)

    for train_idx, test_idx in plan.split(timed_frame, timed_frame["target"]):
        assert train_idx.max() < len(timed_frame)
        assert test_idx.max() < len(timed_frame)
        assert not set(train_idx) & set(test_idx), "a row cannot be in both sides"


def test_time_split_gap_excludes_rows_between_train_and_test(timed_frame):
    """`gap` drops rows immediately before the test fold — the embargo that stops
    a lagged feature from spanning the boundary."""
    plan = make_splitter(time_col="date", stratify=False, n_splits=3, gap=5)
    times = timed_frame["date"].to_numpy()

    for train_idx, test_idx in plan.split(timed_frame, timed_frame["target"]):
        assert_temporal_order(train_idx, test_idx, times)
        gap_days = (times[test_idx].min() - times[train_idx].max()) / np.timedelta64(1, "D")
        assert gap_days > 5, "the embargo must leave a real gap, not a nominal one"


def test_default_is_stratified_when_nothing_is_declared():
    plan = make_splitter()
    assert isinstance(plan.splitter, StratifiedKFold)
    assert plan.kind == "stratified"


def test_plan_records_a_reason_for_every_choice():
    """The report states its own validation strategy; that requires the plan to
    carry a reason rather than just a splitter object."""
    plans = [
        make_splitter(),
        make_splitter(group_col="entity", stratify=False),
        make_splitter(group_col="entity", stratify=True),
        make_splitter(time_col="date", stratify=False),
    ]
    for plan in plans:
        assert plan.reason, f"{plan.kind} has no recorded reason"
        assert plan.kind in plan.reason or len(plan.reason) > 20


def test_splits_are_deterministic_across_calls(grouped_frame):
    """random_state=42 everywhere — two identical calls yield identical folds."""
    first = make_splitter(group_col="entity", stratify=True, n_splits=4)
    second = make_splitter(group_col="entity", stratify=True, n_splits=4)

    for (train_a, test_a), (train_b, test_b) in zip(
        first.split(grouped_frame, grouped_frame["target"]),
        second.split(grouped_frame, grouped_frame["target"]),
        strict=True,
    ):
        np.testing.assert_array_equal(train_a, train_b)
        np.testing.assert_array_equal(test_a, test_b)
