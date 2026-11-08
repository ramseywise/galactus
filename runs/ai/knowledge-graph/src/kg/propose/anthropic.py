"""The Anthropic proposer, shaped exactly like marketing-comms `model/gateway.py`.

Same request: structured output through `output_config`, thinking disabled, no sampling
parameters, lazy injectable async client, exception mapping by class. The difference is the
failure contract: the gateway raises, this returns. Every provider failure is a
`PageResult(status="not_run", reason=...)` with a reason distinct per cause, so a failed
page is never read as a page with nothing to say (spec F2, fog FA-002, FA-013).

A missing API key is the one exception that still raises (`ConfigError`): it is not a
page-level failure but an unavailable proposer, and the orchestrator refuses by name.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from kg.config import Settings
from kg.contract import Pack
from kg.models import Candidate, PageResult, Usage
from kg.observability import OP_PROPOSE, span
from kg.profile import Page
from kg.propose.prompt import build_prompt, build_schema

MAX_TOKENS = 8000
"""Ceiling for one page's candidates. Bounds thinking and answer together."""

THINKING: dict[str, str] = {"type": "disabled"}
"""Thinking is off, deliberately: adaptive thinking shares `max_tokens` with the answer and
can consume the whole ceiling, returning no JSON, which reads as a model that found nothing
rather than a misconfigured request. The reasoning this task needs (is the quote verbatim,
are the types legal) is done by the gates, not the model."""

# Reason prefixes: one per cause, asserted distinct by the tests.
R_NOT_FOUND = "model_not_found"
R_RATE_LIMIT = "rate_limited"
R_STATUS = "api_status_error"
R_CONNECTION = "connection_error"
R_REFUSAL = "refusal"
R_TRUNCATED = "truncated"
R_NO_TEXT = "no_text_content"
R_BAD_JSON = "invalid_json"
R_SCHEMA = "schema_mismatch"


class AnthropicProposer:
    """Proposes candidate triples for one page per call."""

    name = "anthropic"

    def __init__(
        self,
        settings: Settings | None = None,
        client: Any = None,
        *,
        model: str | None = None,
        max_tokens: int = MAX_TOKENS,
    ) -> None:
        self._settings = settings if settings is not None else Settings.load()
        self._client = client
        self.model = model or self._settings.proposer_model
        self._max_tokens = max_tokens
        self.calls = 0
        self.last_usage: Usage | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=self._settings.require_anthropic_key())
        return self._client

    async def propose(self, page: Page, pack: Pack) -> PageResult:
        import anthropic

        client = self._get_client()
        self.last_usage = None
        self.calls += 1  # counted before the call: a failed attempt is still spend

        with span(OP_PROPOSE, self.model, page_path=page.path) as sp:
            try:
                response = await client.messages.create(
                    model=self.model,
                    max_tokens=self._max_tokens,
                    thinking=THINKING,
                    messages=[{"role": "user", "content": build_prompt(page, pack)}],
                    output_config={"format": {"type": "json_schema", "schema": build_schema(pack)}},
                )
            # Most specific first; classes, not message text, are the SDK's contract.
            except anthropic.NotFoundError:
                return self._not_run(sp, page, f"{R_NOT_FOUND}: {self.model!r} unavailable")
            except anthropic.RateLimitError:
                return self._not_run(sp, page, f"{R_RATE_LIMIT}: Anthropic API")
            except anthropic.APIStatusError as exc:
                return self._not_run(sp, page, f"{R_STATUS}: HTTP {exc.status_code}")
            except anthropic.APIConnectionError:
                return self._not_run(sp, page, f"{R_CONNECTION}: could not reach Anthropic API")

            usage = getattr(response, "usage", None)
            in_tok = int(getattr(usage, "input_tokens", 0) or 0)
            out_tok = int(getattr(usage, "output_tokens", 0) or 0)
            self.last_usage = Usage(model=self.model, input_tokens=in_tok, output_tokens=out_tok)
            sp.record_usage(in_tok, out_tok)

            result = self._interpret(response, page)
            sp.metadata["page_status"] = result.status
            sp.metadata["n_candidates"] = len(result.candidates)
            if result.status == "not_run":
                sp.finish(error=result.reason)
            return result

    def _not_run(self, sp: Any, page: Page, reason: str) -> PageResult:
        sp.finish(error=reason)
        return PageResult(page_path=page.path, status="not_run", reason=reason)

    def _interpret(self, response: Any, page: Page) -> PageResult:
        def not_run(reason: str) -> PageResult:
            return PageResult(page_path=page.path, status="not_run", reason=reason)

        stop_reason = getattr(response, "stop_reason", None)
        if stop_reason == "refusal":
            return not_run(f"{R_REFUSAL}: model declined to answer for this page")
        if stop_reason == "max_tokens":
            return not_run(f"{R_TRUNCATED}: hit the {self._max_tokens}-token ceiling")

        blocks = getattr(response, "content", None) or []
        text = "".join(b.text for b in blocks if getattr(b, "type", None) == "text")
        if not text.strip():
            return not_run(f"{R_NO_TEXT}: response had no text block")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            return not_run(f"{R_BAD_JSON}: {exc.msg} at char {exc.pos}")

        raw = parsed.get("candidates") if isinstance(parsed, dict) else None
        if not isinstance(raw, list):
            return not_run(f"{R_SCHEMA}: expected an object with a 'candidates' list")
        try:
            candidates = tuple(Candidate.model_validate(item) for item in raw)
        except ValidationError as exc:
            # One malformed item fails the page: dropping it would hide a proposer fault.
            return not_run(f"{R_SCHEMA}: {exc.error_count()} invalid field(s) in candidates")

        if not candidates:
            return PageResult(page_path=page.path, status="no_candidates")
        return PageResult(page_path=page.path, status="proposed", candidates=candidates)
