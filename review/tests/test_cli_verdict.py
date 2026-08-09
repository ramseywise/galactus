"""The `verdict` subcommand's payload boundary.

`test_verdict.py` covers the ladder as a pure function over typed inputs. This
covers what happens before those types exist: everything reaching
`compute_verdict` arrives as untyped JSON on stdin, and the orchestrator that
pipes it in reads stdout as JSON. So a malformed payload has to come back as a
structured rejection with a non-zero exit, never as a traceback.

The distinction the last test pins down is the one worth keeping: a bad payload
is `error: invalid_payload`, not `insufficient_context`. The latter is a verdict
about a review that ran and came back untrustworthy; a payload that never parsed
has no review behind it to describe.
"""

from __future__ import annotations

import io
import json

import pytest

from review.cli import main
from review.models import MergeDecision

VALID_FINDING = {
    "id": "CR-001",
    "reporter": "correctness",
    "category": "correctness",
    "evidence_state": "verified",
    "location": {"files": [{"path": "a.py"}]},
    "claim": {"title": "t", "observation": "o"},
    "severity": {"merge_impact": "blocker"},
    "comment_type": "request_change",
    "quoted_span": "x = 1",
}

VALID_DISPATCH = {
    "reporter": "correctness",
    "status": "completed",
    "finding_count": 1,
}


def run_verdict(monkeypatch, capsys, stdin_text: str) -> tuple[int, dict]:
    """Drive `main(["verdict"])` over `stdin_text`, returning (exit_code, parsed stdout).

    In-process rather than via subprocess: the exit code and the stdout JSON are
    the whole contract, and both are observable here without paying for an
    interpreter start per case.
    """
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
    code = main(["verdict"])
    out = capsys.readouterr().out
    return code, json.loads(out)


# --- The reported bug --------------------------------------------------------


def test_wrong_typed_validation_failures_is_structured_not_traceback(
    monkeypatch, capsys
):
    """The reproduce case: `validation_failures` as a list, not an int.

    It reached `validation_failures >= 2` inside the ladder and raised
    `TypeError: '>=' not supported between instances of 'list' and 'int'`.
    """
    payload = {
        "findings": [],
        "dispatch": [],
        "injection_hits": [],
        "validation_failures": [],
    }
    code, out = run_verdict(monkeypatch, capsys, json.dumps(payload))
    assert code == 1
    assert out["error"] == "invalid_payload"
    assert out["reason"] == "schema"
    assert "validation_failures" in out["message"]


# --- The rest of the payload surface ----------------------------------------


def test_stdin_is_not_json(monkeypatch, capsys):
    code, out = run_verdict(monkeypatch, capsys, "not json at all")
    assert code == 1
    assert out["reason"] == "not_json"


def test_payload_is_not_an_object(monkeypatch, capsys):
    """A bare JSON list parses fine but has no `.get` — it crashed with
    AttributeError before the guard."""
    code, out = run_verdict(monkeypatch, capsys, "[]")
    assert code == 1
    assert out["reason"] == "schema"
    assert "JSON object" in out["message"]


@pytest.mark.parametrize("field", ["findings", "dispatch", "injection_hits"])
def test_list_fields_reject_non_lists(monkeypatch, capsys, field):
    payload = {field: {"not": "a list"}}
    code, out = run_verdict(monkeypatch, capsys, json.dumps(payload))
    assert code == 1
    assert out["reason"] == "schema"
    assert field in out["message"]


def test_validation_failures_rejects_bool(monkeypatch, capsys):
    """`bool` subclasses `int`, so `True` would otherwise pass as 1 — a payload
    that says `true` does not mean "one validation failure"."""
    payload = {"validation_failures": True}
    code, out = run_verdict(monkeypatch, capsys, json.dumps(payload))
    assert code == 1
    assert out["reason"] == "schema"


def test_validation_failures_rejects_negative(monkeypatch, capsys):
    payload = {"validation_failures": -1}
    code, out = run_verdict(monkeypatch, capsys, json.dumps(payload))
    assert code == 1
    assert out["reason"] == "schema"


def test_malformed_finding_is_rejected(monkeypatch, capsys):
    """A `safety` reporter carrying a `CR-` id trips the prefix validator. It
    raised a bare pydantic ValidationError through main() before the guard."""
    bad = {**VALID_FINDING, "reporter": "safety"}
    payload = {"findings": [bad], "dispatch": [VALID_DISPATCH]}
    code, out = run_verdict(monkeypatch, capsys, json.dumps(payload))
    assert code == 1
    assert out["reason"] == "schema"
    assert "findings" in out["message"]


def test_malformed_dispatch_entry_is_rejected(monkeypatch, capsys):
    """`status='skipped'` with no `skip_reason` trips the model validator."""
    payload = {
        "findings": [],
        "dispatch": [{"reporter": "safety", "status": "skipped"}],
    }
    code, out = run_verdict(monkeypatch, capsys, json.dumps(payload))
    assert code == 1
    assert out["reason"] == "schema"
    assert "dispatch" in out["message"]


# --- Valid payloads still compute --------------------------------------------


def test_valid_payload_computes_verdict(monkeypatch, capsys):
    payload = {
        "findings": [VALID_FINDING],
        "dispatch": [VALID_DISPATCH],
        "injection_hits": [],
        "validation_failures": 0,
    }
    code, out = run_verdict(monkeypatch, capsys, json.dumps(payload))
    assert code == 0
    assert out["merge_decision"] == MergeDecision.REQUEST_CHANGES.value


def test_empty_object_defaults_to_approve(monkeypatch, capsys):
    """Every field is optional and defaults to empty. An empty review is a
    clean diff, which rung 4 approves — the guard must not turn absent fields
    into a rejection."""
    code, out = run_verdict(monkeypatch, capsys, "{}")
    assert code == 0
    assert out["merge_decision"] == MergeDecision.APPROVE.value


def test_bad_payload_is_not_insufficient_context(monkeypatch, capsys):
    """The distinction that matters to the orchestrator.

    `insufficient_context` means the review ran and cannot be trusted — it is a
    real rung with a real meaning. A payload that never parsed must not borrow
    it, or the operator cannot tell a poisoned diff from a broken pipe.
    """
    payload = {"validation_failures": []}
    code, out = run_verdict(monkeypatch, capsys, json.dumps(payload))
    assert code == 1
    assert "merge_decision" not in out
    assert out["error"] == "invalid_payload"
