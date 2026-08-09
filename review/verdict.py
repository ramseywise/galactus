"""The merge-decision ladder, as a pure function.

No I/O, no model call, no filesystem access. Purity is what makes the
determinism claim testable: the same inputs yield the same verdict, and the
verdict is computed by running this, never by an agent reading the rungs.
"""

from __future__ import annotations

from review.models import (
    MergeDecision,
    MergeImpact,
    ReporterDispatchEntry,
    ReviewFinding,
)


def compute_verdict(
    findings: list[ReviewFinding],
    dispatch: list[ReporterDispatchEntry],
    injection_hits: list[dict],
    validation_failures: int = 0,
) -> MergeDecision:
    """Return the merge decision. Five rungs, first match wins.

    `injection_hits` is required, not optional: rung 0 cannot be evaluated
    without `signals.detect_injection`'s output, so the two halves of the
    prompt-injection defence are one signature rather than two files someone
    might ship one of.
    """
    # Rung 0 — silence conjoined with injection evidence.
    #
    # Emptiness alone carries no information: a clean diff legitimately yields
    # zero findings everywhere, and keying on all-empty would both refuse clean
    # diffs and wave through scoped poison that silences two dimensions while
    # six others return nits. One silenced dimension plus an injection hit is
    # the signal; either alone is not.
    if injection_hits and any(
        e.status == "completed" and e.finding_count == 0 for e in dispatch
    ):
        return MergeDecision.INSUFFICIENT_CONTEXT

    # Rung 1 — the review did not actually run.
    if any(e.status in {"failed", "dropped"} for e in dispatch):
        return MergeDecision.INSUFFICIENT_CONTEXT
    if validation_failures >= 2:
        return MergeDecision.INSUFFICIENT_CONTEXT

    # Rungs 2-4 — what the review found.
    impacts = {f.severity.merge_impact for f in findings}
    if MergeImpact.BLOCKER in impacts:
        return MergeDecision.REQUEST_CHANGES
    if MergeImpact.IMPORTANT in impacts:
        return MergeDecision.COMMENT
    return MergeDecision.APPROVE
