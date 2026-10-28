"""Per-session ADK Runner management and SSE event queue.

Each session gets one Runner and one asyncio.Queue. The POST /chat endpoint
fires a background task that runs the ADK turn and enqueues SSE events; the
GET /chat/stream endpoint dequeues and forwards them to the browser.

SSE/POST ordering: the client MUST open GET /chat/stream before calling
POST /chat. session_manager guarantees the queue exists as soon as
get_or_create is called, which happens when the stream is opened.
"""

from __future__ import annotations

import json
import logging
from asyncio import Queue
from dataclasses import dataclass, field

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from ..app import app as adk_app
from ..schema import AssistantResponse

log = logging.getLogger(__name__)

_SENTINEL = object()  # signals stream end


@dataclass
class _Session:
    runner: Runner
    user_id: str = "default"
    queue: Queue = field(default_factory=Queue)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, _Session] = {}
        self._session_svc = InMemorySessionService()

    async def get_or_create(self, session_id: str, user_id: str = "default") -> _Session:
        if session_id not in self._sessions:
            try:
                await self._session_svc.create_session(
                    app_name=adk_app.name,
                    user_id=user_id,
                    session_id=session_id,
                )
            except Exception:
                log.debug("adk-session-precreate-skipped", exc_info=True)

            runner = Runner(
                app_name=adk_app.name,
                agent=adk_app.root_agent,
                session_service=self._session_svc,
            )
            self._sessions[session_id] = _Session(runner=runner, user_id=user_id)
        return self._sessions[session_id]

    async def run_turn(
        self,
        session_id: str,
        message: str,
        user_id: str = "default",
    ) -> None:
        """Execute one ADK turn and push SSE events onto the session queue."""
        session = await self.get_or_create(session_id, user_id)
        content = types.Content(role="user", parts=[types.Part(text=message)])

        def _evt(type_: str, data) -> dict:
            return {"type": type_, "data": data}

        try:
            async for event in session.runner.run_async(
                user_id=session.user_id,
                session_id=session_id,
                new_message=content,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text and not getattr(part, "thought", False):
                            await session.queue.put(_evt("text", part.text))

                if event.is_final_response():
                    structured = _extract_response(event)
                    await session.queue.put(_evt("response", structured))

        except Exception as exc:
            log.exception("adk-turn-error session_id=%s", session_id)
            await session.queue.put(_evt("error", str(exc)))
        finally:
            await session.queue.put(_SENTINEL)


def _extract_response(event) -> dict:
    """Parse the final event into an AssistantResponse dict.

    When a sub-agent has output_schema=AssistantResponse, the model outputs
    JSON. We try to parse it; if it fails we fall back to plain text wrapped
    in a minimal AssistantResponse.
    """
    text = ""
    if event.content and event.content.parts:
        text = "".join(
            p.text for p in event.content.parts if p.text and not getattr(p, "thought", False)
        )

    structured_from_state: dict | None = None
    try:
        state = event._invocation_context.session.state  # type: ignore[attr-defined]
        if "response" in state:
            raw = state["response"]
            if isinstance(raw, dict):
                structured_from_state = raw
            elif isinstance(raw, str):
                structured_from_state = json.loads(raw)
    except Exception:
        log.debug("adk-response-extract-skipped state-read", exc_info=True)

    if structured_from_state:
        try:
            return AssistantResponse(**structured_from_state).model_dump()
        except Exception:
            log.debug("adk-response-extract-skipped state-parse", exc_info=True)

    if text.strip().startswith("{"):
        try:
            parsed = json.loads(text.strip())
            return AssistantResponse(**parsed).model_dump()
        except Exception:
            log.debug("adk-response-extract-skipped text-parse", exc_info=True)

    return AssistantResponse(message=text or "(no response)").model_dump()


session_manager = SessionManager()
