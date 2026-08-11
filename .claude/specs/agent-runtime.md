# Agent Runtime — Conventions

**Durable question:** Stateless function, long-lived process, or managed runtime — and what does each force? Where does spend go, and which lever moves it?

*Absorbs the stateless-function constraint analysis previously buried in a framework-specific doc. For LangGraph deployment see `langgraph.md`.*

---

## 1. Topology variants

Three topologies cover the space. Pick the simplest that satisfies the constraints.

| Topology | Description | Forces |
|---|---|---|
| **Stateless function** | Agent runs in a short-lived function invocation; no persistent process | Session state must be externalized (DB); timeout bound is strict; no in-memory caching across requests; streaming must complete within the function timeout |
| **Long-lived process** | Agent runs in a persistent container or service | In-memory session state is possible; timeout is self-managed; scales vertically first; restart policy critical |
| **Managed runtime** | Platform-provided agent hosting (e.g., ADK-managed sessions, LangGraph Cloud) | State and checkpointing are platform-managed; you give up deployment control for operational simplicity; platform cost model applies |

Default for prototypes and low-scale deployments: **stateless function**. Migrate to long-lived process when:
- Agent needs in-memory state across requests for the same session.
- Tool warm-up latency is significant and amortizable over many requests.
- Streaming sessions require persistent connections.

> **Conflict — flagged, not resolved.** The wiki does not carve the space three ways on technical forces. It gives a **five-rung ladder** — local → single service → cloud service → split service → serverless — and selects on cost and operational complexity rather than capability:
>
> | Rung | Infra cost | Ops complexity |
> |---|---|---|
> | Local-only | $0 | None |
> | Single service | $5–20/mo | Low |
> | Cloud service | $20–100/mo | Medium |
> | Split service | $40–150/mo | High |
> | Serverless | Pay-per-use | Medium |
>
> Its selection axis is stated as **"audience, not capability"** — *"'who uses this?' rather than 'what does it do?'"* Single, cloud, and split service all collapse into "long-lived process" above, so the table here cannot express a distinction the wiki treats as primary. Neither taxonomy is wrong; they answer different questions, and this spec has no answer for the audience question. *(Source: `infra/deployment-topology-ladder.md`)*

### Match the trigger to the topology

A fourth axis neither table above carries: how the run starts.

| Trigger | Latency expectation |
|---|---|
| HTTP / API | p50 < 2s |
| Webhook / event | Near-real-time |
| Message queue | Seconds to minutes |
| Cron / schedule | Defined interval |

*"Runtime topology must match the trigger. **A cron trigger that assumes a long-lived worker will fail in serverless.**"* *(Source: `langgraph/runtime-topology.md`)*

### The checkpointer must match the runtime

| Runtime | Checkpointer |
|---|---|
| Lambda / serverless | External DB required |
| Long-lived worker | In-memory viable for dev; Postgres for multi-worker prod |
| Managed platform | Platform-managed |
| Kubernetes pod | External DB — pods restart |

***"Your checkpointer backend must match your runtime hosting model."*** The failure mode is the one this spec's own §5 of `agent-reliability.md` forbids: an in-memory checkpointer in a multi-worker or serverless deployment ***"silently loses state between invocations — no error, just broken sessions."*** **"Never use `MemorySaver` in a multi-worker deployment."**

§2's "state externalization" bullet says state *should* go to a persistent store. It does not say that failing to do so degrades silently rather than erroring, which is what makes this the single most costly misconfiguration on the list. *(Source: `langgraph/runtime-topology.md`, `infra/serverless-deployment.md`, `infra/production-hardening-patterns.md`)*

Related gotcha at the graph level: setting a checkpointer on a subgraph that runs in parallel produces a namespace conflict. *(Source: `infra/production-hardening-patterns.md`)*

---

## 2. Stateless function constraints

These constraints are non-negotiable for stateless deployments (Vercel, Cloud Run, Lambda, etc.):

- **No in-memory session manager** — session objects are reconstructed from DB state at request start.
- **Timeout bound** — design the agent loop to complete within the platform timeout. Vercel: Hobby=10s, Pro=60s, Enterprise=300s. Stream early; do not buffer full responses.
- **No background tasks** — any async work must complete before the function returns or be handed to a queue/job system.
- **Cold start cost** — tool initialization, model client setup, and prompt loading happen on every cold start unless the platform caches function instances.
- **State externalization** — conversation history, session state, checkpoints → persistent store. Load at request start; write at request end.

### The duplex exception

These constraints are scoped to **request/response deployments** — they hold for every tool-calling leaf, including the leaves inside a voice turn. They do not hold for the session process itself.

A duplex voice session *is* a long-lived background task: a media connection held open for minutes, with in-memory state (endpointer, partial hypotheses, playback cursor) that cannot round-trip to a store between audio frames without blowing the latency budget. "No background tasks" and "no in-memory session manager" describe exactly what a voice session must do. So a duplex design does not run on a stateless function — it runs on a process that outlives the request, and the two rules become a boundary rather than a prohibition: **stateless below the session, stateful at it.**

What the session process owns, and what nothing else will do for it:

- **Connection lifetime** — the session ends when the media connection ends, not when a response is returned. There is no `return` to hang cleanup off.
- **Reconnect** — a dropped WebRTC or SIP leg may re-establish. Whether the session resumes or restarts is a design decision, not a transport default.
- **Cleanup on disconnect** — the caller hanging up is the common exit path, and it arrives as a transport event rather than a completed turn. Audio buffers, the ASR stream, and any in-flight TTS must be released on it, including when the hangup lands mid-generation.

Timeout bound and cold start still apply, but they bind differently: the ceiling is the session, not the turn, and a cold start inside a live call is audible. See `agent-voice.md §7`.

> **Conflict — flagged, not resolved.** The wiki treats several of these as **disqualifiers**, not constraints to design around. Serverless is the wrong choice when: *"responses take **> 30 seconds** (function timeouts)... you need persistent connections (WebSockets, streaming)... you need in-memory state between requests."* And it unifies them: ***"three of the four exclusions are the same underlying constraint: the function does not outlive the request."***
>
> Two tensions with the text above. (1) The generic **30s** ceiling sits below this spec's own Pro (60s) and Enterprise (300s) tiers, which are presented as viable envelopes. (2) *"Stream early"* is offered here as a way to live inside the timeout, while the wiki lists streaming as a disqualifier for the category — *"good fit for low-traffic tools (< 100 requests/day) that don't need streaming. **Not ideal for chat applications that need persistent connections.**"* A reader combining this spec's stateless default with §6's streaming guidance builds exactly the combination the wiki rules out. Also unlisted above: cold starts of **1–3s on first request**. *(Source: `infra/serverless-deployment.md`)*

> **Numeric divergence.** Vercel Functions with **fluid compute** run to **800s** — well above the 300s Enterprise figure above, which is a different configuration rather than a correction. The wiki draws the same line regardless of the number: *"anything longer must **checkpoint and resume** rather than hold the process."* A related loop bound from the same page: `stopWhen: stepCountIs(25)` is *"the required ceiling — non-optional in practice when the loop calls paid search tools."* *(Source: `loop/loop-engineering.md`)*

---

## 3. Long-lived process conventions

- **Restart policy**: the agent must reload all state from the persistent store on startup. Do not rely on in-memory state surviving a restart.
- **Health check**: expose a health endpoint that verifies connectivity to all required services (LLM API, DB, vector store).
- **Graceful shutdown**: on SIGTERM, complete the current turn (or checkpoint it), drain in-flight tool calls, then exit. Do not kill mid-turn.
- **Connection pooling**: LLM API clients, DB connections, and vector store clients should be pooled at the process level, not created per-request.

---

## 4. Cost and latency levers

Know where spend goes before optimizing. Typical cost distribution for a RAG agent:

| Component | Typical share | Primary lever |
|---|---|---|
| LLM input tokens | 30–50% | Compaction, caching, context curation |
| LLM output tokens | 20–30% | Response length constraints, streaming early termination |
| Retrieval (embeddings + vector search) | 10–20% | Cache embeddings; use approximate search |
| Reranker (if used) | 5–15% | Apply only to top-k, not all results |
| Tool calls (external APIs) | Variable | Rate-limit; cache idempotent reads |

**The highest-leverage levers:**

1. **Prompt caching** — for large, stable system prompts. Cache hit eliminates input-token cost for the cached prefix. Track `cached_tokens` separately (see `agent-observability.md §5`).

   > **Conflict — flagged, not resolved.** A cache hit does not eliminate the cost: the wiki puts a prefix hit at ***"~10% of prefix token cost"*** against ~100% without. Nine-tenths off is not free, and the difference matters when caching is being weighed against compaction.
   >
   > The field names are also wrong here. The Anthropic API reports `cache_read_input_tokens` and `cache_creation_input_tokens`; `cached_tokens` appears nowhere in the wiki. The health check is *"`cache_read_input_tokens > 0` on all calls after the first."*
   >
   > Two preconditions this list omits: **TTL is 5 minutes**, and *"the prefix must be byte-identical to hit."* Byte-identity implies an ordering rule — stable content before dynamic content, so *"keep retrieved chunks AFTER the system prompt, not before."* Caching *"does not apply to dynamic content appended per turn."*
   >
   > And lever 1 is in tension with lever 3 below: **compaction invalidates the cached prefix from the compaction point forward.** Compacting to save input tokens forfeits the cache on everything after the cut. Neither this spec nor the wiki prices that trade. *(Source: `infra/prefix-caching.md`)*
2. **Model tier selection** — haiku/flash for fan-out and extraction; sonnet for execution; opus for judgment.
3. **Context compaction** — reducing input tokens on re-invocations. See `agent-context.md §3`.
4. **Retrieval latency** — the main wall-clock bottleneck for RAG agents (500–1500ms). Invest in index quality and approximate search before adding more model calls.

### Prefill is cheap and parallel; decode is expensive and sequential

| Phase | Shape | Cost |
|---|---|---|
| **Prefill** | Parallel — all prompt tokens at once | Cheap |
| **Decode** | Sequential — one token at a time | Expensive |

*"Decode is sequential because token n+1 cannot be computed before token n exists."* Two consequences the table above understates: ***"output-length discipline matters more than prompt-length discipline"***, and ***"streaming improves* perceived *latency without reducing total cost"*** — §6's "stream early" is a UX lever, not a cost lever.

Four levers this section doesn't list: **quantization**; **distillation** — *"route the ~80% of traffic that doesn't need frontier capability to the small model"*; **speculative decoding**; and **output-length discipline**, *"the cheapest lever, since decode dominates."* *(Source: `infra/llm-inference-economics.md`)*

### System bottlenecks, with mitigations

| Bottleneck | Mitigation |
|---|---|
| Token overload | Truncate, summarize, stream, paginate |
| Queue congestion | Shard queues; priority tiers |
| Vector index bloat | Prune, compress, periodic rebuild |
| Model cold start | Warm pools, pre-warming |
| Rate-limited APIs | Backoff, caching, multi-provider fallback |

*"Vector index bloat is the bottleneck most often missed, because it **degrades quality before it degrades latency**... the failure surfaces as a hallucination complaint rather than a performance alert."* Note that §2's cold-start bullet names the cost but not the mitigation. *(Source: `infra/llm-system-bottleneck-table.md`)*

### Cache the answer, not just the embedding

The retrieval row above caches embeddings. A **semantic cache** sits in front of the whole pipeline, *"skipping embedding, retrieval, reranking, and LLM generation (**~3–6s, 2+ LLM calls saved**)"* on a hit. Similarity threshold ≥ **0.85** (sweep 0.75–0.95); latency on hits ≤ **500ms end-to-end**. A stronger lever for that line item than approximate search. *(Source: `rag/semantic-cache.md`)*

---

## 5. Model routing and cascade

Model selection can change mid-run:

- **Routing by step type**: use the cheapest model that can do the job. Extraction → haiku; reasoning → sonnet; verdict → opus.
- **Cascade on failure**: if the assigned model returns a refusal or a schema-invalid response, retry with a higher-tier model (once). Log the escalation.
- **Cascade on quality gate**: if post-generation quality check fails (see `agent-safety.md §1` Layer 4), optionally retry with a stronger model.

Cascade adds latency and cost — it is a last resort, not a first-line strategy. Prefer better prompting and context curation to model escalation.

The wiki gives that preference a diagnostic order — orchestration, then context, then model, *"last, and rarely the answer"* — and a warning: ***"reaching for a model upgrade before auditing tool descriptions is the field's most expensive reflex."*** See `agent-reliability.md §1`. *(Source: `harness/harness-maturity-and-failure-modes.md`)*

Routing also applies *within* a run rather than only per step type: a frontier model for loop reasoning and synthesis, a smaller one for aggregation and structured extraction. *(Source: `loop/loop-engineering.md`)*

---

## 6. Streaming

Stream early. Do not buffer full responses if the client supports streaming.

- Begin streaming as soon as the first output tokens arrive.
- For structured-output agents: stream the text; parse the structure client-side, or buffer the structured fields only.
- Streaming errors mid-stream: close the stream with an error event; do not leave it hanging. Return a structured error frame (see `agent-reliability.md §7`).
- Reconnect semantics: if the client disconnects mid-stream, the server must decide whether to continue generating (for checkpoint-based agents) or abort. Document the policy.

**A mechanism for that policy.** Marking each tool's `execute` as a step makes a checkpoint boundary, so *"completed steps replay from recorded output instead of re-executing; failed steps retry automatically."* A reconnecting client resumes against recorded output rather than against a regenerating process — the same resume-from-failed-node primitive as `agent-reliability.md §4`, at the tool layer. *(Source: `loop/loop-engineering.md`)*

**Streaming is not a cost lever.** See §4 — it moves perceived latency only, because decode cost is the same whether or not tokens are shown as they arrive.

---

## 7. Sandbox lifecycle

When the runtime executes model-written code, the sandbox is a runtime resource with its own lifetime:

```
Sandbox.getOrCreate({ name: `analysis-${researchId}`, runtime: 'node24',
                      timeout: 600_000, networkPolicy: 'deny-all' })
```

Two properties matter. It is **keyed by run id**, so a retried step reattaches rather than paying setup again (`agent-reliability.md §3`). And it carries its own timeout and egress policy, independent of the function or process timeouts in §1–2 — a 600s sandbox inside a 300s function is a configuration that cannot complete.

Cloud sandboxes *"cost money while idle"*, which is the pressure against keeping one warm for reattachment. *(Source: `loop/loop-engineering.md`, `harness/execution-boundaries-and-guardrails.md`)*

---

## Sources

- Topics 6.4, 6.6 from `2026-07-19-research-B-topic-canon.md`
- `new-agent/references/infra.md` (Dockerfile / deployment boilerplate)
- `infra/deployment-topology-ladder.md` — the five-rung ladder; audience as the selection axis
- `infra/serverless-deployment.md` — serverless disqualifiers; the 30s ceiling; cold starts; silent state loss
- `langgraph/runtime-topology.md` — trigger/topology matching; checkpointer-per-runtime table
- `infra/production-hardening-patterns.md` — checkpointer selection; subgraph namespace conflict
- `infra/prefix-caching.md` — ~10% hit cost; TTL; byte-identical prefix; ordering; compaction invalidation; API field names
- `infra/llm-inference-economics.md` — prefill vs decode; quantization, distillation, speculative decoding, output-length discipline
- `infra/llm-system-bottleneck-table.md` — five bottlenecks and mitigations
- `rag/semantic-cache.md` — full-pipeline cache; 0.85 threshold; hit latency
- `loop/loop-engineering.md` — fluid-compute 800s; `stepCountIs(25)`; `'use step'` durability; per-step model routing; sandbox keying
- `harness/harness-maturity-and-failure-modes.md` — diagnostic order before model escalation
- `harness/execution-boundaries-and-guardrails.md` — sandbox idle cost
