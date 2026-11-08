"""JevSeat request shape and failure mapping against httpx.MockTransport. No network, no key.

The request shape is UNVERIFIED against live docs; `REQUEST_SHAPE` pins it here."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from kg_fakes import ScriptedProposer
from test_kg_build import CAL, GRADER, Env

from kg import build as kb
from kg.config import Settings
from kg.judge import JevSeat, JudgeSeat
from kg.models import Candidate, NotRun, Verdict

WINDOW = "intro. Calibration is measured with ECE. outro."

REQUEST_SHAPE = {
    "model": "typesafe/jev-1.13",
    "question_type": "noul",
    "input": {
        "subject": CAL.subject,
        "subject_type": CAL.subject_type,
        "relation": CAL.relation,
        "object": CAL.object,
        "object_type": CAL.object_type,
        "quote": CAL.quote,
        "evidence": WINDOW,
    },
}


def _settings(key: str | None) -> Settings:
    base = Settings.load(use_dotenv=False)
    return Settings(
        anthropic_api_key=None,
        openrouter_api_key=key,
        neo4j_uri=None,
        corpus_root=base.corpus_root,
        librarian_root=base.librarian_root,
    )


def _seat(handler: Callable[[httpx.Request], httpx.Response]) -> JevSeat:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return JevSeat(settings=_settings("sk-fake"), client=client)


def _json(payload: object, status: int = 200) -> Callable[[httpx.Request], httpx.Response]:
    return lambda req: httpx.Response(status, json=payload)


def _judge(seat: JevSeat, cand: Candidate = CAL) -> Verdict | NotRun:
    return asyncio.run(seat.judge(cand, WINDOW))


def test_satisfies_the_protocol_and_is_named() -> None:
    seat = _seat(_json({}))
    assert isinstance(seat, JudgeSeat) and seat.name == "jev"


def test_unavailable_without_key_by_name() -> None:
    seat = JevSeat(settings=_settings(None))
    assert seat.available() == (False, "OPENROUTER_API_KEY not set")
    out = _judge(seat)
    assert isinstance(out, NotRun) and out.reason.startswith("unavailable:")
    assert JevSeat(settings=_settings("k")).available() == (True, "")


def test_request_body_url_and_auth_match_documented_shape() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, json={"probability": 0.8})

    out = _judge(_seat(handler))
    assert isinstance(out, Verdict)
    (req,) = seen
    assert req.method == "POST"
    assert str(req.url) == "https://openrouter.ai/api/alpha/decisions"
    assert req.headers["authorization"] == "Bearer sk-fake"
    assert json.loads(req.content) == REQUEST_SHAPE


@pytest.mark.parametrize(
    ("p", "label"),
    [(0.5, "supported"), (1.0, "supported"), (0.49, "not_supported"), (0.0, "not_supported")],
)
def test_probability_maps_to_label_and_score(p: float, label: str) -> None:
    out = _judge(_seat(_json({"probability": p})))
    assert isinstance(out, Verdict) and out.label == label and out.score == p
    assert out.usage.model == "typesafe/jev-1.13"


@pytest.mark.parametrize("status", [429, 500, 503])
def test_non_2xx_is_http_error_not_run(status: int) -> None:
    out = _judge(_seat(_json({"error": "x"}, status)))
    assert isinstance(out, NotRun) and out.reason == f"http_error: status {status}"


def test_transport_failure_is_http_error_not_run() -> None:
    def boom(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    out = _judge(_seat(boom))
    assert isinstance(out, NotRun) and out.reason == "http_error: ConnectError"


@pytest.mark.parametrize(
    "payload", [{}, {"probability": "0.9"}, {"probability": None}, {"probability": True}, [0.9]]
)
def test_missing_or_non_numeric_probability_is_schema_mismatch(payload: object) -> None:
    out = _judge(_seat(_json(payload)))
    assert isinstance(out, NotRun) and out.reason.startswith("schema_mismatch:")


def test_non_json_body_is_schema_mismatch() -> None:
    out = _judge(_seat(lambda req: httpx.Response(200, text="<html>")))
    assert isinstance(out, NotRun) and out.reason.startswith("schema_mismatch:")


@pytest.mark.parametrize("p", [1.5, -0.1, 85, 9.0])
def test_out_of_range_probability_is_reported_never_clamped(p: float) -> None:
    out = _judge(_seat(_json({"probability": p})))
    assert isinstance(out, NotRun)
    assert out.reason.startswith("schema_mismatch:") and "out of range" in out.reason


def test_5xx_on_every_call_fails_the_build_with_no_reject_tiers(tmp_path: Path) -> None:
    env = Env(tmp_path)
    seat = _seat(_json({"error": "unavailable"}, 503))
    proposer = ScriptedProposer({"pages/normal.md": [CAL], "pages/injected.md": [GRADER]})
    r = asyncio.run(
        kb.abuild(
            "pages",
            env.settings,
            proposer,
            seat,
            env.store,
            pack=env.pack,
            pack_path=env.pack_path,
            dry_run=False,
            records_dir=env.records,
            build_id="b1",
        )
    )
    assert r.judge_not_run == 2 and r.verdicts == 0 and r.accepted == 0
    assert {p for p, _ in r.not_run} == {"pages/normal.md", "pages/injected.md"}
    assert all("http_error" in why for _, why in r.not_run)
    assert env.store.triples("b1") == []
    assert env.store.stats("b1").triples == {}
    assert not r.promotable
