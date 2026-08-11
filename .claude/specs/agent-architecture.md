# Agent Architecture — Conventions

**Durable question:** When does the agent decide vs. the harness decide? What loop shape fits this task, and how are subagents coordinated?

*Tooling-agnostic. For LangGraph-specific binding see `langgraph.md`.*

---

## 0. Orchestration levels

Loop shape is a choice *within* a level. The coarser question is which level of control you are buying. The wiki orders four, and the ordering is an escalation path: each level's limits are the next one's entry condition.

| Level | What decides control flow | Entry condition (from the level below) |
|---|---|---|
| 1 — Single prompt | Nothing; one call | — |
| 2 — Single agent + tools | The LLM | "a single prompt that needs to act becomes an agent with tools" |
| 3 — Multi-step graph | You, in code | "an agent whose tool order needs controlling becomes a graph" |
| 4 — Multi-agent | Agents delegate to agents | "a graph whose quality suffers across distinct modes of thinking becomes multi-agent" |

§1's three loop shapes are a level-2/level-3 choice, not a description of the whole space.

**The clearest escalation trigger is behavioural, not architectural:**

> *"Start with a single agent. If you find yourself writing 'if the tool result shows X, then call tool Y' — that's a graph wanting to exist. Refactor into LangGraph then, not before."*

Control logic accumulating in your own code *around* the loop already **is** the graph — implicit, and without checkpointing. *(Sources: `patterns/agent-orchestration-patterns.md`, `patterns/multi-step-graph-orchestration.md`)*

### Five signals that justify adding a node

*"A loop is a graph with one node and an edge back to itself"* — so a graph is a cost you justify, not a maturity level you graduate to. Each signal names something a single loop **structurally cannot do**:

1. Distinct specialties needing different instructions, context, or tools.
2. Parallel fan-out with a join.
3. Per-step model or tool variation.
4. Auditable control flow for regulated work.
5. An overloaded verifier judging several criteria at once.

**Yes to any → add a node. No to all → strengthen the verifier and ship the loop.**

The most common false positive is signal 5: *"the most common 'we need a graph' is really an overloaded verifier, and splitting the verifier is far cheaper than splitting the system."* Try the loop answer (a narrower rubric) before the graph answer (a dedicated reviewer node). *(Source: `graph/loop-to-graph-escalation.md`)*

### When *not* to build a graph

The counterweight: generic deep research *"requires planning and delegation in ways that are hard to pin down ahead of time,"* and forcing agentic tasks *"into deterministic paths is the wrong move."* The operational test — **if you cannot name every node before the run starts, you want a harness with a good loop, not a graph.** *(Source: `graph/graph-engineering.md`)*

### Production agents are cyclic

*"Production agents need cycles: retrying failed tool calls, asking users for missing information, revising answers after validation, calling tools repeatedly until they have enough context."* The DAG mental model imported from data engineering breaks here — anything that forbids cycles is a workflow engine, not an agent framework. *(Source: `graph/graph-engineering.md`)*

### Workflow patterns

The wiki also carries Anthropic's five composable workflow patterns, which cut the space at a different altitude than §1's loop shapes. Workflow = *"LLMs and tools orchestrated through predefined code paths"*; Agent = *"LLM dynamically directs its own processes and tool usage."*

| Pattern | Shape |
|---|---|
| **Prompt chaining** | Sequential calls with programmatic gate checks between them |
| **Routing** | Classifier → specialized downstream handler (easy → Haiku, hard → Sonnet) |
| **Parallelization** | *Sectioning* (independent subtasks) or *voting* (same task run several times) |
| **Orchestrator-workers** | Subtasks determined dynamically from input, not pre-defined |
| **Evaluator-optimizer** | Two fit signals: responses improve with feedback, and an LLM can supply that feedback |

> **Naming caution.** These five and §1's three loop shapes are two taxonomies at different altitudes, not one list. Roughly, "Plan-then-Act" ≈ prompt chaining. Do not read them as competing names for the same thing. *(Source: `patterns/agentic-workflow-patterns.md`)*

---

## 1. Loop shapes

Three shapes cover nearly all cases. Pick the simplest one that fits.

| Shape | Pattern | Use when |
|---|---|---|
| **ReAct** | Observe → Reason → Act, repeat | Single-step uncertain tasks; model drives next-action |
| **Plan-then-Act** | Fixed plan → sequential execution | Deterministic multi-step tasks; plan is stable |
| **Plan-and-Revise** | Plan → Act → assess → replan | Long-horizon tasks; environment may change mid-run |

**Prefer ReAct for short tasks** (≤10 steps); prefer Plan-and-Revise when environment feedback materially changes what step N+1 should do. Plan-then-Act is correct when the plan is known at the start and no mid-run branching is needed.

> **Conflict — flagged, not resolved.** This section says *"prefer ReAct for short tasks (≤10 steps)."* Three wiki pages cluster an order of magnitude lower. `patterns/react-pattern.md` places ReAct's sweet spot at **1–3 tool calls per turn** on well-defined atomic, low-stakes tasks, and says it breaks down at **5+ tool calls in sequence where ordering matters** — specifically when partial failure mid-sequence leaves inconsistent state (*invoice created but email not sent*), or when the model needs to plan and verify each step before executing. `adk/plan-and-execute-pattern.md` independently says *"ReAct is fine for 1-2 tool calls"* and names 5+ API calls as where ReAct "can go off-script mid-sequence." Whether ≤10 is defensible here is a repo-local judgement; the wiki does not support it. *(Sources: `patterns/react-pattern.md`, `adk/plan-and-execute-pattern.md`)*

Dynamic fan-out to many parallel subagents is frontier; do not default to it. The dominant baseline is orchestrator-holds-plan + isolated-window subagents.

> **Conflict — flagged, not resolved.** The wiki presents **orchestrator-workers** — *"topographically similar to Plan and Execute but with dynamic rather than pre-planned subtask creation"* — as an established Anthropic pattern with a stated use-when: task requirements that cannot be predicted in advance (multi-file code changes, open-ended research). "Frontier" and "established pattern with a use-when" are not strictly contradictory, and *dynamic* is not the same claim as *many parallel*, but a reader will feel the tension. *(Source: `patterns/agentic-workflow-patterns.md`)*

---

## 2. What terminates a turn

A turn ends when the model emits a **stop_reason** that is not a tool call. The harness controls what happens next:

- `end_turn` / `stop` — return to caller, no further invocations.
- `tool_use` / `function_call` — execute tools, re-invoke model with results.
- `max_tokens` — truncation; must be treated as an error, not a completion.
- Context-window budget exhausted — harness must compact before re-invoking (see `agent-context.md`).

> **Streaming variant.** The above assumes a turn that ends with a protocol event. In a duplex audio stream there is no `stop_reason` — turn end is *inferred* by an endpointer on the audio stream, which is a probabilistic judgement rather than a protocol event, and can be wrong in both directions (cutting the user off, or waiting through a pause they meant as a comma). See `agent-voice.md §3`. The iteration-cap rule below still applies unchanged; note only that a streaming design also needs a *session*-level cap — turns per session, wall-clock, spend — which the per-turn cap does not provide.

The harness (not the model) decides the **maximum iteration count**. Always set one.

### At what granularity

The wiki bounds **per node, not per graph**: n8n caps Discovery at **50** iterations and Builder at **100** per session, independently. Per-node bounds localize the blast radius of a stuck node instead of letting one node consume the whole run's budget. A single graph-wide cap cannot tell you *which* node ran away. *(Source: `graph/graph-topology-primitives.md`)*

### Pausing needs somewhere to put the stack

Human-in-the-loop is a **first-class graph primitive, not a UI feature** — it requires stateful persistence across the pause, *"a capability loops alone cannot provide, because a loop that pauses has nowhere to put its stack."* That is the sharpest argument for graph-over-loop when approval is required mid-execution.

A checkpointer delivers three things from one mechanism: mid-run interrupts, resume-after-crash, and time-travel debugging. `agent-memory.md §3` treats checkpointing purely as failure recovery; the interrupt capability is the same machinery. *(Sources: `graph/graph-topology-primitives.md`, `graph/graph-engineering.md`)*

---

## 3. Planning

### Plan-up-front vs. ReAct

The choice is architectural, not stylistic:

- If the task decomposes cleanly before execution starts, represent the plan as data (list of steps, each with inputs/outputs).
- If the task requires information that can only be obtained by executing earlier steps, use ReAct.
- Hybrid: generate a plan, execute it, allow the model to mark individual steps as "needs replan" rather than replanning from scratch.

### Who holds the plan

When subagents are involved, the orchestrator holds the plan as shared state. Subagents receive a task slice, not the full plan. This preserves context-window isolation and avoids subagents making planning decisions that belong to the orchestrator.

### Plan-and-Execute has four roles and a replan cap

The wiki's concrete binding of the abstract Plan-and-Revise shape, with model tiering stated:

| Role | Tier | Job |
|---|---|---|
| **Planner** | Sonnet | Full task + available tools → step list |
| **Executor** | Haiku | One step at a time; mechanical execution of a pre-approved plan |
| **Replanner** | Haiku | After each step, check the plan still makes sense — **max 3 replanning rounds** |
| **Responder** | Sonnet | Synthesize the final answer |

Two structural details: the step schema carries `depends_on: list[str]`, so dependency-free steps fan out in parallel without a separate parallelism decision; and the HITL confirmation gate sits **after the planner, before the executor** — approving a plan is cheap, approving 40 executed steps is not.

The **max 3 replanning rounds** cap is a number this spec lacks — §2 says "always set a maximum iteration count" but never bounds *replanning* specifically, which is the loop most likely to churn without visibly failing. *(Source: `adk/plan-and-execute-pattern.md`)*

### Start at 3–5 nodes

For a first graph, pick a job that splits naturally into a produce step and an independent check step — draft-then-review, research-then-write, build-then-test. *"The separation is what creates the value; the parallelism is a bonus."* The wiki's adoption sequence: AUDIT → IDENTIFY → DESIGN (**start at 3–5 nodes**) → IMPLEMENT (measure a baseline before optimizing) → TYPE.

> *"A 3–5 node graph with one honest verification step beats a twelve-node topology whose failure modes you can't reason about."*

*(Source: `graph/graph-engineering.md`)*

---

## 4. Schema contracts

Every agent has an **invocation contract**:

```
Request schema:  what the caller must supply (session_id, query, context)
Response schema: what the agent always returns (answer, sources, confidence, metadata)
Error schema:    what a failed turn returns (error_code, message, is_fatal)
```

The request and response schemas are the public API. Once used in production, changing them is a breaking change — apply `/sanyi` change contracts before modifying. See `agent-context.md §3` for prompt versioning, which is part of the same contract.

Schema evolution rule: **add fields, never remove or rename** until all callers have migrated.

### The subagent-return schema

The contract above is per-*agent* and public-facing. A second contract governs what crosses an agent boundary internally. Four rules:

1. **Structured, not prose.** A typed schema — findings, files touched, confidence, open questions — beats a paragraph.
2. **Summaries, never transcripts.** Sending a subagent's full history back defeats the firewall that justified the subagent (see §5).
3. **State on disk, references in the message.** Large artifacts go to files; the handoff carries paths.
4. **Declare what was *not* done.** Scoped claims prevent the orchestrator assuming coverage that does not exist.

Rule 4 is the sharpest and is entirely absent from this spec today: an orchestrator that cannot distinguish "checked and clean" from "did not check" will treat the second as the first. That is the §6 collapse-site rule applied to handoffs. *(Source: `harness/harness-orchestration.md`)*

### Validate at the node boundary

ADK 2.0 validates inputs and outputs at node boundaries with Pydantic schemas, *"so key errors surface at the boundary rather than three nodes downstream"* — *"the contract between agents is enforced, not documented."* This is the enforcement ladder (`DESIGN-PROCESS.md §3`) applied to inter-agent contracts: a schema checked at the seam is a tool-schema-tier control, while the same contract in a system prompt is an instruction-tier one.

Related: nodes return `Event` objects carrying routing instructions, and the engine evaluates the matching edge — **a node states its outcome and the graph decides what that means**, so rewiring the workflow does not touch node code. Compiled workflows are first-class nodes, which is how subgraph composition works. *(Source: `harness/harness-orchestration.md`)*

---

## 5. Multi-agent orchestration

### When to use a subagent

A subagent is worth the isolation cost when:
- The subtask has a meaningfully different tool set or system prompt.
- Context isolation matters (subagent sees only its slice; orchestrator sees plan state).
- The subtask is parallelizable and independent.
- Failure in the subtask should be catchable and retryable independently.

Do not spin up a subagent to avoid writing a tool.

**On "parallelizable and independent" —** one question decides it: **does the next step actually read the previous step's output?** If not, the serialization is incidental and belongs in a fan-out. *"Most 'sequential' pipelines contain more incidental serialization than their authors assume."* *(Source: `graph/loop-to-graph-escalation.md`)*

**The named baseline is "single agent *with verification*", not "single agent."** The wiki's cost-ordered ladder: **single agent with verification → two-agent supervisor → multi-agent with a shared harness layer.** Four permitted reasons to escalate, roughly in strength order:

1. **Context genuinely doesn't fit** — the firewall argument, and the strongest of the four.
2. **Roles need different tools or trust levels.**
3. **Self-evaluation bias is the blocker.**
4. **Branches are genuinely independent.**

This overlaps the four bullets above rather than extending them; the additions are the verification baseline and the cost ordering. *(Source: `harness/harness-orchestration.md`)*

### Disqualifiers

The sharpest one: *"the 'roles' are just different prompts for the same task."* Naming a prompt "Researcher" does not make it a specialist — *"a critic that only reruns the writer's prompt with harsher wording is one agent wearing two hats, and pays multi-agent cost for single-agent capability."* The wiki also advises against multi-agent when the team is **under four engineers** or the system has fewer than **5+ distinct responsibilities**. *(Source: `patterns/multi-agent-role-specialization.md`)*

> **Tension worth noting.** This disqualifier sits against the prompt-only-specialization default below. They reconcile — the default is about *nodes in a graph you have already decided to build*; the disqualifier is about *whether to build multi-agent at all* — but read side by side they will look contradictory.

### The cost of escalating

Graphs cost roughly **3× the tokens per cycle** versus a loop, and break even around a **~50% per-cycle pass rate**; below that you are paying fan-out cost for work that will be redone. Anthropic's own multi-agent research system runs at *"roughly 15× the tokens of a chat turn."* *(Sources: `graph/graph-engineering.md`, `graph/loop-to-graph-escalation.md`)*

### How to cut the work

This section says *when* to use a subagent but never *along what axis*. The wiki names four, and *"each pattern is a bet about where the dependencies aren't."*

| Axis | Cut by | Sharpest cost |
|---|---|---|
| **Functional** | Kind of work | The default, because it maps to org charts — and it carries maximum handoff traffic per unit of work |
| **Spatial** | File or directory | Breaks when files have cross-dependencies |
| **Temporal** | Sequential stages | Deliberately does *not* parallelize; its value is the gate between stages |
| **Data-driven** | Partition | Cleanest parallelism; the hidden cost is the aggregation barrier |

**Diagnostic:** *"what would two agents on this axis need to tell each other?"* — "nothing" means the axis is real.

**The spatial slice test:** an agent must be able to complete its slice **without reading outside it**. *"If it can't, the slice isn't a slice."* A rename crossing module boundaries is not a spatial task no matter how many files it touches. *(Source: `harness/task-decomposition-patterns.md`)*

### Role separation

Cheapest first:

| Pattern | Shape | Fixes |
|---|---|---|
| **Explorer / Executor** | Explorer: read-only tools, cheaper model, isolated disposable context. Executor: full tools, stronger model, holds the plan | Exploration debris polluting the executing window |
| **Planner / Executor** | Plan approved, then executed step-wise | *"the agent got lost in a 40-step task"* |
| **Generator / Evaluator** | Separate agent judges the output | Self-evaluation bias, structurally |

> *"Constraining the tool set per role is the point — the explorer physically cannot mutate anything. That is a grant, not a label."*

Which is the enforcement ladder again: a role enforced by a tool grant is a different object from a role asserted in a prompt. *(Source: `harness/harness-orchestration.md`)*

### Multi-agent failure modes

Four named failures, each with a distinct mechanism and mitigation. *"All four are harness bugs. None is fixed by a better model"* — and all four get worse as agent count rises.

| Failure | Mechanism | Mitigation |
|---|---|---|
| **Loop oscillation** | Two nodes bounce work between them indefinitely | Iteration counters on cyclic edges; forced escalation |
| **Context pollution** | Nested workflows leak state upward, defeating isolation | Explicit boundary schemas; return summaries only |
| **Concurrency collision** | Parallel branches write the same state key or file | Join barriers; per-branch ownership of state keys |
| **Consensus deadlock** | Reviewer agents never agree | A tie-break rule, majority threshold, or final arbiter |

This is the architecture-side analogue of the five context failure modes in `agent-context.md §7`. *(Source: `harness/harness-orchestration.md`)*

### Protocols precede parallelism

*"Establish a task graph and isolation boundaries before introducing parallelism."* Parallelism added to an undefined task structure produces **collision, not speed**. Define what each agent owns, receives, returns, and may touch — then parallelize. *(Source: `harness/harness-orchestration.md`)*

### Orchestrator responsibilities

- Maintain the plan and overall state.
- Dispatch subtasks with scoped context, not the full conversation.
- Handle subagent failure — retry policy lives in the orchestrator, not the subagent.
- Assemble and validate subagent outputs before proceeding.

### Agency is budgeted per node

*"Nodes do work. A node can be deterministic code, a single LLM call, a tool call, or a full agent with its own internal loop."* The design skill is deciding **per node how much agency to spend** — *"every node that could be deterministic code and isn't is a node you pay tokens and variance for."*

Specialization should be **prompt-only by default**: n8n runs every node on the same model at temperature 0, differentiating roles entirely by system prompt. A separate model per node is an optimization to justify, not a starting point. The subagent criterion above — "meaningfully different tool set or system prompt" — is consistent with this but does not state the default. *(Source: `graph/graph-topology-primitives.md`)*

### Named topology patterns

| Pattern | Shape |
|---|---|
| **Supervisor** | The settled baseline for most multi-agent work |
| **Parallel fan-out / fan-in** | Wins wall-clock, costs tokens |
| **Hierarchical team-of-teams** | A subgraph is itself a node |
| **Handoff protocol** | An agent signals completion by writing a designated state key; the conditional edge reads that key to pick the next agent — *"keeps coupling in state, not code"* |
| **Parallel review** | Planner → worker → three reviewers in parallel → synthesizer → gate; reported ~3× faster wall-clock than sequential |

The handoff-protocol row is really a state-design rule and belongs read alongside §7. *(Source: `graph/graph-engineering.md`)*

### Trust boundaries

When an agent calls across a trust boundary (different service, external agent), it is no longer just an orchestrator — it is a caller of an A2A interface. See `.claude/skills/new-agent/references/cap-a2a.md` for the protocol contract. Never pass raw user input to a cross-trust-boundary agent without sanitization (see `agent-safety.md §2`).

---

## 6. Uncertainty is an architectural concern

Loop shape and subagent topology decide *how* work flows; they do not decide what the system does when a step does not know. That is `agent-uncertainty.md`, and two of its rules constrain the choices in this spec directly:

- **A step that returns the same thing on empty input as on success is a collapse site.** This bears on §5's orchestrator responsibilities: a subagent that fails to dispatch must be distinguishable from one that ran and found nothing. Merging them means a broken node reads as a clean one.
- **Rank by blast radius, not confidence.** Where the orchestrator triages subagent output, consequence is the sort key — not how certain the reporter was.

---

## 6a. Duplex designs are a different loop shape

Everything above assumes a turn that ends (§2). When audio — or any stream — flows both directions concurrently, that assumption fails at the loop layer, and the five-layer stack reads `prompt ⊂ context ⊂ harness`, then **streaming loop**, then graph. `design-system` §4b names the same variant and lists its five required components; `agent-voice.md` is the depth.

The test for which applies: **can you point at the protocol event that ends a turn?** If yes, this spec's §2 governs. If turn end is inferred from the stream rather than signalled by it, the design is duplex — read `agent-voice.md`, and treat §2's guidance as inapplicable rather than merely stricter.

---

## 7. State vs. context

| Location | What lives there | Lifetime |
|---|---|---|
| Context window | Current reasoning, tool results, conversation | This turn |
| Agent state (memory) | Decisions made, plan progress, session data | Session / process |
| Persistent store | Long-lived facts, checkpoints | Cross-session |

State that must survive a process restart belongs in a persistent store, not in-memory. See `agent-memory.md` for the full taxonomy.

### Reducers are the concurrency primitive

> *"Reducers are the concurrency primitive. Without one, parallel fan-out into a single key is a race."*

Designate **one writer per key**, or use a reducer that makes multi-writer merging explicit. n8n enforces the same rule for concurrent edits with optimistic locking (`versionId` + `expectedChecksum`) — *"the single-writer rule enforced by compare-and-swap instead of by convention."*

This generalizes `agent-memory.md §4`'s single-writer rule from *memory tiers* to *state keys*, and adds compare-and-swap as the enforcement option where convention is not enough. *(Source: `graph/graph-topology-primitives.md`)*

---

## 8. Failure at scale

A control-theory reading of why **independent loops degrade as their number rises** — four structural failure modes:

| Mode | What happens |
|---|---|
| **Goodhart's Law** | Metrics detach from meaning under optimization pressure |
| **Upward blindness** | A loop cannot question its own targets |
| **Inter-loop conflict** | Loops fight over shared resources, unaware of each other |
| **Measurement decay** | Sensors drift while loops keep running on stale data |

Governance answers: **paired metrics** (every optimization metric gets a counter-metric and an anchor metric), **owned references** (targets are owned by slower loops), **separated cadences** (fast loops *escalate* rather than override), and **frozen nodes**.

The load-bearing idea is the anchor — *"external fixed nodes the internal machinery is forbidden to rewrite"*:

> *"An anchor made tunable is an anchor that will eventually be tuned."*

This is the same shape as `agent-eval.md §8`'s rule that the evaluator must sit outside the agent's write boundary, and the same shape as `/sanyi`'s 不易 (invariant) layer, which this repo already runs. Three statements of one constraint at three altitudes. *(Source: `graph/graph-engineering.md`)*

---

## Sources

- Topics 5.1, 5.6, 5.8, 5.10 from `2026-07-19-research-B-topic-canon.md`
- `new-agent/references/core.md`, `framework-lg.md`, `framework-adk.md`
- `patterns/agent-orchestration-patterns.md` — the four orchestration levels as an escalation path
- `patterns/multi-step-graph-orchestration.md` — the "if X then call Y" refactor trigger
- `graph/loop-to-graph-escalation.md` — five signals; the overloaded-verifier false positive; the true-dependency test
- `graph/graph-engineering.md` — cyclic vs DAG; break-even economics; 3–5 node start; topology patterns; failure at scale and anchors
- `graph/graph-topology-primitives.md` — per-node iteration bounds; per-node agency budget; checkpointers; reducers and single-writer
- `harness/harness-orchestration.md` — escalation ladder; handoff rules; role separation; the four multi-agent failure modes; boundary validation
- `harness/task-decomposition-patterns.md` — the four decomposition axes; the spatial slice test
- `patterns/agentic-workflow-patterns.md` — Anthropic's five workflow patterns; orchestrator-workers
- `patterns/multi-agent-role-specialization.md` — the "just different prompts" disqualifier
- `patterns/react-pattern.md`, `adk/plan-and-execute-pattern.md` — ReAct thresholds; Plan-and-Execute roles and the replan cap
