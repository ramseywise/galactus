"""Extracts structured action items/decisions from a meeting transcript via one
LLM call. Input is plain transcript text (from a Granola/Fireflies webhook,
manual paste, whatever) — this module doesn't fetch transcripts itself."""

from __future__ import annotations

import json

from pydantic import BaseModel

from integrations.model.gateway import get_client
from integrations.settings import settings

_SYSTEM_PROMPT = """\
You extract structured action items and decisions from a meeting transcript. \
Respond with ONLY a JSON object matching this shape, no other text:
{"summary": "...", "decisions": ["..."], "action_items": \
[{"description": "...", "owner": "... or null", "deadline": "... or null"}]}\
"""


class ActionItem(BaseModel):
    description: str
    owner: str | None = None
    deadline: str | None = None


class MeetingExtraction(BaseModel):
    summary: str
    decisions: list[str] = []
    action_items: list[ActionItem] = []


def extract_action_items(transcript: str) -> MeetingExtraction:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set for integrations/meeting_intelligence")
    client = get_client()
    response = client.messages.create(
        model=settings.meeting_intelligence_model,
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": transcript}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    return MeetingExtraction.model_validate(json.loads(text))
