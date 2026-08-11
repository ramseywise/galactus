# Agent Observability — Conventions

**Durable question:** What must a trace contain to debug a bad agent run after the fact? How is cost attributed to the agent, route, or user that generated it?

*Extends structlog mechanics for agent-shaped spans. For tool/framework instrumentation see framework refs.*

**OTel GenAI semconv version note:** This file targets OTel semantic conventions v1.41 (2026). Nearly all `gen_ai.*` attributes carry **Development stability badges** — names can change without a major version bump. Adopt the span shape; pin attribute names loosely and re-verify on upgrade.

---

## 0. Four words that are not synonyms

The wiki separates terms this spec uses interchangeably:

- **Tracking** — *"the practice of recording selected events."* The write side.
- **Tracing** — linking those events into a causal structure (the span tree in §1).
- **Monitoring** — built on top of the pillars; reading the record continuously.
- **Alerting** — *"a subset of monitoring — you can monitor without alerting, but not alert without monitoring."*

The ordering matters because instrumentation gaps propagate downward: you cannot alert on what you never tracked. *(Source: `eval/observability-glossary.md`)*

### Why production tracing, and not just CI

The structural argument this spec assumes but never states: a model version rolls forward, a retrieval corpus grows, user phrasing shifts. *"None of these involve a change to your code, which is why drift is invisible to CI and only online evaluation catches it."* An offline suite that passes proves the code did not regress — not that the system still works. *(Sources: `eval/online-eval-sampling.md`, `infra/agent-management-layer.md`)*

---

## 1. Required span types

Four span types cover a complete agent trace. All are nested under a root `invoke_agent` span.

| Span type | OTel operation name | What it wraps |
|---|---|---|
| **Agent invocation** | `invoke_agent` | Full agent turn (request → response) |
| **Model call** | `chat` / `completions` | Single LLM API call within a turn |
| **Tool execution** | `execute_tool` | One tool call (input → output) |
| **Retrieval** | `retrieve` | RAG/search query + results |

> **Streaming variant — the tree assumption fails.** "All are nested under a root `invoke_agent` span" holds because a request/response turn has one root and its children close inside it. A duplex voice session has neither property. The shape is `session → turn → {asr, llm, tts}`, and those leaf spans **overlap**: TTS begins emitting audio while the LLM is still generating, so `tts` opens before `llm` closes. This is not instrumentation sloppiness to be cleaned up — it is the design, and it is where the latency budget is won. Tooling that assumes strict nesting will render it wrong or drop spans silently. The session, not the turn, is the root. OTel GenAI semconv does not cover audio; see §6 for the local attribute extension and `agent-voice.md §9`.

Minimum required attributes per span:

```
trace_id:              string — root trace, propagated to all child spans
span_id:               string — unique per span
parent_span_id:        string — links to parent; null on root
operation_name:        one of the four types above
start_time:            ISO-8601 with milliseconds
end_time:              ISO-8601 with milliseconds
status:                ok | error
error_message:         string (when status=error)
```

**`status` and `error_message` are load-bearing, not decorative.** *"Without explicit error marking, failed traces either don't flush or appear successful in the dashboard."* A failed run that renders as a successful one is worse than a missing trace, because nobody goes looking. *(Source: `infra/langfuse-adk-tracing-patterns.md`)*

**Decompose the `retrieve` span.** *"Without a dedicated span, retrieval time is reported as one lump — you cannot tell whether slowness comes from the embedding API call or the vector database query."* Those two have different fixes and different owners. *(Source: `infra/langfuse-adk-tracing-patterns.md`)*

> **Naming divergence, flagged.** ADK's native span hierarchy is `invocation → agent_run → {call_llm, execute_tool}`, which does not match the OTel operation names above (`invoke_agent`, `chat`/`completions`). Given this file's own header note that `gen_ai.*` names "can change without a major version bump," expect to map rather than match. *(Source: `adk/adk-observability.md`)*

---

## 2. Agent invocation span

```
gen_ai.system:              "anthropic" | "google" | "openai" | ...
gen_ai.request.model:       model ID (e.g., "claude-sonnet-4-5")
prompt_version:             from PROMPT_VERSION (see agent-context.md §4)
agent_id:                   stable identifier for the agent type
session_id:                 caller-supplied session identifier
user_id / tenant_id:        for cost attribution (see §5)
gen_ai.usage.input_tokens:  integer
gen_ai.usage.output_tokens: integer
iteration_count:             how many model turns this invocation took
tool_call_count:             total tools called in this invocation
```

### `run_id` is missing here and required elsewhere

`agent-eval.md §2` requires `run_id` in every grader's `metadata` dict; this list does not carry it, and `trace_id`/`span_id` from §1 do not substitute — they are tracing-layer IDs. The wiki treats `run_id` as a distinct base field: *`run_id | str | "uuid4, unique per invocation"`*, and `infra/langfuse-platform.md` is explicit about why it must be generated independently — *"Tag it with your own `run_id` so platform results join back to your experiment-tracking records"*; *"`run_id` is the join key."* Without it, platform scores and local experiment records cannot be joined. Add `run_id` to this span. *(Sources: `eval/experiment-tracking-schemas.md`, `infra/langfuse-platform.md`)*

### The reproduction key

Three fields *"jointly [form] the reproduction key. Without all three, a regression cannot be attributed"*: `prompt_version`, `git_commit`, and the model ID. This spec carries two of them and has **no `git_commit` field anywhere**. A regression traced to a prompt version that shipped alongside three code changes is not attributed — it is narrowed. *(Source: `eval/experiment-tracking-schemas.md`)*

### Behavioural counters

The wiki's base trace schema carries fields this spec has no equivalent for — *"behavioural counters, not diagnostics"*, whose value is that they *"let you compute rates over a slice"* rather than explain one incident:

```
guardrail_triggered:  boolean
escalated:            boolean
retrieval_k:          integer
grounding_score:      float | None
contact_support:      boolean
```

§6 tells you to "wire into the span as custom attributes" without naming any; these are the names. *(Source: `eval/experiment-tracking-schemas.md`)*

> **Naming drift — flagged, not resolved.** This section uses `agent_id` ("stable identifier for the agent type"); the wiki uses `agent` — *"which agent implementation handled the turn"*, a subtly different referent. §3 uses `duration_ms: integer`; the wiki uses `latency_ms: float` — *"wall-clock, request in to response out"* — a different name **and** type, and `infra/observability-runtime-patterns.md` independently uses `latency_ms=87` in its structlog example. Pick one per repo and pick deliberately; the two vocabularies do not merge silently. *(Sources: `eval/experiment-tracking-schemas.md`, `infra/observability-runtime-patterns.md`)*

---

## 3. Model call span

```
gen_ai.request.model:            model ID
gen_ai.request.max_tokens:       integer
gen_ai.request.temperature:      float
gen_ai.usage.input_tokens:       integer
gen_ai.usage.output_tokens:      integer
gen_ai.response.finish_reasons:  ["end_turn"] | ["tool_use"] | ["max_tokens"] | ...
duration_ms:                     integer
```

`finish_reason: max_tokens` should be treated as an error, not a completion — log at WARN level and surface in cost dashboards (truncated outputs are wasted spend).

---

## 4. Tool execution span

```
tool.name:        registered tool name (from schema)
tool.version:     tool schema version
input_hash:       hash of inputs (not raw inputs — avoid logging PII)
duration_ms:      integer
is_error:         boolean
error_code:       string (when is_error=true)
retry_count:      how many retries this call took (see agent-reliability.md)
```

Do not log raw tool inputs if they may contain PII or credentials. Log the hash for correlation; log the full input only to a secured audit store when required.

> **Conflict — flagged, not resolved.** This section makes hashing the baseline and full capture the exception. The wiki's "what a trace must contain" list states the opposite as an unconditional requirement: *"Each tool call + parameters + return value"* — with no redaction or PII caveat anywhere on the page. The two positions are reconcilable in principle (the wiki may be assuming a non-PII domain) but as written the wiki asks for the baseline this spec forbids. Note that a hash satisfies §8's question 3 — *"Which tool was called with what inputs, and what did it return?"* — only if you also hold the pre-image somewhere. *(Source: `eval/experiment-tracking-schemas.md`)*

### Tag the retrieval path

For agents with a corrective or fallback retrieval branch, record which path a query took. *"The single most useful filter for operational monitoring… A rising `corrective` rate signals retrieval quality issues."* The wiki's own priority matrix ranks this **low effort / highest operational value** — it converts a per-incident debugging artifact into a leading indicator. *(Source: `infra/langfuse-adk-tracing-patterns.md`)*

---

## 5. Cost attribution

Cost attribution answers: which agent, route, user, or tenant generated this spend?

**Required for attribution:**
- `agent_id` on every `invoke_agent` span.
- `user_id` or `tenant_id` on every span (propagated from the root).
- Token counts on every model call span (`input_tokens`, `output_tokens`).

**Derived metrics to compute and emit:**
- Cost per invocation: `(input_tokens × input_rate) + (output_tokens × output_rate)`.
- Cost per session: aggregate over all invocations for a `session_id`.
- Cost per route: aggregate by `agent_id` + routing label.
- Cache hit rate: `cached_tokens / input_tokens` (reduces effective cost; track separately).

Prompt caching reduces cost significantly on large, stable system prompts. Track `cached_tokens` as a separate counter; do not fold it into `input_tokens` — it obscures the cache benefit signal.

---

## 6. What OTel GenAI semconv does NOT cover

Do not wait for a standard on these — keep them local:

- **Output evaluation / quality scoring** — no `gen_ai.*` attribute covers this. Use project-local labels (e.g., `eval.grounding_score`, `eval.pass`).
- **Safety scoring** — agent-specific; wire into the span as custom attributes.
- **Grounding / citation checks** — project-local (see `agent-safety.md §1`).
- **Audio** — nothing in the semconv covers audio frames, VAD confidence, or TTS buffer state. Duplex designs need the extension below.

### The audio attribute extension

Local until the GenAI SIG standardizes audio. These names are canonical here and are duplicated in `agent-voice.md §9` — **change them in both places or in neither.**

| Attribute | Meaning |
|---|---|
| `vad.confidence` | Endpointer confidence at the turn-end decision |
| `asr.confidence_score` | Confidence on the final transcript |
| `asr.n_best_count` | Alternatives retained |
| `tts.latency_ms` | Time to first audio out |
| `audio.codec` | Codec in use on this leg |
| `latency_to_first_token` | The dominant hop in the latency budget |
| `turn_duration_ms` | Wall-clock for the full turn |

The last two are the ones a dashboard should default to: `latency_to_first_token` is where a voice design is usually lost, and `turn_duration_ms` is the only span-level number a non-engineer can read as "how long did the caller wait."

### Audio retention is a legal question, not an ops one

§7's three audit purposes set retention by what debugging and compliance *want*. Audio inverts that: it is special-category personal data under GDPR Art. 9 — a recording carries identity in the voice itself, independently of what was said, so it cannot be de-identified by redacting the transcript.

The consequence for this spec: **a voice design sets a retention window for audio explicitly, and it is shorter than the trace retention around it.** Traces, transcripts, and audio are three artifacts with three windows, not one policy. Keeping audio "as long as the traces" is the default that fails an erasure request. Derive the window from the lawful basis, not from disk cost, and record it where the trace config lives so it is auditable. Erasure must reach audio, transcript, and derived context alike — see `agent-memory.md §5b` and `agent-safety.md §7a`.

### Post scores as scores, not as metadata

*"Burying `overall_score` in generation metadata makes it invisible to… dashboards. Post it as a proper Score"* — the wiki calls this *"the primary mechanism for detecting retrieval regression."* A quality number that only a human reading one trace can see is not instrumentation. *(Source: `infra/langfuse-adk-tracing-patterns.md`)*

### New checks ship log-only first

A staged-rollout policy for any new grounding or guardrail check: *"New grounding checks are not deployed as blocking. They start as **log-only diagnostics**"* — *"Implement → observe false-positive rate in production → promote to escalation trigger only after confirming the false-positive rate is acceptable."* The stated reason is that the cost of a premature check *"falls on users."*

This is the same shape as `agent-eval.md §7`'s experimental/calibrated/hard-gate ladder, applied to runtime guards rather than release gates. *(Source: `eval/experiment-tracking-schemas.md`)*

---

## 7. Logging integration

Agent spans complement, not replace, structured application logs.

- Span: machine-readable trace for distributed tracing and cost analysis.
- Log: human-readable event record for debugging.

Every log line emitted during an agent turn should carry `trace_id` and `span_id` so logs and traces are correlatable.

### Audit logs serve three purposes with different requirements

This section frames logs as a debugging artifact. The wiki names three consumers, and they pull the retention and access design in different directions:

| Purpose | What it needs |
|---|---|
| **Debugging** | Depth and recency |
| **Compliance** | Immutability and retention |
| **Improvement** | Queryability across runs |

A store tuned only for the first will fail the other two — and the failure surfaces late, when someone asks for a year-old record or wants to slice across a thousand runs. *(Source: `infra/agent-management-layer.md`)*

### Traces are a corpus, not a pile of incidents

The improvement purpose has a concrete form: *"being able to ask 'which traces call two tools' without exact string matching is what enables workflow automation over the trace corpus."* This spec treats a trace as something you read after a failure; the wiki treats the collection as queryable substrate. *(Source: `eval/experiment-tracking-schemas.md`)*

---

## 8. What a bad run needs

To debug a failed agent run, the trace must allow you to answer:

1. Which turn failed (span timeline)?
2. What was the model's `finish_reason`?
3. Which tool was called with what inputs, and what did it return?
4. What was the token budget at failure, and was compaction triggered?
5. What was the prompt version?
6. What was the cost of this run?

If the trace cannot answer all six questions, the instrumentation is incomplete.

### A seventh question: did the path make sense?

*"A good outcome doesn't validate the path that produced it."* The wiki's case: retry logic that *"discarded the sources it had already found"* — the final answer was fine, and the waste was *"invisible in the outcome."* None of the six questions above asks whether evidence or state persisted across iterations, despite `iteration_count` already being on the invocation span.

The wiki names five nodes that are independently assertable from a trace: **router, retriever, retry/loop, escalation, synthesizer**. Trajectory assertions are what make `iteration_count` diagnostic rather than decorative. *(Source: `eval/trajectory-over-outcome.md`)*

### Incompleteness can be silent

This section assumes a gap is detectable by trying the six questions. It is not always: *"an ADK agent's trace looks sparse next to a LangGraph agent's not because the agent did less, but because only the decorated call sites were recorded"* — at which point you are *"measuring instrumentation, not behaviour."* The failure mode is worse than sparse output, because misconfiguration can be entirely silent: setting `LANGCHAIN_*` variables for an ADK agent *"produces no traces and no error."*

Verify instrumentation coverage against a run you already understand, before trusting a trace to tell you about one you don't. *(Source: `infra/langsmith-platform.md`)*

### An eighth question: would this trace show the system being wrong?

The seven questions above assume a run that visibly failed. The harder case is the run that succeeded, was wrong, and looked identical to a correct one — where the trace is complete and still shows nothing.

Two additions make that case visible, both of them things the model already knows and the span currently discards:

- **Record abstentions and low-confidence completions as first-class events**, not as ordinary successes. `agent-uncertainty.md §2` requires that "ran and could not tell" stay distinguishable from "ran and found nothing"; if the trace collapses them, the distinction exists in the code and dies at the span boundary — an unknown-known in the literal sense.
- **Record what the run did not see**: retrieval that returned nothing, a tool that was unavailable and skipped, a filter that removed every candidate. An empty retrieval followed by a confident answer is the highest-signal pattern in a trace and is invisible unless the empty result is recorded as an event rather than an absence.

The question this section ultimately serves: **is there any path by which this system learns it was wrong?** Instrumentation that only explains failures already known to be failures closes no loop (`agent-uncertainty.md §6`). If nothing in the pipeline can promote a confidently-wrong run to attention, that is an observability finding, not an eval one.

---

## Sources

- Topics 6.1, 6.8 from `2026-07-19-research-B-topic-canon.md`
- OTel GenAI semantic conventions v1.41 (Development stability)
- `eval/observability-glossary.md` — tracking / tracing / monitoring / alerting
- `eval/experiment-tracking-schemas.md` — `run_id`; the reproduction key; behavioural counters; full-parameter capture; trace corpus queryability; log-only promotion policy
- `infra/langfuse-platform.md` — `run_id` as the join key
- `infra/langfuse-adk-tracing-patterns.md` — explicit error marking; embedding/vector sub-spans; RAG path tagging; scores as first-class
- `infra/langsmith-platform.md` — silent instrumentation gaps
- `infra/observability-runtime-patterns.md` — `latency_ms` naming
- `infra/agent-management-layer.md` — the three audit-log purposes
- `eval/online-eval-sampling.md` — drift is invisible to CI
- `eval/trajectory-over-outcome.md` — path assertions; the five scoring nodes
- `adk/adk-observability.md` — ADK span-name hierarchy
