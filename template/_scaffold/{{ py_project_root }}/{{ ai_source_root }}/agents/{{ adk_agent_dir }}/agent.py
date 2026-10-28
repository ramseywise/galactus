"""Root agent (support_assistant) — routes every user message to the correct sub-agent."""

from __future__ import annotations

import re
from pathlib import Path

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from .sub_agents.direct_agent import direct_agent
from .sub_agents.rag_agent import rag_agent

_PROMPTS = Path(__file__).parent / "prompts"
_INSTRUCTION = (_PROMPTS / "support_assistant.txt").read_text()
_TRIED_AGENTS_TEMPLATE = (_PROMPTS / "router_tried_agents.txt").read_text()

# ---------------------------------------------------------------------------
# Guardrail patterns
# ---------------------------------------------------------------------------

_INJECTION_RE = re.compile(
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions"
    r"|forget\s+everything"
    r"|system\s*:\s*you\s+are",
    re.IGNORECASE,
)

_BLOCKED_RESPONSE = (
    '{"message": "I detected an unusual pattern in your message and cannot process it. '
    'Please rephrase your request.", "contact_support": true}'
)


# ---------------------------------------------------------------------------
# Router callbacks
# ---------------------------------------------------------------------------


def provide_router_instruction(ctx: ReadonlyContext) -> str:
    state = ctx._invocation_context.session.state
    tried = state.get("tried_agents", [])
    if not tried:
        return ""
    return _TRIED_AGENTS_TEMPLATE.format(agents=", ".join(tried))


def _before_agent_callback(callback_context: CallbackContext) -> types.Content | None:
    invocation_id = callback_context._invocation_context.invocation_id
    if callback_context.state.get("_tried_agents_invocation") != invocation_id:
        callback_context.state["tried_agents"] = []
        callback_context.state["_tried_agents_invocation"] = invocation_id
    # Store invocation_id so sub-agent pruning callbacks can identify current-turn KB calls
    callback_context.state["_invocation_id"] = invocation_id
    return None


def _guardrail_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> LlmResponse | None:
    if not llm_request.contents:
        return None

    for content in reversed(llm_request.contents):
        role = getattr(content, "role", "")
        if role != "user":
            continue
        parts = getattr(content, "parts", [])
        text = "".join(getattr(p, "text", "") or "" for p in parts)

        if _INJECTION_RE.search(text):
            return LlmResponse(
                content=types.Content(role="model", parts=[types.Part(text=_BLOCKED_RESPONSE)]),
            )
        break

    return None


# ---------------------------------------------------------------------------
# Root agent
# ---------------------------------------------------------------------------

root_agent = Agent(
    model="gemini-2.5-flash-lite",
    name="support_assistant",
    description=(
        "Routing assistant for a support knowledge base. Classifies user requests "
        "and delegates to the correct sub-agent: rag_agent (retrieval-grounded answers) "
        "or direct_agent (conversational / general knowledge). "
        "Does not answer domain questions directly."
    ),
    generate_content_config=types.GenerateContentConfig(
        temperature=0,
        max_output_tokens=150,
    ),
    static_instruction=types.Content(role="user", parts=[types.Part(text=_INSTRUCTION)]),
    instruction=provide_router_instruction,
    sub_agents=[rag_agent, direct_agent],
    before_agent_callback=_before_agent_callback,
    before_model_callback=_guardrail_callback,
)
