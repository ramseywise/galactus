"""Generic inbound webhook receiver for n8n (or any external workflow tool) to
call back into this project — e.g. "workflow finished, update this record".

This is the *inbound* direction only. The other direction — n8n calling one of
this project's own agent endpoints (POST /chat, POST /api/v1/retrieval) — needs
no new code here; those endpoints already exist and are plain JSON-over-HTTP,
callable from n8n's HTTP Request node directly (see the generated README's
"Integrations" section for the request/response contract).

Verifies an HMAC-SHA256 signature (X-Webhook-Signature header, hex-encoded,
computed over the raw request body with N8N_WEBHOOK_SECRET) rather than
trusting the caller, since — unlike the outbound direction — this endpoint
accepts arbitrary POSTed events from outside the process.

Dispatches to a pluggable handler by event name via EVENT_HANDLERS. Unrecognized
events are accepted (200) but not dispatched, so an n8n workflow calling an event
this project doesn't handle yet gets a clean response rather than a 4xx it has to
special-case.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from integrations.settings import settings


class WebhookPayload(BaseModel):
    event: str
    data: dict = {}


def _handle_example_event(payload: WebhookPayload) -> None:
    """Placeholder handler — replace with real logic, or remove once you've
    added your own entries to EVENT_HANDLERS below."""
    print(f"Received '{payload.event}' webhook: {payload.data}")


EVENT_HANDLERS: dict[str, Callable[[WebhookPayload], None]] = {
    "example.event": _handle_example_event,
}

router = APIRouter()


def _verify_signature(raw_body: bytes, signature: str | None) -> None:
    if not settings.n8n_webhook_secret:
        raise HTTPException(
            status_code=503,
            detail="Webhook receiver not configured (N8N_WEBHOOK_SECRET unset)",
        )
    if not signature:
        raise HTTPException(status_code=401, detail="Missing X-Webhook-Signature header")
    expected = hmac.new(settings.n8n_webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")


@router.post("/webhooks/n8n")
async def receive_n8n_webhook(request: Request) -> dict:
    raw_body = await request.body()
    _verify_signature(raw_body, request.headers.get("x-webhook-signature"))
    payload = WebhookPayload.model_validate_json(raw_body)
    handler = EVENT_HANDLERS.get(payload.event)
    if handler:
        handler(payload)
    return {"status": "accepted", "event": payload.event}
