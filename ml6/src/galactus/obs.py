"""Structured logging and per-call spans.

Adapted from `cap-observability.md` (see docs/cap-reuse.md): `AgentSpan` is an
OTel-GenAI-conformant span contract and `configure_structlog` is lifted close to
as-is. The `OTelExporter` from that spec is deliberately not carried over —
there is no collector to export to, and a span that logs is enough to compute
every metric Step 9 needs.

The rule that matters here is **one span per LLM call, never aggregated**. The
repair loop's whole point is that attempt 1 and attempt 2 are different events:
a run that passed on the first try and a run that passed on the third both end
valid, and only the per-call spans distinguish them. Aggregating at the run
level would erase repair convergence — the metric the loop exists to justify.

Spans carry pipeline identity in `metadata` (`stage`, `attempt`, `job_id`)
rather than in new dataclass fields, so the shape stays portable back to the
spec it came from.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

import structlog

logger = structlog.get_logger(__name__)

PROVIDER = "anthropic"

OP_GENERATE = "gen_ai.generate"
"""The first generation call for a job — the one contract pass rate scores."""

OP_REPAIR = "gen_ai.repair"
"""A re-prompt carrying violations back. Attempt number lives in metadata."""

OP_VISION = "gen_ai.vision"
"""A page-reading call from the ingest path."""


@dataclass
class AgentSpan:
    """One model call, timed and accounted.

    Conforms to OTel GenAI semconv v0.4.x attribute names so the spans remain
    exportable if a collector ever appears, without depending on one now.
    """

    operation_name: str
    model: str
    provider: str = PROVIDER

    start_time: float = field(default_factory=time.monotonic)
    end_time: float | None = None

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    error: str | None = None
    status_code: str = "OK"

    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def latency_ms(self) -> float:
        end = time.monotonic() if self.end_time is None else self.end_time
        return (end - self.start_time) * 1000

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def effective_input_tokens(self) -> int:
        """Input tokens excluding cache reads, which bill at roughly 10%."""
        return self.input_tokens - self.cache_read_tokens

    def finish(self, error: str | None = None) -> None:
        self.end_time = time.monotonic()
        if error:
            self.error = error
            self.status_code = "ERROR"

    def to_otel_attrs(self) -> dict[str, Any]:
        """Render as an OTel GenAI semconv v0.4 attribute dict."""
        attrs: dict[str, Any] = {
            "gen_ai.operation.name": self.operation_name,
            "gen_ai.system": self.provider,
            "gen_ai.request.model": self.model,
            "gen_ai.usage.input_tokens": self.input_tokens,
            "gen_ai.usage.output_tokens": self.output_tokens,
        }
        if self.cache_read_tokens:
            attrs["gen_ai.usage.cache_read_input_tokens"] = self.cache_read_tokens
        if self.cache_creation_tokens:
            attrs["gen_ai.usage.cache_creation_input_tokens"] = self.cache_creation_tokens
        if self.error:
            attrs["error.message"] = self.error
        return attrs

    def log(self) -> None:
        """Emit this span as one structured log line."""
        logger.info(
            "agent_span",
            operation=self.operation_name,
            model=self.model,
            provider=self.provider,
            latency_ms=round(self.latency_ms, 1),
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            total_tokens=self.total_tokens,
            status=self.status_code,
            error=self.error,
            **self.metadata,
        )


@contextmanager
def span(operation_name: str, model: str, **metadata: Any) -> Iterator[AgentSpan]:
    """Time one model call, log it, and let the exception through.

    The span is finished and logged on the way out whether the call succeeded or
    raised — a failed provider call is exactly the event worth having a record
    of, and dropping it on the error path would make the log a record of only
    the successes.
    """
    active = AgentSpan(operation_name=operation_name, model=model, metadata=metadata)
    try:
        yield active
    except Exception as exc:
        active.finish(error=f"{type(exc).__name__}: {exc}")
        active.log()
        raise
    else:
        active.finish()
        active.log()


def configure_structlog(log_level: str = "INFO") -> None:
    """Configure JSON structured logging. Call once at process startup."""
    import logging as stdlib_logging

    level = getattr(stdlib_logging, log_level.upper(), stdlib_logging.INFO)
    stdlib_logging.basicConfig(level=level, format="%(message)s")

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def bind_job(job_id: str) -> None:
    """Put `job_id` on every subsequent log line in this context.

    R2 asks for `job_id` on every line. Binding it to a contextvar rather than
    threading it through each call site means a log statement added later gets
    it for free, including from inside the layout package, which knows nothing
    about jobs.
    """
    structlog.contextvars.bind_contextvars(job_id=job_id)


def clear_job() -> None:
    """Drop the bound job context. Background tasks share a context pool."""
    structlog.contextvars.clear_contextvars()
