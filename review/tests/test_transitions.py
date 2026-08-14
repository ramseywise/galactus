"""The D10 measurement — reading the transition ledger.

The tests that matter most here are the ones about *ambiguity*: a missing ledger
must not read as an empty one, and a partly-corrupt ledger must not report a
clean count. Those are the two ways a measurement lies while looking fine, and
they are the same failure (§2a, absence-is-ambiguous) the write side already
guards at the hook.
"""

from __future__ import annotations

import json
from pathlib import Path

from review.transitions import LOOP_BACK_EDGE, read_ledger


def write_ledger(tmp_path: Path, records: list[dict]) -> str:
    p = tmp_path / "plan-transitions.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return str(p)


def edge(doc: str, frm: str, to: str, **kw: object) -> dict:
    base = {"ts": "2026-08-14T12:00:00Z", "repo": "galactus", "doc": doc, "from": frm, "to": to}
    base.update(kw)
    return base


# --- absence is not zero -----------------------------------------------------


def test_missing_ledger_is_not_an_empty_one(tmp_path: Path) -> None:
    """The distinction the whole control plane rests on, at the read side."""
    result = read_ledger(str(tmp_path / "nope.jsonl"))
    assert result["exists"] is False
    assert "loop_backs" not in result, "a nonexistent ledger must not report a count"
    assert "no transition has been recorded yet" in str(result["reason"])


def test_empty_ledger_reports_a_measured_zero(tmp_path: Path) -> None:
    """Present-but-empty is a real answer: the mechanism ran, nothing traversed."""
    result = read_ledger(write_ledger(tmp_path, []))
    assert result["exists"] is True
    assert result["transitions"] == 0
    assert result["loop_backs"] == 0
    assert result["loop_backs_per_run"] is None, "no runs means no rate, not a rate of zero"


# --- D10, the count the graph decision turns on ------------------------------


def test_loop_back_is_counted(tmp_path: Path) -> None:
    path = write_ledger(
        tmp_path,
        [
            edge("a.md", "READY", "IN_PROGRESS"),
            edge("a.md", "IN_PROGRESS", "EXECUTED"),
            edge("a.md", "EXECUTED", "PLANNED"),
            edge("a.md", "PLANNED", "REFINED"),
        ],
    )
    result = read_ledger(path)
    assert result["loop_backs"] == 1
    assert result["transitions"] == 4
    assert result["runs_started"] == 1
    assert result["loop_backs_per_run"] == 1.0


def test_loop_back_rate_is_per_run_not_per_transition(tmp_path: Path) -> None:
    """§13 wants P(re-plan), which is per work item — three runs, one loop-back."""
    path = write_ledger(
        tmp_path,
        [
            edge("a.md", "EXECUTED", "PLANNED"),
            edge("b.md", "IN_PROGRESS", "EXECUTED"),
            edge("c.md", "READY", "IN_PROGRESS"),
        ],
    )
    result = read_ledger(path)
    assert result["loop_backs"] == 1
    assert result["runs_started"] == 3
    assert result["loop_backs_per_run"] == round(1 / 3, 3)


def test_loop_back_edge_matches_the_state_vocabulary() -> None:
    """Guards the constant against a rename of either state."""
    from review.models import STATE_COMPLETED_PHASE

    frm, to = LOOP_BACK_EDGE
    assert frm in STATE_COMPLETED_PHASE
    assert to in STATE_COMPLETED_PHASE


# --- runs completed ----------------------------------------------------------


def test_terminal_edges_count_a_completed_run(tmp_path: Path) -> None:
    path = write_ledger(
        tmp_path,
        [
            edge("a.md", "EXECUTED", "COMPLETE"),
            edge("b.md", "RESEARCH", "SUPERSEDED"),
            edge("c.md", "READY", "IN_PROGRESS"),
        ],
    )
    result = read_ledger(path)
    assert result["runs_started"] == 3
    assert result["runs_completed"] == 2, "COMPLETE and SUPERSEDED are both terminal"


def test_a_run_is_a_doc_not_a_transition(tmp_path: Path) -> None:
    """One work item traversing five edges is one run, not five."""
    path = write_ledger(
        tmp_path,
        [
            edge("a.md", "RESEARCH", "RESEARCHED"),
            edge("a.md", "RESEARCHED", "PLANNED"),
            edge("a.md", "PLANNED", "REFINED"),
            edge("a.md", "REFINED", "READY"),
            edge("a.md", "READY", "IN_PROGRESS"),
        ],
    )
    result = read_ledger(path)
    assert result["runs_started"] == 1
    assert result["transitions"] == 5


# --- a corrupt ledger must not report a clean count --------------------------


def test_malformed_lines_are_surfaced_not_dropped(tmp_path: Path) -> None:
    p = tmp_path / "plan-transitions.jsonl"
    p.write_text(
        json.dumps(edge("a.md", "EXECUTED", "PLANNED")) + "\n"
        "{not json at all\n"
        + json.dumps({"ts": "x", "doc": "b.md"})  # valid JSON, missing from/to
        + "\n",
        encoding="utf-8",
    )
    result = read_ledger(str(p))
    assert result["loop_backs"] == 1
    assert len(result["malformed"]) == 2, "both unparseable and shape-invalid lines are reported"


def test_blank_lines_are_not_malformed(tmp_path: Path) -> None:
    p = tmp_path / "plan-transitions.jsonl"
    p.write_text("\n" + json.dumps(edge("a.md", "READY", "IN_PROGRESS")) + "\n\n", encoding="utf-8")
    result = read_ledger(str(p))
    assert result["transitions"] == 1
    assert result["malformed"] == []


def test_unknown_states_are_flagged(tmp_path: Path) -> None:
    """A vocabulary drift silently narrows every count above it."""
    path = write_ledger(tmp_path, [edge("a.md", "READY", "DEPLOYED")])
    result = read_ledger(path)
    assert result["unknown_states"] == ["DEPLOYED"]


# --- what the ledger cannot answer, stated rather than estimated -------------


def test_unmeasurable_quantities_are_named_in_every_payload(tmp_path: Path) -> None:
    """§13 lists four quantities; the ledger supplies two. The gap is explicit."""
    for result in (
        read_ledger(str(tmp_path / "gone.jsonl")),
        read_ledger(write_ledger(tmp_path, [])),
    ):
        unavailable = result["unavailable"]
        assert isinstance(unavailable, dict)
        assert set(unavailable) == {
            "tokens_per_cycle",
            "latency_per_cycle",
            "human_interventions",
        }
        assert all(v for v in unavailable.values()), "each gap states why, not just that"
