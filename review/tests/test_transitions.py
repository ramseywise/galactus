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
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "plan-transitions.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return str(p)


def edge(doc: str, frm: str, to: str, **kw: object) -> dict:
    base = {"ts": "2026-08-14T12:00:00Z", "repo": "galactus", "doc": doc, "from": frm, "to": to}
    base.update(kw)
    return base


def marker(session: str, **kw: object) -> dict:
    base = {
        "ts": "2026-08-14T12:00:00Z",
        "kind": "session",
        "session": session,
        "repo": "galactus",
        "recorder": "plan_status_validate",
    }
    base.update(kw)
    return base


# --- absence is not zero -----------------------------------------------------


def test_missing_ledger_is_not_an_empty_one(tmp_path: Path) -> None:
    """The distinction the whole control plane rests on, at the read side."""
    result = read_ledger(str(tmp_path / "nope.jsonl"))
    assert result["exists"] is False
    assert "loop_backs" not in result, "a nonexistent ledger must not report a count"
    assert "no transition has been recorded yet" in str(result["reason"])


def test_empty_ledger_counts_zero_but_does_not_attest_it(tmp_path: Path) -> None:
    """Present-but-empty is a count of zero — and NOT yet evidence of zero.

    The file existing proves a recorder ran at some point, never that one ran
    during the window being read. That second fact is `recorder.attested`.
    """
    result = read_ledger(write_ledger(tmp_path, []))
    assert result["exists"] is True
    assert result["transitions"] == 0
    assert result["loop_backs"] == 0
    assert result["loop_backs_per_run"] is None, "no runs means no rate, not a rate of zero"
    assert result["recorder"]["attested"] is None, "silence must not read as an observed zero"


# --- the recorder marker: was the instrument alive? (galactus#20 item 2) ------


def test_marker_makes_an_empty_ledger_a_real_zero(tmp_path: Path) -> None:
    """The case the marker exists for: nothing moved, and we know it.

    Without a marker this ledger is byte-identical to one whose recorder never
    ran. With one, "no loop-backs" means what it says.
    """
    result = read_ledger(write_ledger(tmp_path, [marker("sess-1")]))
    assert result["transitions"] == 0, "a marker is not an edge"
    assert result["loop_backs"] == 0
    rec = result["recorder"]
    assert rec["attested"] is True
    assert rec["sessions_recorded"] == 1
    assert "measurements, not lower bounds" in str(rec["reason"])


def test_unmarked_edges_are_a_lower_bound_not_a_measurement(tmp_path: Path) -> None:
    """Every pre-#20 ledger. Counts are real but incomplete by an unknown amount."""
    result = read_ledger(write_ledger(tmp_path, [edge("a.md", "READY", "IN_PROGRESS")]))
    assert result["transitions"] == 1
    assert result["recorder"]["attested"] is False
    assert "LOWER BOUND" in str(result["recorder"]["reason"])


def test_the_three_recorder_states_are_mutually_distinct(tmp_path: Path) -> None:
    """The §2a distinction itself: yes / no / never asked must not collapse.

    A boolean here would render "attested empty" and "unattested" the same,
    which is the exact ambiguity the marker was added to end.
    """
    attested = read_ledger(write_ledger(tmp_path / "a", [marker("s")]))["recorder"]["attested"]
    unattested = read_ledger(write_ledger(tmp_path / "b", [edge("a.md", "READY", "IN_PROGRESS")]))[
        "recorder"
    ]["attested"]
    silent = read_ledger(write_ledger(tmp_path / "c", []))["recorder"]["attested"]
    assert [attested, unattested, silent] == [True, False, None]


def test_sessions_are_deduplicated_by_id(tmp_path: Path) -> None:
    """Two ledgers' worth of markers from one session is still one session.

    Settings layers merge, so both the repo hook and the global hook can write.
    The count is of distinct sessions, not of marker lines.
    """
    result = read_ledger(
        write_ledger(tmp_path, [marker("sess-1"), marker("sess-1", ts="2026-08-14T13:00:00Z")])
    )
    assert result["recorder"]["sessions_recorded"] == 1
    assert result["recorder"]["first_seen"] == "2026-08-14T12:00:00Z"
    assert result["recorder"]["last_seen"] == "2026-08-14T13:00:00Z"


def test_markers_never_inflate_the_d10_count(tmp_path: Path) -> None:
    """The marker must contextualize the measurement without becoming part of it."""
    result = read_ledger(
        write_ledger(
            tmp_path,
            [
                marker("sess-1"),
                edge("a.md", "EXECUTED", "PLANNED"),
                marker("sess-2", ts="2026-08-14T14:00:00Z"),
            ],
        )
    )
    assert result["transitions"] == 1
    assert result["loop_backs"] == 1
    assert result["runs_started"] == 1, "a marker carries no doc and is not a run"
    assert result["docs"] == ["a.md"]
    assert result["recorder"]["sessions_recorded"] == 2


def test_a_marker_without_a_session_id_is_malformed(tmp_path: Path) -> None:
    """Anonymous markers cannot be deduplicated, so they would inflate the count."""
    result = read_ledger(
        write_ledger(tmp_path, [{"kind": "session", "ts": "2026-08-14T12:00:00Z"}])
    )
    assert result["recorder"]["attested"] is None
    assert len(result["malformed"]) == 1


def test_pre_marker_edges_still_read_without_migration(tmp_path: Path) -> None:
    """Records with no `kind` are edges. Absence must never mean marker."""
    result = read_ledger(
        write_ledger(
            tmp_path, [edge("a.md", "EXECUTED", "PLANNED"), edge("a.md", "PLANNED", "REFINED")]
        )
    )
    assert result["transitions"] == 2
    assert result["loop_backs"] == 1
    assert result["malformed"] == []


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
