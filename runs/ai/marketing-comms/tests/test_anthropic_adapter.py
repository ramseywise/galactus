"""The Anthropic adapter's request shape and response handling.

Exercised with a stub client rather than the real SDK: these tests assert the
adapter's own logic — how it builds the request and how it interprets a
response — not that Anthropic's API works. No network, no key, no spend.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

from config import ConfigError, Settings
from model.gateway import LLM, MAX_TOKENS, AnthropicAdapter, LLMError


@dataclass
class StubBlock:
    text: str
    type: str = "text"


@dataclass
class StubResponse:
    content: list[StubBlock]
    stop_reason: str = "end_turn"
    usage: Any = None
    """Only the truncation path reads this, so most stubs leave it None —
    which also covers the real case of a response carrying no usage details."""


@dataclass
class StubMessages:
    response: Any
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class StubClient:
    def __init__(self, response: Any) -> None:
        self.messages = StubMessages(response=response)


def _json_response(payload: dict[str, Any]) -> StubResponse:
    return StubResponse(content=[StubBlock(text=json.dumps(payload))])


@pytest.fixture
def settings() -> Settings:
    return Settings(
        anthropic_api_key="sk-ant-test",
        model="claude-sonnet-5",
        max_repairs=3,
        log_level="INFO",
    )


def _adapter(settings: Settings, response: Any) -> tuple[AnthropicAdapter, StubClient]:
    client = StubClient(response)
    return AnthropicAdapter(settings=settings, client=client), client


async def test_returns_the_parsed_object(settings, clean_draft):
    adapter, _ = _adapter(settings, _json_response(clean_draft))

    result = await adapter.complete_structured("prompt", {"type": "object"})

    assert result == clean_draft


async def test_sends_the_schema_in_output_config(settings, clean_draft):
    schema = {"type": "object", "additionalProperties": False}
    adapter, client = _adapter(settings, _json_response(clean_draft))

    await adapter.complete_structured("prompt", schema)

    call = client.messages.calls[0]
    assert call["output_config"] == {"format": {"type": "json_schema", "schema": schema}}
    assert call["model"] == "claude-sonnet-5"
    assert call["max_tokens"] == MAX_TOKENS
    assert call["messages"] == [{"role": "user", "content": "prompt"}]


async def test_images_travel_as_content_blocks_before_the_prompt(settings, clean_draft):
    """The vision regression: an image passed to the port must reach the request."""
    import base64

    adapter, client = _adapter(settings, _json_response(clean_draft))
    png = b"\x89PNG\r\n\x1a\nfake"

    await adapter.complete_structured("Read this page.", {"type": "object"}, images=[png])

    content = client.messages.calls[0]["messages"][0]["content"]
    assert content[0]["type"] == "image"
    assert content[0]["source"]["media_type"] == "image/png"
    assert base64.standard_b64decode(content[0]["source"]["data"]) == png
    assert content[-1] == {"type": "text", "text": "Read this page."}


async def test_no_images_keeps_plain_string_content(settings, clean_draft):
    adapter, client = _adapter(settings, _json_response(clean_draft))

    await adapter.complete_structured("prompt", {"type": "object"})

    assert client.messages.calls[0]["messages"] == [{"role": "user", "content": "prompt"}]


async def test_sends_no_sampling_parameters(settings, clean_draft):
    """Current models reject `temperature`/`top_p`/`top_k` with a 400."""
    adapter, client = _adapter(settings, _json_response(clean_draft))

    await adapter.complete_structured("prompt", {"type": "object"})

    call = client.messages.calls[0]
    assert "temperature" not in call
    assert "top_p" not in call
    assert "top_k" not in call


async def test_thinking_is_disabled(settings, clean_draft):
    """The regression that made every live eval case fail.

    Current models run adaptive thinking when `thinking` is omitted, and
    `max_tokens` bounds thinking and answer as one budget. Without this
    parameter the whole ceiling went to thinking and the response carried an
    empty thinking block and no draft.
    """
    adapter, client = _adapter(settings, _json_response(clean_draft))

    await adapter.complete_structured("prompt", {"type": "object"})

    assert client.messages.calls[0]["thinking"] == {"type": "disabled"}


async def test_counts_calls_for_spend_reporting(settings, clean_draft):
    """The eval harness reads `.calls` off whatever provider it is handed."""
    adapter, _ = _adapter(settings, _json_response(clean_draft))

    assert adapter.calls == 0
    await adapter.complete_structured("prompt", {"type": "object"})
    await adapter.complete_structured("prompt", {"type": "object"})

    assert adapter.calls == 2


async def test_counts_a_call_that_failed(settings):
    """A failed attempt is spend too, so it counts."""
    response = StubResponse(content=[StubBlock(text="{}")], stop_reason="refusal")
    adapter, _ = _adapter(settings, response)

    with pytest.raises(LLMError):
        await adapter.complete_structured("prompt", {"type": "object"})

    assert adapter.calls == 1


async def test_truncation_error_names_thinking_spend(settings):
    """A ceiling hit is almost always thinking, and the message should say so."""
    response = StubResponse(
        content=[StubBlock(text="")],
        stop_reason="max_tokens",
        usage=SimpleNamespace(output_tokens_details=SimpleNamespace(thinking_tokens=8000)),
    )
    adapter, _ = _adapter(settings, response)

    with pytest.raises(LLMError, match="8000 spent on thinking"):
        await adapter.complete_structured("prompt", {"type": "object"})


async def test_refusal_raises_before_content_is_read(settings):
    response = StubResponse(content=[StubBlock(text="{}")], stop_reason="refusal")
    adapter, _ = _adapter(settings, response)

    with pytest.raises(LLMError, match="declined"):
        await adapter.complete_structured("prompt", {"type": "object"})


async def test_truncated_response_raises(settings):
    response = StubResponse(
        content=[StubBlock(text='{"headline": "unter')], stop_reason="max_tokens"
    )
    adapter, _ = _adapter(settings, response)

    with pytest.raises(LLMError, match="incomplete"):
        await adapter.complete_structured("prompt", {"type": "object"})


async def test_unparseable_json_raises(settings):
    adapter, _ = _adapter(settings, StubResponse(content=[StubBlock(text="not json")]))

    with pytest.raises(LLMError, match="not valid JSON"):
        await adapter.complete_structured("prompt", {"type": "object"})


async def test_non_object_json_raises(settings):
    adapter, _ = _adapter(settings, StubResponse(content=[StubBlock(text="[1, 2]")]))

    with pytest.raises(LLMError, match="expected a JSON object"):
        await adapter.complete_structured("prompt", {"type": "object"})


async def test_empty_content_raises(settings):
    adapter, _ = _adapter(settings, StubResponse(content=[]))

    with pytest.raises(LLMError, match="no text content"):
        await adapter.complete_structured("prompt", {"type": "object"})


async def test_non_text_blocks_are_ignored(settings, clean_draft):
    response = StubResponse(
        content=[
            StubBlock(text="ignored", type="thinking"),
            StubBlock(text=json.dumps(clean_draft)),
        ]
    )
    adapter, _ = _adapter(settings, response)

    assert await adapter.complete_structured("p", {"type": "object"}) == clean_draft


def test_construction_does_not_require_a_key():
    """Importing and building the adapter must not need a credential.

    The API layer constructs one at startup; only a generation call needs the key.
    """
    adapter = AnthropicAdapter(
        settings=Settings(
            anthropic_api_key=None,
            model="claude-sonnet-5",
            max_repairs=3,
            log_level="INFO",
        )
    )

    assert adapter.model == "claude-sonnet-5"


async def test_missing_key_raises_config_error_on_call():
    adapter = AnthropicAdapter(
        settings=Settings(
            anthropic_api_key=None,
            model="claude-sonnet-5",
            max_repairs=3,
            log_level="INFO",
        )
    )

    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        await adapter.complete_structured("prompt", {"type": "object"})


def test_adapter_satisfies_the_port(settings):
    adapter, _ = _adapter(settings, _json_response({}))

    assert isinstance(adapter, LLM)
