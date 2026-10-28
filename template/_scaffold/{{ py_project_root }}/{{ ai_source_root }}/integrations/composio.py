"""Composio client — discover and execute third-party app actions (Gmail,
Slack, GitHub, hundreds more) through Composio's unified tool-execution API.

Verified against ``composio==0.17.1``'s real API: prefer ``composio.tools``
(this module) over the deprecated ``composio.tool_router`` alias — the SDK's
own docstring flags this explicitly for code-generation tools. ``user_id``
scopes which connected account(s) a call acts on; connecting an account (the
OAuth-style consent for e.g. Gmail) happens once via Composio's own
dashboard/CLI, out of scope for this module — same division of responsibility
as ``google_calendar.py``'s one-time refresh-token setup.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from integrations.settings import settings


@lru_cache(maxsize=1)
def get_client() -> Any:
    if not settings.composio_api_key:
        raise RuntimeError("COMPOSIO_API_KEY is not set")
    from composio import Composio

    return Composio(api_key=settings.composio_api_key)


def get_tools(user_id: str, toolkits: list[str] | None = None, search: str | None = None) -> Any:
    """Discover available tools for a connected user, optionally scoped to
    specific toolkits (e.g. ``["GMAIL", "SLACK"]``) or a free-text search."""
    return get_client().tools.get(user_id=user_id, toolkits=toolkits, search=search)


def execute_tool(slug: str, arguments: dict, user_id: str) -> dict:
    """Execute a specific tool action by slug (e.g. ``"GMAIL_SEND_EMAIL"``)."""
    result = get_client().tools.execute(slug=slug, arguments=arguments, user_id=user_id)
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)
