"""Spans, and the rule that they are never aggregated.

The claim `obs.py` makes is that one model call produces exactly one span. It
is worth a test rather than a docstring because the failure is silent: a run
that aggregated at the job level would still log, still carry a job id, and
still look correct — it would just quietly make repair convergence
unmeasurable, which is the one metric the repair loop exists to justify.

`structlog.testing.capture_logs` swaps in a capturing processor, so these
assert on the event dicts themselves rather than parsing rendered JSON.
"""

from __future__ import annotations

import io
import json
from typing import Any

import pytest
import structlog
from galactus.generate import generate_collateral
from galactus.models import PipelineState
from galactus.observability import (
    OP_GENERATE,
    OP_REPAIR,
    AgentSpan,
    bind_job,
    clear_job,
    configure_structlog,
    span,
)
from structlog.testing import capture_logs


class ScriptedLLM:
    """Returns scripted drafts in order; the last one repeats."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.calls = 0

    async def complete_structured(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        return dict(self.responses[min(self.calls - 1, len(self.responses) - 1)])


@pytest.fixture(autouse=True)
def _clean_context():
    """Contextvars outlive a test. Leaking a job id would cross-contaminate."""
    clear_job()
    yield
    clear_job()


@pytest.fixture
def rendered_logs():
    """Capture log lines as production renders them, and parse them back.

    The alternative, `structlog.testing.capture_logs`, intercepts before the
    processor chain runs — which is fine for event contents but blind to
    `merge_contextvars` and to the JSON renderer, the two things R2 is about.
    """
    import logging

    configure_structlog("INFO")

    # Attached to the named loggers rather than to root: pytest's logging
    # plugin owns root's handlers, and records would land in its capture
    # instead of the buffer.
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    targets = [logging.getLogger("galactus.observability"), logging.getLogger(__name__)]
    saved = [(lg, lg.handlers, lg.propagate, lg.level) for lg in targets]

    for lg in targets:
        lg.handlers = [handler]
        lg.propagate = False
        lg.setLevel(logging.INFO)

    def read() -> list[dict[str, Any]]:
        return [json.loads(line) for line in buffer.getvalue().splitlines() if line.strip()]

    try:
        yield read
    finally:
        for lg, handlers, propagate, level in saved:
            lg.handlers, lg.propagate, lg.level = handlers, propagate, level


def _too_long(draft: dict[str, str]) -> dict[str, str]:
    return {**draft, "headline": " ".join(["overlong"] * 20)}


# ---------------------------------------------------------------------------
# AgentSpan
# ---------------------------------------------------------------------------


def test_a_finished_span_records_a_latency():
    active = AgentSpan(operation_name=OP_GENERATE, model="m")
    active.finish()

    assert active.end_time is not None
    assert active.latency_ms >= 0


def test_finishing_with_an_error_flips_the_status():
    active = AgentSpan(operation_name=OP_GENERATE, model="m")
    active.finish(error="LLMError: boom")

    assert active.status_code == "ERROR"
    assert active.error == "LLMError: boom"


def test_effective_input_tokens_excludes_cache_reads():
    active = AgentSpan(
        operation_name=OP_GENERATE, model="m", input_tokens=1000, cache_read_tokens=800
    )

    assert active.effective_input_tokens == 200
    assert active.total_tokens == 1000


def test_otel_attrs_use_semconv_names():
    attrs = AgentSpan(operation_name=OP_GENERATE, model="m").to_otel_attrs()

    assert attrs["gen_ai.operation.name"] == OP_GENERATE
    assert attrs["gen_ai.system"] == "anthropic"
    assert attrs["gen_ai.request.model"] == "m"


def test_cache_attrs_are_omitted_when_there_was_no_cache_activity():
    attrs = AgentSpan(operation_name=OP_GENERATE, model="m").to_otel_attrs()

    assert "gen_ai.usage.cache_read_input_tokens" not in attrs


# ---------------------------------------------------------------------------
# The span context manager
# ---------------------------------------------------------------------------


def test_span_logs_one_line_carrying_its_metadata():
    with capture_logs() as logs, span(OP_GENERATE, "m", stage="generate", attempt=0):
        pass

    assert len(logs) == 1
    assert logs[0]["event"] == "agent_span"
    assert logs[0]["operation"] == OP_GENERATE
    assert logs[0]["stage"] == "generate"
    assert logs[0]["attempt"] == 0
    assert logs[0]["status"] == "OK"


def test_a_failing_call_is_still_logged_and_the_error_still_raises():
    """A log of only the successes is not a log worth keeping."""
    with (
        capture_logs() as logs,
        pytest.raises(RuntimeError, match="provider is down"),
        span(OP_GENERATE, "m"),
    ):
        raise RuntimeError("provider is down")

    assert len(logs) == 1
    assert logs[0]["status"] == "ERROR"
    assert "provider is down" in logs[0]["error"]


# ---------------------------------------------------------------------------
# One span per call, never aggregated
# ---------------------------------------------------------------------------


async def test_a_clean_run_emits_exactly_one_generate_span(clean_draft, template):
    state = PipelineState(job_id="job-clean")

    with capture_logs() as logs:
        await generate_collateral(state, template, ScriptedLLM([clean_draft]), model="m")

    spans = [entry for entry in logs if entry["event"] == "agent_span"]
    assert [s["operation"] for s in spans] == [OP_GENERATE]


async def test_each_repair_attempt_gets_its_own_span(clean_draft, template):
    """Two runs both end valid; only the per-call spans say which repaired."""
    state = PipelineState(job_id="job-repair")
    llm = ScriptedLLM([_too_long(clean_draft), _too_long(clean_draft), clean_draft])

    with capture_logs() as logs:
        await generate_collateral(state, template, llm, model="m")

    spans = [entry for entry in logs if entry["event"] == "agent_span"]

    assert llm.calls == 3
    assert [s["operation"] for s in spans] == [OP_GENERATE, OP_REPAIR, OP_REPAIR]
    assert [s["attempt"] for s in spans] == [0, 1, 2]


async def test_repair_spans_carry_the_violation_count_they_were_answering(clean_draft, template):
    """The count is what makes 'is the loop converging?' answerable from logs."""
    state = PipelineState(job_id="job-count")
    llm = ScriptedLLM([_too_long(clean_draft), clean_draft])

    with capture_logs() as logs:
        await generate_collateral(state, template, llm, model="m")

    repairs = [e for e in logs if e.get("operation") == OP_REPAIR]
    assert len(repairs) == 1
    assert repairs[0]["violation_count"] >= 1


async def test_an_exhausted_budget_emits_a_span_for_every_attempt(clean_draft, template):
    """Four calls, four spans — the fallback itself is not a model call."""
    state = PipelineState(job_id="job-exhausted")
    llm = ScriptedLLM([_too_long(clean_draft)])

    with capture_logs() as logs:
        _, used_fallback = await generate_collateral(state, template, llm, max_repairs=3, model="m")

    spans = [entry for entry in logs if entry["event"] == "agent_span"]

    assert used_fallback
    assert llm.calls == 4
    assert len(spans) == 4


async def test_spans_name_the_model_they_were_told_about(clean_draft, template):
    state = PipelineState(job_id="job-model")

    with capture_logs() as logs:
        await generate_collateral(
            state, template, ScriptedLLM([clean_draft]), model="claude-sonnet-5"
        )

    assert all(e["model"] == "claude-sonnet-5" for e in logs if e["event"] == "agent_span")


# ---------------------------------------------------------------------------
# Job binding
# ---------------------------------------------------------------------------


def test_a_bound_job_id_reaches_every_subsequent_line(rendered_logs):
    """R2's requirement, checked against the real renderer.

    Not `capture_logs` here: it swaps out the whole processor chain, including
    `merge_contextvars`, so it cannot observe contextvar binding at all — a test
    written against it would fail on working code. Reading the rendered JSON
    also checks the thing production actually emits.
    """
    bind_job("job-bound")

    with span(OP_GENERATE, "m"):
        pass
    structlog.get_logger(__name__).info("something_unrelated")

    lines = rendered_logs()
    assert [entry["event"] for entry in lines] == ["agent_span", "something_unrelated"]
    assert all(entry["job_id"] == "job-bound" for entry in lines)


def test_clearing_the_job_stops_the_leak(rendered_logs):
    """Background tasks share a context pool, so a stale id lands on the next job."""
    bind_job("job-first")
    clear_job()

    with span(OP_GENERATE, "m"):
        pass

    assert "job_id" not in rendered_logs()[0]


def test_rendered_span_lines_are_json(rendered_logs):
    """R2 asks for JSON logs, not console-formatted ones."""
    bind_job("job-json")
    with span(OP_GENERATE, "m", stage="generate", attempt=0):
        pass

    entry = rendered_logs()[0]
    assert entry["operation"] == OP_GENERATE
    assert entry["provider"] == "anthropic"
    assert entry["stage"] == "generate"
    assert isinstance(entry["latency_ms"], float)
    assert "timestamp" in entry
