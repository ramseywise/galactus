"""Read side of the BUILD transition ledger — the D10 measurement.

`plan_status_validate.sh` writes one JSONL record per *accepted* state edge
(`lib.sh:log_transition`). This module reads that file and computes the four
quantities design §13 says gate the graph-versus-loop decision:

    BUILD runs started / completed
    EXECUTED → PLANNED transitions   ← D10, the loop-back count
    human interventions per run
    tokens + latency per cycle

The last row is not derivable from the ledger and is reported as unavailable
rather than estimated — see `read_ledger`'s `unavailable` key. Emitting a
plausible number for something never measured is the manufactured-certainty
failure the whole control plane exists to avoid (design §2a), and it would be
the *specific* number that flips the 3a/3b verdict (§9).

Why a reader at all, when the ledger is nine fields of JSONL: because the
question D10 asks is not "what is in the file" but "has the loop-back ever been
traversed, and at what rate." That is an aggregate over docs, and computing it
by eye is how `Review: pending` went unnoticed on 6 of 6 docs. The point of
step 4 is that the count exists without anyone choosing to look.

**A zero here is a real answer — when `recorder.attested` is true.** The ledger
began at zero on 2026-08-14 with the mechanism proven by test rather than by
fixture data. But galactus#20 showed the writer could be absent for a whole
session while the file sat there looking merely quiet: two copies of the hook at
different vintages both registered, and the one that ran had no ledger. So the
ledger now also records *that a recorder was alive*, once per session, and
`recorder` reports it. Read that key before reading any zero — "rare" versus
"nothing records it" is the ambiguity §7 names as the one thing HITL cannot
paper over, and `exists: True` alone never resolved it.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from review.models import STATE_COMPLETED_PHASE, TERMINAL_STATES

DEFAULT_LEDGER = ".claude/logs/plan-transitions.jsonl"

# The loop-back D10 names: review found blockers and the work item went back to
# planning. Held as a constant because it is the one edge the graph decision
# turns on, and a literal buried in a comprehension is not greppable.
LOOP_BACK_EDGE: tuple[str, str] = ("EXECUTED", "PLANNED")

# What the ledger structurally cannot answer. Named rather than omitted: a
# metrics payload silent about its own gaps reads as complete.
_UNAVAILABLE: dict[str, str] = {
    "tokens_per_cycle": (
        "not recorded — the hook sees file writes, not model usage; needs an "
        "instrumented dispatch (design §9, the number most likely to flip 3a/3b)"
    ),
    "latency_per_cycle": (
        "not recorded — ledger timestamps span operator think-time, so an "
        "inter-edge delta measures the human, not the cycle"
    ),
    "human_interventions": (
        "not distinguishable — every edge in this ledger is currently written by "
        "a human-invoked skill, so the count equals the transition count until a "
        "driver writes some of them (design §7)"
    ),
}


def _parse(lines: list[str]) -> tuple[list[dict], list[dict], list[str]]:
    """Split the ledger into edges, session markers, and malformed lines.

    Malformed lines are returned, never dropped silently. A ledger that is
    partly unparseable and reports a clean count is asserting a measurement it
    did not make — the same two-way-semantics failure `Outcome` exists to
    prevent one level down.

    `kind` discriminates the two record types, and only markers carry it.
    Every edge written before galactus#20 fix direction 2 has no `kind` at all,
    so absence means edge — the existing ledger reads correctly with no
    migration, and an edge is never silently reclassified as a marker.
    """
    records: list[dict] = []
    markers: list[dict] = []
    malformed: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            malformed.append(line[:120])
            continue
        if not isinstance(obj, dict):
            malformed.append(line[:120])
            continue
        if obj.get("kind") == "session":
            # A marker with no session id cannot be counted — sessions are
            # deduplicated by that id, and an anonymous marker would inflate the
            # count of distinct sessions on every write. The writer declines to
            # emit one; a hand-edited ledger might still contain one.
            if obj.get("session"):
                markers.append(obj)
            else:
                malformed.append(line[:120])
            continue
        if "from" not in obj or "to" not in obj:
            malformed.append(line[:120])
            continue
        records.append(obj)
    return records, markers, malformed


def _recorder_status(markers: list[dict], transitions: int) -> dict[str, object]:
    """Say whether the instrument was alive, not just what it recorded.

    This is galactus#20 fix direction 2 at the read side. `log_transition` alone
    makes a zero mean two incompatible things: no state moved, or nothing was
    watching. The §2a three-way distinction — yes / no / never asked — applied
    to the recorder itself.

    The three `attested` values map to exactly that:

    - `True`  — a marker exists. Every session that wrote here announced itself,
                so a zero in this window is a measurement.
    - `False` — no marker, but edges are present. The ledger was written by a
                recorder predating markers (or by hand); the count is a **lower
                bound**, since a silent session leaves no trace to subtract.
    - `None`  — no marker and no edges. The file exists and says nothing at all,
                which is the case that must never be read as "no loop-backs."

    Deliberately not folded into a boolean. A two-valued answer here would
    reintroduce the collapse one level up: "not attested" and "attested empty"
    would render identically, which is the ambiguity the marker exists to end.
    """
    sessions = sorted({m["session"] for m in markers})
    if sessions:
        return {
            "attested": True,
            "sessions_recorded": len(sessions),
            "first_seen": min(m.get("ts", "") for m in markers) or None,
            "last_seen": max(m.get("ts", "") for m in markers) or None,
            "recorders": sorted({m.get("recorder", "") for m in markers if m.get("recorder")}),
            "reason": (
                f"{len(sessions)} session(s) recorded a marker; counts in this "
                "ledger are measurements, not lower bounds"
            ),
        }
    if transitions:
        return {
            "attested": False,
            "sessions_recorded": 0,
            "reason": (
                "edges present but no session marker — written by a recorder "
                "predating markers, or by hand. Treat every count as a LOWER "
                "BOUND: a session that recorded nothing is indistinguishable "
                "from one that never ran (galactus#20)"
            ),
        }
    return {
        "attested": None,
        "sessions_recorded": 0,
        "reason": (
            "ledger is empty and no recorder ever announced itself — this is NOT "
            "evidence of zero loop-backs, it is absence of evidence either way"
        ),
    }


def _observation_status(records: list[dict]) -> dict[str, object]:
    """Split the edges into verified, unverified, and unobserved populations.

    galactus#14. Once `plan_transition_validate.sh` (PreToolUse) exists, the
    ledger holds two kinds of record — edges whose declared `From:` was checked
    against the doc on disk, and edges written before any observer existed. A
    D10 count over the whole file would silently launder the old ones into the
    new credibility, so the populations are reported separately and a caller
    cannot quote a blended number without seeing the split.

    Three-valued, mirroring `attested` and for the same reason:

    - `verified`   — the observer ran on this exact edge and the declared prior
                     matched what was on disk.
    - `unverified` — an observer was registered but did not check this edge.
                     The fragment rule skips any write that does not carry both
                     `From:` and `Status:`, and any that merely restates settled
                     front matter.
    - absent       — no observer, or the observer could not run. A PreToolUse
                     crash exits non-2 and is otherwise indistinguishable from a
                     pass, so this MUST stay distinct from `unverified`.

    Absent is never upgraded to either of the other two. Same rule already
    written into `_parse` for `kind`: an unmarked record is read as what it was
    when written, never as what a later mechanism would have made it.
    """
    verified = [r for r in records if r.get("observed") == "verified"]
    unverified = [r for r in records if r.get("observed") == "unverified"]
    unobserved = [r for r in records if "observed" not in r]
    # A value outside the vocabulary is not silently folded into `unobserved` —
    # it means a writer emitted something this reader does not understand.
    unknown = sorted(
        {
            str(r.get("observed"))
            for r in records
            if "observed" in r and r.get("observed") not in ("verified", "unverified")
        }
    )

    loop_back_verified = sum(1 for r in verified if (r["from"], r["to"]) == LOOP_BACK_EDGE)

    # Vintages let a defective observer generation be excluded by selection
    # rather than by editing an append-only file.
    vintages = sorted({r["observer"] for r in records if "observer" in r})

    return {
        "verified": len(verified),
        "unverified": len(unverified),
        "unobserved": len(unobserved),
        "unknown_values": unknown,
        "observer_vintages": vintages,
        "loop_backs_verified": loop_back_verified,
        "reason": (
            "no edge has been verified against the doc on disk; every count here "
            "is self-reported (the writer declared its own prior state)"
            if not verified
            else (
                f"{len(verified)} edge(s) verified against the doc on disk, "
                f"{len(unverified)} skipped by the fragment rule, "
                f"{len(unobserved)} written before an observer existed — "
                "do not quote a blended total"
            )
        ),
    }


def read_ledger(path: str = DEFAULT_LEDGER) -> dict[str, object]:
    """Compute the D10 metrics from the transition ledger.

    A missing ledger is `exists: False`, not an empty one. "The mechanism has
    never run" and "the mechanism ran and observed nothing" are different facts
    about the pipeline, and collapsing them is what made D10 unmeasurable in the
    first place.

    `exists: True` is necessary but not sufficient for a count to be a
    measurement — the file's presence says a recorder ran *once*, not that one
    ran during the window being read. `recorder.attested` carries that second
    fact; read it before trusting any zero here.
    """
    ledger = Path(path)
    if not ledger.is_file():
        return {
            "exists": False,
            "path": str(path),
            "reason": f"no ledger at {path}; no transition has been recorded yet",
            "unavailable": _UNAVAILABLE,
        }

    records, markers, malformed = _parse(
        ledger.read_text(encoding="utf-8", errors="replace").splitlines()
    )

    edges = Counter((r["from"], r["to"]) for r in records)
    docs = sorted({r.get("doc", "") for r in records if r.get("doc")})

    # A run is "started" when a doc first appears and "completed" when it
    # reaches a terminal state. Counted per doc rather than per record: one work
    # item is one BUILD run, however many edges it traversed.
    completed = sorted({r.get("doc", "") for r in records if r["to"] in TERMINAL_STATES})

    # Edges naming a state outside the plan-doc vocabulary. The hook validates
    # this on write, so a hit here means the ledger predates a vocabulary change
    # — worth surfacing, because it silently narrows every count above.
    known = set(STATE_COMPLETED_PHASE)
    unknown_states = sorted(
        {s for r in records for s in (r["from"], r["to"]) if s and s not in known}
    )

    loop_backs = edges[LOOP_BACK_EDGE]

    return {
        "exists": True,
        "path": str(path),
        "recorder": _recorder_status(markers, len(records)),
        "observation": _observation_status(records),
        "transitions": len(records),
        "runs_started": len(docs),
        "runs_completed": len(completed),
        "loop_backs": loop_backs,
        # The rate the graph decision actually turns on: §13 wants P(re-plan),
        # which is loop-backs per run, not loop-backs outright.
        "loop_backs_per_run": round(loop_backs / len(docs), 3) if docs else None,
        "edges": {f"{f} -> {t}": n for (f, t), n in sorted(edges.items(), key=lambda kv: -kv[1])},
        "docs": docs,
        "malformed": malformed,
        "unknown_states": unknown_states,
        "unavailable": _UNAVAILABLE,
    }
