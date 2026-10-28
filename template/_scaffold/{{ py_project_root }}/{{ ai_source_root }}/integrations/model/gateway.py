from __future__ import annotations

from functools import lru_cache

import anthropic

from integrations.settings import settings


@lru_cache(maxsize=1)
def get_client() -> anthropic.Anthropic:
    """The only place in integrations/ allowed to instantiate the Anthropic
    client directly — see .claude/hooks/sdk_lint.sh's sdk-factory check."""
    return anthropic.Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.llm_timeout_seconds,
        # SDK retries 408/409/429/5xx + connection errors with exponential
        # backoff. Worst-case wall-clock is timeout * (max_retries + 1) — 90s
        # at these defaults. Do not add a retry loop on top of this.
        max_retries=settings.llm_max_retries,
    )
