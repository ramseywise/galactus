"""Support Assistant Gateway — FastAPI server with SSE streaming.

Endpoints:
  POST /chat            Trigger a new agent turn (fires background task)
  GET  /chat/stream      SSE stream for a session
  GET  /health           Health check
"""

from __future__ import annotations

import asyncio
import json
import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, Query, Security  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from fastapi.security import APIKeyHeader  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from .session_manager import _SENTINEL, session_manager  # noqa: E402

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY", "")
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_MAX_MESSAGE_CHARS = int(os.getenv("MAX_MESSAGE_CHARS", "4000"))
# Fire-and-forget turn tasks need a live reference or the event loop may GC
# them mid-run (RUF006); done-callback discards keep the set bounded.
_turn_tasks: set[asyncio.Task] = set()


def _require_api_key(key: str | None = Security(_api_key_header)) -> None:
    if not _GATEWAY_API_KEY:
        return  # not configured — dev / local mode
    if key != _GATEWAY_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


app = FastAPI(title=f"{__package__.split('.')[1]} api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    from integrations.n8n_webhook import router as n8n_webhook_router

    app.include_router(n8n_webhook_router)
except ImportError:
    pass  # include_n8n_webhook=false — integrations/ wasn't scaffolded


class ChatRequest(BaseModel):
    session_id: str
    request_id: str
    message: str
    user_id: str = "default"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat", dependencies=[Depends(_require_api_key)])
async def post_chat(req: ChatRequest):
    """Accept a user message and start an ADK turn as a background task.

    The client must open GET /chat/stream BEFORE calling this endpoint so that
    SSE events are not lost.
    """
    if len(req.message) > _MAX_MESSAGE_CHARS:
        raise HTTPException(
            status_code=400, detail=f"Message exceeds {_MAX_MESSAGE_CHARS} characters"
        )

    # Ensure session + queue exist before the background task starts
    await session_manager.get_or_create(req.session_id, req.user_id)

    task = asyncio.create_task(
        session_manager.run_turn(
            session_id=req.session_id,
            message=req.message,
            user_id=req.user_id,
        )
    )
    _turn_tasks.add(task)
    task.add_done_callback(_turn_tasks.discard)
    return {"status": "accepted", "request_id": req.request_id}


@app.get("/chat/stream", dependencies=[Depends(_require_api_key)])
async def stream_chat(session_id: str = Query(...)):
    """SSE stream for a session.

    Events:
      data: {"type": "text",     "data": "<markdown chunk>"}
      data: {"type": "response", "data": {<AssistantResponse>}}
      data: {"type": "error",    "data": "<error message>"}
      data: {"type": "done"}
    """
    session = await session_manager.get_or_create(session_id)

    async def event_generator():
        while True:
            item = await session.queue.get()
            if item is _SENTINEL:
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
