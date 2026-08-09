# cap-a2a — Templates for agent-to-agent-builder subagent

**Tier: T1 — Runtime-coupled.** Agent-to-agent communication requires runtime or transport primitives; support varies significantly across frameworks.

## Agnostic contract

One agent must be able to address another as a peer, transmit a structured request across a trust boundary, authenticate the caller, receive a schema-conformant response, and handle partial failure when fanning out to multiple peers — without either agent sharing the other's process, memory, or model context. The "not sharing context" clause is what separates true peer A2A from in-process delegation (subagents/subgraphs), which is a distinct capability. The transport-level content here — exponential backoff (`_BACKOFF_BASE * 2^attempt`), 4xx-no-retry / 5xx-retry split, `asyncio.gather(return_exceptions=True)` broadcast with per-agent error isolation — is genuine HTTP client hygiene portable across all runtimes.

| Runtime | Support | Notes |
|---|---|---|
| Claude API (raw) | ASSEMBLABLE | No first-party A2A protocol; MCP is the recommended assembly route for cross-process structured tool exposure |
| Claude Managed Agents | NATIVE (delegation) | `multiagent: {type: "coordinator", agents: [...]}` with per-subagent threads — but this is in-session delegation, not cross-process peer A2A |
| Google ADK | NATIVE | Ships A2A protocol support; agent-to-agent is a design centre; cross-runtime interrupt format shared with ADK Go |
| LangGraph | ASSEMBLABLE | Subgraphs for in-process composition; cross-process peer A2A is hand-rolled or via LangGraph Platform assistant API |
| Vercel AI SDK | ASSEMBLABLE | A2A 1.0 ecosystem protocol; Vercel integration (`json-renderer`, A2UI) is proof-of-concept stage |

> **Security fix (2026-07-20):** The original `_verify_secret()` had an auth-bypass: when `_SHARED_SECRET` was set but the request carried no header, the function returned (allowed) instead of rejecting. Fixed — missing header now raises 401 unconditionally when a secret is configured. Uses `secrets.compare_digest` (constant-time) to prevent timing attacks. Shared-secret-in-header is the minimum acceptable auth; prefer mTLS or OAuth 2.0 for production cross-trust-boundary calls.

## File: {OUTPUT_DIR}/a2a_client.py

```python
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0  # seconds; retry delay = _BACKOFF_BASE * 2^attempt


class A2AClient:
    """HTTP client for agent-to-agent communication.

    Agents expose a POST /a2a/{agent_name} endpoint (see a2a_router.py).
    This client handles:
    - Request dispatch with shared-secret auth header
    - Parallel broadcast to multiple agents
    - Exponential backoff retry (max 3 attempts)
    - 30-second timeout per request

    Usage:
        client = A2AClient(base_url="http://localhost:8080")
        response = await client.send("billing_agent", {"query": "What is my balance?"})
        responses = await client.broadcast(["billing_agent", "tax_agent"], payload)
    """

    def __init__(
        self,
        base_url: str,
        secret: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._secret = secret or os.environ.get("A2A_SECRET", "")
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Single send
    # ------------------------------------------------------------------

    async def send(
        self,
        target_agent: str,
        payload: dict[str, Any],
        *,
        retries: int = _MAX_RETRIES,
    ) -> dict[str, Any]:
        """POST payload to /a2a/{target_agent} with retry and backoff.

        Args:
            target_agent: Name of the destination agent.
            payload: Dict to send as JSON body.
            retries: Number of retry attempts on transient failures.

        Returns:
            Parsed JSON response dict from the target agent.

        Raises:
            httpx.HTTPStatusError: On non-retryable HTTP errors (4xx).
            RuntimeError: If all retry attempts are exhausted.
        """
        url = f"{self._base_url}/a2a/{target_agent}"
        headers = self._build_headers()
        last_exc: Exception | None = None

        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)

                    # 4xx errors are not retried (caller error)
                    if 400 <= response.status_code < 500:
                        response.raise_for_status()

                    # 5xx are retried
                    if response.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            f"Server error {response.status_code}",
                            request=response.request,
                            response=response,
                        )

                    return response.json()

            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt < retries - 1:
                    delay = _BACKOFF_BASE * (2**attempt)
                    logger.warning(
                        "A2A send to %r failed (attempt %d/%d): %s — retrying in %.1fs",
                        target_agent,
                        attempt + 1,
                        retries,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)

        raise RuntimeError(
            f"A2A send to {target_agent!r} failed after {retries} attempts: {last_exc}"
        )

    # ------------------------------------------------------------------
    # Broadcast
    # ------------------------------------------------------------------

    async def broadcast(
        self,
        agents: list[str],
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Send the same payload to multiple agents in parallel.

        Args:
            agents: List of agent names to broadcast to.
            payload: Payload to send to each agent.

        Returns:
            List of response dicts in the same order as agents.
            Failed agents return {"error": "<message>", "agent": "<name>"}.
        """
        tasks = [self.send(agent, payload) for agent in agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        responses: list[dict[str, Any]] = []
        for agent, result in zip(agents, results):
            if isinstance(result, Exception):
                logger.error("Broadcast to %r failed: %s", agent, result)
                responses.append({"error": str(result), "agent": agent})
            else:
                responses.append(result)  # type: ignore[arg-type]

        return responses

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._secret:
            headers["X-A2A-Secret"] = self._secret
        return headers
```

## File: {OUTPUT_DIR}/a2a_router.py

```python
from __future__ import annotations

import logging
import os
import secrets
from typing import Any, Callable

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from {AGENT_NAME}.schema import AssistantResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_SHARED_SECRET = os.environ.get("A2A_SECRET", "")

security = HTTPBearer(auto_error=False)


def _verify_secret(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    x_a2a_secret: str | None = Header(default=None, alias="X-A2A-Secret"),
) -> None:
    """Validate the shared secret from X-A2A-Secret or Bearer token header.

    Once A2A_SECRET is configured, a request MUST present a matching secret in
    one of the two accepted headers. A missing header is rejected exactly like a
    wrong one — anything else means omitting auth entirely is easier than
    defeating it.
    """
    if not _SHARED_SECRET:
        # Secret not configured — skip auth (development mode)
        logger.debug("A2A auth: no secret configured, skipping verification")
        return

    # Accept either header. The client in this same spec sends X-A2A-Secret, so
    # a Bearer-only server silently fails to authenticate its own generated client.
    token = x_a2a_secret or (credentials.credentials if credentials else None)

    if token is None:
        raise HTTPException(status_code=401, detail="Missing A2A secret")

    # Constant-time compare — a shared secret checked with != leaks its prefix
    # to a timing attacker.
    if not secrets.compare_digest(token, _SHARED_SECRET):
        raise HTTPException(status_code=401, detail="Invalid A2A secret")


# ---------------------------------------------------------------------------
# Request / response schema
# ---------------------------------------------------------------------------


class A2ARequest(BaseModel):
    query: str
    session_id: str | None = None
    context: dict[str, Any] | None = None
    source_agent: str | None = None


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

_HANDLERS: dict[str, Callable] = {}


def register_handler(agent_name: str, handler: Callable) -> Callable:
    """Decorator to register a handler for incoming A2A messages.

    Usage:
        @register_handler("billing_agent")
        async def handle_billing(request: A2ARequest) -> AssistantResponse:
            ...
    """
    _HANDLERS[agent_name] = handler
    logger.debug("Registered A2A handler for agent: %s", agent_name)
    return handler


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/a2a", tags=["a2a"])


@router.post("/{agent_name}")
async def receive_a2a_message(
    agent_name: str,
    request: A2ARequest,
    _auth: None = Depends(_verify_secret),
) -> AssistantResponse:
    """Receive an A2A message and route it to the registered handler.

    Authentication: pass the shared secret in one of:
    - X-A2A-Secret header
    - Authorization: Bearer <secret> header

    If no handler is registered for agent_name, returns 404.
    If the handler raises, returns 500 with error detail.
    """
    handler = _HANDLERS.get(agent_name)

    if handler is None:
        available = list(_HANDLERS)
        logger.warning(
            "No A2A handler for %r. Registered: %s", agent_name, available
        )
        raise HTTPException(
            status_code=404,
            detail=f"No handler registered for agent {agent_name!r}. "
                   f"Available: {available}",
        )

    logger.info(
        "A2A message received for %r from %r: %r",
        agent_name,
        request.source_agent,
        request.query[:80],
    )

    try:
        result = await handler(request)
    except Exception as exc:  # noqa: BLE001
        logger.error("A2A handler for %r raised: %s", agent_name, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not isinstance(result, AssistantResponse):
        raise TypeError(
            f"A2A handler for {agent_name!r} must return AssistantResponse, "
            f"got {type(result).__name__}"
        )

    return result


# ---------------------------------------------------------------------------
# Mount example — add this to your FastAPI app in app.py:
#
#   from {AGENT_NAME}.a2a_router import router as a2a_router, register_handler
#   app.include_router(a2a_router)
#
#   @register_handler("{AGENT_NAME}")
#   async def handle_incoming(request: A2ARequest) -> AssistantResponse:
#       runner = AgentRunner(session_id=request.session_id or str(uuid.uuid4()))
#       return await runner.run(request.query)
# ---------------------------------------------------------------------------
```
