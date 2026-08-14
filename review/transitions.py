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

**A zero here is a real answer.** The ledger began at zero on 2026-08-14 with
the mechanism proven by test rather than by fixture data, so "no loop-backs
observed" now means what it says. Before that it was ambiguous between "rare"
and "nothing records it" — which is the ambiguity §7 names as the one thing HITL
cannot paper over.
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


def _parse(lines: list[str]) -> tuple[list[dict], list[str]]:
    """Split the ledger into valid records and malformed lines.

    Malformed lines are returned, never dropped silently. A ledger that is
    partly unparseable and reports a clean count is asserting a measurement it
    did not make — the same two-way-semantics failure `Outcome` exists to
    prevent one level down.
    """
    records: list[dict] = []
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
        if not isinstance(obj, dict) or "from" not in obj or "to" not in obj:
            malformed.append(line[:120])
            continue
        records.append(obj)
    return records, malformed


def read_ledger(path: str = DEFAULT_LEDGER) -> dict[str, object]:
    """Compute the D10 metrics from the transition ledger.

    A missing ledger is `exists: False`, not an empty one. "The mechanism has
    never run" and "the mechanism ran and observed nothing" are different facts
    about the pipeline, and collapsing them is what made D10 unmeasurable in the
    first place.
    """
    ledger = Path(path)
    if not ledger.is_file():
        return {
            "exists": False,
            "path": str(path),
            "reason": f"no ledger at {path}; no transition has been recorded yet",
            "unavailable": _UNAVAILABLE,
        }

    records, malformed = _parse(ledger.read_text(encoding="utf-8", errors="replace").splitlines())

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
