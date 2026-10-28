"""Offline tests for llm_kit. No API key, no network, no token spend.

Every fixture here is a hand-rolled stub. That is deliberate: an unset
``ANTHROPIC_API_KEY`` does NOT guarantee the SDK fails to build a client — it
falls through to ``ANTHROPIC_AUTH_TOKEN``, an ``ant auth login`` profile, and
other sources — so "no key" is not a usable test condition. Assert on stubbed
response objects instead, and never let the real client be constructed.

Run: ``uv run pytest template/llm_kit/ -v``
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from llm_kit import call, cost_of, guard_tokens, text_of, usage_of


def _block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _fake_response(
    *,
    stop_reason: str = "end_turn",
    blocks: list | None = None,
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> SimpleNamespace:
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=blocks if blocks is not None else [_block("hello")],
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
    )


class _FakeMessages:
    def __init__(self, response):
        self._response = response
        self.received: dict | None = None

    def create(self, **kwargs):
        self.received = kwargs
        return self._response

    def count_tokens(self, **kwargs):
        self.received = kwargs
        return SimpleNamespace(input_tokens=self._response)


class _FakeClient:
    def __init__(self, response):
        self.messages = _FakeMessages(response)


def test_call_returns_raw_response_with_usage_intact():
    """Happy path: the caller gets the Message, not a bare string."""
    expected = _fake_response(blocks=[_block("ready")])
    client = _FakeClient(expected)

    response = call("ping", system="be terse", client=client)

    assert response is expected
    assert text_of(response) == "ready"
    assert usage_of(response) == {"input_tokens": 100, "output_tokens": 50}
    assert cost_of(response) == pytest.approx((100 * 5.00 + 50 * 25.00) / 1_000_000)

    sent = client.messages.received
    assert sent["model"] == "claude-opus-5"
    assert sent["system"] == "be terse"
    assert sent["messages"] == [{"role": "user", "content": "ping"}]
    assert "temperature" not in sent  # 400s on thinking-by-default models


def test_truncation_is_loud(caplog):
    """Boundary: stop_reason == max_tokens must surface, not pass as a short answer."""
    resp = _fake_response(stop_reason="max_tokens", blocks=[_block("half an ans")])

    with caplog.at_level(logging.WARNING, logger="llm_kit"):
        assert text_of(resp) == "half an ans"

    assert "llm_kit.truncated" in caplog.text


def test_empty_content_warns_instead_of_returning_silently(caplog):
    """Failure path: no text block returns "" — but says so first."""
    resp = _fake_response(stop_reason="end_turn", blocks=[])

    with caplog.at_level(logging.WARNING, logger="llm_kit"):
        assert text_of(resp) == ""

    assert "llm_kit.no_text_block" in caplog.text


def test_guard_tokens_raises_before_spending(caplog):
    """Budgeting: over-limit prompts fail pre-flight, not at the API."""
    client = _FakeClient(9_000)  # count_tokens returns this

    with (
        caplog.at_level(logging.WARNING, logger="llm_kit"),
        pytest.raises(ValueError, match="9000 input tokens"),
    ):
        guard_tokens("a long prompt", limit=1_000, client=client)

    assert "llm_kit.over_budget" in caplog.text
    assert client.messages.received["model"] == "claude-opus-5"


def test_cost_of_unknown_model_warns_rather_than_reporting_zero(caplog):
    resp = _fake_response()

    with caplog.at_level(logging.WARNING, logger="llm_kit"):
        assert cost_of(resp, model="not-a-model") == 0.0

    assert "llm_kit.unknown_model_price" in caplog.text
