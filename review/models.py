"""Canonical finding schema for the review subsystem.

Ported from `guacamayo/review/schemas/models.py`, narrowed to what a prototyping
review needs: no fingerprints, no sweep records, no trend reports, no
`ReviewReport` — the orchestrator writes its report as markdown.

The ten-way `REPORTER_ID_PREFIX` map is authoritative. The `review_*` skills
follow it; `review/tests/test_prefix_map.py` fails loudly when they drift.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class EvidenceState(StrEnum):
    VERIFIED = "verified"
    SUPPORTED = "supported"
    HYPOTHESIS = "hypothesis"
    QUESTION = "question"


class MergeImpact(StrEnum):
    BLOCKER = "blocker"
    IMPORTANT = "important"
    QUESTION = "question"
    SUGGESTION = "suggestion"
    NIT = "nit"


class NativeSeverity(StrEnum):
    BLOCKER = "blocker"
    WARNING = "warning"
    INFO = "info"
    NOTICE = "notice"


class CommentType(StrEnum):
    REQUEST_CHANGE = "request_change"
    QUESTION = "question"
    SUGGESTION = "suggestion"
    NIT = "nit"


class MergeDecision(StrEnum):
    APPROVE = "approve"
    COMMENT = "comment"
    REQUEST_CHANGES = "request_changes"
    INSUFFICIENT_CONTEXT = "insufficient_context"


class Category(StrEnum):
    CORRECTNESS = "correctness"
    # RELIABILITY and OPERATIONS still have no emitting dimension — Parallax's
    # `reliability-operations` was deliberately dropped from the original
    # nine-dimension menu. Kept so a dimension can be added without a schema
    # change, which is what `leakage` (the tenth) did: it emits DATA and
    # CORRECTNESS, both already present, so no Category was added for it.
    RELIABILITY = "reliability"
    SECURITY = "security"
    DATA = "data"
    ARCHITECTURE = "architecture"
    TESTING = "testing"
    OPERATIONS = "operations"
    AGENT_BEHAVIOR = "agent_behavior"
    EVALUATION = "evaluation"
    COMMUNICATION = "communication"


class Reporter(StrEnum):
    """The ten review dimensions.

    Guacamayo's legacy members (`akira_scan`, `sanyi`, `structure`,
    `agent_quality`) are not carried over: galactus has no persisted findings,
    so there is no back-compat obligation.

    `LEAKAGE` is the tabular-ML analogue of `SILENT_FAILURE` and is justified by
    the same argument: a leaked feature does not raise — it returns AUC 0.97 and
    reads as success.
    """

    INTENT = "intent"
    CORRECTNESS = "correctness"
    SILENT_FAILURE = "silent_failure"
    TESTING = "testing"
    SAFETY = "safety"
    ARCHITECTURE = "architecture"
    RUNTIME = "runtime"
    SAFEGUARDS = "safeguards"
    CONTRACTS = "contracts"
    LEAKAGE = "leakage"


# Maps dimension reporter → required finding ID prefix (e.g. correctness → "CR").
# Authoritative: `.claude/skills/review_*/SKILL.md` frontmatter must match this
# exactly, and `test_prefix_map.py` asserts it.
REPORTER_ID_PREFIX: dict[str, str] = {
    Reporter.INTENT: "IN",
    Reporter.CORRECTNESS: "CR",
    Reporter.SILENT_FAILURE: "SI",
    Reporter.TESTING: "TE",
    Reporter.SAFETY: "SF",
    Reporter.ARCHITECTURE: "AR",
    Reporter.RUNTIME: "RT",
    Reporter.SAFEGUARDS: "SG",
    Reporter.CONTRACTS: "CT",
    Reporter.LEAKAGE: "LK",
}


class FileLocation(BaseModel):
    path: str
    start_line: int | None = None
    end_line: int | None = None

    @model_validator(mode="after")
    def validate_line_range(self) -> FileLocation:
        if (
            self.start_line is not None
            and self.end_line is not None
            and self.end_line < self.start_line
        ):
            raise ValueError(
                f"end_line ({self.end_line}) must be >= start_line ({self.start_line})"
            )
        return self


class Location(BaseModel):
    files: list[FileLocation]
    symbols: list[str] = Field(default_factory=list)


class Claim(BaseModel):
    title: str
    observation: str
    failure_scenario: str | None = None
    impact: str | None = None


class Severity(BaseModel):
    source_native: NativeSeverity | None = None
    merge_impact: MergeImpact
    violation_code: str | None = None


_FINDING_ID_PATTERN = re.compile(r"^[A-Z]{2,}-\d{3,}$")


class ReviewFinding(BaseModel):
    id: str
    reporter: Reporter
    category: Category
    evidence_state: EvidenceState
    location: Location
    claim: Claim
    severity: Severity
    basis: list[str] = Field(default_factory=list)
    comment_type: CommentType
    plan_step: int | None = None
    # The literal source text at the cited line. Required: a finding that cannot
    # quote the code it cites did not read the code.
    quoted_span: str
    # Path + section of the convention spec a claimed breach rests on.
    spec_citation: str | None = None
    # True when the diff did not cause the problem — surgical scope.
    pre_existing: bool = False

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not _FINDING_ID_PATTERN.match(v):
            raise ValueError(f"id {v!r} must match {{SRC}}-{{NNN}} (e.g. CR-001)")
        return v

    @model_validator(mode="after")
    def dimension_id_prefix_matches_reporter(self) -> ReviewFinding:
        """Under the agent collapse this is skill-load verification, not naming.

        One `review` agent serves all ten dimensions, so the prefix is the only
        in-band evidence that the dispatch loaded the skill it was told to.
        """
        expected = REPORTER_ID_PREFIX.get(self.reporter)
        if expected is not None:
            actual_prefix = self.id.split("-")[0]
            if actual_prefix != expected:
                raise ValueError(
                    f"reporter={self.reporter.value!r} requires id prefix {expected!r}, "
                    f"got {actual_prefix!r} in id={self.id!r}"
                )
        return self

    @model_validator(mode="after")
    def question_state_constrains_impact(self) -> ReviewFinding:
        if self.evidence_state == EvidenceState.QUESTION and self.severity.merge_impact not in (
            MergeImpact.QUESTION,
            MergeImpact.SUGGESTION,
            MergeImpact.NIT,
        ):
            raise ValueError(
                "evidence_state=question cannot carry "
                f"merge_impact={self.severity.merge_impact.value}"
            )
        return self


class ReporterDispatchEntry(BaseModel):
    reporter: Reporter
    status: str  # completed, skipped, failed, dropped
    skip_reason: str | None = None
    finding_count: int = 0

    @model_validator(mode="after")
    def skipped_requires_reason(self) -> ReporterDispatchEntry:
        if self.status == "skipped" and not self.skip_reason:
            raise ValueError("skip_reason is required when status is 'skipped'")
        return self
