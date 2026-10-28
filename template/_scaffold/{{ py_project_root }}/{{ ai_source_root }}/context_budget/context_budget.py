"""Context-budget tracker — token counting, per-category usage logging,
compaction trigger, and prompt-caching annotation helpers.

Usage
-----
Wrap any Anthropic messages.create call with ``track_usage()``:

    from context_budget.context_budget import track_usage, should_compact, compact_history

    response = client.messages.create(...)
    track_usage(response, category_sizes={"system": 800, "tools": 120})

    if should_compact(response):
        history = compact_history(history, client, model=settings.lg_model)

For prompt-caching, annotate stable system-prompt sections before the call:

    from context_budget.context_budget import cache_breakpoint
    system = [cache_breakpoint("You are a helpful assistant ...")]

Architecture note
-----------------
- This module never instantiates an Anthropic client — import one from
  ``agents.<name>.model.gateway`` (sdk-factory rule; see .claude/hooks/sdk_lint.sh).
- ``track_usage()`` and ``should_compact()`` are pure functions: they read
  ``settings`` for thresholds and log to the standard logger, but they never
  mutate shared state. Callers own the history list.
- Compaction is opt-in per call site. The trigger fires when
  ``input_tokens / settings.max_context_tokens >= settings.compaction_threshold``;
  the decision is surfaced as a boolean so nodes can decide whether the current
  turn is a safe point to compact.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .settings import settings

log = logging.getLogger(__name__)

# ── Per-category token buckets ──────────────────────────────────────────────

_CATEGORIES = ("system", "history", "tools", "scratch")


@dataclass
class TokenUsage:
    """Breakdown of token consumption for one model call.

    ``total_input`` and ``total_output`` mirror the values in
    ``response.usage``; the category fields are caller-supplied estimates
    that must sum to <= ``total_input``.
    """

    total_input: int = 0
    total_output: int = 0
    # Per-category estimates (caller fills what it knows; rest goes to scratch)
    system: int = 0
    history: int = 0
    tools: int = 0
    scratch: int = 0

    @property
    def utilisation(self) -> float:
        """Fraction of ``settings.max_context_tokens`` consumed by input."""
        if settings.max_context_tokens <= 0:
            return 0.0
        return self.total_input / settings.max_context_tokens


# ── Core helpers ─────────────────────────────────────────────────────────────


def track_usage(
    response: Any,
    *,
    category_sizes: dict[str, int] | None = None,
) -> TokenUsage:
    """Extract token counts from an Anthropic ``Message`` response and log them.

    Parameters
    ----------
    response:
        The ``anthropic.types.Message`` (or any object with a ``.usage``
        attribute carrying ``.input_tokens`` / ``.output_tokens``).
    category_sizes:
        Optional dict with any subset of keys ``system``, ``history``,
        ``tools``, ``scratch`` — caller-supplied token estimates. Unknown
        tokens are charged to ``scratch``.

    Returns
    -------
    TokenUsage
        Populated usage object (also logged at INFO when
        ``settings.log_token_categories`` is True).
    """
    usage_attr = getattr(response, "usage", None)
    input_tokens: int = getattr(usage_attr, "input_tokens", 0)
    output_tokens: int = getattr(usage_attr, "output_tokens", 0)

    cats = dict.fromkeys(_CATEGORIES, 0)
    for key, val in (category_sizes or {}).items():
        if key in cats:
            cats[key] = int(val)

    # Charge any unaccounted input tokens to scratch
    accounted = cats["system"] + cats["history"] + cats["tools"]
    cats["scratch"] = max(0, input_tokens - accounted)

    usage = TokenUsage(
        total_input=input_tokens,
        total_output=output_tokens,
        **cats,
    )

    if settings.log_token_categories:
        log.info(
            "context_budget.usage",
            extra={
                "total_input": usage.total_input,
                "total_output": usage.total_output,
                "system": usage.system,
                "history": usage.history,
                "tools": usage.tools,
                "scratch": usage.scratch,
                "utilisation_pct": round(usage.utilisation * 100, 1),
                "threshold_pct": round(settings.compaction_threshold * 100, 1),
            },
        )

    return usage


def should_compact(response: Any) -> bool:
    """Return True when the response's input-token count crosses the
    compaction threshold.

    Call this immediately after ``track_usage()``:

        usage = track_usage(response)
        if should_compact(response):
            history = compact_history(history, client, model=model)
    """
    usage = track_usage(response, category_sizes=None)
    triggered = usage.utilisation >= settings.compaction_threshold
    if triggered:
        log.warning(
            "context_budget.compaction_triggered",
            extra={
                "utilisation_pct": round(usage.utilisation * 100, 1),
                "threshold_pct": round(settings.compaction_threshold * 100, 1),
                "max_context_tokens": settings.max_context_tokens,
            },
        )
    return triggered


def compact_history(
    history: list[dict],
    client: Any,
    *,
    model: str,
    keep_last_n: int = 2,
) -> list[dict]:
    """Summarise conversation history to reclaim context space.

    Sends the oldest ``len(history) - keep_last_n`` turns to the model for
    summarisation, then replaces them with a single assistant summary message.
    The ``keep_last_n`` most-recent turns are preserved verbatim so the agent
    retains immediate conversational context.

    Parameters
    ----------
    history:
        List of ``{"role": ..., "content": ...}`` dicts (the messages list
        passed to ``messages.create``).
    client:
        An ``anthropic.Anthropic`` or ``anthropic.AsyncAnthropic`` instance
        sourced from ``agents.<name>.model.gateway.get_client()``.
    model:
        Model to use for summarisation (typically the same as the agent model).
    keep_last_n:
        Number of trailing turns to preserve unchanged. Must be >= 1.

    Returns
    -------
    list[dict]
        Compacted history: one summary assistant message + the kept tail turns.
        Returns ``history`` unchanged if it has ``keep_last_n`` turns or fewer.
    """
    keep_last_n = max(1, keep_last_n)
    if len(history) <= keep_last_n:
        return history

    to_summarise = history[:-keep_last_n]
    tail = history[-keep_last_n:]

    conversation_text = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}" for msg in to_summarise
    )
    summary_prompt = (
        "Summarise the following conversation concisely, preserving key decisions, "
        "facts, and open questions. Output only the summary — no preamble.\n\n"
        f"{conversation_text}"
    )

    try:
        summary_response = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": summary_prompt}],
        )
        summary_text = "".join(
            block.text
            for block in summary_response.content
            if getattr(block, "type", None) == "text"
        )
        log.info(
            "context_budget.compacted",
            extra={"turns_summarised": len(to_summarise), "kept": keep_last_n},
        )
    except Exception as exc:
        # Compaction failure must not crash the agent — return history unchanged.
        log.warning(
            "context_budget.compact_failed",
            extra={"error": str(exc)},
        )
        return history

    compacted: list[dict] = [
        {"role": "assistant", "content": f"[Conversation summary]\n{summary_text}"},
        *tail,
    ]
    return compacted


# ── Prompt-caching annotation helper (Anthropic-specific) ─────────────────


def cache_breakpoint(text: str) -> dict:
    """Wrap a stable system-prompt section with Anthropic's cache_control marker.

    Sections annotated with ``cache_control: {"type": "ephemeral"}`` are
    eligible for prompt caching (cache TTL: 5 min; billed at 10 % of base
    input price on cache hit). Mark sections that do NOT change between turns:
    static instructions, tool schemas, large reference documents.

    Do NOT annotate sections that vary per turn (user query, retrieved docs,
    dynamic context) — the cache is keyed on the full prefix up to each
    breakpoint, so a changing prefix invalidates downstream cache entries.

    Anthropic docs: https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching

    Example
    -------
        system = [
            cache_breakpoint(STATIC_INSTRUCTIONS),      # cached
            {"type": "text", "text": dynamic_context},  # NOT cached
        ]
        response = client.messages.create(
            model=model,
            system=system,
            messages=messages,
            ...
        )
    """
    return {
        "type": "text",
        "text": text,
        "cache_control": {"type": "ephemeral"},
    }
