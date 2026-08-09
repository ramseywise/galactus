# cap-compaction — Templates for context compaction

**Tier: T2 — Runtime-adjacent.** The compaction strategy (what to evict, when to trigger) is runtime-agnostic; the node implementation is framework-specific. LangGraph gets a graph node; ADK gets a session-state hook; Anthropic-native agents can use server-side `clear_tool_uses`.

## Agnostic contract

A long-running agent must be able to reduce its context window footprint at defined trigger points without losing the information required to continue the current task. The two portable techniques are: (1) **summarizer node** — LLM pass that condenses conversation history and completed tool results into a structured summary; (2) **tool-result eviction** — drop tool call/result pairs for completed steps, retaining only their final outputs. Both must preserve: the current plan state, schema contracts, and any committed outputs. See `agent-context.md §3` for trigger points and what must survive.

| Runtime | Support | Notes |
|---|---|---|
| Claude API (raw) | NATIVE | `clear_tool_uses` and `clear_thinking` are server-side context-editing primitives. Server-managed compaction available in long-context agentic calls |
| Claude Managed Agents | NATIVE | Platform-managed compaction between turns; configure via `max_tokens_to_sample` on subagent turns |
| Google ADK | ASSEMBLABLE | Session state hook: summarize history before reconstructing session from DB state each request |
| LangGraph | ASSEMBLABLE | Compaction node between phases (`add_node("compact", compact_node)`); conditional edge triggers on token count |
| Vercel AI SDK | ASSEMBLABLE | Message array trim + summary injection before each API call; no framework primitive |

> **Design note:** The `compact_node` below is LangGraph-specific but the `summarize_history` async function is pure Python with no framework imports — it works in any runtime. The `should_compact` trigger is a heuristic; tune the 80% threshold and rolling window for your model and use case.

## Design notes

- **Trigger proactively**: compact when approaching 80% of the context limit, not when it's full. Reactive compaction at 100% loses information at the worst possible moment.
- **Phase boundaries are compaction boundaries**: after completing a plan phase, before spawning a subagent. This is cheaper than mid-turn compaction.
- **Preserve the summary structure**: the summary must include decisions made, active task state, and schema invariants — not just a prose summary. Use structured fields.
- **Rolling window**: keep the last N turns verbatim for coherence; summarize everything before that. N=6 is a reasonable default for most tasks.
- **Tool-result eviction is cheaper than summarization**: evict completed-step tool results first; call the LLM summarizer only when that's not enough.

## File: {OUTPUT_DIR}/compaction.py

```python
"""Context compaction utilities for {AGENT_NAME}.

Two strategies:
1. summarize_history(): LLM-based condensation of conversation history
2. evict_tool_results(): Drop completed-step tool call/result pairs

The compact_node() function is a LangGraph node that applies both.
The summarize_history() function is runtime-agnostic.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Rolling window: keep this many recent messages verbatim; summarize the rest.
_ROLLING_WINDOW = 6

# Trigger compaction when token count exceeds this fraction of the model limit.
_COMPACT_THRESHOLD = 0.80


# ---------------------------------------------------------------------------
# Runtime-agnostic: summarize history
# ---------------------------------------------------------------------------


async def summarize_history(
    messages: list[dict[str, Any]],
    llm: Any,
    rolling_window: int = _ROLLING_WINDOW,
) -> list[dict[str, Any]]:
    """Condense conversation history older than the rolling window into a summary.

    Keeps the most recent `rolling_window` messages verbatim.
    Older messages are summarized by an LLM call into a single system message.

    Args:
        messages: Full conversation message list.
        llm: Async LLM client with .ainvoke() returning a message with .content.
        rolling_window: Number of most-recent messages to keep verbatim.

    Returns:
        Compacted message list: [summary_system_msg] + last N messages.
    """
    if len(messages) <= rolling_window:
        logger.debug("Compaction: %d messages ≤ rolling window %d — skip", len(messages), rolling_window)
        return messages

    to_summarize = messages[:-rolling_window]
    recent = messages[-rolling_window:]

    # Build a summary request
    history_text = "\n".join(
        f"{m.get('role', 'unknown').upper()}: {_extract_text(m)}"
        for m in to_summarize
    )
    summary_prompt = (
        "Summarize the following conversation history. "
        "Preserve: decisions made, current task state, schema invariants, and any committed outputs. "
        "Be concise. Use bullet points.\n\n"
        f"{history_text}"
    )

    try:
        result = await llm.ainvoke(summary_prompt)
        summary_text = result.content if hasattr(result, "content") else str(result)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Summarization LLM call failed: %s — retaining full history", exc)
        return messages

    summary_msg = {
        "role": "system",
        "content": f"[Compacted history summary]\n{summary_text}",
    }

    compacted = [summary_msg] + recent
    logger.info(
        "Compaction: %d messages → %d (summarized %d into 1 + kept %d)",
        len(messages),
        len(compacted),
        len(to_summarize),
        len(recent),
    )
    return compacted


def evict_tool_results(
    messages: list[dict[str, Any]],
    keep_last_n: int = 2,
) -> list[dict[str, Any]]:
    """Drop completed-step tool call/result pairs, keeping only the most recent N.

    Evicts tool_use / tool_result message pairs for steps that are no longer
    in the active reasoning window. The model does not need to see the full
    history of tool calls — only the outcomes that inform the current step.

    Args:
        messages: Full conversation message list.
        keep_last_n: Number of most recent tool call/result pairs to retain.

    Returns:
        Message list with stale tool call/result pairs evicted.
    """
    # Identify tool call/result pair indices
    tool_pair_indices: list[tuple[int, int]] = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        if msg.get("role") == "assistant" and _has_tool_use(msg):
            # Next message should be the tool result
            if i + 1 < len(messages) and messages[i + 1].get("role") == "tool":
                tool_pair_indices.append((i, i + 1))
                i += 2
                continue
        i += 1

    if len(tool_pair_indices) <= keep_last_n:
        return messages

    # Evict all but the last N pairs
    evict_indices: set[int] = set()
    for call_idx, result_idx in tool_pair_indices[:-keep_last_n]:
        evict_indices.add(call_idx)
        evict_indices.add(result_idx)

    evicted = [m for idx, m in enumerate(messages) if idx not in evict_indices]
    logger.info(
        "Tool-result eviction: removed %d messages (%d pairs), kept %d",
        len(evict_indices),
        len(evict_indices) // 2,
        keep_last_n,
    )
    return evicted


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------


def should_compact(state: dict[str, Any], threshold: float = _COMPACT_THRESHOLD) -> bool:
    """Heuristic: should we compact now?

    Uses message count as a proxy for token count. Override with actual token
    counting (e.g., tiktoken) if you have it.

    Args:
        state: LangGraph state dict with a "messages" key.
        threshold: Fraction of a notional 200-message budget to trigger at.

    Returns:
        True if compaction is recommended.
    """
    messages = state.get("messages", [])
    # 200-message budget is a rough heuristic for a 200k context model at typical verbosity.
    notional_budget = 200
    return len(messages) >= int(notional_budget * threshold)


async def compact_node(state: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    """LangGraph node: apply tool-result eviction then history summarization.

    Wires into the graph as:
        graph.add_node("compact", compact_node)
        graph.add_conditional_edges("some_node", lambda s: "compact" if should_compact(s) else "next_node")

    Requires state["messages"] and state["llm"] (or pass the LLM via config).

    Args:
        state: LangGraph state dict.
        config: Optional RunnableConfig; use config["configurable"]["llm"] if provided.

    Returns:
        State delta with compacted messages.
    """
    messages = state.get("messages", [])
    llm = (config or {}).get("configurable", {}).get("llm") or state.get("llm")

    if not messages:
        return {}

    # Step 1: evict stale tool results (cheap, no LLM call)
    messages = evict_tool_results(messages)

    # Step 2: summarize history (LLM call — only if still needed)
    if llm and len(messages) > _ROLLING_WINDOW:
        messages = await summarize_history(messages, llm)

    return {"messages": messages}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_text(msg: dict[str, Any]) -> str:
    """Extract text content from a message dict."""
    content = msg.get("content", "")
    if isinstance(content, str):
        return content[:200]  # truncate for the summary prompt
    if isinstance(content, list):
        parts = [p.get("text", "") for p in content if isinstance(p, dict) and "text" in p]
        return " ".join(parts)[:200]
    return str(content)[:200]


def _has_tool_use(msg: dict[str, Any]) -> bool:
    """Return True if the assistant message contains a tool_use block."""
    content = msg.get("content", [])
    if isinstance(content, list):
        return any(isinstance(p, dict) and p.get("type") == "tool_use" for p in content)
    return False
```
