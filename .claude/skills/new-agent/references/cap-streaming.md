# cap-streaming — Templates for streaming-builder subagent

**Tier: T1 — Runtime-coupled.** Streaming requires runtime primitives; all four major runtimes provide NATIVE support but with different event taxonomies.

## Agnostic contract

The runtime must expose partial model output as an async iterable of typed events before generation completes, and the transport must preserve event ordering, distinguish content-type boundaries (text vs. reasoning vs. tool-call), signal terminal completion distinctly from mid-stream error, and propagate client disconnect back to cancel upstream generation. The last clause — cancellation propagation — is the one implementations most often miss. The `[DONE]` / `[SOURCES]` / `[ERROR]` sentinel protocol is a reasonable neutral wire convention for SSE transports regardless of runtime.

| Runtime | Support | Notes |
|---|---|---|
| Claude API | NATIVE | Six-event taxonomy: `message_start`, `content_block_start/stop`, `content_block_delta` (text/thinking/input_json), `message_delta/stop`. Managed Agents uses a different wire format (`content_delta`, not `content_block_delta`) — do not conflate the two surfaces |
| Google ADK | NATIVE | Runner yields events; `run_live()` supports bidirectional streaming |
| LangGraph | NATIVE | `graph.astream()` / `astream_events()` with stream modes: values / updates / messages / custom |
| Vercel AI SDK | NATIVE | `streamText`, `streamObject`, `useChat` — the SDK's centre of gravity |

> **Spec note:** The code below is a FastAPI SSE server, not a streaming contract. The `async for token in runner.astream(...)` loop is the actual streaming; the word-splitting fallback that fabricates tokens by splitting on spaces with a 10 ms sleep is a correctness anti-pattern — do not copy it. Transport (SSE/chunked HTTP/WebSocket) is orthogonal to the runtime streaming primitive.

## File: {OUTPUT_DIR}/app.py

```python
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from {AGENT_NAME}.main import AgentRunner
from {AGENT_NAME}.schema import AssistantResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="{AGENT_NAME}",
    version="0.1.0",
    description="Streaming RAG support agent",
)

# CORS — allow all origins in development; tighten in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    query: str
    session_id: str | None = None


class SyncChatResponse(BaseModel):
    session_id: str
    response: AssistantResponse


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — returns agent name and status."""
    return {"status": "ok", "agent": "{AGENT_NAME}"}


# ---------------------------------------------------------------------------
# Streaming endpoint
# ---------------------------------------------------------------------------


@app.post("/chat")
async def chat_stream(request: ChatRequest) -> EventSourceResponse:
    """Stream agent response tokens via Server-Sent Events.

    Events:
        data: <token>         — individual token (text fragment)
        data: [SOURCES]       — JSON-encoded list of Source objects
        data: [DONE]          — final event, stream is complete
        data: [ERROR] <msg>   — error event

    Client usage (JavaScript):
        const es = new EventSource('/chat', {method: 'POST', ...});
        es.onmessage = (e) => {
            if (e.data === '[DONE]') { es.close(); return; }
            appendToken(e.data);
        };
    """
    session_id = request.session_id or str(uuid.uuid4())

    async def event_generator() -> AsyncGenerator[dict[str, Any], None]:
        try:
            runner = AgentRunner(session_id=session_id)

            # Stream tokens if the runner supports it; otherwise stream the full response
            if hasattr(runner, "astream"):
                async for token in runner.astream(request.query):
                    yield {"data": token}
                    await asyncio.sleep(0)  # yield control to event loop
            else:
                # Fallback: run synchronously and emit the full message as one chunk
                response: AssistantResponse = await runner.run(request.query)

                # Simulate token-by-token streaming by splitting on spaces
                words = response.message.split(" ")
                for i, word in enumerate(words):
                    chunk = word if i == len(words) - 1 else word + " "
                    yield {"data": chunk}
                    await asyncio.sleep(0.01)  # small delay for realistic streaming

                # Emit sources as a JSON event before [DONE]
                if response.sources:
                    import json  # noqa: PLC0415
                    sources_json = json.dumps([s.model_dump() for s in response.sources])
                    yield {"data": f"[SOURCES] {sources_json}"}

            yield {"data": "[DONE]"}

        except asyncio.CancelledError:
            logger.info("Stream cancelled for session %s", session_id)
        except Exception as exc:  # noqa: BLE001
            logger.error("Stream error for session %s: %s", session_id, exc)
            yield {"data": f"[ERROR] {exc!s}"}

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# Synchronous endpoint
# ---------------------------------------------------------------------------


@app.post("/chat/sync", response_model=SyncChatResponse)
async def chat_sync(request: ChatRequest) -> SyncChatResponse:
    """Run the agent and return a complete AssistantResponse (no streaming).

    Use this endpoint for clients that don't support SSE or when the full
    response is needed before rendering.
    """
    session_id = request.session_id or str(uuid.uuid4())

    try:
        runner = AgentRunner(session_id=session_id)
        response: AssistantResponse = await runner.run(request.query)
        return SyncChatResponse(session_id=session_id, response=response)
    except Exception as exc:
        logger.error("Sync chat error for session %s: %s", session_id, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import uvicorn  # noqa: PLC0415

    port = int(os.environ.get("PORT", "8080"))
    log_level = os.environ.get("LOG_LEVEL", "info").lower()

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=os.environ.get("ENV", "development") == "development",
        log_level=log_level,
    )
```
