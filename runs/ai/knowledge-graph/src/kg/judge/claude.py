"""`ClaudeSeat`: the one real `JudgeSeat`. Follows marketing-comms `model/gateway.py`.

Every failure to answer becomes `NotRun` with a distinct reason; none becomes a `Verdict`
and none becomes `unclear` (fog FA-002, FA-013). A score outside [0, 1] is a schema
mismatch: it is reported, never clamped or rescaled (fog FA-003).
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from kg.config import DEFAULT_JUDGE_MODEL, Settings
from kg.judge.prompt import SCHEMA, build_prompt
from kg.models import Candidate, NotRun, Usage, Verdict

MAX_TOKENS = 200
"""The answer is a label and a number; this is generous headroom, valid only with thinking off."""

THINKING: dict[str, str] = {"type": "disabled"}
"""Thinking is off, as in gateway.py: `max_tokens` bounds thinking and answer as one budget,
and adaptive thinking can spend the whole ceiling and return no answer. The judge's job is a
short structured verdict on a window it was handed."""


class ClaudeSeat:
    name = "claude"

    def __init__(
        self,
        settings: Settings | None = None,
        client: Any = None,
        model: str | None = None,
    ) -> None:
        """`client` is an injected `AsyncAnthropic` for tests; production leaves it None.
        `model` overrides `settings.judge_model`."""
        self._settings = settings if settings is not None else Settings.load(use_dotenv=False)
        self._client = client
        self.model = model or self._settings.judge_model or DEFAULT_JUDGE_MODEL
        self.calls = 0

    def available(self) -> tuple[bool, str]:
        if self._client is None and not self._settings.anthropic_api_key:
            return False, "ANTHROPIC_API_KEY not set"
        return True, ""

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=self._settings.require_anthropic_key())
        return self._client

    async def judge(self, candidate: Candidate, window: str) -> Verdict | NotRun:
        import anthropic

        ok, why = self.available()
        if not ok:
            return NotRun(reason=f"unavailable: {why}")
        client = self._get_client()
        self.calls += 1
        try:
            response = await client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                thinking=THINKING,
                messages=[{"role": "user", "content": build_prompt(candidate, window)}],
                output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
            )
        except anthropic.RateLimitError:
            return NotRun(reason="sdk_error: rate limited by the Anthropic API")
        except anthropic.NotFoundError:
            return NotRun(reason=f"sdk_error: model {self.model!r} not found")
        except anthropic.APIStatusError as exc:
            return NotRun(reason=f"sdk_error: Anthropic API returned status {exc.status_code}")
        except anthropic.APIConnectionError:
            return NotRun(reason="sdk_error: could not reach the Anthropic API")
        except anthropic.AnthropicError as exc:
            return NotRun(reason=f"sdk_error: {type(exc).__name__}")

        usage = _usage(response, self.model)
        stop = getattr(response, "stop_reason", None)
        if stop == "refusal":
            return NotRun(reason="refusal: the model declined to answer", usage=usage)
        if stop == "max_tokens":
            return NotRun(reason="truncated: output hit max_tokens", usage=usage)

        text = "".join(
            b.text for b in getattr(response, "content", []) if getattr(b, "type", None) == "text"
        )
        if not text:
            return NotRun(reason="schema_mismatch: response had no text content", usage=usage)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return NotRun(reason="schema_mismatch: response was not valid JSON", usage=usage)
        if not isinstance(data, dict) or set(data) != {"label", "score"}:
            return NotRun(
                reason="schema_mismatch: expected an object with keys label and score",
                usage=usage,
            )
        try:
            return Verdict(label=data["label"], score=data["score"], usage=usage)
        except ValidationError as exc:
            fields = sorted({str(e["loc"][0]) for e in exc.errors() if e["loc"]})
            detail = (
                f"score out of range [0, 1]: {data['score']!r}"
                if "score" in fields
                else (f"invalid {', '.join(fields)}")
            )
            return NotRun(reason=f"schema_mismatch: {detail}", usage=usage)


def _usage(response: Any, model: str) -> Usage:
    raw = getattr(response, "usage", None)
    return Usage(
        model=model,
        input_tokens=int(getattr(raw, "input_tokens", 0) or 0),
        output_tokens=int(getattr(raw, "output_tokens", 0) or 0),
    )
