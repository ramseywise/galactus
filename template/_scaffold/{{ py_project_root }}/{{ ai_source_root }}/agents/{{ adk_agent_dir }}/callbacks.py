"""ADK before-model callbacks for the support assistant.

Single concern: prune old KB passage text from prior-turn tool responses to
prevent context window bloat during multi-turn sessions.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

_INVOCATION_ID_KEY = "_invocation_id"
_KB_TOOL_NAME = "search_articles"


def prune_old_kb_passages(callback_context: Any, llm_request: Any) -> None:
    """Strip search_articles text from prior-invocation tool responses.

    Keeps all KB tool responses from the *current* invocation intact so the model
    can synthesise across multiple same-turn searches. Replaces text from earlier
    invocations (prior user turns) with a placeholder to avoid context window bloat.

    Falls back to keeping only the most recent KB response when no invocation ID
    is available (e.g. first turn or state not yet populated).
    """
    state = callback_context.state
    current_invocation_id = state.get(_INVOCATION_ID_KEY)
    contents = getattr(llm_request, "contents", None) or []

    kb_indices: list[int] = []
    for i, content in enumerate(contents):
        for part in getattr(content, "parts", None) or []:
            fn_resp = getattr(part, "function_response", None)
            if fn_resp and getattr(fn_resp, "name", "") == _KB_TOOL_NAME:
                kb_indices.append(i)
                break

    if not kb_indices:
        return

    if current_invocation_id:
        kb_calls: list[dict] = state.get("_kb_calls") or []
        current_count = sum(1 for c in kb_calls if c.get("invocation_id") == current_invocation_id)
        prune_indices = set(kb_indices[:-current_count]) if current_count else set(kb_indices)
    else:
        prune_indices = set(kb_indices[:-1])

    for idx in prune_indices:
        for part in getattr(contents[idx], "parts", None) or []:
            fn_resp = getattr(part, "function_response", None)
            if fn_resp and getattr(fn_resp, "name", "") == _KB_TOOL_NAME:
                resp = getattr(fn_resp, "response", {}) or {}
                if "result" in resp:
                    resp["result"] = "[passage text pruned — see current turn tool responses]"
                    log.debug("pruned kb passage at content index %d", idx)


def before_model_rag(callback_context: Any, llm_request: Any) -> None:
    """before_model_callback for rag_agent — prunes stale KB passages."""
    prune_old_kb_passages(callback_context, llm_request)
    return None
