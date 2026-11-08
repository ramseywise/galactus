"""Per-call spans for the proposer and the judge seats.

Adapted from marketing-comms `observability.AgentSpan`: one span per model call, never
aggregated, OTel GenAI attribute names, structlog output. Ops are `kg.propose` and `kg.judge`.

Quote text is redacted to its length wherever it would reach an attribute or a log line: a
quote is page content, and logs outlive the corpus checkout.
"""

from __future__ import annotations

import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

PROVIDER = "anthropic"
OP_PROPOSE = "kg.propose"
OP_JUDGE = "kg.judge"

_QUOTE_KEYS = frozenset({"quote"})


def redact_quote(quote: str) -> str:
    """A quote reduced to its length."""
    return f"<quote len={len(quote)}>"


def redact(attrs: Mapping[str, Any]) -> dict[str, Any]:
    """Copy of `attrs` with every quote value replaced by its length."""
    return {
        k: redact_quote(v) if k in _QUOTE_KEYS and isinstance(v, str) else v
        for k, v in attrs.items()
    }


@dataclass
class AgentSpan:
    operation_name: str
    model: str
    provider: str = PROVIDER
    start_time: float = field(default_factory=time.monotonic)
    end_time: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None
    status_code: str = "OK"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def latency_ms(self) -> float:
        end = time.monotonic() if self.end_time is None else self.end_time
        return (end - self.start_time) * 1000

    def record_usage(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    def finish(self, error: str | None = None) -> None:
        self.end_time = time.monotonic()
        if error:
            self.error = error
            self.status_code = "ERROR"

    def to_otel_attrs(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "gen_ai.operation.name": self.operation_name,
            "gen_ai.system": self.provider,
            "gen_ai.request.model": self.model,
            "gen_ai.usage.input_tokens": self.input_tokens,
            "gen_ai.usage.output_tokens": self.output_tokens,
        }
        if self.error:
            attrs["error.message"] = self.error
        attrs.update({f"kg.{k}": v for k, v in redact(self.metadata).items()})
        return attrs

    def log(self) -> None:
        logger.info(
            "agent_span",
            operation=self.operation_name,
            model=self.model,
            provider=self.provider,
            latency_ms=round(self.latency_ms, 1),
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            status=self.status_code,
            error=self.error,
            meta=redact(self.metadata),
        )


@contextmanager
def span(operation_name: str, model: str, **metadata: Any) -> Iterator[AgentSpan]:
    """Time one model call and log it on the way out, success or exception."""
    active = AgentSpan(operation_name=operation_name, model=model, metadata=metadata)
    try:
        yield active
    except Exception as exc:
        active.finish(error=f"{type(exc).__name__}: {exc}")
        active.log()
        raise
    else:
        # A span that already recorded a failure keeps it; finish() only restamps the end.
        active.finish()
        active.log()
