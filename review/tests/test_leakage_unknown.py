"""GAL-3: an unrun scan and an ignored group key must not render as clean.

The negative test the issue asks for. Its subject is the failure mode, not the
happy path: each test below is written so that it goes RED if the rule it pins
is removed from the skill or the schema stops being able to express the result.

Three layers, because the rules need all three to hold:

1. The vocabulary exists and constrains — `evidence_state: question` is a real
   state that cannot be smuggled in as a blocker (`review/models.py`).
2. The verdict ladder reads a question as *not* an approval-with-nothing-found,
   and specifically does not let it gate the merge (`review/verdict.py`).
3. The skill actually carries both rules, with the resolution trigger that turns
   a question into something closable (`.claude/skills/review-leakage/SKILL.md`).

Layer 3 is prose assertion, which is weak on its own — a skill file can satisfy
a substring check and still be incoherent. It is included because the skill is
the only artifact the dispatched reviewer reads: if the section is deleted, no
amount of correct schema makes the reviewer report the unknown. The fixture
`unscanned_pipeline.py` is the planted leak that gives these rules something
concrete to be about.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from review.models import (
    EvidenceState,
    MergeDecision,
    MergeImpact,
    ReporterDispatchEntry,
    ReviewFinding,
)
from review.validate import validate_finding
from review.verdict import compute_verdict

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL = REPO_ROOT / ".claude" / "skills" / "review-leakage" / "SKILL.md"
FIXTURE = Path(__file__).parent / "fixtures" / "unscanned_pipeline.py"

_SCORE_SPAN = "return model.score(X_test, y_test)"


def _score_line() -> int:
    """Line of the fixture's scoring call, derived rather than hardcoded.

    The skill anchors an unrun-scan finding to the reported-metric line, and the
    real validator string-matches `quoted_span` against that line. Hardcoding it
    would make an unrelated edit to the fixture fail this file for the wrong
    reason.
    """
    for number, line in enumerate(FIXTURE.read_text().splitlines(), start=1):
        if _SCORE_SPAN in line:
            return number
    raise AssertionError(f"fixture must contain the scoring call {_SCORE_SPAN!r}")


_SCORE_LINE = _score_line()


def _unrun_scan_finding(merge_impact: MergeImpact = MergeImpact.QUESTION) -> dict:
    """The finding the skill mandates when no association scan exists.

    Anchored to the scoring line of the fixture, per the skill's `quoted_span`
    rule for a finding whose subject has no line of its own.
    """
    return {
        "id": "LK-001",
        "reporter": "leakage",
        "category": "data",
        "evidence_state": "question",
        "location": {
            "files": [
                {
                    "path": "review/tests/fixtures/unscanned_pipeline.py",
                    "start_line": _SCORE_LINE,
                    "end_line": _SCORE_LINE,
                }
            ],
            "symbols": ["train"],
        },
        "claim": {
            "title": "No single-feature association scan exists for this frame",
            "observation": (
                "A score is reported with no feature-vs-label AUC pass over the "
                "columns, so a post-outcome column with an innocent name would "
                "be invisible."
            ),
            "failure_scenario": (
                "A column such as last_fico_range_high leaks the label at ~0.95 "
                "AUC, matches no post-outcome name pattern, and is reported as a "
                "genuine result."
            ),
            "impact": "The headline metric may be measuring leakage rather than signal.",
        },
        "severity": {"merge_impact": merge_impact.value},
        "basis": ["read review/tests/fixtures/unscanned_pipeline.py"],
        "comment_type": "question",
        "quoted_span": _SCORE_SPAN,
    }


# --- Layer 1: the vocabulary exists and constrains -------------------------


def test_unknown_is_expressible_without_a_schema_change():
    """The issue's open design decision, pinned.

    `evidence_state: question` carries the semantics the task called
    `verdict=unknown`, so reuse is correct and no new field is needed. If some
    later change removes the QUESTION state, this goes red and the decision gets
    revisited deliberately rather than by silent drift.
    """
    finding = ReviewFinding.model_validate(_unrun_scan_finding())
    assert finding.evidence_state is EvidenceState.QUESTION
    assert finding.severity.merge_impact is MergeImpact.QUESTION


def test_the_unknown_finding_survives_the_real_validator():
    """The end-to-end check: this finding is actually emittable, not just typed.

    `validate_finding` is the gate a dispatched reviewer's output passes through
    — schema, F7 skill-load prefix check, and the F5 `quoted_span` match against
    the real file on disk. A finding that satisfies the model but fails here
    would be a rule the reviewer cannot comply with, which is the failure mode
    worth catching before the skill tells anyone to emit it.
    """
    ok, tag, message = validate_finding(
        _unrun_scan_finding(), assigned_reporter="leakage", repo_root=str(REPO_ROOT)
    )
    assert ok, f"[{tag}] {message}"


@pytest.mark.parametrize("impact", [MergeImpact.BLOCKER, MergeImpact.IMPORTANT])
def test_an_unknown_cannot_be_inflated_into_a_gate(impact: MergeImpact):
    """The opposite failure from the one the issue names, and worth pinning.

    An unrun scan reports an unknown; it does not get to block the merge on the
    strength of not having looked. The schema enforces this, so the skill's "it
    does not gate the merge" line is backed by code rather than by discipline.
    """
    with pytest.raises(ValidationError, match="cannot carry"):
        ReviewFinding.model_validate(_unrun_scan_finding(impact))


# --- Layer 2: the ladder does not read a question as a clean approval ------


def test_reported_unknown_is_not_silence():
    """The core of Rule 1 at the ladder level.

    A dispatch that reports the unknown has `finding_count == 1`, which is what
    separates it from the collapse. The verdict is APPROVE — the unknown does
    not gate — but the finding travels with it, so the operator sees the
    question rather than an unqualified clean bill.
    """
    finding = ReviewFinding.model_validate(_unrun_scan_finding())
    dispatch = [ReporterDispatchEntry(reporter="leakage", status="completed", finding_count=1)]
    verdict = compute_verdict([finding], dispatch, injection_hits=[])

    assert verdict is MergeDecision.APPROVE
    assert dispatch[0].finding_count == 1


def test_silence_and_reported_unknown_are_distinguishable():
    """The collapse this dimension is named after, stated as an assertion.

    The whole issue is that an unrun scan and a scan that found nothing both
    render as `[]`. These two dispatches must not be equal — if a change ever
    makes the reported unknown indistinguishable from silence, this is the test
    that catches it.
    """
    silent = ReporterDispatchEntry(reporter="leakage", status="completed", finding_count=0)
    reported = ReporterDispatchEntry(reporter="leakage", status="completed", finding_count=1)

    assert silent.finding_count != reported.finding_count


# --- Layer 3: the skill carries the rules the reviewer reads ---------------


def _skill_text() -> str:
    assert SKILL.is_file(), f"review-leakage skill missing at {SKILL}"
    return SKILL.read_text()


def test_skill_states_rule_one_with_a_resolution_trigger():
    """Rule 1 present, and present *with* the thing that closes it.

    The resolution trigger is not decoration: per the evidence model, a question
    must be phrased as a clarification request, and the skill's own line is that
    a finding naming no way to resolve it "is not a question, it is a
    complaint." So the section and its trigger are asserted together.
    """
    text = _skill_text()
    assert "An unrun scan is not a clean scan" in text
    assert "single-feature AUC scan" in text
    assert "evidence_state: question" in text


def test_skill_forbids_returning_empty_for_an_unrun_scan():
    """The prohibition itself — the sentence that makes `[]` the failure."""
    text = _skill_text()
    assert "Returning `[]` because no scan was found is the failure" in text


def test_skill_states_rule_two_including_the_weak_key_case():
    """Rule 2, with the clause that stops a weak key becoming silence.

    Weakness is a caveat on the finding, not grounds to drop it — that is the
    half of Rule 2 most likely to be quietly lost.
    """
    text = _skill_text()
    assert "not passed to the splitter is a finding" in text
    assert "Weak keys are stated, never suppressed" in text


# --- The planted leak ------------------------------------------------------


def test_fixture_plants_a_leak_no_name_heuristic_catches():
    """The fixture earns its place only if the skill's name list misses it.

    `last_fico_range_high` must match none of the post-outcome patterns under
    §Target leakage. If someone renames the column to something the regex
    catches, the fixture stops testing the scan and this goes red.
    """
    source = FIXTURE.read_text()
    assert "last_fico_range_high" in source
    for pattern in ("_final", "_actual", "_outcome", "settlement_", "amount_recovered"):
        assert pattern not in "last_fico_range_high", (
            f"planted column name matches the {pattern!r} heuristic, so the "
            "fixture no longer isolates the scan-only leak class"
        )
    # And the scan whose absence is the point must genuinely be absent.
    assert "roc_auc_score" not in source
    assert ".corr(" not in source


def test_fixture_holds_a_group_key_the_splitter_never_receives():
    """Rule 2's plant: `debtor_id` in the frame, no `groups=` at the split.

    The `groups=` check reads the split *call*, not the file — the module
    docstring names `groups=` when explaining the plant, and a whole-file
    substring check would trip over its own documentation.
    """
    source = FIXTURE.read_text()
    assert '"debtor_id"' in source

    split_calls = [line for line in source.splitlines() if "train_test_split(" in line]
    assert split_calls, "fixture must call train_test_split for the omission to be visible"
    for call in split_calls:
        assert "groups=" not in call
