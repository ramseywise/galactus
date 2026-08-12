# Google ADK — Framework Binding

> Read these convention refs first, then the bindings below:
> - `agent-architecture.md` — loop design, tool declaration, multi-agent orchestration
> - `agent-context.md` — context window management, prompt versioning
> - `agent-memory.md` — session persistence strategy
> - `agent-safety.md` — injection defense, credential custody
> - `agent-reliability.md` — error handling in tool wrappers
> - `agent-eval.md` — grader-interface contract

*ADK is the fast-prototype choice; production auditability needs → LangGraph. TS/Vercel-specific ADK rules live in `adk-vercel.md`.*

---

## When to use

ADK for **quick POCs** and demo scaffolds — fast to stand up, good defaults. Production auditability (traceable graph, durable checkpointing) → LangGraph.

---

## Binding table — convention ref → ADK surface

| Convention concern | Convention ref | ADK surface |
|---|---|---|
| Tool declaration | `agent-tools.md §1` | `FunctionDeclaration` with explicit input/output schema — never free-form kwargs |
| Tool error handling | `agent-reliability.md §4` | Caught in tool wrapper; returned as tool result with `is_error: true`, not raised through the loop |
| Session persistence | `agent-memory.md §2` | No `InMemorySessionService` outside local dev; Supabase/Postgres-backed state (see `adk-vercel.md`) |
| Multi-agent orchestration | `agent-architecture.md §5` | `sub_agents` delegation; ADK ships native A2A protocol support |
| Streaming | `agent-runtime.md §6` | Stream; never buffer full responses in request handlers |
| Safety | `agent-safety.md §4` | Credentials server-side only — never in `VITE_`/`NEXT_PUBLIC_` env vars |
| Structured output | `agent-architecture.md §3` | `output_schema=` on `Agent`; validates before returning |

---

## ADK-specific rules

- **`FunctionDeclaration` only** — typed input/output; no `**kwargs` reaching the agent loop.
- **Tool errors are results, not exceptions** — catch errors in the wrapper and return `{"is_error": true, "message": ...}`; let the model decide how to surface them.
- **No `InMemorySessionService` in production** — sessions must survive restarts.
- **Gemini / Anthropic API keys server-side only** — never in client bundles.
- **No irreversible tool writes without a confirmation step** in the agent loop (see `agent-safety.md §5`).
- **No blocking synchronous LLM calls** in request handlers — stream.

---

## Capabilities with ADK-specific support

| Capability | Note |
|---|---|
| RAG | `VertexAiRagRetrieval` built-in tool — the only runtime with a first-party managed ingest pipeline; see `cap-rag.md` |
| Vision | Gemini `inline_data` parts — `provider="gemini"` branch in `cap-vision.py` is correct |
| A2A | Native A2A protocol; cross-runtime interrupt format shared with ADK Go; see `cap-a2a.md` |
| Batch | Client-side concurrency; Vertex Batch API available for embeddings; see `cap-batch.md` |
| HITL | Interrupt support for human confirmation steps; see `cap-hitl.md` |
