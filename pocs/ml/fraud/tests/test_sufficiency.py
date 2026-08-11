"""Tests for the sufficiency guard. Refusal is the primary behaviour under test, not an
error case — a thin-frame fixture that returns `sufficient=False` is a passing test."""

from __future__ import annotations

from sufficiency import MIN_POSITIVES_PER_FOLD, assess_sufficiency


def test_refuses_on_a_thin_frame(thin_frame):
    y, plan = thin_frame
    verdict = assess_sufficiency(y, plan)
    assert verdict.sufficient is False
    assert verdict.min_positives_in_fold == 2
    assert "2" in verdict.reason
    assert str(MIN_POSITIVES_PER_FOLD) in verdict.reason


def test_accepts_a_healthy_frame(healthy_frame):
    y, plan = healthy_frame
    verdict = assess_sufficiency(y, plan)
    assert verdict.sufficient is True
    assert verdict.min_positives_in_fold >= MIN_POSITIVES_PER_FOLD
    assert verdict.threshold_reportable is True


def test_boundary_at_exactly_the_floor_is_sufficient(boundary_frame):
    """Every fold has exactly MIN_POSITIVES_PER_FOLD positives — the line is inclusive."""
    y, plan = boundary_frame
    verdict = assess_sufficiency(y, plan)
    assert verdict.min_positives_in_fold == MIN_POSITIVES_PER_FOLD
    assert verdict.sufficient is True


def test_refuses_on_the_thinnest_fold_not_the_average(healthy_and_one_thin_frame):
    """Four folds at 40 positives and one at 2 averages to 32.8 — comfortably above the
    line, and completely wrong. The guard reads the minimum for exactly this reason."""
    y, plan = healthy_and_one_thin_frame
    verdict = assess_sufficiency(y, plan)
    assert verdict.sufficient is False
    assert verdict.min_positives_in_fold == 2


def test_zero_positives_refuses_without_a_zero_division_error(zero_positive_frame):
    y, plan = zero_positive_frame
    verdict = assess_sufficiency(y, plan)  # must not raise
    assert verdict.sufficient is False
    assert verdict.min_positives_in_fold == 0
    assert verdict.n_positives == 0
    assert verdict.prevalence == 0.0


def test_assess_sufficiency_never_raises(thin_frame, healthy_frame, zero_positive_frame):
    for y, plan in (thin_frame, healthy_frame, zero_positive_frame):
        assess_sufficiency(y, plan)  # no exception is the assertion
