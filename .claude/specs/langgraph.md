# LangGraph — Framework Binding

> Read these convention refs first, then the bindings below:
> - `agent-architecture.md` — loop design, state schema, multi-agent orchestration
> - `agent-context.md` — context window management, compaction, prompt versioning
> - `agent-memory.md` — memory tiers, checkpointing strategy
> - `agent-observability.md` — span schema, cost attribution
> - `agent-safety.md` — five-layer guardrails, injection defense
> - `agent-reliability.md` — retries, idempotency, resumability
> - `agent-eval.md` — grader-interface contract, golden-dataset curation

*LangGraph is the production-grade choice for auditable, stateful agents. ADK for quick POCs.*

---

## When to use

LangGraph for **production** agent systems — empirically chosen for auditability (explicit state graph, checkpointing, traceable transitions). ADK for quick POCs.

---

## Binding table — convention ref → LangGraph surface

| Convention concern | Convention ref | LangGraph surface |
|---|---|---|
| Agent loop / state machine | `agent-architecture.md §1` | `StateGraph` with typed state; nodes return state deltas |
| State schema | `agent-architecture.md §3` | Pydantic v2 model or `TypedDict` — never a raw dict |
| Conditional routing | `agent-architecture.md §4` | `add_conditional_edges`; topology tells the story, not embedded if/else |
| Multi-agent orchestration | `agent-architecture.md §5` | Subgraphs for in-process; LangGraph Platform assistant API for cross-process |
| Checkpointing / persistence | `agent-memory.md §2` | `MemorySaver` (dev) → Postgres/Redis checkpointer (prod); configured explicitly |
| Long-term memory | `agent-memory.md §3` | `langmem` / store API scoped by user id; summarize, don't replay |
| Context compaction | `agent-context.md §3` | Compaction node between phases; `clear_tool_uses` / `clear_thinking` for Anthropic |
| Observability | `agent-observability.md §1` | `structlog` at node entry/exit: `graph.<node>.start` / `.done` with structured fields |
| Eval | `agent-eval.md §2` | Every production graph gets a golden-dataset harness before conclusions are drawn |
| Safety | `agent-safety.md §1` | Five-layer model applied as pre/post-node middleware |

---

## LangGraph-specific rules

- **Nodes are pure-ish functions**: read state in, return state delta out; side effects (DB writes, API calls) live in tools, not node bodies.
- **Explicit conditional edges over embedded routing**: `add_conditional_edges` so the graph topology documents the flow.
- **Name nodes/edges functionally**: what they do (`grade_passages`, `rewrite_query`), not what they are (`node_1`, `router`).
- **No unbounded loops**: always set a recursion/step limit on cyclic graphs.
- **No mixing framework state with app state**: the `StateGraph` state model is the boundary; application models are separate.
- **No silent in-memory checkpointer in production**: `MemorySaver` is dev-only; configure a durable checkpointer explicitly.

---

## Capabilities that have LangGraph-specific notes

| Capability | Note |
|---|---|
| RAG / CRAG | Cyclic graph with `confidence_gate` conditional edge; see `.claude/skills/new-agent/references/cap-rag.md` |
| Compaction | Summarizer node between phases; see `.claude/skills/new-agent/references/cap-compaction.md` |
| Streaming | `graph.astream_events()`; stream tokens, not full responses |
| Batch | `graph.abatch()` with `RunnableConfig(max_concurrency=N)`; see `.claude/skills/new-agent/references/cap-batch.md` |
| A2A | Subgraphs for in-process; cross-process A2A is assemblable; see `.claude/skills/new-agent/references/cap-a2a.md` |
| HITL | `interrupt_after=` on nodes that need confirmation; see `.claude/skills/new-agent/references/cap-hitl.md` |
