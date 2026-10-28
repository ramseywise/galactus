from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from integrations import meeting_intelligence as mi_module
from integrations.meeting_intelligence import ActionItem, MeetingExtraction, extract_action_items


def _text_response(payload: dict) -> SimpleNamespace:
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(payload))])


def test_extract_action_items_parses_mocked_llm_response(monkeypatch: pytest.MonkeyPatch) -> None:
    canned_payload = {
        "summary": "Discussed venue booking and food vendor outreach.",
        "decisions": ["Book Community Hall for the hackathon date"],
        "action_items": [
            {"description": "Confirm venue deposit", "owner": "Alex", "deadline": "2026-07-20"},
            {"description": "Email food vendors", "owner": None, "deadline": None},
        ],
    }

    fake_client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **_kwargs: _text_response(canned_payload))
    )
    monkeypatch.setattr(mi_module, "get_client", lambda: fake_client)
    monkeypatch.setattr(mi_module.settings, "anthropic_api_key", "test-key")

    result = extract_action_items("some transcript text")

    assert isinstance(result, MeetingExtraction)
    assert result.summary == canned_payload["summary"]
    assert result.decisions == canned_payload["decisions"]
    assert result.action_items == [
        ActionItem(description="Confirm venue deposit", owner="Alex", deadline="2026-07-20"),
        ActionItem(description="Email food vendors", owner=None, deadline=None),
    ]


def test_extract_action_items_raises_clearly_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mi_module.settings, "anthropic_api_key", "")

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        extract_action_items("some transcript text")
