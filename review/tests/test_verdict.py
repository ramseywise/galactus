"""The ladder, rung by rung.

The first four cases are the revised rung 0. Any two of them pass under the old
global-emptiness rule, so all four together are what prove the fix landed:
scoped poison must fire, and a clean diff must not.
"""

from __future__ import annotations

import random

import pytest

from review.models import (
    Category,
    CommentType,
    EvidenceState,
    MergeDecision,
    MergeImpact,
    Reporter,
    ReporterDispatchEntry,
    ReviewFinding,
    Severity,
)
from review.verdict import compute_verdict

HIT = {
    "file": "a.py",
    "line": 1,
    "pattern_name": "preaudited_claim",
    "matched_text": "pre-audited",
}


def finding(reporter: Reporter, prefix: str, impact: MergeImpact, n: int = 1) -> ReviewFinding:
    return ReviewFinding(
        id=f"{prefix}-{n:03d}",
        reporter=reporter,
        category=Category.CORRECTNESS,
        evidence_state=EvidenceState.VERIFIED,
        location={"files": [{"path": "a.py", "start_line": 1, "end_line": 1}]},
        claim={"title": "t", "observation": "o"},
        severity=Severity(merge_impact=impact),
        comment_type=CommentType.NIT,
        quoted_span="x = 1",
    )


def completed(reporter: Reporter, count: int) -> ReporterDispatchEntry:
    return ReporterDispatchEntry(
        reporter=reporter, status="completed", finding_count=count
    )


NIT = MergeImpact.NIT


# --- Rung 0 -----------------------------------------------------------------


def test_rung0_blunt_poison_all_empty_with_hit():
    dispatch = [completed(r, 0) for r in Reporter]
    assert compute_verdict([], dispatch, [HIT]) == MergeDecision.INSUFFICIENT_CONTEXT


def test_rung0_scoped_poison_one_empty_with_hit():
    """The case the original all-empty rule approved.

    Two dimensions silenced, six returning ordinary nits. Not-all-empty, no
    dispatch failed, no blocker among the nits — the old ladder walked straight
    to `approve` on a poisoned diff.
    """
    reporters = list(Reporter)
    dispatch = [completed(reporters[0], 0)] + [completed(r, 1) for r in reporters[1:7]]
    findings = [
        finding(Reporter.CORRECTNESS, "CR", NIT, i) for i in range(1, 7)
    ]
    assert compute_verdict(findings, dispatch, [HIT]) == MergeDecision.INSUFFICIENT_CONTEXT


def test_rung0_clean_diff_all_empty_no_hit_approves():
    """The case the original rule refused.

    A typo fix legitimately finds nothing anywhere. Without this test the
    subsystem can never approve anything and `insufficient_context` decays into
    noise the operator learns to ignore.
    """
    dispatch = [completed(r, 0) for r in Reporter]
    assert compute_verdict([], dispatch, []) == MergeDecision.APPROVE


def test_rung0_hit_without_empty_dispatch_falls_through():
    """A hit alone is evidence, not a verdict.

    False positives are expected from the loose patterns; the conjunction is
    what keeps them from moving the verdict.
    """
    dispatch = [completed(r, 1) for r in Reporter]
    findings = [finding(Reporter.CORRECTNESS, "CR", NIT)]
    assert compute_verdict(findings, dispatch, [HIT]) == MergeDecision.APPROVE


# --- Rungs 1-4 --------------------------------------------------------------


def test_rung1_failed_dispatch():
    dispatch = [
        completed(Reporter.CORRECTNESS, 1),
        ReporterDispatchEntry(reporter=Reporter.SAFETY, status="failed"),
    ]
    assert compute_verdict([], dispatch, []) == MergeDecision.INSUFFICIENT_CONTEXT


def test_rung1_dropped_dispatch():
    dispatch = [ReporterDispatchEntry(reporter=Reporter.SAFETY, status="dropped")]
    assert compute_verdict([], dispatch, []) == MergeDecision.INSUFFICIENT_CONTEXT


def test_rung1_two_validation_failures():
    dispatch = [completed(Reporter.CORRECTNESS, 1)]
    assert (
        compute_verdict([], dispatch, [], validation_failures=2)
        == MergeDecision.INSUFFICIENT_CONTEXT
    )


def test_one_validation_failure_does_not_trip_rung1():
    dispatch = [completed(Reporter.CORRECTNESS, 1)]
    assert compute_verdict([], dispatch, [], validation_failures=1) == MergeDecision.APPROVE


def test_rung2_blocker():
    dispatch = [completed(Reporter.CORRECTNESS, 1)]
    findings = [finding(Reporter.CORRECTNESS, "CR", MergeImpact.BLOCKER)]
    assert compute_verdict(findings, dispatch, []) == MergeDecision.REQUEST_CHANGES


def test_rung3_important_only():
    dispatch = [completed(Reporter.CORRECTNESS, 1)]
    findings = [finding(Reporter.CORRECTNESS, "CR", MergeImpact.IMPORTANT)]
    assert compute_verdict(findings, dispatch, []) == MergeDecision.COMMENT


def test_rung4_nits_only():
    dispatch = [completed(Reporter.CORRECTNESS, 1)]
    findings = [finding(Reporter.CORRECTNESS, "CR", NIT)]
    assert compute_verdict(findings, dispatch, []) == MergeDecision.APPROVE


def test_rung1_beats_rung2_order_matters():
    """A blocker plus a failed dispatch is `insufficient_context`, not
    `request_changes` — the review did not run, so its findings are partial."""
    dispatch = [
        completed(Reporter.CORRECTNESS, 1),
        ReporterDispatchEntry(reporter=Reporter.SAFETY, status="failed"),
    ]
    findings = [finding(Reporter.CORRECTNESS, "CR", MergeImpact.BLOCKER)]
    assert compute_verdict(findings, dispatch, []) == MergeDecision.INSUFFICIENT_CONTEXT


def test_rung0_beats_rung2():
    """Rung 0 wins over a blocker too: under injection, what came back cannot
    be trusted to be complete."""
    dispatch = [completed(Reporter.CORRECTNESS, 1), completed(Reporter.SAFETY, 0)]
    findings = [finding(Reporter.CORRECTNESS, "CR", MergeImpact.BLOCKER)]
    assert compute_verdict(findings, dispatch, [HIT]) == MergeDecision.INSUFFICIENT_CONTEXT


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_determinism_under_shuffle(seed: int):
    dispatch = [completed(Reporter.CORRECTNESS, 3)]
    findings = [
        finding(Reporter.CORRECTNESS, "CR", NIT, 1),
        finding(Reporter.CORRECTNESS, "CR", MergeImpact.IMPORTANT, 2),
        finding(Reporter.CORRECTNESS, "CR", MergeImpact.BLOCKER, 3),
    ]
    shuffled = list(findings)
    random.Random(seed).shuffle(shuffled)
    assert compute_verdict(shuffled, dispatch, []) == compute_verdict(findings, dispatch, [])
