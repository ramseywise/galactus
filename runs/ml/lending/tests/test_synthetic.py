"""Tests for the synthetic fixture twins — determinism, twin-ness, and guard behaviour.

Guard trips are asserted through the *real* `prepare_frame` path wherever the pipeline
allows it. The one place it does not: an intact `prepare_frame` drops exact-name
`LEAKAGE_COLUMNS` members, so plant (i) cannot survive it by construction — guard (a)
is therefore asserted against the raw planted frame (simulating the drop regressing,
which is the failure (a) exists to catch), alongside proof that the drop currently holds.
"""

from __future__ import annotations

import pandas as pd
import pytest

import synthetic
from frame import GROUP_COL, TARGET, prepare_frame
from guards import GuardError, assert_excluded_absent, single_feature_auc_alarm


def test_same_seed_same_frames():
    pd.testing.assert_frame_equal(synthetic.clean_frame(3), synthetic.clean_frame(3))
    pd.testing.assert_frame_equal(synthetic.planted_leak_frame(3), synthetic.planted_leak_frame(3))


def test_different_seeds_differ():
    with pytest.raises(AssertionError):
        pd.testing.assert_frame_equal(synthetic.clean_frame(3), synthetic.clean_frame(4))


def test_twins_are_identical_outside_the_plants():
    clean = synthetic.clean_frame(3)
    planted = synthetic.planted_leak_frame(3)
    assert set(planted.columns) - set(clean.columns) == {"recoveries", "post_outcome_score"}
    pd.testing.assert_frame_equal(planted[clean.columns], clean)


def test_prevalence_is_exact_by_construction(clean_frame):
    df = prepare_frame(clean_frame)
    assert len(df) == synthetic.N_RESOLVED
    assert df[TARGET].mean() == pytest.approx(synthetic.SYNTHETIC_PREVALENCE)


def test_clean_twin_passes_guards_through_prepare_frame(clean_frame):
    df = prepare_frame(clean_frame)
    assert_excluded_absent(df)
    single_feature_auc_alarm(df)
    # The frame is fit-shaped: label and group key present, sources gone.
    assert TARGET in df.columns
    assert GROUP_COL in df.columns


def test_planted_twin_trips_auc_alarm_through_prepare_frame(planted_leak_frame):
    """Plant (ii) survives the drops — guard (b) must catch it, naming it."""
    df = prepare_frame(planted_leak_frame)
    with pytest.raises(GuardError) as exc_info:
        single_feature_auc_alarm(df)
    assert "post_outcome_score" in str(exc_info.value)


def test_planted_twin_trips_excluded_guard_on_raw_frame(planted_leak_frame):
    """Plant (i) against guard (a) directly: the raw frame stands in for a frame the
    drop failed to clean, which is the regression (a) exists to abort."""
    with pytest.raises(GuardError) as exc_info:
        assert_excluded_absent(planted_leak_frame)
    assert "recoveries" in str(exc_info.value)


def test_prepare_frame_currently_drops_plant_one(planted_leak_frame):
    """The complement of the raw-frame test above: today's drop does hold, so (a)'s
    trip can only ever mean a regression, never a false alarm on the intact path."""
    df = prepare_frame(planted_leak_frame)
    assert "recoveries" not in df.columns
    assert_excluded_absent(df)
