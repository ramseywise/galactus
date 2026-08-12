# ADK + Vercel — Framework Binding

> Read these convention refs first, then the bindings below:
> - `agent-runtime.md` — stateless-function constraints, topology, cost/latency levers
> - `agent-safety.md` — credential custody, tenant isolation, injection defense
> - `agent-memory.md` — session persistence (external DB)
> - `agent-context.md` — context window management, streaming
> - `agent-tools.md` — tool schema, error handling
> - `agent-reliability.md` — streaming error handling, timeouts

Applies when building TypeScript agent systems on Vercel (AI SDK, Google ADK TS, or Anthropic SDK) deployed as Vercel Functions / Next.js API routes.

---

## Binding table — convention ref → Vercel/TS surface

| Convention concern | Convention ref | Vercel/TS surface |
|---|---|---|
| Stateless function constraints | `agent-runtime.md §2` | Each Function invocation is independent; no persistent process; see constraints below |
| Session state externalization | `agent-memory.md §2` | Supabase/Postgres rows; load at request start, write at end |
| Streaming | `agent-runtime.md §6` | `ReadableStream` / `StreamingTextResponse`; never buffer full responses |
| Timeout management | `agent-runtime.md §2` | Hobby=10s, Pro=60s, Enterprise=300s; `export const maxDuration = 60` on long routes |
| API key custody | `agent-safety.md §4` | Server-side only — never `NEXT_PUBLIC_`, never `VITE_`, never in client components |
| Tenant isolation | `agent-safety.md §4` | Every DB query scoped to `tenant_id` or user org via RLS |
| Tool declaration | `agent-tools.md §1` | Zod schemas for Vercel AI SDK; `FunctionDeclaration` for ADK TS |
| Tool errors | `agent-reliability.md §4` | Structured `{ error: string, code: string }` — never throw to client |
| Streaming errors | `agent-reliability.md §7` | Close stream with error event; do not leave hanging |

---

## Stateless-function constraints (summary)

Full treatment in `agent-runtime.md §2`. For Vercel specifically:

- **No `InMemorySessionService`** — sessions disappear on cold starts.
- **No ADK session manager in MVP** — ADK session objects created per-request from DB state.
- **No synchronous LLM calls blocking response** — always stream or use background jobs.
- **No `fetch` without timeout** in agent tool calls — external API calls can hang indefinitely.
- **`export const runtime = 'edge'`** only if the function is truly stateless and doesn't need Node.js APIs.

---

## Phase 2 — stateful sessions

When stateful sessions are needed:

- ADK persistent session manager as a long-running service (not a serverless function).
- Session affinity via a dedicated agent service — Vercel Functions remain the API layer, proxying to the stateful backend.
- Design the handoff point now: Supabase session rows should be readable by either the stateless MVP or a future stateful manager without schema changes.

---

## Vercel-specific deployment rules

- Functions in `/app/api/` (Next.js App Router) or `/api/` (Pages Router) — pick one per project, do not mix.
- `maxDuration` annotation on long-running agent routes: `export const maxDuration = 60`.
- Supabase anon key is the only key safe to expose client-side (it is rate-limited and RLS-governed).
- Never store Supabase service role key in client-accessible env vars.
- Never log request bodies that might contain tokens or PII; structured logging only.

---

## Capabilities with Vercel-specific notes

| Capability | Note |
|---|---|
| RAG | AI SDK 6+ `embed`/`embedMany`; retriever as tool; no managed corpus; see `cap-rag.md` |
| Streaming | AI SDK `StreamingTextResponse`; message parts with `type: 'image'` for vision |
| Batch | `Promise.all` with concurrency limiter, or Workflow SDK for durable fan-out; see `cap-batch.md` |
| A2A | A2A 1.0 ecosystem protocol; Vercel integration is proof-of-concept stage; see `cap-a2a.md` |
