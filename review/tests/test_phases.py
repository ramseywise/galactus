"""Phase and capability derivation — the `active_dimensions` contract one level up.

The tests that matter most here are the completeness ones. Routing tests prove
the branches work; the completeness tests prove that *adding a phase and
forgetting to route it* fails loudly instead of silently shrinking the pipeline.
"""

from __future__ import annotations

import pytest

from review.models import (
    STATE_COMPLETED_PHASE,
    TERMINAL_STATES,
    Capability,
    Phase,
)
from review.phases import (
    CAPABILITY_AGENT,
    Outcome,
    active_capabilities,
    active_phases,
    epistemic_for,
    read_doc_signals,
    resolve_capability_agent,
)


def sig(status: str | None, **kw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "status": status,
        "track": "agent",
        "epistemic": None,
        "has_research_section": False,
    }
    base.update(kw)
    return base


# --- completeness: the reason this module mirrors signals.py at all ----------


@pytest.mark.parametrize("status", sorted(STATE_COMPLETED_PHASE))
def test_every_phase_accounted_for_at_every_state(status: str):
    """Active plus skipped must cover the whole menu, at every state.

    Pinned against `Phase` rather than a hand-written literal: a hardcoded list
    means adding a phase to the enum and forgetting it in `active_phases` leaves
    this test green, which is the omission it exists to catch.
    """
    result = active_phases(sig(status))
    covered = set(result["active"]) | set(result["skipped"])
    assert covered == {p.value for p in Phase}


def test_every_capability_accounted_for():
    result = active_capabilities(sig("PLANNED"))
    covered = set(result["active"]) | set(result["skipped"])
    assert covered == {c.value for c in Capability}


def test_unwired_capability_raises_rather_than_skipping(monkeypatch):
    """A capability registered with no call site at all must fail loudly.

    Found while verifying the assertion was not decorative. Inside the routing
    loop this case is indistinguishable from a capability whose sites have
    already passed — both produce no reachable site — so a never-wired
    capability was being reported as a routine skip. That is the vanishing
    failure the two-halves contract exists to prevent, one level down.
    """
    from enum import StrEnum

    class CapabilityPlusUnwired(StrEnum):
        ASSUMPTION_AUDIT = "assumption_audit"
        WAR_GAME = "war_game"
        FOG = "fog"
        RED_TEAM = "red_team"

    monkeypatch.setattr("review.phases.Capability", CapabilityPlusUnwired)
    with pytest.raises(AssertionError, match=r"unwired.*red_team"):
        active_capabilities(sig("PLANNED"))


def test_unrouted_phase_raises_rather_than_vanishing(monkeypatch):
    """The completeness assertion, proven to fire.

    An assertion nobody has watched fail is a comment. This adds a phase to the
    registry without routing it and asserts the name appears in the error.
    """
    from enum import StrEnum

    class PhasePlusDeploy(StrEnum):
        RESEARCH = "research"
        PLAN = "plan"
        REFINE = "refine"
        EXECUTE = "execute"
        REVIEW = "review"
        DEPLOY = "deploy"

    monkeypatch.setattr("review.phases.Phase", PhasePlusDeploy)
    with pytest.raises(AssertionError, match=r"unaccounted.*deploy"):
        active_phases(sig("PLANNED"))


def test_skipped_phases_always_carry_a_reason():
    """A skip with no reason is the silent-omission failure wearing a label."""
    for status in STATE_COMPLETED_PHASE:
        result = active_phases(sig(status))
        for phase, reason in result["skipped"].items():
            assert reason.strip(), f"{phase} at {status} skipped with no reason"


def test_state_vocabulary_matches_the_hook():
    """`STATE_COMPLETED_PHASE` must not drift from the enum the hook guards.

    Two readers of `Status:` that disagree about the vocabulary is a defect, and
    the hook is the reference because it is the one that blocks writes.

    Parsed out of the hook rather than pinned to a literal, for the reason
    `test_doc_registry.py` documents at length: a hardcoded copy means adding a
    state to the hook and forgetting it here leaves this test green, which is
    the drift it exists to catch. Same failure the registry tests were written
    about, one vocabulary over.
    """
    import re
    from pathlib import Path

    hook_src = (
        Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "plan_status_validate.sh"
    ).read_text(encoding="utf-8")
    block = re.search(r"STATES = \{(.*?)\}", hook_src, re.DOTALL)
    assert block, "could not find the STATES enum in plan_status_validate.sh"
    hook_states = set(re.findall(r'"([A-Z_]+)"', block.group(1)))
    assert hook_states, "parsed no states out of the hook"
    assert set(STATE_COMPLETED_PHASE) == hook_states


# --- routing -----------------------------------------------------------------


def test_fresh_doc_runs_every_phase():
    result = active_phases(sig("RESEARCH"))
    assert result["active"] == [p.value for p in Phase]
    assert result["skipped"] == {}


def test_completed_phases_are_skipped_not_dropped():
    result = active_phases(sig("EXECUTED"))
    assert result["active"] == ["review"]
    assert set(result["skipped"]) == {"research", "plan", "refine", "execute"}
    assert all("already completed" in r for r in result["skipped"].values())


def test_research_is_conditional_when_already_recorded():
    """Design §3f: research is skippable for small/understood work, and the
    legal-edge table carries `RESEARCH → PLANNED` for exactly that case."""
    result = active_phases(sig("RESEARCH", has_research_section=True))
    assert "research" not in result["active"]
    assert "research already recorded" in result["skipped"]["research"]
    assert result["active"][0] == "plan"


@pytest.mark.parametrize("status", sorted(TERMINAL_STATES))
def test_terminal_states_run_nothing(status: str):
    result = active_phases(sig(status))
    assert result["active"] == []
    assert set(result["skipped"]) == {p.value for p in Phase}
    assert result["unroutable"] is False


def test_ready_and_in_progress_both_await_execute():
    """READY, IN_PROGRESS and REFINED all sit after the refine gate — the
    distinction between them is operational, not a phase boundary."""
    for status in ("REFINED", "READY", "IN_PROGRESS"):
        assert active_phases(sig(status))["active"] == ["execute", "review"]


# --- unroutable is not empty -------------------------------------------------


def test_unknown_state_is_unroutable_not_finished():
    """§2a: reporting an underivable work item as "no phases left" is the
    false-confidence failure — it looks exactly like a completed run."""
    result = active_phases(sig("NOT_A_STATE"))
    assert result["unroutable"] is True
    assert result["active"] == []
    assert all("cannot derive" in r for r in result["skipped"].values())


def test_missing_status_is_unroutable():
    result = active_phases(sig(None))
    assert result["unroutable"] is True
    assert all("no Status:" in r for r in result["skipped"].values())


def test_terminal_and_unroutable_are_distinguishable():
    """Both run zero phases; conflating them loses the difference between
    "finished" and "cannot tell"."""
    assert active_phases(sig("COMPLETE"))["unroutable"] is False
    assert active_phases(sig("NOT_A_STATE"))["unroutable"] is True


# --- CROSS is positionless ---------------------------------------------------


def test_capabilities_are_not_phases():
    """Design §3e: a capability must never appear in the phase list."""
    for status in STATE_COMPLETED_PHASE:
        active = set(active_phases(sig(status))["active"])
        assert active.isdisjoint({c.value for c in Capability})


def test_capabilities_live_while_their_call_site_remains():
    result = active_capabilities(sig("PLANNED"))
    assert set(result["active"]) == {"assumption_audit", "fog", "war_game"}


def test_war_game_drops_once_review_is_the_only_site_passed():
    """`/war-game` is scheduled at review only, so a doc past review has no
    remaining call site for it — while `assumption_audit`, scheduled at both
    refine and review, drops at the same point for the same reason."""
    result = active_capabilities(sig("COMPLETE"))
    assert result["active"] == []
    assert "no scheduled call site remaining" in result["skipped"]["war_game"]


def test_fog_is_refine_only():
    """At EXECUTED only review remains, so the refine-only capability is gone
    while the review-scheduled ones stay live."""
    result = active_capabilities(sig("EXECUTED"))
    assert set(result["active"]) == {"war_game", "assumption_audit"}
    assert "fog" in result["skipped"]


# --- outcome is three-way ----------------------------------------------------


def test_outcome_distinguishes_ran_empty_from_never_ran():
    """§2a: the distinction that makes a silent skip visible."""
    assert len(set(Outcome)) == 3
    assert Outcome.COMPLETED != Outcome.SKIPPED != Outcome.FAILED


# --- doc reading is content-first --------------------------------------------


def test_read_doc_signals_extracts_front_matter():
    doc = "# t\n\nStatus: PLANNED\nTrack: ml\nEpistemic: NO_CONFLICT\n\n## Research\n"
    assert read_doc_signals(doc) == {
        "status": "PLANNED",
        "track": "ml",
        "epistemic": "NO_CONFLICT",
        "has_research_section": True,
    }


def test_fenced_fields_are_not_front_matter():
    """Same rule as the hook: a doc that *documents* the state machine must not
    be read as declaring it."""
    doc = "Status: PLANNED\n\n```\nStatus: COMPLETE\nEpistemic: BLOCKED\n```\n"
    signals = read_doc_signals(doc)
    assert signals["status"] == "PLANNED"
    assert signals["epistemic"] is None


def test_nested_fence_does_not_desync():
    """A 4-backtick block wrapping a 3-backtick one toggles a naive boolean
    four times and leaks the inner content as front matter."""
    doc = "Status: PLANNED\n\n````\n```\nStatus: COMPLETE\n```\n````\n"
    assert read_doc_signals(doc)["status"] == "PLANNED"


def test_bold_field_form_is_read():
    """The corpus carries both `Status:` and `**Status**:`."""
    assert read_doc_signals("**Status**: REFINED\n")["status"] == "REFINED"


def test_routing_is_content_first_not_path_first():
    """A doc that merely *mentions* research in prose has not recorded it —
    only a `## Research` heading counts, per the signals.py precedent."""
    doc = "Status: RESEARCH\n\nWe should do research on this later.\n"
    assert "research" in active_phases(read_doc_signals(doc))["active"]


# --- CLI surface -------------------------------------------------------------


def run_cli(monkeypatch, capsys, stdin_text: str) -> tuple[int, dict]:
    """Drive `main(["derive-phases"])` in-process, as `test_cli_verdict` does."""
    import io
    import json

    from review.cli import main

    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
    code = main(["derive-phases"])
    return code, json.loads(capsys.readouterr().out)


def test_cli_derives_a_real_doc(monkeypatch, capsys):
    import json

    code, out = run_cli(monkeypatch, capsys, json.dumps({"doc": "Status: PLANNED\n"}))
    assert code == 0
    assert out["phases"]["active"] == ["refine", "execute", "review"]
    assert out["unroutable"] is False


def test_cli_unroutable_doc_exits_nonzero(monkeypatch, capsys):
    """An underivable doc is a failure to route, not a successful empty result.

    The exit code is the part that matters: a caller that only checks the code
    must not read "cannot tell" as "nothing left to do".
    """
    import json

    code, out = run_cli(monkeypatch, capsys, json.dumps({"doc": "Status: BOGUS\n"}))
    assert code == 1
    assert out["unroutable"] is True
    assert out["phases"]["active"] == []


def test_cli_terminal_doc_exits_zero(monkeypatch, capsys):
    """Terminal and unroutable both derive zero phases — only the exit code and
    `unroutable` flag separate them."""
    import json

    doc = "Status: COMPLETE\nReview: passed\nCompleted: 2026-08-14\n"
    code, out = run_cli(monkeypatch, capsys, json.dumps({"doc": doc}))
    assert code == 0
    assert out["unroutable"] is False
    assert out["phases"]["active"] == []


def test_cli_rejects_malformed_payload(monkeypatch, capsys):
    """Structured rejection on stdout, never a traceback — the caller pipes
    JSON and must get JSON it can branch on."""
    code, out = run_cli(monkeypatch, capsys, "not json")
    assert code == 1
    assert out["error"] == "invalid_payload"
    assert out["reason"] == "not_json"


def test_cli_rejects_non_object_payload(monkeypatch, capsys):
    code, out = run_cli(monkeypatch, capsys, '["a"]')
    assert code == 1
    assert out["reason"] == "schema"


def test_cli_rejects_missing_doc(monkeypatch, capsys):
    code, out = run_cli(monkeypatch, capsys, "{}")
    assert code == 1
    assert out["reason"] == "schema"


# --- the corpus routes -------------------------------------------------------


def test_every_corpus_doc_routes():
    """The strongest available test: real docs, not fixtures.

    Every plan doc in the repo must derive a complete phase set with no
    unroutable case — an unroutable doc in the live corpus means the derivation
    and the hook disagree about the state vocabulary.
    """
    from pathlib import Path

    plans = sorted(Path(".claude/docs/plans").glob("*.md"))
    if not plans:
        pytest.skip("no plan docs in this checkout")
    for doc in plans:
        signals = read_doc_signals(doc.read_text(encoding="utf-8"))
        result = active_phases(signals)
        assert not result["unroutable"], f"{doc.name} did not route: {signals}"
        covered = set(result["active"]) | set(result["skipped"])
        assert covered == {p.value for p in Phase}


# --- capability resolution: the #15 collapse ---------------------------------
#
# These are the negative tests for the substituted-dispatch failure. The one
# that matters is `test_unresolvable_advisor_cannot_yield_no_conflict`: it is
# the executable form of the issue's "Done when", and it fails against any
# implementation that lets a failed dispatch reach `NO_CONFLICT`.


def test_fog_advisor_resolves_in_this_checkout():
    """The regression test proper: `fog-advisor` must actually load.

    #15's observed symptom. Reads the live agent file rather than a fixture,
    because a fixture would pass while the real registry entry stayed broken —
    which is the exact gap that let the original failure through.
    """
    result = resolve_capability_agent(Capability.FOG)
    assert result["resolved"], result["reason"]
    assert result["agent"] == ".claude/agents/fog-advisor.md"
    assert result["reason"] == ""


def test_unresolvable_advisor_cannot_yield_no_conflict():
    """A dispatch that did not happen may never read as one that found nothing.

    This is the whole issue in one assertion. `NO_CONFLICT` means "applicable
    checks ran and surfaced nothing unresolved"; deriving it from a failed
    dispatch is manufactured certainty.
    """
    assert epistemic_for(Outcome.FAILED) == "UNTESTED"
    assert epistemic_for(Outcome.SKIPPED) == "UNTESTED"
    assert epistemic_for(Outcome.COMPLETED, findings=0) == "NO_CONFLICT"
    assert epistemic_for(Outcome.COMPLETED, findings=3) == "CONFLICTED"

    # The property, not just the table: `NO_CONFLICT` is unreachable from any
    # outcome other than COMPLETED, at any finding count.
    for outcome in (Outcome.FAILED, Outcome.SKIPPED):
        for findings in (0, 1, 99):
            assert epistemic_for(outcome, findings) != "NO_CONFLICT"


def test_missing_agent_file_fails_loud_with_reason(tmp_path):
    """A missing advisor is a failure that names what it looked for.

    Fails, and says which path — a bare False sends the caller back to guessing,
    and a caller that has to guess writes the optimistic value.
    """
    result = resolve_capability_agent(Capability.FOG, repo_root=str(tmp_path))
    assert result["resolved"] is False
    assert ".claude/agents/fog-advisor.md" in result["reason"]
    assert epistemic_for(Outcome.FAILED) == "UNTESTED"


def test_agent_registering_under_wrong_name_does_not_resolve(tmp_path):
    """The subtle substitution: the file exists and parses, but is not that agent.

    A dispatch naming `fog-advisor` that lands on a file registering as
    something else has resolved to a *different* advisor. Indistinguishable
    from success unless the name is checked, which is why it is checked.
    """
    agent = tmp_path / ".claude" / "agents"
    agent.mkdir(parents=True)
    (agent / "fog-advisor.md").write_text(
        "---\nname: something-else\ntools: Read\n---\n\nbody\n", encoding="utf-8"
    )
    result = resolve_capability_agent(Capability.FOG, repo_root=str(tmp_path))
    assert result["resolved"] is False
    assert "something-else" in result["reason"]


def test_agent_without_front_matter_does_not_resolve(tmp_path):
    """A file the registry cannot parse is not a registered agent."""
    agent = tmp_path / ".claude" / "agents"
    agent.mkdir(parents=True)
    (agent / "fog-advisor.md").write_text("no front matter here\n", encoding="utf-8")
    result = resolve_capability_agent(Capability.FOG, repo_root=str(tmp_path))
    assert result["resolved"] is False
    assert "front matter" in result["reason"]


def test_capability_without_registered_agent_is_not_silently_ok():
    """An unregistered capability fails rather than reporting a clean resolve.

    Same rule as `active_capabilities`' unwired check: absence of a registration
    is a bug, and reporting it as an ok is the vanishing failure this module
    exists to prevent.
    """
    unregistered = [c for c in Capability if c not in CAPABILITY_AGENT]
    assert unregistered, "test is vacuous if every capability has an agent"
    for capability in unregistered:
        result = resolve_capability_agent(capability)
        assert result["resolved"] is False
        assert "no registered agent" in result["reason"]


def test_registered_agents_all_exist():
    """Every entry in `CAPABILITY_AGENT` points at a real, loadable agent.

    Catches the table drifting away from the filesystem — a rename that updates
    one and not the other reintroduces #15 for a different capability.
    """
    for capability in CAPABILITY_AGENT:
        result = resolve_capability_agent(capability)
        assert result["resolved"], f"{capability.value}: {result['reason']}"


def test_cli_resolve_capability_exits_1_on_failure(capsys, tmp_path):
    """The skill's actual instrument: exit code and a reason it can quote."""
    import json

    from review.cli import main

    code = main(["--repo-root", str(tmp_path), "resolve-capability", "fog"])
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out["resolved"] is False
    assert out["epistemic"] == "UNTESTED"
    assert out["reason"]


def test_cli_resolve_capability_exits_0_when_live(capsys):
    """Against the real checkout, `fog` resolves and licenses no epistemic override."""
    import json

    from review.cli import main

    code = main(["resolve-capability", "fog"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["resolved"] is True
    assert out["epistemic"] is None


def test_cli_resolve_capability_rejects_unknown_name(capsys):
    import json

    from review.cli import main

    code = main(["resolve-capability", "not-a-capability"])
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert out["reason"] == "schema"
