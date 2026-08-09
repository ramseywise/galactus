# cap-hitl — Templates for hitl-builder subagent

**Tier: T1 — Runtime-coupled.** HITL genuinely requires runtime primitives; capability and parity answers differ per framework.

## Agnostic contract

Execution must be able to (a) suspend at an arbitrary point mid-run, (b) serialize the full resumption state to durable storage keyed by a stable thread/session identifier, (c) surface a structured payload to an external actor, and (d) resume from that exact point — not from the top — when an external input arrives, potentially in a different process, after an arbitrary delay. Four sub-invariants: **C1 Suspension** — the loop can halt mid-step without unwinding; **C2 Durability** — state survives process death; **C3 Addressability** — a stable ID lets an unrelated process target the paused run; **C4 Exact resume** — re-entry is at the suspension point, not a replay from turn 0. The gate predicate (`should_interrupt`), interrupt payload shape (query/confidence/intent/session_id/instructions), and resume taxonomy (pass / intent-override / free-text clarification) are runtime-neutral and portable. The env-var gate pattern (`HITL_GATES_ENABLED`, `HITL_CONFIDENCE_THRESHOLD`) is runtime-neutral policy.

| Runtime | Support | Notes |
|---|---|---|
| Claude API (raw) | ASSEMBLABLE | Stateless Messages API; tool-gated approval satisfies C1; C2/C3/C4 are caller's responsibility |
| Claude Managed Agents | NATIVE | `permission_policy: {type: "always_ask"}` → idle on `evaluated_permission == "ask"`; server-persisted session gives C2/C3/C4 |
| Google ADK | NATIVE | `LongRunningFunctionTool` pauses mid-run; state reconstructed from session history across process restarts |
| LangGraph | NATIVE | `interrupt(payload)` + checkpointer + `thread_id` + `Command(resume=value)` — the reference implementation |
| Vercel AI SDK | NATIVE* | Tool-execution approval (AI SDK 6) for C1; C2/C4 require Workflow SDK `step.waitForEvent()` |

> **Spec note:** The code below is ~90% LangGraph-specific. Portable pieces: `should_interrupt()`, the interrupt payload shape, and `resume_handler()`'s three-way taxonomy. The `hitl_gate_node` and `make_resume_command` are LangGraph plumbing.

## File: {OUTPUT_DIR}/interrupt.py

```python
from __future__ import annotations

import logging
import os
from typing import Any

from langgraph.types import Command, interrupt

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Env var helpers
# ---------------------------------------------------------------------------

def _hitl_enabled() -> bool:
    return os.environ.get("HITL_GATES_ENABLED", "false").lower() == "true"


def _hitl_threshold() -> float:
    return float(os.environ.get("HITL_CONFIDENCE_THRESHOLD", "0.3"))


# ---------------------------------------------------------------------------
# Gate predicate
# ---------------------------------------------------------------------------


def should_interrupt(state: dict[str, Any]) -> bool:
    """Return True if the current state warrants a human-in-the-loop pause.

    Triggers when HITL_GATES_ENABLED=true AND either:
    - confidence_score is below HITL_CONFIDENCE_THRESHOLD
    - intent is "ambiguous" (router couldn't classify)

    Args:
        state: LangGraph state dict. Must contain at minimum:
               confidence_score (float) and optionally intent (str).
    """
    if not _hitl_enabled():
        return False

    threshold = _hitl_threshold()
    confidence = float(state.get("confidence_score", 1.0))
    intent = state.get("intent", "")

    if confidence < threshold:
        logger.info(
            "HITL gate triggered: confidence %.3f < threshold %.3f",
            confidence,
            threshold,
        )
        return True

    if intent == "ambiguous":
        logger.info("HITL gate triggered: intent is ambiguous")
        return True

    return False


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------


def hitl_gate_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node that pauses execution and waits for human input.

    When should_interrupt() returns True, this node calls interrupt() to
    surface the current state to the human operator. Execution is paused
    until the graph is resumed with a Command(resume=...) value.

    When HITL is disabled or confidence is high, the node passes through
    without interrupting.

    Usage in graph builder:
        builder.add_node("hitl_gate", hitl_gate_node)
        builder.add_conditional_edges(
            "classify_intent",
            lambda s: "hitl_gate" if should_interrupt(s) else "answer",
        )

    Expected state keys:
        query (str)             — original user query
        confidence_score (float) — routing confidence 0–1
        intent (str)            — classified intent
        session_id (str)        — session identifier

    Returns updated state dict (may be unchanged if no interrupt occurred).
    """
    if not should_interrupt(state):
        logger.debug("HITL gate: confidence OK, passing through")
        return {}

    # Build the interrupt payload surfaced to the operator
    interrupt_payload: dict[str, Any] = {
        "query": state.get("query", ""),
        "confidence": state.get("confidence_score", 0.0),
        "intent": state.get("intent", "unknown"),
        "session_id": state.get("session_id", ""),
        "instructions": (
            "Low-confidence routing detected. Please review the query and either:\n"
            "  1. Provide the correct intent (answerable/escalation/clarification)\n"
            "  2. Provide a clarifying response directly\n"
            "  3. Type 'pass' to let the agent proceed with its best guess."
        ),
    }

    logger.info("Interrupting for HITL review — session=%s", state.get("session_id"))

    # interrupt() suspends graph execution. The return value is the human's response.
    human_input: str = interrupt(interrupt_payload)

    # Return updated state incorporating human feedback
    return resume_handler(state, human_input)


# ---------------------------------------------------------------------------
# Resume handler
# ---------------------------------------------------------------------------


def resume_handler(state: dict[str, Any], human_input: str) -> dict[str, Any]:
    """Merge human clarification into agent state after HITL resume.

    Args:
        state: Current graph state.
        human_input: The value passed via Command(resume=...).

    Returns:
        Partial state dict with updated fields. Merged into state by LangGraph.
    """
    human_input = (human_input or "").strip()

    if human_input.lower() == "pass":
        # Operator is happy with agent's best guess — clear the ambiguity flag
        logger.info("HITL: operator approved, continuing with best-guess intent")
        return {
            "intent": state.get("intent", "answerable"),
            "hitl_reviewed": True,
            "hitl_clarification": None,
        }

    # Check if the operator provided a direct intent override
    valid_intents = {"answerable", "escalation", "clarification"}
    if human_input.lower() in valid_intents:
        logger.info("HITL: operator overrode intent → %s", human_input.lower())
        return {
            "intent": human_input.lower(),
            "confidence_score": 1.0,  # human override = max confidence
            "hitl_reviewed": True,
            "hitl_clarification": None,
        }

    # Treat anything else as a human-provided clarification / rephrased query
    logger.info("HITL: operator provided clarification: %r", human_input[:100])
    return {
        "query": human_input,
        "intent": "answerable",
        "confidence_score": 1.0,
        "hitl_reviewed": True,
        "hitl_clarification": human_input,
    }


# ---------------------------------------------------------------------------
# Resume from client — Command(resume=...) pattern
# ---------------------------------------------------------------------------


def make_resume_command(human_response: str) -> Command:
    """Build a LangGraph Command to resume an interrupted graph.

    Usage:
        # In your API endpoint or CLI, after receiving the operator's input:
        command = make_resume_command("answerable")
        result = await graph.ainvoke(command, config={"configurable": {"thread_id": session_id}})

    Args:
        human_response: The operator's input — an intent override, clarification text,
                        or "pass" to accept the agent's best guess.

    Returns:
        A LangGraph Command with resume= set to the human response string.
    """
    return Command(resume=human_response)


# ---------------------------------------------------------------------------
# Example: wiring HITL into a LangGraph builder
# ---------------------------------------------------------------------------
#
#   from langgraph.graph import StateGraph
#   from {AGENT_NAME}.state import State
#   from {AGENT_NAME}.interrupt import hitl_gate_node, should_interrupt
#
#   builder = StateGraph(State)
#   builder.add_node("classify_intent", classify_intent_node)
#   builder.add_node("hitl_gate", hitl_gate_node)
#   builder.add_node("answer", answer_node)
#
#   builder.add_conditional_edges(
#       "classify_intent",
#       lambda s: "hitl_gate" if should_interrupt(s) else "answer",
#       {"hitl_gate": "hitl_gate", "answer": "answer"},
#   )
#   builder.add_edge("hitl_gate", "answer")  # resume flows into answer
```
