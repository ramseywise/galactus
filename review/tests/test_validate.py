"""One accept, one reject per mechanism, and the reject reasons are tagged.

Fixtures are anchored on `runs/ai/marketing-comms/src/model/gateway.py:125`, which
really does read `import anthropic` — the `quoted_span` check is only meaningful
against real source.

That coupling is the point and also the maintenance cost: when the anchor line
moves, these tests fail by design. `test_anchor_line_is_the_expected_source`
below fails *first* and says so, so the next drift reads as "the anchor moved",
not as "the validator broke".
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from review.validate import validate_finding

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"


ANCHOR_PATH = "runs/ai/marketing-comms/src/model/gateway.py"
ANCHOR_LINE = 125
ANCHOR_TEXT = "import anthropic"


def load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text())


def test_anchor_line_is_the_expected_source():
    """Fail loudly when the anchor drifts, before the validator tests do.

    Every positive fixture quotes `import anthropic` at the anchor. If that line
    moves, the quoted_span check correctly rejects them — and six tests fail
    pointing at the validator instead of at the anchor. This test names the real
    cause: repoint the fixtures, never loosen the check.
    """
    lines = (REPO_ROOT / ANCHOR_PATH).read_text().splitlines()
    assert len(lines) >= ANCHOR_LINE, f"{ANCHOR_PATH} is shorter than line {ANCHOR_LINE}"
    actual = lines[ANCHOR_LINE - 1].strip()
    assert actual == ANCHOR_TEXT, (
        f"fixture anchor drifted: {ANCHOR_PATH}:{ANCHOR_LINE} reads {actual!r}, "
        f"expected {ANCHOR_TEXT!r}. Repoint the fixtures' start_line/end_line to "
        f"wherever {ANCHOR_TEXT!r} now lives; do not weaken the quoted_span check."
    )


def test_valid_finding_accepted():
    ok, reason, message = validate_finding(load("finding_valid"), repo_root=str(REPO_ROOT))
    assert ok, message
    assert reason == ""


@pytest.mark.parametrize(
    ("fixture", "expected_reason"),
    [
        ("finding_bad_prefix", "prefix"),
        ("finding_bad_quoted_span", "quoted_span"),
        ("finding_bad_sanyi", "sanyi"),
        ("finding_bad_citation", "citation"),
    ],
)
def test_malformed_finding_rejected_with_reason(fixture: str, expected_reason: str):
    ok, reason, message = validate_finding(load(fixture), repo_root=str(REPO_ROOT))
    assert not ok
    assert reason == expected_reason, message


def test_f7_load_verification_rejects_wrong_dimension():
    """A dispatch told to load `review_safety` that returns a CR- finding did
    not load the skill it was assigned. Under one shared agent this is the only
    in-band evidence of skill load."""
    ok, reason, _ = validate_finding(
        load("finding_valid"), assigned_reporter="safety", repo_root=str(REPO_ROOT)
    )
    assert not ok
    assert reason == "prefix"


def test_f7_passes_when_dimension_matches():
    ok, _, message = validate_finding(
        load("finding_valid"), assigned_reporter="correctness", repo_root=str(REPO_ROOT)
    )
    assert ok, message


def test_quoted_span_tolerates_whitespace_differences():
    data = load("finding_valid")
    data["quoted_span"] = "   import      anthropic  "
    ok, _, message = validate_finding(data, repo_root=str(REPO_ROOT))
    assert ok, message


def test_empty_quoted_span_rejected():
    data = load("finding_valid")
    data["quoted_span"] = "   "
    ok, reason, _ = validate_finding(data, repo_root=str(REPO_ROOT))
    assert not ok
    assert reason == "quoted_span"


def test_spec_bound_finding_with_citation_accepted():
    """F4 requires a citation only when a spec is invoked — supplying one clears it."""
    data = load("finding_bad_citation")
    data["spec_citation"] = ".claude/specs/agent-runtime.md#tool-side-effects"
    ok, _, message = validate_finding(data, repo_root=str(REPO_ROOT))
    assert ok, message


def test_spec_bound_finding_without_spec_mention_needs_no_citation():
    """The trigger is narrow on purpose: a runtime finding that rests on the
    code alone is not making a convention claim."""
    data = load("finding_bad_citation")
    data["claim"]["observation"] = "The adapter retries without a ceiling."
    data["basis"] = ["read the adapter"]
    ok, _, message = validate_finding(data, repo_root=str(REPO_ROOT))
    assert ok, message


def test_unknown_violation_code_rejected():
    data = load("finding_bad_sanyi")
    data["severity"]["violation_code"] = "ZZ-9"
    ok, reason, _ = validate_finding(data, repo_root=str(REPO_ROOT))
    assert not ok
    assert reason == "sanyi"
