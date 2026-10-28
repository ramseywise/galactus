# Agent Reliability — Conventions

**Durable question:** What happens on tool error, rate limit, refusal, or timeout — and is the run resumable?

*Tooling-agnostic. This is the policy layer; mechanism (checkpointing) is in `agent-memory.md §3` and framework refs.*

---

## 1. Failure taxonomy

Classify failures before writing retry logic. Different classes need different responses.

| Class | Examples | Default response |
|---|---|---|
| **Transient** | Rate limit (429), timeout, network error | Retry with backoff |
| **Tool error** | Tool returns `is_error: true`, invalid output | Retry once; escalate to orchestrator on second failure |
| **Model refusal** | Model declines to act (safety, policy) | Do not retry. Log the refusal. Route to human or return structured error. |
| **Schema violation** | Model output does not match expected schema | Retry with a rephrased prompt once; fail hard on second violation |
| **Context exhaustion** | Max tokens hit mid-run | Compact and resume from last checkpoint (see `agent-context.md §3`) |
| **Fatal** | Unrecoverable state corruption, missing required credential | Abort. Return structured error. Log with full context. |

Refusals must never be retried as-is — retrying a refused request with identical input produces the same refusal and wastes spend. Log the refusal, emit a `refusal` span event, and route accordingly.

### Three classes the table doesn't have

**Ambiguous intent.** *"The system asks a clarifying question when intent is ambiguous."* This is a distinct class, not a tool error — nothing failed. The wiki attaches a two-sided condition: *"a clarifying question is cheaper than a wrong execution, **but only if it's rare**. Both halves matter"* — otherwise it becomes *"friction users learn to click through."* The governing shape is *"the machine proposes, the domain expert disposes."* *(Source: `harness/production-reliability-primitives.md`)*

**Provider unavailable.** Currently folded into Transient or Fatal, but it has its own response — see §6a.

**Symmetric verification.** *"The same model confirms its own wrong work, confidently."* There is no failure signal at all here, which is what makes it dangerous: the run reports success. Mitigation is structural — *"separate evaluator, stronger model than the generator."* *(Source: `harness/harness-maturity-and-failure-modes.md`)*

### The taxonomy is single-component; some failures are not

Every row above names one thing going wrong: a call times out, a schema mismatches, a model refuses. That framing covers most incidents and is the right default. It has a blind spot worth naming, because the failures it misses are the expensive ones.

**In a system that is both complex and tightly coupled, some failures are interactions between components that are each behaving correctly.** No row applies, because nothing failed. The classic engineering statement of this is Perrow's *Normal Accidents*: past a threshold of interactive complexity and coupling, such failures stop being anomalies and become a property of the system's shape. The design response is not a longer taxonomy — you cannot enumerate interactions — but a change to the two variables:

| Variable | What raises it here | What lowers it |
|---|---|---|
| **Interactive complexity** | Shared mutable state, implicit ordering, one component's retry feeding another's rate limit | Explicit interfaces, single-writer keys (`agent-architecture.md`), fewer edges |
| **Coupling** | Synchronous chains, no timeouts, unbuffered fan-out, all-or-nothing transactions | Queues, timeouts, bulkheads, circuit breakers (§6), idempotent steps (§3) |

Read §3 and §6 in this light: idempotency and circuit breaking are usually justified as retry hygiene, but their larger payoff is **decoupling** — they let one component's bad hour stop at a boundary instead of propagating. The `retry-storm` shape is the canonical local example: every component retrying correctly, in a pattern that synchronizes, and the aggregate load takes down a dependency none of them individually overloaded.

The practical rule: **when a postmortem finds no faulty component, do not keep hunting for one.** Record it as a coupling finding and reduce a variable in the table. "Nobody made a mistake and it broke anyway" is a valid, actionable diagnosis — treating it as an unsolved single-component failure is how the same incident recurs. This is the reliability-side counterpart of `agent-uncertainty.md`'s unknown-unknowns quadrant: not enumerable, only survivable.

### Diagnose in order: orchestration → context → model

Before classifying a failure as a model failure, check the two layers above it:

1. **Orchestration** — tool wiring, control flow, gates.
2. **Context** — what the model was actually given.
3. **Model** — last, and rarely the answer. *"The model itself is rarely the bottleneck in mature setups."*

***"Reaching for a model upgrade before auditing tool descriptions is the field's most expensive reflex."*** This is the diagnostic ordering behind `agent-runtime.md §5`'s "prefer better prompting" guidance. *(Source: `harness/harness-maturity-and-failure-modes.md`)*

---

## 2. Retry policy

**Defaults (override per tool/route as needed):**

```
max_retries:    3 (transient), 1 (tool error), 0 (refusal, fatal)
initial_delay:  1s
backoff:        exponential, factor 2x
max_delay:      30s
jitter:         ±20% of computed delay (prevents thundering herd)
```

Retry budget is per-invocation, not per-tool. If an invocation has consumed its budget across multiple tool failures, fail the invocation — do not reset the counter for a new tool.

**Do not retry:**
- Refusals.
- Authentication failures (retrying won't fix a bad credential).
- Fatal errors.
- Tool calls that are not idempotent (unless you have an idempotency key).

### Retry at the right level

Retry happens at two levels, and *"retrying the wrong level wastes the attempt."*

| Level | Retries | Use when |
|---|---|---|
| **Call** | The individual LLM call | Transient noise — *"nothing about the plan was wrong"* |
| **Node** | The logical step | *"The call succeeded but the step didn't achieve its purpose"* |

The counts above are call-level. A node that produced a valid but useless result has consumed zero call-level retries and needs a different decision. *(Source: `harness/agent-retry-taxonomy.md`)*

### Feed the error back, or it isn't a retry

*"An identical retry re-runs the reasoning that just failed and **tends to fail identically**."* Passing the failure back into context is what turns a repeat into a re-plan — *"which then produces a **corrected** query rather than the same one."* After the cap, the tool *"reports failure honestly."*

This is a precondition for the numbers above, not an optional refinement. A retry policy without error feedback is a policy for paying three times for the same answer. *(Source: `harness/agent-retry-taxonomy.md`)*

> **Conflict — flagged, not resolved.** The wiki states a flat cap that does not match the per-class table above: ***"Cap retries at two per gate failure. Beyond that, the problem is in the context or the specification — not the execution."*** Its argument is epistemic rather than economic — *"three failures on the same gate means **the agent lacks information or the spec is wrong**. More attempts spend money to confirm that"* — and it is explicitly conditional on the previous subsection: *"the rule is load-bearing only when paired with feeding the error back as context... **once the error is already in context, further attempts add no new information**, so the third failure is genuine signal rather than bad luck."*
>
> Note the unit may differ: a *gate failure* is not obviously the same thing as a call-level retry, and `harness/agent-retry-taxonomy.md` corroborates the table above exactly (transient max 3, tool error and schema retry once). The likely reconciliation is that 3/1/0 governs call-level retries and *two* governs node-level gate failures — but the wiki does not say so, and the tension is left standing. *(Source: `harness/loop-detection-and-the-two-retry-rule.md`, `harness/agent-retry-taxonomy.md`)*

### Bound cost, not just count

A retry cap bounds attempts on one failure; it does not bound total spend on a run that fails in many different places. The wiki pairs them: *"retry caps **+ cost ceiling per run**."* See `agent-safety.md §5a` — an unbounded loop is a safety problem, not only a budget one. *(Source: `harness/harness-maturity-and-failure-modes.md`)*

### Failures become permanent fixes

Two further items from the same build checklist: **incident memory** — *"failures become permanent fixes"*, so that a class of failure is retired rather than re-encountered — and a **subtraction pass** scheduled *"on each model upgrade — **and on any gate that false-positives**."* A gate that fires on correct work is a cost with no benefit, and the trigger to remove it is its own false-positive rate. *(Source: `harness/harness-maturity-and-failure-modes.md`)*

---

## 3. Idempotency

Every tool that writes, sends, or mutates should have an **idempotency key**:

- Key is caller-generated (e.g., `run_id + step_id + tool_name`).
- On retry, the same key is sent. The tool (or its backend) returns the prior result rather than executing again.
- The agent treats a repeated successful result identically to the first — the operation is complete.

Tools that are inherently idempotent (read-only, pure computation) do not need keys.

Tools that are **not** idempotent and do not accept idempotency keys must not be retried. Escalate to a human if execution is required.

**The key can address an environment, not just a record.** A sandbox created as `analysis-${researchId}` is fetched with get-or-create, so *"retried steps reattach to the existing sandbox"* rather than paying setup again — the idempotency-key pattern above applied to a resource rather than to a write. *(Source: `loop/loop-engineering.md`)*

### Supersede — when a turn cannot be retried

Everything above holds wherever a turn can be replayed, which is every request/response design. The key `run_id + step_id + tool_name` presumes exactly that: the same step, run again, addressed by the same name.

Streaming breaks the presumption at the output. **Audio already played cannot be unplayed.** When a caller interrupts mid-sentence, or the endpointer cuts an utterance short, the half-delivered turn is not a failed attempt waiting on a retry — the caller *heard* part of it, and that hearing is now a fact about the conversation. Retrying would replay speech they have already listened to. The turn must instead be **superseded**: marked truncated at the point delivery actually stopped, and replaced by a new turn whose context includes what was heard.

The criterion is one question: **did any effect escape before the failure?**

| | Retry | Supersede |
|---|---|---|
| Effect escaped? | No — nothing observable happened | Yes — audio played, and the caller heard it |
| Addressed by | Same idempotency key | New turn, referencing the truncated one |
| Prior attempt | Discarded as if it never ran | Retained; it is conversational context |

Note the boundary is *effect escape*, not *streaming*. A tool call inside a voice turn that fails before writing is an ordinary retry, keyed as above — the fact that it lives in a streaming session changes nothing. Only the audio leg supersedes.

**The rest of this section transfers unchanged.** Backoff, jitter, circuit breakers, and the non-idempotent-tools rule at `:120` all apply identically in a streaming design; supersede is an addition to the taxonomy, not a replacement for it. What supersede requires beyond them is state: how much was generated, how much was actually heard, and where the interruption landed. See `agent-voice.md §4`.

---

## 4. Resumability

A run is resumable if, after a failure, it can continue from the last stable checkpoint without re-executing completed steps.

Requirements:
1. Checkpoint written after each plan step completes (see `agent-memory.md §3`).
2. Each step is deterministic given its inputs — re-running from checkpoint produces the same result.
3. On restart, the agent loads the checkpoint, logs the resume point, and proceeds from the next incomplete step.
4. The checkpoint includes: completed step list, step outputs needed by remaining steps, run metadata (IDs, versions, config).

Without checkpointing, a failure at step 9 of 10 means re-running steps 1–9 — costly and potentially unsafe for write operations.

### The payoff nobody counts first

The wiki ranks checkpointing's benefits *"in ascending order of importance"*: cost, then latency, then —

***"User-initiated retry becomes viable... Without checkpointing, 'retry' means 'start the multi-minute workflow over,' which nobody does twice."***

The cost argument above is the weakest of the three. The real one is that a run which cannot be cheaply retried will be abandoned instead, which converts every failure into a lost task.

**Two stores, not one.** State is persisted *"after every step"*, with graph state checkpointed to Postgres via the checkpointer and *"application-level state (logs, intermediate steps, citations) kept separately"* in a document store. The split matters because the two have different lifetimes: graph state is discarded once the run completes, while the citation trail is what §7's audit obligations run on.

**At the tool layer.** The same primitive appears one layer down: each tool's `execute` carries a `'use step'` directive that makes a checkpoint boundary, so *"completed steps replay from recorded output instead of re-executing; failed steps retry automatically."* Same resume-from-failed-node idea, different granularity. *(Source: `harness/production-reliability-primitives.md`, `loop/loop-engineering.md`)*

---

## 5. Graceful degradation

When a non-critical path fails, the agent should degrade gracefully rather than abort:

- Mark the failed step in state with its error code and continue if the remaining steps do not depend on it.
- Return a partial result with a `degraded: true` flag and a list of skipped steps.
- Emit a `degraded_run` span event for alerting.

Do not degrade silently. Callers must know the result is partial.

***"Degrade loudly.* Silent degradation is worse than failure because it looks like success."** *(Source: `harness/agent-retry-taxonomy.md`)*

### Route by confidence instead of degrading

Degradation is a whole-run decision. At volume, the finer-grained version routes each item: *"each extracted field is scored and routed by confidence — high-confidence fields apply automatically, low-confidence fields are **quarantined for human review**."*

*"The threshold decides which regime each item lands in"*, and moving it as measured accuracy improves is *"the ratchet running in the direction of less human work."* The threshold is the tunable; the quarantine lane is what makes it safe to tune. *(Source: `harness/production-reliability-primitives.md`)*

---

## 6. Circuit breaking

For repeated failures to the same tool or downstream service:

- After N consecutive failures (default: 5), open the circuit — do not call the tool for a cooldown period (default: 60s).
- Log circuit open/close as span events.
- While the circuit is open, fail fast with a clear error code (`circuit_open`) rather than waiting for timeout.

Circuit state is per-agent-instance, not global, unless the tool is a shared service — in which case the circuit should live in the service or a shared circuit-breaker layer.

---

## 6a. Where an open circuit escalates to

The section above says stop calling; it does not say what to do instead. For model calls, the answer is a fallback: *"when a model fails after its retries, fall back to a different model, **ideally on a different provider**."*

The reason it is a design concern and not a monitoring one: ***"provider availability is outside your control, so it must be designed around rather than monitored."*** No amount of alerting converts someone else's outage into a run that completes.

What makes it cheap is the ordering — *"every model sits behind a single OpenAI-compatible endpoint, which is what makes swapping one for another a config change rather than an integration."* Hence: ***"uniform interface first, fallback policy second."*** Building the policy against direct SDK calls means the fallback is an integration project at the moment you need it. *(Source: `harness/production-reliability-primitives.md`)*

---

## 7. Structured error returns

Every error path returns a structured object. Never throw to the caller unhandled:

```
{
  "is_error": true,
  "error_code":  string,  -- stable identifier (e.g., "rate_limit", "tool_failure", "refusal")
  "message":     string,  -- human-readable description
  "is_fatal":    boolean, -- if true, the run cannot continue
  "retry_after": int,     -- seconds, when applicable (rate limits)
  "run_id":      string,  -- for correlation with traces
  "step":        string   -- which step failed
}
```

Error codes must be stable across versions. Callers build routing logic on them.

---

## Sources

- Topic 6.7 from `2026-07-19-research-B-topic-canon.md`
- `.claude/skills/new-agent/references/cap-streaming.md` (exception handler patterns)
- `.claude/skills/langgraph-persistence/SKILL.md` (checkpointing mechanism)
- `harness/agent-retry-taxonomy.md` — call-level vs node-level retry; error-as-context; degrade loudly
- `harness/loop-detection-and-the-two-retry-rule.md` — the two-per-gate cap and its epistemic argument
- `harness/production-reliability-primitives.md` — clarifying questions; confidence routing and quarantine; checkpointing payoff ranking and the two-store split; cross-provider fallback behind a uniform endpoint
- `harness/harness-maturity-and-failure-modes.md` — diagnose orchestration → context → model; symmetric verification; cost ceiling; incident memory; subtraction pass
- `loop/loop-engineering.md` — sandbox reattachment by run id; `'use step'` checkpoint boundaries
