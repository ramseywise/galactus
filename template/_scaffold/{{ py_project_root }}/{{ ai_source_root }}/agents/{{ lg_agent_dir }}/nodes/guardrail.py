"""Guard layer 1 — screens the untrusted user turn before any model call.

This node delegates to `guardrails.guards.check_input` rather than carrying its
own pattern list. It previously held a four-entry substring check that
duplicated, less well, what `guardrails/guards.py` already did — and left the
real module called by nothing (AIT-50). One implementation, one place to extend.

The node still owns the graph-shaped decision: `check_input` returns a verdict,
and translating that verdict into `blocked` / `block_reason` state that
generate_node reads is this node's job, not the guard's.
"""

from __future__ import annotations

from guardrails.guards import check_input

from ..state import State


def guardrail_node(state: State) -> dict:
    verdict = check_input(state["message"])
    if verdict.blocked:
        # verdict.text is the refusal message, never the reasons -- surfacing
        # rule ids teaches a probing caller what tripped.
        return {"blocked": True, "block_reason": verdict.text}
    return {"blocked": False, "block_reason": ""}
