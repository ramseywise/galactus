"""Deterministic phase and capability derivation for a BUILD work item.

`active_dimensions` (signals.py) one level up. That function answers "which of
the eleven review dimensions run against this diff"; these answer "which BUILD
phases and CROSS capabilities are live for this work item, and which are not."

The shape is deliberately identical, because the property worth copying is not
the routing but the **two-halves contract**: every registered phase appears in
`active` or in `skipped` *with a reason*, enforced by assertion rather than
intended. A phase that is neither dispatched nor explicitly skipped has vanished
from the table, and a vanished phase is indistinguishable from one that ran
clean — the failure `signals.py:433-440` exists to prevent, and the same one
`silent_failure` and `leakage` exist to catch in the code under review.

Three properties this module holds that a naive port would lose:

- **CROSS is positionless** (design §3e). Capabilities are derived by *call
  site*, never as phases. Giving them a slot in a sequence removes the one
  property that makes them useful.
- **Research is conditional** (design §3f). `/proto-plan` may skip it for
  small/understood work, and the legal-edge table already carries
  `RESEARCH → PLANNED` for exactly that case.
- **Absence of output is ambiguous** (design §2a). `Outcome` is three-way:
  `completed` (including empty), `failed`, `skipped`. Two-way success/failure
  manufactures false confidence in any pipeline where a step can silently not
  run.

Derivation is content-first, not path-first, following the `signals.py`
precedent (`:241-247`): what a doc *records* decides routing, not what it is
named.
"""

from __future__ import annotations

import re
from enum import StrEnum

from review.models import (
    STATE_COMPLETED_PHASE,
    TERMINAL_STATES,
    Capability,
    Phase,
)

# The BUILD phase order. `STATE_COMPLETED_PHASE` maps a state to the phase it
# finished; this list is what "remaining" is computed against.
_PHASE_ORDER: list[Phase] = [
    Phase.RESEARCH,
    Phase.PLAN,
    Phase.REFINE,
    Phase.EXECUTE,
    Phase.REVIEW,
]

# CROSS call sites, per design §3e. Both are gated by risk rather than
# unconditional: "a gate that dispatches an advisor on every trivial plan trains
# people to ignore the advisor."
_CAPABILITY_CALL_SITES: dict[Phase, list[Capability]] = {
    Phase.REFINE: [Capability.ASSUMPTION_AUDIT, Capability.FOG],
    Phase.REVIEW: [Capability.WAR_GAME, Capability.ASSUMPTION_AUDIT],
}


class Outcome(StrEnum):
    """What happened on a dispatch — the third axis of design §3d-quater.

    `COMPLETED` covers "ran and found nothing": an empty result is a result.
    `SKIPPED` means it never ran and that was intended. `FAILED` means it should
    have run and did not. Collapsing the last two is what makes an orchestrated
    pipeline less trustworthy than a manual one, because a silent skip reads as
    a pass.
    """

    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


_STATUS_RE = re.compile(r"^[ \t]*(?:\*\*)?Status(?:\*\*)?:[ \t]*(.*)$")
_TRACK_RE = re.compile(r"^[ \t]*(?:\*\*)?Track(?:\*\*)?:[ \t]*(.*)$")
_EPISTEMIC_RE = re.compile(r"^[ \t]*(?:\*\*)?Epistemic(?:\*\*)?:[ \t]*(.*)$")
_RESEARCH_HEADING_RE = re.compile(r"^#{1,6}[ \t]+Research\b", re.IGNORECASE)


def _unfenced(src: list[str]) -> list[str]:
    """Drop fenced code blocks before any field scan.

    Same rule and same reason as `plan_status_validate.sh`: front matter is
    never inside a fence, and a doc that *documents* the state machine would
    otherwise be read as declaring it. Fences are matched by marker and width
    per CommonMark, so a 4-backtick block wrapping a 3-backtick one does not
    desync — a doc explaining this function is the most likely place that
    happens.

    Kept in sync with the hook deliberately: two readers of the same front
    matter that disagree about what counts as front matter is a defect, and the
    hook is the one that blocks writes.
    """
    out: list[str] = []
    opener: str | None = None
    fence_re = re.compile(r"^[ \t]*(`{3,}|~{3,})")
    for line in src:
        m = fence_re.match(line)
        if m:
            marker = m.group(1)
            if opener is None:
                opener = marker
                continue
            if marker[0] == opener[0] and len(marker) >= len(opener):
                opener = None
                continue
        if opener is None:
            out.append(line)
    return out


def _field(lines: list[str], pattern: re.Pattern[str]) -> str | None:
    """First-match-wins over unfenced lines, one token, or None."""
    for line in lines:
        m = pattern.match(line)
        if m:
            value = m.group(1).strip()
            return value.split()[0] if value.split() else None
    return None


def read_doc_signals(doc_text: str) -> dict[str, object]:
    """Extract the routing inputs from a plan doc.

    Content-first: everything here is read from what the doc *records*, never
    from its filename or path.
    """
    lines = _unfenced(doc_text.splitlines())
    return {
        "status": _field(lines, _STATUS_RE),
        "track": _field(lines, _TRACK_RE),
        "epistemic": _field(lines, _EPISTEMIC_RE),
        "has_research_section": any(_RESEARCH_HEADING_RE.match(ln) for ln in lines),
    }


def active_phases(signals: dict[str, object]) -> dict[str, object]:
    """Return the BUILD phases still to run *and* those skipped, with reasons.

    Returns both halves rather than letting the caller infer the complement —
    the same contract as `active_dimensions`, and for the same reason: a
    dispatch table that omits what did not run cannot be mandatory-complete.
    """
    status = signals.get("status")
    active: list[str] = []
    skipped: dict[str, str] = {}

    if status is None or status not in STATE_COMPLETED_PHASE:
        # Unroutable rather than empty. An unrecognised state is a failure to
        # derive, not a work item with no phases left — reporting it as the
        # latter is precisely the false-confidence case §2a forbids.
        for phase in _PHASE_ORDER:
            skipped[phase.value] = (
                f"cannot derive: {status!r} is not a canonical state"
                if status is not None
                else "cannot derive: doc has no Status: line"
            )
        _assert_complete(active, skipped)
        return {"active": active, "skipped": skipped, "unroutable": True}

    if status in TERMINAL_STATES:
        reason = f"work item is terminal at {status}"
        for phase in _PHASE_ORDER:
            skipped[phase.value] = reason
        _assert_complete(active, skipped)
        return {"active": active, "skipped": skipped, "unroutable": False}

    completed = STATE_COMPLETED_PHASE[status]
    cutoff = _PHASE_ORDER.index(completed) + 1 if completed is not None else 0

    for index, phase in enumerate(_PHASE_ORDER):
        if index < cutoff:
            skipped[phase.value] = f"already completed — doc is at {status}"
            continue
        # Research is conditional, not mandatory (design §3f). A doc that already
        # carries a `## Research` section but sits at RESEARCH has had the work
        # done without the state advancing; a doc with neither is a genuine skip
        # that `/proto-plan` is entitled to make for small, understood work.
        if phase is Phase.RESEARCH and signals.get("has_research_section"):
            skipped[phase.value] = "research already recorded in the doc"
            continue
        active.append(phase.value)

    _assert_complete(active, skipped)
    return {"active": active, "skipped": skipped, "unroutable": False}


def active_capabilities(signals: dict[str, object]) -> dict[str, object]:
    """Return the CROSS capabilities live at the current phase, with reasons.

    Derived by **call site**, never by position: CROSS has no position (design
    §3e). A capability is active when the phase that schedules it is still to
    run, which is what makes this a projection of `active_phases` rather than a
    second sequence.
    """
    phases = active_phases(signals)
    live_phases = set(phases["active"])
    active: list[str] = []
    skipped: dict[str, str] = {}

    # A capability with no declared call site at all is a registration bug, not
    # a routing outcome. Caught before the loop, because inside it the two are
    # indistinguishable: both produce an empty `reachable` and would be reported
    # as "no call site remaining" — a capability that was never wired reading
    # exactly like one whose sites have passed. That is the vanishing failure
    # this module exists to prevent, so it fails loudly rather than skipping.
    unwired = [
        c.value
        for c in Capability
        if not any(c in caps for caps in _CAPABILITY_CALL_SITES.values())
    ]
    if unwired:
        raise AssertionError(
            "every registered capability needs at least one scheduled call site; "
            f"unwired: {sorted(unwired)}"
        )

    for capability in Capability:
        sites = [p for p, caps in _CAPABILITY_CALL_SITES.items() if capability in caps]
        reachable = [p for p in sites if p.value in live_phases]
        if reachable:
            active.append(capability.value)
        else:
            site_names = ", ".join(sorted(p.value for p in sites))
            skipped[capability.value] = f"no scheduled call site remaining (sites: {site_names})"

    covered = set(active) | set(skipped)
    expected = {c.value for c in Capability}
    if covered != expected:
        raise AssertionError(
            "active_capabilities must account for every registered capability; "
            f"unaccounted: {sorted(expected - covered)}, "
            f"unregistered: {sorted(covered - expected)}"
        )

    return {"active": active, "skipped": skipped}


def _assert_complete(active: list[str], skipped: dict[str, str]) -> None:
    """Mandatory-complete, enforced rather than intended.

    `_PHASE_ORDER` and the branches above name phases as bare strings, so a
    phase added to `Phase` but forgotten here would appear in neither list —
    vanishing from the dispatch table with no skip reason, which is
    indistinguishable from a phase that ran clean. That is the one failure this
    module's two-halves contract exists to prevent, so it fails loudly here
    instead.
    """
    covered = set(active) | set(skipped)
    expected = {p.value for p in Phase}
    if covered != expected:
        raise AssertionError(
            "active_phases must account for every registered phase; "
            f"unaccounted: {sorted(expected - covered)}, "
            f"unregistered: {sorted(covered - expected)}"
        )
