"""The Anthropic adapter's request shape and response handling.

Exercised with a stub client rather than the real SDK: these tests assert the
adapter's own logic — how it builds the request and how it interprets a
response — not that Anthropic's API works. No network, no key, no spend.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
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


async def test_sends_no_sampling_parameters(settings, clean_draft):
    """Current models reject `temperature`/`top_p`/`top_k` with a 400."""
    adapter, client = _adapter(settings, _json_response(clean_draft))

    await adapter.complete_structured("prompt", {"type": "object"})

    call = client.messages.calls[0]
    assert "temperature" not in call
    assert "top_p" not in call
    assert "top_k" not in call


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
