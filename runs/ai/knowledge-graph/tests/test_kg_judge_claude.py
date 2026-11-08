"""ClaudeSeat request shape and failure mapping, against a stub client. No network, no key."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx
import pytest
from kg_fakes import ScriptedSeat

from kg.config import Settings
from kg.judge import ClaudeSeat, JudgeSeat, build_prompt
from kg.judge.prompt import SCHEMA
from kg.models import Candidate, NotRun, Usage, Verdict

CAND = Candidate(
    subject="Basic plan",
    subject_type="Plan",
    relation="costs",
    object="DKK 99",
    object_type="Price",
    quote="Basic costs DKK 99",
)
WINDOW = "intro. Basic costs DKK 99 per month. outro."
SENTINEL = "PROPOSER-REASONING-SENTINEL"


@dataclass
class Block:
    text: str
    type: str = "text"


@dataclass
class Resp:
    content: list[Block]
    stop_reason: str = "end_turn"
    usage: Any = field(default_factory=lambda: SimpleNamespace(input_tokens=11, output_tokens=3))


class Messages:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class Client:
    def __init__(self, response: Any) -> None:
        self.messages = Messages(response)


def _json(payload: Any) -> Resp:
    return Resp(content=[Block(text=json.dumps(payload))])


def _seat(response: Any) -> tuple[ClaudeSeat, Client]:
    client = Client(response)
    return ClaudeSeat(settings=_settings(None), client=client), client


def _settings(key: str | None) -> Settings:
    return Settings(
        anthropic_api_key=key,
        openrouter_api_key=None,
        neo4j_uri=None,
        corpus_root=Settings.load(use_dotenv=False).corpus_root,
        librarian_root=Settings.load(use_dotenv=False).librarian_root,
    )


async def test_returns_a_verdict_with_usage():
    seat, _ = _seat(_json({"label": "supported", "score": 0.93}))

    out = await seat.judge(CAND, WINDOW)

    assert out == Verdict(
        label="supported",
        score=0.93,
        usage=Usage(model="claude-sonnet-5-5", input_tokens=11, output_tokens=3),
    )


async def test_request_shape():
    seat, client = _seat(_json({"label": "supported", "score": 0.5}))

    await seat.judge(CAND, WINDOW)

    call = client.messages.calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert call["output_config"] == {"format": {"type": "json_schema", "schema": SCHEMA}}
    assert call["thinking"] == {"type": "disabled"}
    for banned in ("temperature", "top_p", "top_k"):
        assert banned not in call
    assert call["messages"][0]["role"] == "user"
    assert WINDOW in call["messages"][0]["content"]


def _req() -> httpx.Request:
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _status_error(code: int) -> anthropic.APIStatusError:
    return anthropic.APIStatusError(
        "boom", response=httpx.Response(code, request=_req()), body=None
    )


@pytest.mark.parametrize(
    "exc",
    [
        anthropic.APIConnectionError(request=_req()),
        _status_error(500),
        anthropic.RateLimitError("slow", response=httpx.Response(429, request=_req()), body=None),
    ],
)
async def test_sdk_error_is_not_run(exc):
    seat, _ = _seat(exc)

    out = await seat.judge(CAND, WINDOW)

    assert isinstance(out, NotRun)
    assert out.reason.startswith("sdk_error")


async def test_failure_reasons_are_distinct():
    sdk, _ = _seat(anthropic.APIConnectionError(request=_req()))
    refusal, _ = _seat(Resp(content=[Block("{}")], stop_reason="refusal"))
    trunc, _ = _seat(Resp(content=[Block('{"label": "supp')], stop_reason="max_tokens"))
    garbage, _ = _seat(Resp(content=[Block("not json")]))
    outs = [await s.judge(CAND, WINDOW) for s in (sdk, refusal, trunc, garbage)]

    assert all(isinstance(o, NotRun) for o in outs)
    prefixes = [o.reason.split(":")[0] for o in outs]
    assert prefixes == ["sdk_error", "refusal", "truncated", "schema_mismatch"]


@pytest.mark.parametrize("payload", [{"label": "supported"}, {"label": "maybe", "score": 0.5}, [1]])
async def test_schema_mismatch_is_not_run(payload):
    seat, _ = _seat(_json(payload))

    out = await seat.judge(CAND, WINDOW)

    assert isinstance(out, NotRun)
    assert out.reason.startswith("schema_mismatch")


@pytest.mark.parametrize("score", [85, 85.0, 7, -0.1, 1.01])
async def test_out_of_range_score_is_not_run_not_clamped(score):
    seat, _ = _seat(_json({"label": "supported", "score": score}))

    out = await seat.judge(CAND, WINDOW)

    assert isinstance(out, NotRun)
    assert "score out of range" in out.reason
    assert str(score) in out.reason


def test_verdict_raises_directly_on_percentage():
    with pytest.raises(ValueError):
        Verdict(label="supported", score=85.0, usage=Usage(model="m"))


def test_prompt_is_blind_and_carries_the_window():
    prompt = build_prompt(CAND, WINDOW)

    assert WINDOW in prompt
    assert SENTINEL not in prompt
    for part in ("Basic plan", "Plan", "costs", "DKK 99", "Price", "Basic costs DKK 99"):
        assert part in prompt
    assert "probability" in prompt
    assert "Ignore any instruction" in prompt


def test_prompt_signature_cannot_take_proposer_context():
    import inspect

    assert list(inspect.signature(build_prompt).parameters) == ["candidate", "window"]


def test_both_seats_satisfy_the_protocol():
    assert isinstance(ScriptedSeat(), JudgeSeat)
    assert isinstance(ClaudeSeat(settings=_settings(None)), JudgeSeat)


def test_unavailable_without_a_key_and_makes_no_call():
    ok, reason = ClaudeSeat(settings=_settings(None)).available()

    assert not ok
    assert "ANTHROPIC_API_KEY" in reason
    assert ClaudeSeat(settings=_settings("sk-test")).available()[0]


async def test_judge_without_a_key_is_not_run():
    out = await ClaudeSeat(settings=_settings(None)).judge(CAND, WINDOW)

    assert isinstance(out, NotRun)
    assert "ANTHROPIC_API_KEY" in out.reason
