"""The Anthropic proposer's request shape and failure mapping, against a stub client.

No network, no key, no spend. Every provider failure must come back as `not_run` with a
reason distinct per cause, never a raise and never `no_candidates`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic
import httpx
import pytest
import structlog.testing
from kg_fakes import ScriptedProposer

from kg.config import ConfigError, Settings
from kg.contract import load_pack
from kg.models import PageResult
from kg.observability import OP_PROPOSE, AgentSpan, redact, redact_quote
from kg.profile import Page
from kg.propose import AnthropicProposer, Proposer, ProposerError, build_schema
from kg.propose.anthropic import THINKING

PACK = load_pack(Path(__file__).parent.parent / "packs" / "eval-v1.json")
PAGE = Page(
    path="eval/judge.md",
    body="Blind relabel mitigates self-preference bias by hiding which model wrote each answer.",
)
CAND = {
    "subject": "blind relabel",
    "subject_type": "Method",
    "relation": "mitigates",
    "object": "self-preference bias",
    "object_type": "FailureMode",
    "quote": PAGE.body,
}


@dataclass
class StubBlock:
    text: str
    type: str = "text"


@dataclass
class StubUsage:
    input_tokens: int = 120
    output_tokens: int = 45


@dataclass
class StubResponse:
    content: list[StubBlock]
    stop_reason: str = "end_turn"
    usage: Any = field(default_factory=StubUsage)


class StubMessages:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class StubClient:
    def __init__(self, response: Any) -> None:
        self.messages = StubMessages(response)


def _json(payload: Any) -> StubResponse:
    return StubResponse(content=[StubBlock(json.dumps(payload))])


def _proposer(response: Any) -> tuple[AnthropicProposer, StubClient]:
    client = StubClient(response)
    settings = Settings.load(use_dotenv=False)
    return AnthropicProposer(settings=settings, client=client), client


def _http(status: int) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request("POST", "https://api.anthropic.com"))


async def test_returns_proposed_candidates_and_records_usage() -> None:
    proposer, _ = _proposer(_json({"candidates": [CAND]}))

    result = await proposer.propose(PAGE, PACK)

    assert result.status == "proposed"
    assert result.candidates[0].subject == "blind relabel"
    assert proposer.last_usage is not None
    assert (proposer.last_usage.input_tokens, proposer.last_usage.output_tokens) == (120, 45)
    assert proposer.last_usage.model == "claude-haiku-5-5"


async def test_request_shape() -> None:
    proposer, client = _proposer(_json({"candidates": []}))

    await proposer.propose(PAGE, PACK)

    call = client.messages.calls[0]
    assert call["model"] == "claude-haiku-5-5"
    assert call["output_config"] == {
        "format": {"type": "json_schema", "schema": build_schema(PACK)}
    }
    assert call["thinking"] == THINKING == {"type": "disabled"}
    assert not {"temperature", "top_p", "top_k"} & call.keys()
    (message,) = call["messages"]
    assert message["role"] == "user"
    assert PAGE.body in message["content"]


async def test_model_override_is_used() -> None:
    client = StubClient(_json({"candidates": []}))
    proposer = AnthropicProposer(
        settings=Settings.load(use_dotenv=False), client=client, model="claude-sonnet-5-5"
    )
    await proposer.propose(PAGE, PACK)
    assert client.messages.calls[0]["model"] == "claude-sonnet-5-5"


async def test_empty_candidate_list_is_no_candidates() -> None:
    proposer, _ = _proposer(_json({"candidates": []}))
    assert (await proposer.propose(PAGE, PACK)).status == "no_candidates"


def _failures() -> dict[str, Any]:
    return {
        "sdk_status": anthropic.InternalServerError("boom", response=_http(500), body=None),
        "rate_limit": anthropic.RateLimitError("slow", response=_http(429), body=None),
        "not_found": anthropic.NotFoundError("no model", response=_http(404), body=None),
        "connection": anthropic.APIConnectionError(
            request=httpx.Request("POST", "https://api.anthropic.com")
        ),
        "refusal": StubResponse([StubBlock("{}")], stop_reason="refusal"),
        "truncated": StubResponse([StubBlock('{"candidates": [{"subj')], stop_reason="max_tokens"),
        "bad_json": StubResponse([StubBlock("not json")]),
        "no_text": StubResponse([]),
        "not_object": _json([1, 2]),
        "wrong_shape": _json({"candidates": "none"}),
        "bad_item": _json({"candidates": [{**CAND, "quote": ""}]}),
        "missing_field": _json({"candidates": [{"subject": "x"}]}),
    }


@pytest.mark.parametrize("case", list(_failures()))
async def test_every_failure_is_not_run_never_a_raise_or_no_candidates(case: str) -> None:
    proposer, _ = _proposer(_failures()[case])

    result = await proposer.propose(PAGE, PACK)

    assert isinstance(result, PageResult)
    assert result.status == "not_run"
    assert result.reason
    assert result.candidates == ()


async def test_each_cause_has_a_distinct_reason() -> None:
    reasons: dict[str, str] = {}
    for case, response in _failures().items():
        proposer, _ = _proposer(response)
        reasons[case] = (await proposer.propose(PAGE, PACK)).reason or ""

    # the causes the plan names must never share a reason
    named = [reasons[k] for k in ("sdk_status", "refusal", "truncated", "bad_json")]
    assert len({r.split(":")[0] for r in named}) == 4
    assert reasons["refusal"].startswith("refusal")
    assert reasons["truncated"].startswith("truncated")
    assert reasons["rate_limit"].split(":")[0] != reasons["sdk_status"].split(":")[0]
    assert reasons["sdk_status"].endswith("HTTP 500")


async def test_failed_call_still_counts_and_clears_usage() -> None:
    proposer, _ = _proposer(anthropic.InternalServerError("x", response=_http(500), body=None))
    await proposer.propose(PAGE, PACK)
    assert proposer.calls == 1
    assert proposer.last_usage is None


async def test_truncated_call_still_records_usage() -> None:
    proposer, _ = _proposer(StubResponse([StubBlock("{")], stop_reason="max_tokens"))
    await proposer.propose(PAGE, PACK)
    assert proposer.last_usage is not None


def test_construction_needs_no_key_but_a_call_does(clean_env: pytest.MonkeyPatch) -> None:
    proposer = AnthropicProposer(settings=Settings.load(use_dotenv=False))
    assert proposer.model == "claude-haiku-5-5"
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        proposer._get_client()


def test_fakes_and_adapter_satisfy_the_protocol() -> None:
    assert isinstance(ScriptedProposer(), Proposer)
    assert isinstance(AnthropicProposer(settings=Settings.load(use_dotenv=False)), Proposer)
    assert issubclass(ProposerError, RuntimeError)


# --- observability ---------------------------------------------------------------------


def test_redact_reduces_quote_to_its_length() -> None:
    assert redact_quote("abcdef") == "<quote len=6>"
    out = redact({"quote": "secret page text", "page_path": "a.md"})
    assert out == {"quote": "<quote len=16>", "page_path": "a.md"}


def test_span_attrs_and_log_never_carry_quote_text() -> None:
    sp = AgentSpan(OP_PROPOSE, "m", metadata={"quote": "secret page text"})
    sp.record_usage(3, 4)
    attrs = sp.to_otel_attrs()
    assert attrs["gen_ai.operation.name"] == "kg.propose"
    assert attrs["gen_ai.usage.output_tokens"] == 4
    assert "secret page text" not in json.dumps(attrs)
    assert attrs["kg.quote"] == "<quote len=16>"


async def test_proposer_emits_a_span_that_records_the_failure() -> None:
    # capture_logs, not capsys: marketing-comms configures structlog globally in the same
    # session, so where rendered output goes depends on test order.
    proposer, _ = _proposer(StubResponse([StubBlock("{}")], stop_reason="refusal"))
    with structlog.testing.capture_logs() as events:
        await proposer.propose(PAGE, PACK)
    logged = json.dumps(events, default=str)
    assert "kg.propose" in logged
    assert "refusal" in logged
    assert PAGE.body not in logged
