---
name: framework-selection
description: >
  INVOKE THIS SKILL before scaffolding a new agent (e.g. via /new-agent) or writing
  agent code from scratch, whenever the framework hasn't already been decided.
  Decides between Google ADK, LangGraph, and a TS-native Vercel AI SDK agent based
  on deployment target, control-flow needs, and runtime (Python vs. TypeScript).
---

# Framework Selection — ADK vs LangGraph vs Vercel AI SDK

This project supports three agent frameworks. ADK and LangGraph are not layered the
way they sit relative to LangChain elsewhere — pick one per agent based on its
deployment target and control-flow needs. Vercel AI SDK is a different axis
entirely: it's the answer whenever the *runtime* is TypeScript, not Python — the
question below is deliberately asked first, since it's the one branch that isn't
about control-flow complexity at all.

---

## Decision Guide

Answer in order; stop at the first "yes":

| Question | Yes → |
|---|---|
| Does this agent need to run in a TypeScript/Node runtime — e.g. it's the API routes of a Vercel-hosted frontend, and should deploy as part of that same build with no separate Python service? | **Vercel AI SDK** |
| Deploying on GCP / Vertex AI, want a managed session service and a maintained scaffolder CLI (`agent-starter-pack`)? | **ADK** |
| Need fine-grained custom control flow — branching, loops, parallel fan-out/fan-in, or human-in-the-loop gates at arbitrary points in the graph? | **LangGraph** |
| Already have LangChain tools, retrievers, or chains to reuse, or need multi-provider LLM support beyond Gemini? | **LangGraph** |
| Straightforward single-agent (or agent + sub-agents) assistant, Gemini-first, no exotic control flow? | **ADK** |

If none clearly apply, default to **ADK** for anything deploying to GCP, **LangGraph**
for anything that needs to run anywhere else or that already has non-Gemini LLM calls
in the codebase. A TS-native frontend that instead calls out to a separate Python
agent service (rather than hosting the agent loop itself) doesn't need Vercel AI SDK
at all — that's just an HTTP client calling whichever of ADK/LangGraph the backend
agent uses; only pick Vercel AI SDK when the agent loop itself needs to run in the
TS process.

---

## Framework Profiles

### Google ADK

**Best for:**
- Single-agent or sub-agent-hierarchy assistants
- GCP/Vertex AI deployment (Agent Engine or Cloud Run)
- Projects that want a maintained scaffolder CLI rather than hand-rolled infra

**Not ideal when:**
- You need a graph with arbitrary branching/loops/parallel workers
- You need LLM providers other than Gemini

**References to read next:** `adk-scaffold.md`, then `adk-dev-guide.md`

### LangGraph

**Best for:**
- Agents with branching logic, loops, or reflection (retry-until-correct)
- Multi-step workflows where different paths depend on intermediate results
- Human-in-the-loop approval at specific graph nodes
- Parallel fan-out / fan-in (map-reduce patterns)
- Any LLM provider via LangChain integrations

**Not ideal when:**
- A simple single-agent assistant would do — the extra graph-authoring effort isn't worth it
- There's no need for anything beyond what ADK's built-in agent/sub-agent hierarchy gives you for free

**References to read next:** `langgraph-scaffold.md`, then `langgraph-fundamentals.md`;
also `langgraph-persistence.md` and `langgraph-human-in-the-loop.md` as needed.

### Vercel AI SDK

**Best for:**
- A TS-native assistant that lives inside a TypeScript backend/frontend project and
  deploys as part of that same build (e.g. a Vercel-hosted app's own API routes) —
  no second service, no container, no cross-language HTTP hop.
- Straightforward tool-calling loops (`streamText` + `tool()`, automatic multi-step
  tool-calling) — not a replacement for LangGraph's arbitrary graph control.

**Not ideal when:**
- The agent needs LangGraph-grade custom control flow (branching, loops,
  human-in-the-loop interrupts at arbitrary points) — build that in Python and call
  it from the TS layer instead of trying to replicate it here.
- The project's agent logic is already Python and there's no reason to also run a
  TS runtime just for this.

**Requires (scaffolded projects only):** `has_typescript: true` and
`ts_agent_framework: vercel_ai_sdk` in copier.yaml — stages a real `agent/` tree
(settings, Anthropic provider factory, tool registry, `streamText` loop,
framework-agnostic HTTP handler) at
`{{ ts_project_root }}/{{ ts_source_root }}/agent/`.

---

## Quick Reference

| | ADK | LangGraph | Vercel AI SDK |
|---|---|---|---|
| Runtime | Python | Python | TypeScript |
| Scaffolder | `agent-starter-pack` (official Google CLI) | none — hand-written via `langgraph-scaffold` | copier toggle (`ts_agent_framework`) |
| Control flow | Agent / sub-agent hierarchy, callbacks | Full graph control (nodes, edges, `Command`, `Send`) | Single tool-calling loop (`streamText`, automatic multi-step) |
| Managed deployment | Agent Engine (built-in) | Manual (Cloud Run, ECS, etc.) | Vercel (zero-config or `vercel.json`) |
| Persistence | Session service (managed or Cloud SQL) | Checkpointer (`InMemorySaver`/`SqliteSaver`/`PostgresSaver`) | None built in — add explicitly if needed |
| Multi-provider LLM | Gemini-first (Vertex AI or AI Studio) | Any provider via LangChain integrations | Any provider via AI SDK provider adapters (Anthropic by default) |
| Human-in-the-loop | Callback-based approval | `interrupt()` / `Command(resume=...)` | Not built in — use LangGraph instead if this is a hard requirement |
