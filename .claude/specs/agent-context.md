# Agent Context Engineering — Conventions

**Durable question:** What goes in the context window, in what order, and what gets evicted first? How does a long-running agent stay under the window without losing decisions?

*Tooling-agnostic. Generalizes an earlier session-level context-health rule from sessions to agents. For framework-specific compaction nodes see `cap-compaction.md` (payload).*

---

## 0. Why the window is finite

The levers below only make sense against the mechanism that motivates them, which is not token budget.

Every token attends to every other token, producing **n² pairwise relationships**. Doubling the context quadruples the attention pairs while the parameters resolving them stay fixed — so **attention gets thinner, not just slower.** Two consequences follow:

1. **Token cost is not the binding constraint.** A 150k window comfortably within budget and latency can still degrade quality.
2. **"It fits in the window" is not an argument for including something.** The marginal-return curve on added context turns **negative**, not merely flat.

**Four shapes of rot:**

| Shape | What it looks like |
|---|---|
| **Middle neglect** | Start and end recalled, middle not — "lost in the middle" |
| **Distractor sensitivity** | Plausible-but-wrong nearby content pulls the answer off target, more so as the window grows |
| **Instruction decay** | System-prompt constraints obeyed early are quietly dropped later |
| **Needle degradation** | Exact-match retrieval of a planted fact degrades as filler increases — **even when the fact is verbatim present** |

The last is the important one: it is why *"include it just in case"* is a real cost rather than free insurance. Long-context techniques such as position-encoding interpolation **do not repeal rot — they move where it starts.**

**The objective, stated positively:** *"find the smallest set of high-signal tokens that maximize the likelihood of your desired outcome."* Context engineering is a **minimization** problem. That is the field's central counterintuition — large windows invite filling, and filling degrades output.

**Where this spec's edges are.** Downward, toward prompting: *"once you are deciding **what** is in the window rather than **how** to phrase what is already there, you are in context engineering."* Upward, toward the harness: *"once assembly becomes stateful and conditional — a loop that decides when to retrieve, compact, or spawn — you have crossed into harness engineering."* And the inheritance rule that bounds what this spec can fix: **"A well-assembled context window cannot compensate for poorly written instructions inside it."**

**Measure occupancy, not just cost** — percentage of window used is a health metric independent of dollars. And **prefer a pointer to a payload**: a file path costs a handful of tokens; the file costs thousands.

*(Sources: `context/why-context-is-finite.md`, `context/context-engineering.md`)*

---

## 1. The four-lever model

Context engineering has four levers. Apply in order — write first, compress last.

| Lever | Question | Action |
|---|---|---|
| **Write** | Is this content actually needed? | Curate what enters; exclude by default |
| **Select** | Which subset is most relevant right now? | Retrieve, filter, rank before injection |
| **Compress** | Can this be shorter without losing meaning? | Summarize, truncate trailing history, evict stale tool results |
| **Isolate** | Does this subtask need its own context? | Spin up a subagent with a scoped window |

Isolation (subagents) is the highest-cost lever — use it when context collision is unavoidable (two domains sharing a window produces worse output than two isolated subagents). The wiki states the same ordering as an explicit gate: **"Try Compress before reaching for Isolate."**

> **Conflict — flagged, not resolved.** Two of the lever names above are contested by the wiki.
>
> **"Select … before injection"** encodes the RAG-era assumption — retrieve, then infer. The wiki identifies that assumption as precisely what shifted: the agentic pattern is **just-in-time context**, retrieving *during* inference. *"The difference is who decides relevance"* — pre-computed retrieval makes an embedding-similarity guess before it has seen the model's reasoning. The phrasing above isn't wrong, but it forecloses the option. See §1a. *(Source: `context/context-retrieval-strategies.md`)*
>
> **"Compress"** conflates two distinct scopes the wiki insists on separating: **compression** reduces an individual artifact *before* it enters the window (a query-conditional document summary, a truncated tool result) — per-item, pre-injection; **compaction** reduces accumulated *history* into a continuation state — whole window, mid-session. *"Compression bounds what each item costs; compaction bounds what the session costs."* You need both. The lever's action line above ("summarize, truncate trailing history, evict stale tool results") mixes the two senses. *(Source: `context/context-compaction.md`)*

---

## 1a. Retrieval strategy: who decides relevance, and when

**The arithmetic.** A file path costs ~10 tokens; the file costs ~5,000. If the agent needs 3 of 50 files, an identifier index plus three reads spends roughly **500 + 15,000 tokens**, versus **250,000** to pre-load all fifty.

**The costs of just-in-time**, which are real and under-stated: latency (each exploration round-trip is a full inference), wandering, and **non-determinism** — two runs may load different files, which complicates evals and reproducibility (see `agent-eval.md §2a`).

**The hybrid default, with a threshold.** Pre-load what is cheap and near-certainly needed; leave the long tail to runtime. The question that decides it:

> **Is this needed on ≥80% of turns? Yes → pre-load. No → an identifier plus a tool to fetch it.**

| Pre-load | Just-in-time |
|---|---|
| Project conventions file; directory tree / file index; schema summaries; recently touched files | Any specific source file; full API reference sections; historical records; log and test output |

**Fixed `k` is a bug in both directions** — it over-fills simple queries (rot) and under-fills complex ones (missing evidence). Scale retrieval depth to task complexity: a simple factual lookup wants few chunks (*"more is pure dilution"*); comparison and synthesis want more; ambiguous or exploratory work wants **retrieve wide, rerank hard, send narrow**.

**Pre-retrieval pipeline ordering** — each stage narrows the candidate set, so cheap filters go first:

```
metadata filter → vector search → rerank (cross-encoder) → dedup
  → compress → memory injection → structured formatting → LLM
```

- **Metadata filtering first**, because permission and freshness checks are near-free versus embedding search — and **permission filtering here is a security control, not an optimisation.** Push the filter *into* the vector query, not onto the results.
- **Dedup trap:** *"a chunk retrieved by multiple sub-queries is often the most relevant one."* Treat multi-retrieval as a positive ranking signal, not as redundancy.
- **Compression is query-conditional.** A generic summary discards the specific detail the query needed.

*(Source: `context/context-retrieval-strategies.md`)*

---

## 2. What goes in the window, and in what order

**Stable (high priority — keep through compaction):**
1. System prompt (identity, tools, constraints)
2. Persistent memory summaries (decisions already made, session facts)
3. Current task context (retrieved documents, relevant state)

**Ephemeral (compress or evict when pressure grows):**
4. Conversation history (compress to summary beyond last N turns)
5. Tool results (evict results from completed steps; keep final outputs only)
6. Scratch reasoning (thinking tokens / chain-of-thought; discard after use)

Load only what the current turn needs. Do not inject full conversation history if a compressed summary suffices.

### The four context types

Static (role, instructions, rules — stable across sessions) · Dynamic (date/time, user, environment — per turn) · Retrieved (vector store, search, file reads — per query) · Historical (prior states, revisions, outputs).

> **"Historical is the only type without a natural bound. Compaction exists to bound it."**

The others are sized by something external — a spec is as long as it is, a diff is as big as it is. This is the same structural claim `agent-memory.md §1` makes about the episodic tier, on the memory side of the boundary.

### The missing layer: deterministic system

The stable/ephemeral split above organises by **eviction priority**. The wiki organises the same material by **stability and enforcement requirement**, and its fifth layer has no counterpart above:

| Layer | Content | Test |
|---|---|---|
| 1 — Persistent instruction | Identity, standing rules | *"If it isn't true in nearly every task, it doesn't belong here"* |
| 2 — On-demand knowledge | Skills, references | ~10 tokens resident, thousands loaded on demand |
| 3 — Runtime injection | Date/time, user, environment — assembled programmatically at request time | Without injection, every relative date resolves wrong |
| 4 — Long-term memory | Distilled facts — **never a full transcript pasted forward**; must be editable and auditable | See `agent-memory.md` |
| 5 — **Deterministic system** | Hooks, permissions, schemas, validators | *"A code-level control cannot be talked out of enforcing itself"* |

**Layer 5 is the answer to prompt-altitude drift:** *"the agent keeps doing X" is usually a hook, not a stronger sentence.* This is the enforcement ladder of `DESIGN-PROCESS.md §3` appearing inside the context anatomy — and it is the layer most often left out of a context design entirely, because it does not look like context.

> Organise by usage frequency, stability, and enforcement requirement — **not by topic.** Note that the six-item list above and this five-layer model are compatible framings of the same window; pick one as the organising frame rather than stacking both.

### Ordering and cache economics

The ordering above is defensible for eviction and silent on cost. Prompt caching works by **prefix matching**: the cache hits only on a byte-identical prefix, and **the first differing token invalidates everything after it.**

```
[system prompt][tools][stable memory]   ← cacheable prefix
[retrieved docs][history][runtime state] ← dynamic
[current query]                          ← last
```

> **"Put a timestamp at the top of the system prompt and you have destroyed cache reuse for the entire window on every single call."**

- Cache TTL is **5 minutes**; the prefix must be **byte-identical** to hit; a hit costs roughly **10%** of the prefix's token cost.
- **The observable check is the enforceable part.** Anthropic API responses carry `cache_read_input_tokens` and `cache_creation_input_tokens` — *"a healthy prefix-caching setup should show `cache_read_input_tokens > 0` on all calls after the first."*
- Framework specifics: in ADK, `static_instruction` is cache-eligible and `instruction=callable` is not (the callable injects dynamic content, breaking byte-identity). In LangGraph, keep retrieved chunks **after** the system prompt, not before.
- **Aligned quality effect:** for long-document work, put the longform data above the query — reported up to **30% quality improvement** when the query appears at the end.

**Two caches, often confused.** *Prompt caching* is inference-level: it caches prefill computation for a token prefix, is prefix-match only, and so is governed by ordering. *Retrieval caching* is application-level: it caches the *results* of expensive retrieval, keyed by query similarity. They fail differently and are monitored separately.

### Delimit untrusted content

Wrap user input and retrieved documents in tags so the model can distinguish instructions from data — this is also the first rung of the injection defence ladder in §7.

**Structured outputs are context engineering.** A schema constrains what comes back, which determines what the *next* turn's context contains — so **schema discipline compounds across a loop** (see `agent-architecture.md §4`). Relatedly, a handful of well-chosen diverse few-shot examples outperforms an exhaustive rule list, at fewer tokens.

*(Sources: `context/context-anatomy.md`, `context/context-engineering.md`, `infra/prefix-caching.md`, `context/context-retrieval-strategies.md`)*

---

## 3. Compaction strategy

Apply compaction before the window is full — reactive compaction mid-run risks losing context at a decision point.

**Trigger points:**
- Approaching 80% of the model's context limit.
- After completing a plan phase (phase boundaries are compaction boundaries).
- Before spawning a subagent — compact the parent first so the spawn starts lean.
- After large reads (5+ files, or any file >500 lines) that won't be needed again.
- **Past roughly thirty minutes of agent runtime**, write progress to disk regardless of occupancy. *"The probability of some interruption over a long run approaches one"* — past that point crash recovery is mandatory rather than optional, and **state on disk survives everything that happens to a context window.**

> **Numeric tension — flagged.** The 80% trigger above is a *compaction* threshold. The wiki's *diagnostic* threshold is lower: **above ~50% occupancy, suspect rot and distraction first** (§7). Different purposes, but a reader will see 50 against 80. Both are correct for their own question: at 50% you start suspecting degradation; at 80% you act on window pressure.

**Why phase boundaries specifically.** Compaction rewrites the prefix, so it **invalidates the cache from the compaction point forward** — each compaction pays a full re-prefill. That makes it worth doing, and worth not doing more often than necessary. **Compacting at a phase boundary amortises the cost across the phase that follows**, and the post-compaction window should still be structured stable-parts-first (§2).

**The compaction pipeline, in order:**

1. **Prune irrelevant content** — abandoned branches, superseded attempts.
2. **Replace bulky tool outputs** — keep the conclusion, drop the payload.
3. **Extract structured task state** — files touched, decisions, open TODOs.
4. **Summarise older reasoning.**
5. **Preserve recent messages verbatim.**

> **The final step matters most.** *"Recent turns stay verbatim because the agent's immediate working state lives there — half-finished edits, the error currently being debugged. Summarizing the last three turns is how a compaction loses the thread."*

**Component techniques, ranked by loss profile:** sliding window (total loss of dropped content) · summarisation (lossy, unpredictable) · pruning (total but targeted; safest when rule-driven) · state extraction (lossless for what it extracts) · **tool-result clearing (near-lossless)**.

**Tool-result clearing is the highest-value, lowest-risk move — clear it first, before reaching for lossy summarisation.** And: **"State extraction is what makes compaction safe… Agents that write their state down survive compaction; agents that keep it in the transcript do not."**

**What must survive compaction, in priority order:**

1. **Architectural decisions — do not summarise.** *"'We chose X over Y because Z' must survive verbatim. Lose the reasoning and the agent re-litigates a settled decision, or silently contradicts it."*
2. Modified files and critical changes — *"the diff-so-far is state, not history."*
3. Verification status.
4. Unresolved TODOs and rollback notes.
5. **Tool output — deletable.**

> **The asymmetry between 1 and 5 is the core insight.** A 40k-token test output compresses to `"17 passed, 2 failed: test_auth_retry, test_token_refresh"` with essentially no loss. A one-sentence architectural rationale cannot be compressed at all.

Merge this with the three items the spec listed previously (plan state and progress markers; schema contracts and invariants; output committed this turn) rather than concatenating the two lists — they overlap.

**A fourth obligation: resolve contradictions rather than carrying them.** On compaction, record the **settled** fact, not both sides (see the clash failure mode in §7).

For Anthropic-native agents: `clear_tool_uses` and `clear_thinking` are server-side context-editing primitives that can be applied without a full truncation pass. Server-managed compaction is available in long-context agentic API calls. OpenAI's Responses API exposes compaction directly — after appending output items, drop the items preceding the most recent compaction item. The general pattern is the same in both: **the compaction item is a checkpoint, and everything before a checkpoint is discardable.**

*(Source: `context/context-compaction.md`)*

---

## 4. Prompt versioning

Every prompt is a **versioned artifact**, not an inline string.

Rules:
- Prompts live in files (e.g., `prompts/system_prompt.txt`), not in application code.
- Each prompt file carries a `PROMPT_VERSION` identifier (semver or date-slug).
- Bumping the prompt version invalidates: cached model responses, eval baselines, and any grader calibration tied to the prior version. See `agent-eval.md` for the eval impact.
- Breaking prompt changes (new required fields, removed capabilities) increment the major version and require a migration note.

Version propagation: the `PROMPT_VERSION` value should appear in every trace span so a bad run can be attributed to the specific prompt that produced it.

### Prompt altitude

Versioning governs how a prompt changes; **altitude** governs what belongs in it. A system prompt sits between two failure modes:

- **Too low** — hardcoded if/else logic written out in prose. Brittle; breaks on any case not enumerated.
- **Too high** — vague guidance that assumes context the model does not have. The model invents its own interpretation.

**The low-altitude failure is the common one in engineered systems**, because each production bug tempts one more rule. The heuristic:

> *"When you catch yourself adding a fourth conditional to a prompt, the fix is usually a tool or a code-level control, not a fifth conditional."*

This is the enforcement ladder applied to prompt content: past a certain conditional depth, the instruction layer is the wrong layer, and the right move is Layer 5 (§2) — a hook, a permission, or a schema.

*(Source: `context/context-anatomy.md`)*

---

## 5. Skills and progressive disclosure

Not every capability needs to be in the system prompt at all times.

**Progressive disclosure pattern:**
- Load a minimal base system prompt (identity + tool list).
- Load task-specific instruction blocks only when that task type is active.
- Unload task-specific blocks when the task completes.

This reduces the stable portion of the context, leaves more room for conversation history, and avoids the model attempting task-specific behaviors outside their intended scope.

The `/skills/` directory in Claude Code is the practice of this pattern — each skill file is loaded only when invoked, not always-on. The same principle applies to agent system prompts.

**When to inline vs. load dynamically:**
- Always inline: core identity, tool definitions, hard constraints.
- Load dynamically: domain-specific rules, RAG context, task instructions.
- Never inline: retrieved documents (they change per query).

Where the qualitative split is ambiguous, apply the ≥80%-of-turns threshold from §1a.

**Progressive disclosure is one idea with three applications.** On-demand skills (Layer 2 in §2), lightweight identifiers in just-in-time retrieval (§1a), and index-plus-detail memory (`agent-memory.md §6`) are the same pattern: **keep a cheap pointer resident, load the payload on demand.** The Layer-2 economics — *"~10 tokens resident, thousands loaded on demand"* — are the economics of all three. Treating them as one pattern rather than three techniques is what makes the skills directory, the file index, and the memory index reviewable against the same test.

*(Sources: `context/context-anatomy.md`, `context/context-retrieval-strategies.md`, `context/memory-as-context.md`)*

---

## 6. Subagent context isolation

When a subtask would contaminate the orchestrator's window with domain-specific noise, isolate it:

- Subagent receives: task description, required tools, relevant context slice, output schema.
- Subagent does NOT receive: full conversation history, other subagents' intermediate results, the plan document.
- The orchestrator receives: the subagent's structured output only.

Orchestrator-holds-plan + isolated-window subagents is the settled 2026 default. Do not pass the orchestrator's full context to a subagent.

### The economics

> *"A sub-agent may burn 100k tokens exploring a codebase and return a 2k-token summary."*

The orchestrator pays 2k for work that would have cost 100k of its own window — and would have left **98k of exploration debris** polluting the window it needs for synthesis. **"The sub-agent's window is discarded, not merged. That discarding is the feature."** Target return size is roughly **1,000–2,000 tokens**, under the rule: *"a search that reads 40 files and finds 3 relevant ones should return the 3, not the 40."*

### The four costs

1. **Lost shared context** — subagents cannot coordinate; they may duplicate work or reach contradictory conclusions from disjoint evidence.
2. **The summary is lossy** — *"if its judgment about relevance was wrong, the orchestrator never learns what it missed."* This is the cost with no detection mechanism.
3. **The prompt is the whole interface** — an under-specified subagent prompt yields an off-target investigation, *discovered only after it has burned its budget*.
4. **Token multiplier** — three subagents at 80k each is 240k of real tokens for 6k of visible output. Cheap for the orchestrator's window; expensive in absolute spend.

### Why subagents don't set strategy

The rule above — subagents do not receive the plan document — has a reason: **each sees only its slice.** *"An agent that explored one subsystem will over-weight that subsystem — it has no basis for comparison. Cross-cutting judgment requires the window that saw all the summaries."*

### Isolation as a trust boundary

A subagent processing untrusted content has a window that gets discarded, so an injection landing there can reach the orchestrator only through the **summary** — a narrow, inspectable channel.

> **"This only holds if the summary is treated as data, not instructions.** A sub-agent summary interpolated directly into an orchestrator prompt is itself an injection path."

Same structure as the Dual-LLM pattern. Defensible default posture for an isolated worker: skills **allowed**, shell **allowed**, network **enabled only with a minimal allowlist, per request, for narrowly scoped tasks**. And the standing assumption: **tool output is untrusted regardless of source.**

*(Sources: `context/multi-agent-context.md`, `harness/harness-orchestration.md`)*

---

## 7. Context failure modes

Five failures, routinely misdiagnosed as each other — or as *"the model isn't smart enough."* They have distinct mechanisms and distinct fixes, and applying the wrong fix usually makes the actual problem worse.

| Mode | Mechanism | Signature | Fix |
|---|---|---|---|
| **Rot** | Occupancy grows, recall degrades | Correct earlier in the session, wrong later; facts present but unused | Compaction at phase boundaries, tool-result clearing, state to disk |
| **Poisoning** | A false statement enters context and is treated as ground truth | Self-reinforcing — it sits in the window as apparent fact, not as a claim under evaluation | Freshness filters, citation verification, memory hygiene; **distinguish *observed* from *inferred* when writing notes** |
| **Distraction** | Volume of *individually plausible* marginal content crowds out signal | A competent answer to a question *adjacent* to the one asked | Rerank hard, send narrow, dynamic `k` (§1a) |
| **Clash** | Two contradictory pieces coexist; the model resolves arbitrarily without flagging | Output looks confident — **worse than either input alone** | Explicit precedence; resolve on compaction |
| **Injection** | Context has no type system — instructions and data are the same tokens | Structurally different: **an attack, not a degradation** | The ladder below |

**Rot's anti-fix matters as much as its fix: repeating the constraint more forcefully adds tokens, and tokens are the cause. Nor is a bigger window a fix.**

**Poisoning is durable through memory:** *"a poisoned entry written to long-term memory is re-injected every future session — a single hallucination becomes a permanent false belief."* See `agent-memory.md §4`.

**Clash resolution** needs an explicit precedence order — **system > developer > user > retrieved**, with *later superseding earlier within a tier*. Canonical case: the user says "actually, use pnpm" at turn 12 while "we use npm" from turn 3 is still in the window. Two further rules: **on compaction, resolve rather than carry** — record the settled fact, not both sides; and **version-pin retrieved documents**, so contradictions surface as version differences rather than as flat disagreement.

### Diagnostic flow

1. **Print the actual window** — not what you think you assembled; what was sent. Most context bugs are *assembly* bugs and are visible immediately.
2. **Check occupancy — above ~50%, suspect rot and distraction first.**
3. **Search for contradictions** — grep the window for the wrong claim; finding it twice with different values is clash.
4. **Check provenance** — no legitimate source means poisoning or injection.
5. **Test in isolation** — same task, minimal context. Works → context problem. Still fails → prompt or capability problem.

> **"Step 5 is the one that gets skipped, and it's the one that separates a context problem from a prompt problem."**

### Injection defence ladder

Six layers, none sufficient alone:

1. **Structural delimiting** — tag untrusted content (§2).
2. **Trust zones** — user input untrusted, retrieved and tool output semi-trusted, agent state trusted. **Never promote a zone implicitly.**
3. **Instruction hierarchy** — the system prompt outranks retrieved content **unconditionally**.
4. **Isolation** in a discarded subagent window — *but treat its summary as data too* (§6).
5. **Code-level enforcement** — *"an injection can talk a model out of a rule; it cannot talk a permission hook out of denying a write."*
6. **Egress control** — network allowlists, confirmation gates on irreversible operations, no credentials in reachable context.

> **"Defence 5 is load-bearing. Every context-level defence is probabilistic; only code-level controls are guarantees."**

That is `DESIGN-PROCESS.md §3`'s enforcement ladder stated as a security claim. See `agent-safety.md` for the risk taxonomy these defences map onto.

*(Source: `context/context-failure-modes.md`)*

---

## 8. Scoping note

`context/context-engineering.md` treats **memory and tool design as sub-components of the context and harness layers rather than sibling pillars** — which disagrees with this spec set's organization of `agent-memory.md` and `agent-tools.md` as peers. Recorded, not resolved; the peer structure answers to `DESIGN-PROCESS.md`'s five-layer stack. Mirrored in `agent-memory.md §7`.

---

## Sources

- Topics 5.4, 5.5, 5.11, 5.12 from `2026-07-19-research-B-topic-canon.md`
- `new-agent/references/core.md` (PROMPT_VERSION convention)
- Anthropic context-editing API (`clear_tool_uses`, server-side compaction)
- `multiagent context/` readings cluster (vocabulary source)
- `context/why-context-is-finite.md` — the n² mechanism; four shapes of rot; occupancy
- `context/context-engineering.md` — the minimization thesis; four context types; layer boundaries
- `context/context-anatomy.md` — the five layers; prompt altitude; delimiting; structured outputs
- `context/context-compaction.md` — compression vs. compaction; the pipeline; retention priority
- `context/context-retrieval-strategies.md` — just-in-time context; the ≥80% rule; dynamic `k`; pipeline ordering
- `context/context-failure-modes.md` — the five failure modes; diagnostic flow; injection defence ladder
- `context/multi-agent-context.md` — subagent economics; the four costs; isolation as trust boundary
- `context/memory-as-context.md` — progressive disclosure as one pattern
- `infra/prefix-caching.md` — prefix matching; TTL and hit cost; cache-token observability
- `harness/harness-orchestration.md` — subagent return-size rule
