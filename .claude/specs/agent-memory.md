# Agent Memory — Conventions

**Durable question:** What survives a turn, a session, and a process restart — and where does it live?

*Taxonomy only. Backend-agnostic — implementation (vector store, graph, relational) is contested and project-specific. For LangGraph persistence primitives see `langgraph.md`. For framework state management see respective framework refs.*

---

## 1. Memory taxonomy

Three-tier vocabulary is settled (2026). Implementation is not — do not prescribe a backend.

| Tier | What it holds | Scope | Read pattern |
|---|---|---|---|
| **Episodic** | What happened: events, turns, decisions made in prior sessions | Session → long-term | Recent-first retrieval; prune or summarize older entries |
| **Semantic** | What is known: facts, entities, domain knowledge, user preferences | Long-term, stable | Semantic search / key lookup |
| **Procedural** | How to act: skills, instructions, tool-use patterns | Stable, rarely changes | Always-available (loaded into system prompt or skill) |

Episodic is the only tier that grows unboundedly. It requires a compaction or summarization strategy (see `agent-context.md §3`). The wiki names the target of that strategy: **promotion into the semantic tier.** Episodic accumulates linearly with time and rots; semantic is distilled from episodes and stays roughly constant in size. Three episodic records — *"the user corrected me about commit format"* ×3 — collapse to one semantic fact (`type(scope): desc (#num)`), and the fact is the only part that changes future behaviour. A system that only stores episodes grows forever; one that distills converges.

**A second axis: what the memory is *for*.** The tiers above classify by form. The wiki adds a functions axis that cuts across them:

| Function | Holds | Effect |
|---|---|---|
| **Factual** | User preferences, identity, history; environment and task state | Makes the agent *personalized* |
| **Experiential** | Case-based, strategy-based, skill-based traces of what worked | Makes the agent *better at its job over time* |
| **Working** | Single-turn scratchpads; multi-turn dialogue state, partial plans | Carries the current attempt |

*"Experiential memory is the axis most systems don't have… the two are routinely conflated because both are 'long-term memory' in a vector store."* Storing that a user prefers equities is factual; storing **the approach that worked last time a portfolio query failed** is experiential. The skill-based sub-kind — an agent extracting a reusable tool from its own successful trajectory — is the least implemented.

> **Conflict — flagged, not resolved.** This section calls the three-tier vocabulary "settled." The wiki's Forms/Functions/Dynamics survey places the practitioner three-tier taxonomy in **one cell of a much larger space** — *"flat or graph-structured token memory, holding user facts, evolving by summarization."* That is not a challenge to the tiers' usefulness, but it is a direct challenge to "settled." *(Source: `memory/memory-forms-taxonomy.md`)*

**Form also constrains governance.** Token-level memory (logs, graphs, layered summaries) is inspectable, editable, and deletable — *"those three properties are what make memory operable at all."* Parametric memory (weights, LoRA adapters) has none of them: you cannot show a user what an adapter remembers about them, and you cannot honour a deletion request by editing a weight. **That is a governance constraint, not a capability one** — and it is why nearly every deployed system is token-level. KV-cache reuse is the one latent-memory technique in wide production use, and it is used for cost rather than recall.

*(Sources: `context/memory-as-context.md`, `memory/memory-forms-taxonomy.md`)*

---

## 2. State persistence by lifetime

| Lifetime | Where it lives | What fails if this is lost |
|---|---|---|
| **In-turn** | Context window | Nothing — re-derived next turn |
| **Session** | In-memory agent state / session object | Conversation continuity; agent must re-establish context |
| **Cross-session** | Persistent store (DB, file, external service) | Long-term personalization, decisions made in prior runs |
| **Cross-agent** | Shared persistent store | Multi-agent plan state, subagent result coordination |

Design rule: **be explicit about lifetime**. Every piece of state should have a declared lifetime. Undeclared lifetime = usually forgotten on restart.

> **Conflict — flagged, not resolved.** The **In-turn** row above says losing that state costs "nothing." The wiki disagrees: *"Working memory is memory, though it is rarely stored as such. A scratchpad discarded at the end of a turn is a memory decision — the decision to forget everything about how the answer was reached, which is precisely what makes trajectory debugging hard afterward."* The wiki's resolution for the in-session case is not "keep everything": prior revisions fill a window fastest and superseded drafts are prime pruning candidates. **Keep the latest state verbatim plus a compact record of what changed and why** — *"the rejected drafts rarely matter; the reason for rejection often does."* *(Sources: `memory/memory-forms-taxonomy.md`, `context/memory-as-context.md`)*

---

## 3. Checkpointing

For long-running or multi-step agents:

- Checkpoint after each plan step completes, not only at session end.
- A checkpoint must include: plan state, completed steps, intermediate outputs needed for remaining steps, and session metadata (run ID, model version, prompt version).
- On resume, load the checkpoint and skip completed steps. Idempotency is required — re-executing a completed step from checkpoint must be safe.
- If resuming after a failure, the agent should log which step failed and why before retrying.

Checkpointing is the mechanism; retry policy is the orchestrator's responsibility (see `agent-reliability.md §2`).

**In a streaming design, the turn is the checkpoint unit.** "After each plan step" has no mid-utterance analogue — there is no step boundary between audio frames, and a checkpoint taken at frame 400 of an utterance would capture a partial ASR hypothesis that the next 200ms may revise (`agent-voice.md §3`). Checkpoint at **turn boundaries**: when the endpointer commits a turn end and the transcript finalizes. Between those points, session state is in-memory and treated as loseable, which is a deliberate trade — a mid-turn crash costs one turn, and the alternative costs the latency budget on every frame.

Two consequences follow. A checkpoint written at a turn boundary must record whether the previous turn completed or was superseded (`agent-reliability.md §3`) — resuming a session with a truncated turn recorded as complete puts words in the caller's ears that they never heard. And session metadata gains a session ID distinct from the run ID, since one call spans many turns.

**Schema constraints on the short-term store:**

- **Freeze the schema before any agent writes to it.** Retrofitting is expensive — the same rule `agent-architecture.md §4` states as "add fields, never remove or rename."
- **Compaction must write raw turns to cold storage before discarding them** — required for a GDPR audit trail. Discarding in place destroys the only record that the compaction was faithful.
- **`trace_id` on every turn is non-negotiable.**
- **Redact at assembly time, not storage time.** Sensitive data must never enter the LLM payload unredacted; redacting on the way *into* the store destroys the record you may later need to audit.

*(Source: `memory/agent-memory-types.md`)*

---

## 4. Memory write discipline

**Episodic writes:** append-only. Never rewrite episodic history.

**Semantic writes:** update-aware. Facts can be corrected; the update should carry a provenance note (when it was updated and by what).

**Procedural writes:** require explicit review. Changing a skill or instruction changes the agent's future behavior. Treat as a code change: test before deploying.

**Single-writer rule:** for each memory tier, designate one writer. Multi-writer state without locking produces corruption. If multiple agents share semantic memory, one agent (or a dedicated service) is the write authority; others are readers.

> **Conflict — flagged, not resolved.** The append-only rule above is the sharpest disagreement between this spec and the wiki. The wiki: **"A store that only appends does not have memory; it has a log."** It characterises append-only memory as *"a slow-motion failure"* whose end state is context poisoning, and its hygiene list opens with **"update over append."** The two positions are reconcilable — see the layering in "Memory lifecycle" below, where an append-only raw layer sits *underneath* a curated layer that is updated in place — but as written, §4's rule and the wiki's rule are opposites. *(Sources: `memory/memory-lifecycle.md`, `context/memory-as-context.md`)*

### Memory hygiene

Six practices, of which the wiki singles out the last two as *"what separates memory that compounds from memory that decays"*:

- **Update over append** — check whether an existing entry already covers it; revise that one.
- **Delete what proved wrong** — a memory falsified by later evidence is worse than no memory.
- **One fact per file** — granular files can be individually revised or deleted; a monolith cannot.
- **Absolute dates, never relative** — "last week," written six months ago, is now false.
- **Don't store what's derivable** — code structure, git history, and file layout are already in the repo.
- **Verify before relying** — a memory naming a file, flag, or function is a claim about a world that may have moved.

*"Memory should hold what cannot be re-derived… what the artifacts don't record — decisions, preferences, corrections, and the reasons behind them."*

### Write timing

| Path | When | Cost |
|---|---|---|
| **Hot path** | During the run, inside a node | Adds latency to the user-facing response |
| **Background** | Async task spawned after the run | No latency cost; slight delay before the memory is retrievable |

Prefer **background** for session summaries and episodic updates; use the hot path only when the memory is needed *within the same run*. Hot-path reflection adds roughly 1–2s; background reflection is the production default.

### Write the note when the decision is made

Structured note-taking: the agent writes notes to persistent storage outside the window. The discipline is about *timing*, not format — **write the note when the decision is made, not when the window fills.** *"Notes written under compaction pressure are reconstructions. Notes written in the moment are records."* It outperforms its complexity because writes are cheap and reads are selective, it makes the agent trivially compactable, it is auditable, and it doubles as crash recovery.

### Distinguish observed from inferred

**Memory is an injection surface.** Content written to memory is content that will be read back into a future prompt as *trusted* context — R4 (memory poisoning) in the security risk taxonomy. *"A poisoned entry written to long-term memory is re-injected every future session: a single hallucination becomes a permanent false belief."*

The mitigation belongs **at the memory write path**, not in a central guardrail layer — consistent with `agent-safety.md`'s risk-placement rule. The concrete write-side discipline: **mark whether each claim was observed or inferred.** *"An agent recording inference as observation poisons its own future context."*

### What triggers a procedural write

The rule above requires explicit review for procedural writes but does not say what should prompt one. The wiki gives four trigger signals — and distinguishes **self-critique** (*"is this response correct?"* — single turn, affects only this response) from **reflection** (*"what should I do differently going forward?"* — updates procedural memory, affects future turns):

1. The user explicitly corrects the agent.
2. The user ignores or overrides an agent suggestion.
3. Task execution failed (tool error, API rejection).
4. Confidence scored below threshold.

Procedural memory carries an explicit **`version`, `updated_at`, and `updated_reason`**.

> **Conflict — flagged, not resolved.** This spec says procedural writes "require explicit review… treat as a code change." The wiki describes agents **rewriting their own system prompts** automatically on these triggers, via a background optimizer. The versioning and `updated_reason` audit trail partially reconciles the two, but a human-review gate and an autonomous reflection loop are different postures. *(Sources: `memory/agent-memory-types.md`, `memory/self-learning-agents.md`)*

*(Sources: `context/memory-as-context.md`, `memory/memory-store-operations.md`, `context/context-failure-modes.md`, `memory/agent-memory-types.md`, `memory/self-learning-agents.md`)*

---

## 5. What is actively contested (write tentatively)

| Area | Status | Guidance |
|---|---|---|
| Vector vs. vector-graph hybrid backends | Contested | Do not prescribe. Note trade-offs; let the project decide. |
| Temporal reasoning (how memory ages) | Open research | No consensus. Document the need; don't implement a novel scheme without validation. |
| Cross-agent memory sync | Frontier | Orchestrator-holds-plan remains the baseline. Cross-agent shared memory is a future capability. |
| Contradiction resolution | Open research | When two episodic entries conflict, no standard resolution strategy exists. Flag for human review. |

### What the wiki has shipped against these rows

Three of the four rows above have working reference implementations in the wiki. That does not make them consensus — but "open research" is no longer an accurate description of the available evidence, and the rows should be read against it.

**Backends — including "no backend."** The table's first row assumes the choice is vector vs. vector-graph. ChatGPT's shipped design is notable for using **neither**: no vector database and no RAG retrieval enhancement. Four layers — session metadata (device, location, usage patterns; not persistent), user memory (**~33 key preference facts, injected every time**; persistent), conversation summary (**lightweight summaries of ~15 recent conversations**; persistent), and the current session's sliding window. *"~33 facts, injected unconditionally — that is a design choice against retrieval, not a limitation. At that size, selecting is more expensive and less reliable than including everything."* OpenClaw takes the hybrid route instead: append-only `memory/YYYY-MM-DD.md` logs under a curated `MEMORY.md`, searched at **70% vector similarity + 30% keyword weight**.

Better still, the wiki reframes the backend question as a **query-shape** question: *"Flat, planar, and hierarchical are not three storage formats; they are three answers to 'what relationship between memories does retrieval need to traverse?'"* Flat can only answer similarity queries; planar (graphs) can answer **connection** queries; hierarchical can answer queries at a **chosen granularity** — *"which is what a rolling summary approximates badly."* Pick the shape from the queries you need, not from the vendor.

**Temporal reasoning — a shipped scorer with published constants.** Memoria (BlackRock) uses SQLite + ChromaDB with retrieval scored by exponential decay: `wᵢ = e^(−α·xᵢ)`, **α = 0.02**, `xᵢ` = age in **minutes**, **min-max normalized first** (`x_norm = (x − x_min)/(x_max − x_min)`), then renormalized to sum to 1, **top_k = 20**. Because normalisation comes first, α does not encode a fixed half-life — it encodes *how sharply the newest candidates outrank the oldest*, whatever the span. Normalisation also stops very old entries underflowing to zero and dropping out entirely. Reported effect: **~400 average tokens retrieved per turn versus 115K for full-context** — roughly a 99.7% reduction.

> **Conflict — flagged, not resolved.** The row above says "don't implement a novel scheme without validation." That caution still holds; the point is that this scheme is no longer novel to the reader. One implementation is not consensus, but the guidance now has a working reference to be read against.

**Contradiction resolution — decay substitutes for detection.** Decay sidesteps contradiction detection entirely: *"Both 'user is vegetarian' (day 200) and 'user eats meat' (day 3) stay in the store. The recent one outranks the old one **without anything having to notice they conflict**."*

- **Bought:** no contradiction-detection step, no destructive writes, complete history retained.
- **Paid:** stable facts decay at the same rate as volatile ones — *"a preference stated once, two years ago, and never contradicted will eventually rank below noise."*
- **Usual fix:** two tiers — a small always-injected profile for durable facts (the ~33-fact layer) with decay applied only to the episodic store beneath.

**"Decay is the right scorer for events; it is the wrong scorer for identity."** The decision criterion: reach for decay when memories are **time-stamped observations** whose relevance genuinely fades (conversation history, project state, incident context). Prefer explicit conflict resolution when memories are **assertions about durable facts**, where *"most recent" and "most correct" are not the same thing.* Operationally the wiki's fallback is: recent supersedes older, or higher-confidence source wins.

> **Conflict — flagged, not resolved.** The row above says to flag conflicts for human review. Decay-by-ranking is a shipped alternative that resolves them without ever detecting them.

**One constraint that survives backend-agnosticism.** Periodic embedding-model refresh is a trap: *"re-embedding under a new model means the vector store contains two incompatible geometries until backfill completes, and similarity scores across the boundary are meaningless rather than merely degraded."* Embedding migrations are **full reindexes** — worst-case for a store that has accumulated for a year. That argues for **keeping the raw text authoritative and the vectors derived**, which is a constraint on *any* vector backend rather than a choice between them.

*(Sources: `memory/memory-lifecycle.md`, `memory/memory-decay-weighting.md`, `memory/memory-forms-taxonomy.md`, `memory/memory-store-operations.md`)*

---

## 5a. The memory lifecycle

The sections above govern taxonomy and writes. The wiki organises the same material as **five stages**, and singles out the last one:

| Stage | What happens |
|---|---|
| **A — Capture** | Raw turns and events land in a store |
| **B — Formation** | Structure is imposed: summarisation, distillation, triplet extraction |
| **C — Retrieval** | Entries are selected and injected |
| **D — Use** | The agent acts on them |
| **E — Maintenance** | Consolidation, pruning, correction, deletion |

> **"Stage E is the one that decides whether the system still works in month six."**

Stages A–D are what gets built; E is what gets skipped, and skipping it is what turns a working memory into the append-only failure flagged in §4.

**Formation is a cost transfer.** The formation mechanisms — raw logging, semantic summarisation, knowledge distillation, structured construction, latent representation, parametric internalisation — are ordered by **how much structure is imposed at write time**, and that ordering is a trade: *structure at write time is retrieval precision bought with write-time LLM calls.* Triplet extraction sits in the middle; raw logging sits at the free end.

**Consolidation must be rollback-friendly.** The rule that reconciles §4's append-only instinct with the wiki's "update over append": **move the pointer, don't delete the original.** The failed path writes original messages to `archive/`, so a botched consolidation can return to the archive and continue. The reason generalises: **compression is lossy and its loss is discovered later, at read time.** A summariser that drops the one fact you needed raises no error at write time; the only defence is keeping the pre-compression form recoverable. The same rule recurs at three layers — compaction writing raw turns to cold storage (§3), entity resolution being reversible, consolidation keeping originals.

**But consolidation also makes erasure hard.** *"Deletion support is the requirement that constrains architecture rather than merely adding a feature."* A right-to-erasure request must reach every representation: the structured store, the vector index, derived session summaries, and **any consolidated memory that merged this user's facts with others**. *"Once 'user is allergic to dairy' has been merged into a summary, deleting the source message does not delete the fact."* That is a direct argument against aggressive consolidation and in favour of keeping memories traceable to their originating turn.

> The two consolidation rules point the same way — traceability — but they are separate arguments: one is a correctness constraint, the other a compliance one. A design that satisfies rollback may still fail erasure.

**Erasure is an obligation, not an implementation detail.** The framing above treats deletion support as an architectural constraint, which understates it: under GDPR Art. 17 a data subject can compel it, on a deadline, whether or not the architecture makes it convenient. "Deletion support constrains architecture" is the engineering consequence; the obligation is the cause. Legal basis and the special-category rules live in `agent-safety.md §7a` — not restated here.

**In a voice design the erasure scope is wider than text, and it is three artifacts:**

| Artifact | Why it is in scope separately |
|---|---|
| **Audio** | The recording is special-category data on its own — a voice identifies its speaker regardless of the words. Redacting the transcript does not touch it. |
| **Transcript** | Ordinary personal data, in the usual stores plus the trace backend. |
| **Derived context** | Summaries, extracted entities, embeddings, and any consolidated memory built from the call — the merged-fact problem above, which survives deletion of both the audio and the transcript. |

Deleting one or two of the three is the common failure, and it is silent: the request is marked satisfied while the fact remains recoverable. A voice design should be able to answer "where does audio for a given session live, and what deletes it" before it takes its first call — audio tends to accumulate in places the erasure path never learned about, such as the trace backend (`agent-observability.md §6`) and the telephony provider's own recording store.

Also required at this layer: RBAC/ABAC on memory endpoints governing both read *and* modify; AES-256 at rest and TLS in transit.

*(Sources: `memory/memory-lifecycle.md`, `memory/memory-forms-taxonomy.md`, `memory/memory-store-operations.md`)*

---

## 5b. Running a memory store

*"A memory store is a database that sits inside the latency budget of every single request."*

Retrieval happens before generation, so its latency is **fully additive to time-to-first-token** — unlike most infrastructure, there is no path where it is hidden.

- **Asynchronous vector index updates are an explicit consistency trade.** A memory written this turn may not be retrievable next turn. Acceptable for episodic accumulation; **not acceptable for a just-stated user correction** — and that is precisely the case a user notices. The resolution is a synchronous write to the structured store with the summary read back **directly by ID** rather than by search (Memoria's summary retrieval is *"deterministic — just a direct session ID lookup"*).
- **Auto-scale on write volume, not just reads.** Every turn produces both, and the write path is expensive when it includes LLM calls: *"a memory store under load is doing inference, not just I/O."*
- **Automated maintenance:** scheduled pruning of stale entries, and **differential storage** (store deltas rather than full snapshots) to limit bloat.

**Three recurring operational failures:**

| Failure | Mitigation |
|---|---|
| Memory overload | Summarise, or score by relevance, to keep injected memory concise |
| Stale context | TTL and decay policies; **archive rather than delete**, retaining version history |
| Conflicting information | Recent supersedes older, or higher-confidence source wins (see §5) |

**Log the query alongside the entries it used.** The logging requirement is stronger than for ordinary retrieval, and the reason is diagnostic: *"when an agent says something wrong about a user, the question is whether it hallucinated or faithfully repeated a bad memory, and those have opposite fixes."* Trace end-to-end, including the memory lookup span (see `agent-observability.md`).

*(Sources: `memory/memory-store-operations.md`, `memory/memory-decay-weighting.md`)*

---

## 5c. Is the memory earning its cost?

Three metrics, of which one is load-bearing:

- **Memory hit rate** — the ratio of queries that actually leverage a relevant entry.
- **Latency breakdown** — retrieval vs. reasoning fusion vs. generation.
- **Update frequency.**

> **"Memory hit rate is the load-bearing metric and the one nobody instruments."**

A low-hit-rate memory system is pure cost — latency, spend, and context budget for nothing. And the failure is invisible from outside: *"you cannot distinguish a memory system that is working from one that is retrieving diligently and contributing nothing, because both look identical from the outside."*

Hit rate is not mechanically decidable — *retrieved* is countable, but *leveraged* requires attribution or a judge. **The tractable proxy is an ablation:** run the eval set with memory disabled and compare. **If the delta is small, the store is decorative.** This is the memory-side instance of the gate requirement in `agent-eval.md §8`.

*(Source: `memory/memory-store-operations.md`)*

---

## 6. Memory vs. context

Memory is not context. Context is the current window — loaded, used, compacted. Memory is the store the context is loaded from. The read path is:

```
memory store → select/retrieve relevant entries → load into context window → use → [optionally write new entries back to store]
```

Never conflate "store it in memory" with "keep it in context". Context is cheap per-turn but expensive if over-filled. Memory is persistent but requires explicit retrieval.

### The read path is four decisions, not one arrow

The diagram above collapses `select/retrieve` into a single step. The wiki decomposes it, and the ordering of importance is counter-intuitive:

| Decision | Question |
|---|---|
| **Timing** | When to retrieve — at session start, on demand, or continuously |
| **Query construction** | What to ask the store |
| **Strategy** | Sparse, dense, graph, or hybrid |
| **Post-retrieval processing** | Reranking, filtering, compression *before* injection |

> *"Only strategy gets significant engineering attention, and it is arguably the least important of the four. **Timing** is the one that determines whether memory helps or hurts — **retrieving every turn is the default and is actively harmful.**"*

Post-retrieval processing is the augmentation gate — the last point at which a bad entry can be stopped before it becomes trusted context.

> **Note — two wiki pages disagree, and this spec takes no position.** `memory/agent-memory-types.md` shows a `load_memory_node` that loads **all three tiers at the start of every turn** before routing. `memory/memory-forms-taxonomy.md` says retrieving every turn is actively harmful. Both are in the wiki; the disagreement is upstream of this spec.

**Never load the full store — load an index, fetch detail on demand.** Claude Code's auto-memory is exactly this shape: `MEMORY.md` (**first 200 lines / 25 KB**) loads at session start, and topic files are read only when a hook line signals relevance. Which makes the one-line hook the highest-leverage text in the system — *it is the only thing deciding whether the detail ever loads*. And so:

> *"A vague hook makes a correct memory unreachable — the memory is present and useless, which is worse than absent, because it creates false confidence that the fact is available."*

*(Sources: `memory/memory-forms-taxonomy.md`, `context/memory-as-context.md`, `memory/agent-memory-types.md`)*

---

## 7. Scoping note

This spec sits beside `agent-context.md` as a peer. The wiki does not organise it that way: `context/context-engineering.md` and `context/memory-as-context.md` treat **memory and tool design as sub-components of the context and harness layers rather than sibling pillars.** Recorded as a framing disagreement, not resolved here — the peer structure is this repo's choice and `DESIGN-PROCESS.md`'s five-layer stack is what it answers to.

---

## Sources

- Topic 5.3 from `2026-07-19-research-B-topic-canon.md`
- Research B emerging/settled table (taxonomy = settled; backends = contested)
- `.claude/skills/langgraph-persistence/SKILL.md` (mechanism)
- `new-agent/references/core.md` (`memory.py` patterns)
- `memory/memory-lifecycle.md` — the five stages; rollback-friendly consolidation; ChatGPT and OpenClaw designs
- `memory/memory-forms-taxonomy.md` — Forms/Functions/Dynamics; the four retrieval decisions; working memory
- `memory/memory-store-operations.md` — hit rate and the ablation proxy; operations; deletion
- `memory/memory-decay-weighting.md` — exponential decay scorer; decay vs. conflict resolution
- `memory/agent-memory-types.md` — write timing; schema constraints; reflection triggers
- `memory/self-learning-agents.md` — reflection vs. self-critique; the self-improvement stack
- `context/memory-as-context.md` — memory hygiene; index-plus-detail; episodic→semantic distillation
- `context/context-failure-modes.md` — memory poisoning
- `context/context-engineering.md` — the sub-component framing
