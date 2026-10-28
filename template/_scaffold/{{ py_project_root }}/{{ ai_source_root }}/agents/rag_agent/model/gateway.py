from __future__ import annotations

import logging
from functools import lru_cache

import anthropic

from agents.rag_agent.settings import settings

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_client() -> anthropic.Anthropic:
    """The only place allowed to instantiate the Anthropic client directly —
    see .claude/hooks/sdk_lint.sh's sdk-factory check."""
    return anthropic.Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.llm_timeout_seconds,
        # SDK retries 408/409/429/5xx + connection errors with exponential
        # backoff. Worst-case wall-clock is timeout * (max_retries + 1) — 90s
        # at these defaults. Do not add a retry loop on top of this.
        max_retries=settings.llm_max_retries,
    )


def generate(system_prompt: str, user_message: str) -> str:
    """One synchronous turn.

    Note there is no ``temperature``. Claude Opus 5 and the other
    thinking-by-default models reject ``temperature``/``top_p``/``top_k`` with a
    400, and the reject list grows with each release — a model-id gate would go
    stale. Steer with the prompt instead; add a sampling param here only if you
    have checked that your ``rag_model`` accepts one.
    """
    client = get_client()
    response = client.messages.create(
        model=settings.rag_model,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    usage = response.usage
    log.info(
        "llm.usage",
        extra={
            "agent": "rag_agent",
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "stop_reason": response.stop_reason,
        },
    )
    for block in response.content:
        if block.type == "text":
            return block.text
    # No text block at all — indistinguishable from a legitimately empty answer
    # at the call site, so say so here. stop_reason usually explains it
    # ("max_tokens" means the budget ran out before any text was emitted).
    log.warning(
        "llm.no_text_block",
        extra={
            "agent": "rag_agent",
            "stop_reason": response.stop_reason,
            "block_types": [block.type for block in response.content],
        },
    )
    return ""
