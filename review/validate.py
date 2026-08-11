"""Mechanical validation of a returned finding.

Five checks, in order, first failure wins. Each carries a machine-readable
reason tag (`schema` / `prefix` / `sanyi` / `quoted_span` / `citation`) so the
Measurement rows — schema validity, quoted_span rate, skill-load fidelity —
have an instrument rather than a prose claim.

Ported from `guacamayo/review/validation.py`, folding in `sanyi.py`'s violation
tables and adding the three checks the agent collapse requires.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import ValidationError

from review.models import MergeImpact, Reporter, ReviewFinding

# Lifted verbatim from `guacamayo/review/sanyi.py`. Authoritative source for the
# 11 codes is `.claude/skills/review_contracts/references/violations.md`.
_MERGE_IMPACT: dict[str, MergeImpact] = {
    # 不易 Buyi — invariant violations
    "BY-1": MergeImpact.BLOCKER,
    "BY-2": MergeImpact.BLOCKER,
    "BY-3": MergeImpact.BLOCKER,
    "BY-4": MergeImpact.BLOCKER,
    # 简易 Jianyi — complexity/entropy violations
    "JY-1": MergeImpact.IMPORTANT,
    "JY-2": MergeImpact.IMPORTANT,
    "JY-3": MergeImpact.IMPORTANT,
    # 变易 Bianyi — changeable-value violations
    "BN-1": MergeImpact.SUGGESTION,
    # Hygiene / unassigned
    "MG-1": MergeImpact.NIT,
    "UN-1": MergeImpact.NIT,
    "UN-2": MergeImpact.NIT,
}

# Dimensions whose findings rest on a written convention rather than on the code
# alone, and so may be required to cite the spec (check 5).
_SPEC_BOUND_REPORTERS = frozenset({Reporter.RUNTIME, Reporter.SAFEGUARDS, Reporter.CONTRACTS})

# F4 trigger, stated narrowly and deterministically: a spec *path* mention.
_SPEC_PATH_PATTERN = re.compile(r"\.claude/specs/agent-[\w-]+\.md", re.IGNORECASE)


def _normalize(text: str) -> str:
    """Collapse all whitespace runs to single spaces and strip.

    `quoted_span` is model-produced text quoted back from source; indentation
    and line-continuation whitespace are noise, not evidence.
    """
    return " ".join(text.split())


def validate_finding(
    data: dict,
    assigned_reporter: str | None = None,
    repo_root: str = ".",
) -> tuple[bool, str, str]:
    """Validate one finding.

    Args:
        data: The raw finding dict as returned by a dispatch.
        assigned_reporter: The dimension this dispatch was told to load. When
            given, the finding's own `reporter` must match it (F7).
        repo_root: Root the finding's file paths are relative to.

    Returns:
        `(ok, reason_tag, message)`. `reason_tag` is "" when ok, else one of
        `schema` / `prefix` / `sanyi` / `quoted_span` / `citation`.
    """
    # 1. Schema. The `dimension_id_prefix_matches_reporter` validator fires here,
    #    so a prefix/reporter mismatch is tagged `prefix`, not `schema`.
    try:
        finding = ReviewFinding.model_validate(data)
    except ValidationError as e:
        tag = "prefix" if "requires id prefix" in str(e) else "schema"
        return False, tag, e.json()

    # 2. F7 skill-load verification. A dispatch told to load `review_safety`
    #    that returns a `CR-` finding did not load the skill it was assigned.
    if assigned_reporter is not None and finding.reporter.value != assigned_reporter:
        return (
            False,
            "prefix",
            (
                f"dispatch was assigned reporter={assigned_reporter!r} but finding "
                f"declares reporter={finding.reporter.value!r}"
            ),
        )

    # 3. F1 SANYI cross-check. A violation code fixes its own merge impact; a
    #    finding cannot carry BY-1 as a nit.
    if finding.reporter == Reporter.CONTRACTS and finding.severity.violation_code:
        code = finding.severity.violation_code
        expected = _MERGE_IMPACT.get(code)
        if expected is None:
            return False, "sanyi", f"Unknown SANYI violation code: {code!r}"
        if finding.severity.merge_impact != expected:
            return (
                False,
                "sanyi",
                (
                    f"SANYI finding with violation_code={code!r} must have "
                    f"merge_impact={expected.value!r}, "
                    f"got {finding.severity.merge_impact.value!r}"
                ),
            )

    # 4. F5 quoted_span. Read the cited line range and string-match the span
    #    against it, whitespace-normalized. A finding whose cited line does not
    #    contain the text it quotes did not read that line.
    ok, message = _check_quoted_span(finding, repo_root)
    if not ok:
        return False, "quoted_span", message

    # 5. F4 spec citation.
    ok, message = _check_spec_citation(finding)
    if not ok:
        return False, "citation", message

    return True, "", ""


def _check_quoted_span(finding: ReviewFinding, repo_root: str) -> tuple[bool, str]:
    """Match `quoted_span` against `location.files[0]`'s cited lines.

    Whitespace-normalized over `start_line..end_line` with a ±1-line window —
    the loosest reading that still rejects a span the source does not contain.
    A finding with no line anchor is not checkable and passes.
    """
    if not finding.quoted_span.strip():
        return False, "quoted_span is empty"
    if not finding.location.files:
        return False, "finding has no file location to verify quoted_span against"

    file_loc = finding.location.files[0]
    if file_loc.start_line is None:
        return True, ""  # No line anchor — nothing to match against.

    path = Path(file_loc.path)
    if not path.is_absolute():
        path = Path(repo_root) / path
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError as e:
        return False, f"cannot read {file_loc.path!r} to verify quoted_span: {e}"

    end_line = file_loc.end_line or file_loc.start_line
    start_idx = max(0, file_loc.start_line - 1 - 1)  # ±1-line window
    end_idx = min(len(lines), end_line + 1)
    window = _normalize(" ".join(lines[start_idx:end_idx]))

    if _normalize(finding.quoted_span) not in window:
        return (
            False,
            (
                f"quoted_span not found at {file_loc.path}:{file_loc.start_line}"
                f"-{end_line} (±1 line)"
            ),
        )
    return True, ""


def _check_spec_citation(finding: ReviewFinding) -> tuple[bool, str]:
    """Require `spec_citation` when a finding asserts a convention breach.

    Trigger (narrow and deterministic): the finding comes from `runtime`,
    `safeguards`, or `contracts` **and** a `.claude/specs/agent-*.md` path
    appears in `basis` or in the claim text. Naming a spec is what makes a
    finding a convention claim; naming it without citing a section is the
    unfalsifiable shape F4 exists to reject.
    """
    if finding.reporter not in _SPEC_BOUND_REPORTERS:
        return True, ""
    if finding.spec_citation:
        return True, ""

    haystack = " ".join(
        [
            *finding.basis,
            finding.claim.title,
            finding.claim.observation,
            finding.claim.failure_scenario or "",
            finding.claim.impact or "",
        ]
    )
    if _SPEC_PATH_PATTERN.search(haystack):
        return (
            False,
            (
                f"reporter={finding.reporter.value!r} finding references a convention "
                "spec but carries no spec_citation"
            ),
        )
    return True, ""
