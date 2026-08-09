# cap-observability — Templates for agent observability

**Tier: T2 — Runtime-adjacent.** The OTel GenAI semantic conventions and span schema are tooling-agnostic. The exporter setup and instrumentation hooks are runtime-specific. For full cost attribution and structured logging conventions see `agent-observability.md`.

## Agnostic contract

Every agent turn must produce a trace span with: model name, token counts (input/output/cache), latency, tool calls made, and an error field when the turn fails. The span schema must be conformant to OTel GenAI semantic conventions so spans are queryable by standard tooling (Jaeger, Grafana Tempo, Honeycomb). The `AgentSpan` dataclass below is the portable contract; the `OTelExporter` is the Anthropic-SDK-specific implementation — replace the SDK calls when using ADK or Vercel AI SDK.

| Runtime | Support | Notes |
|---|---|---|
| Claude API | ASSEMBLABLE | Wrap `client.messages.create()` calls; extract `usage` from response. `cached_tokens` is `response.usage.cache_read_input_tokens` |
| Google ADK | ASSEMBLABLE | Wrap at the ADK event loop level; ADK emits events that carry usage metadata |
| LangGraph | ASSEMBLABLE | LangSmith auto-instruments LangGraph traces; supplement with structlog at node boundaries for cost attribution |
| Vercel AI SDK | ASSEMBLABLE | `result.usage` on `generateText`/`streamText`; AI SDK telemetry integration via `telemetry: {isEnabled: true}` |

> **OTel GenAI semconv version pin:** This file targets `opentelemetry-semantic-conventions-ai` **v0.4.x** (2025-Q1 stable release). Attribute names changed between v0.3 and v0.4 — specifically `gen_ai.usage.prompt_tokens` was renamed to `gen_ai.usage.input_tokens`. Pin the library version in your `pyproject.toml`. Check the [GenAI semconv changelog](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/README.md) before upgrading. Verified 2026-07-20.

## Design notes

- **Every LLM call gets a span**: do not aggregate multiple turns into one span. Each `messages.create()` / ADK turn / `generateText()` is one span.
- **Cost attribution requires `cached_tokens` tracking**: cache hits are ~10× cheaper than cache misses on Anthropic. Track `cache_read_input_tokens` and `cache_creation_input_tokens` separately — they do not appear in `input_tokens`.
- **Span naming convention**: `gen_ai.{provider}.{operation}` — e.g., `gen_ai.anthropic.messages` for Anthropic API calls. Use `gen_ai.{agent_name}.turn` for top-level agent turns.
- **Tool call spans**: each tool call gets a child span under the turn span with `gen_ai.tool.name` and `gen_ai.tool.call.id`.
- **Error spans**: set `span.set_status(StatusCode.ERROR, description=str(exc))` and record the exception. Never swallow errors silently — an un-traced error is an undiagnosed error.

## File: {OUTPUT_DIR}/observability.py

```python
"""OTel GenAI semconv observability scaffold for {AGENT_NAME}.

Provides:
- AgentSpan: portable span dataclass (runtime-agnostic)
- OTelExporter: OpenTelemetry exporter for Anthropic API calls
- structlog setup with span correlation

OTel GenAI semconv target: opentelemetry-semantic-conventions-ai v0.4.x
Attribute names: gen_ai.usage.input_tokens (NOT prompt_tokens — changed in v0.4)

Requires:
    pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc structlog
    pip install opentelemetry-semantic-conventions-ai>=0.4.0  # pin the minor
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Iterator

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# AgentSpan — portable span dataclass
# ---------------------------------------------------------------------------


@dataclass
class AgentSpan:
    """Portable representation of one agent operation span.

    Conforms to OTel GenAI semconv v0.4.x attribute names.
    Populate and pass to an exporter; or serialize directly to structlog.
    """

    # Required
    operation_name: str          # e.g., "gen_ai.anthropic.messages"
    model: str                   # e.g., "claude-sonnet-4-5"
    provider: str                # e.g., "anthropic"

    # Timing
    start_time: float = field(default_factory=time.monotonic)
    end_time: float | None = None

    # Token usage (OTel GenAI semconv v0.4 names)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0      # Anthropic: cache_read_input_tokens
    cache_creation_tokens: int = 0  # Anthropic: cache_creation_input_tokens

    # Tool calls
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    # Status
    error: str | None = None
    status_code: str = "OK"  # "OK" | "ERROR"

    # Extra
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def latency_ms(self) -> float:
        if self.end_time is None:
            return (time.monotonic() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def effective_input_tokens(self) -> int:
        """Input tokens minus cache reads (cache reads are billed at ~10% rate)."""
        return self.input_tokens - self.cache_read_tokens

    def finish(self, error: str | None = None) -> None:
        self.end_time = time.monotonic()
        if error:
            self.error = error
            self.status_code = "ERROR"

    def to_otel_attrs(self) -> dict[str, Any]:
        """Convert to OTel GenAI semconv v0.4 attribute dict."""
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
            attrs["error.type"] = type(Exception(self.error)).__name__
            attrs["error.message"] = self.error
        return attrs

    def log(self) -> None:
        """Emit a structured log entry for this span."""
        logger.info(
            "agent_span",
            operation=self.operation_name,
            model=self.model,
            provider=self.provider,
            latency_ms=round(self.latency_ms, 1),
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cache_read_tokens=self.cache_read_tokens,
            cache_creation_tokens=self.cache_creation_tokens,
            total_tokens=self.total_tokens,
            tool_calls=[t.get("name") for t in self.tool_calls],
            status=self.status_code,
            error=self.error,
            **self.metadata,
        )


# ---------------------------------------------------------------------------
# OTel exporter — Anthropic SDK
# ---------------------------------------------------------------------------


class OTelExporter:
    """OpenTelemetry span exporter for Anthropic API calls.

    Wraps the Anthropic `messages.create()` call and records a span
    conformant to OTel GenAI semconv v0.4.

    Usage:
        exporter = OTelExporter(tracer_provider=...)
        async with exporter.span("gen_ai.anthropic.messages", model="claude-sonnet-4-5") as span:
            response = await client.messages.create(...)
            span.input_tokens = response.usage.input_tokens
            span.output_tokens = response.usage.output_tokens
            span.cache_read_tokens = response.usage.cache_read_input_tokens or 0
            span.cache_creation_tokens = response.usage.cache_creation_input_tokens or 0
    """

    def __init__(self, tracer_provider: Any | None = None, service_name: str = "{AGENT_NAME}") -> None:
        self._tracer_provider = tracer_provider
        self._service_name = service_name
        self._tracer: Any = None

        if tracer_provider is not None:
            try:
                from opentelemetry import trace  # type: ignore[import]
                self._tracer = trace.get_tracer(service_name, tracer_provider=tracer_provider)
            except ImportError:
                logger.warning("opentelemetry-sdk not installed — OTel export disabled")

    @contextmanager
    def span(
        self,
        operation_name: str,
        model: str,
        provider: str = "anthropic",
        **metadata: Any,
    ) -> Iterator[AgentSpan]:
        """Synchronous context manager for a single agent span.

        Yields an AgentSpan; caller populates token counts from the API response.
        Span is finished and exported on context exit.
        """
        agent_span = AgentSpan(
            operation_name=operation_name,
            model=model,
            provider=provider,
            metadata=metadata,
        )

        otel_span: Any = None
        if self._tracer:
            try:
                from opentelemetry.trace import StatusCode  # type: ignore[import]
                otel_span = self._tracer.start_span(operation_name)
            except Exception:  # noqa: BLE001
                pass

        try:
            yield agent_span
        except Exception as exc:
            agent_span.finish(error=str(exc))
            if otel_span:
                try:
                    from opentelemetry.trace import StatusCode  # type: ignore[import]
                    otel_span.set_status(StatusCode.ERROR, str(exc))
                    otel_span.record_exception(exc)
                except Exception:  # noqa: BLE001
                    pass
            raise
        else:
            agent_span.finish()
        finally:
            agent_span.log()
            if otel_span:
                try:
                    for k, v in agent_span.to_otel_attrs().items():
                        otel_span.set_attribute(k, v)
                    otel_span.end()
                except Exception:  # noqa: BLE001
                    pass

    @asynccontextmanager
    async def async_span(
        self,
        operation_name: str,
        model: str,
        provider: str = "anthropic",
        **metadata: Any,
    ) -> AsyncIterator[AgentSpan]:
        """Async context manager version — same behavior as span()."""
        with self.span(operation_name, model=model, provider=provider, **metadata) as s:
            yield s


# ---------------------------------------------------------------------------
# structlog setup
# ---------------------------------------------------------------------------


def configure_structlog(log_level: str = "INFO") -> None:
    """Configure structlog for structured JSON logging.

    Call once at process startup (e.g., in app.py or main.py).
    Adds ISO timestamp, log level, and logger name to every log entry.
    """
    import logging as stdlib_logging  # noqa: PLC0415

    stdlib_logging.basicConfig(
        level=getattr(stdlib_logging, log_level.upper(), stdlib_logging.INFO),
        format="%(message)s",
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_logger_name,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(stdlib_logging, log_level.upper(), stdlib_logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
```
