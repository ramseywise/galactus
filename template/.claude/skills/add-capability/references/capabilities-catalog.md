# Capabilities catalog — add-capability reference

Each entry maps a named capability to the copier variable(s) it flips, the
files it adds, and any preconditions the current `.copier-answers.yml` must
satisfy. This is the machine-readable backing for `/add-capability`'s
"addable now / already on / blocked by" detection logic.

Format per entry:
- **sets** — the `-d key=value` passed to `copier update`
- **requires** — conditions on current `.copier-answers.yml` answers; if not
  met, the capability is blocked (report why, not just "can't scaffold it")
- **conflicts_with** — answer combinations that make the capability unsafe or
  meaningless
- **companion_questions** — answers the skill should ask if not already set
- **adds** — representative paths/components that appear after render

---

## rag

**Label:** RAG retrieval backend (`rag_agent`)

| Field | Value |
|-------|-------|
| sets | `include_rag_agent=true` |
| requires | `scaffold_full_project=true`; `primary_backend_language` in `[python, both]` |
| companion_questions | `vector_backend` (if not already set; default `duckdb`) |
| adds | `{py_project_root}/{ai_source_root}/agents/rag_agent/`, corpus index pipeline, retrieval golden-QA eval in `evals/` |

Note: already on for `project_type=rag` (it is that shape's working example).
Addable for any other full-project shape via this capability.

---

## mcp

**Label:** MCP adapter (`include_mcp_server`)

| Field | Value |
|-------|-------|
| sets | `include_mcp_server=true` (equivalent: add `mcp` to `agent_tools`) |
| requires | none — available in layering mode (`existing_repo`) too |
| companion_questions | `mcp_server_language` (`python`/`typescript`; default follows `primary_backend_language`) |
| adds | `mcp_servers/{py_mcp_server_slug}/` or `mcp_servers/{ts_mcp_server_slug}/` |

MCP tools are thin REST clients over `/api/v1/*` endpoints. Never add business
logic directly to the MCP server — that belongs in the Python backend.

---

## second-agent-framework

**Label:** Second chat-agent framework (`primary_chat_agent=both`)

| Field | Value |
|-------|-------|
| sets | `primary_chat_agent=both` |
| requires | `scaffold_full_project=true`; current `primary_chat_agent` in `[lg_agent, adk_agent]` (i.e., one framework already scaffolded, not `none` or `both`) |
| conflicts_with | none |
| companion_questions | none |
| adds | The other framework's agent directory (`{agent_slug}_adk/` or `{agent_slug}/`), its Makefile targets (`<slug>-up`/`-chat`) |

Use when the design names both LangGraph and Google ADK as target frameworks.
Each framework gets its own agent directory; `agent_slug` names the LangGraph
one; `{agent_slug}_adk` names the ADK one.

---

## vector-backend-upgrade

**Label:** Vector store upgrade (`vector_backend`)

| Field | Value |
|-------|-------|
| sets | `vector_backend=postgres` or `vector_backend=opensearch` |
| requires | `include_rag_agent=true` (the vector backend only matters when a RAG agent is present) |
| conflicts_with | none |
| companion_questions | none (choice drives itself: `postgres` for Supabase/managed PG; `opensearch` for a production cluster) |
| adds | `pgvector`/`psycopg` deps (postgres) or `opensearch-py` dep (opensearch); updated config in `rag_agent/` |

`duckdb` (default) and `memory` are zero-external-service options for local
dev. Upgrade to `postgres` or `opensearch` when the design needs a production-
scale vector store or the project already has a Postgres dependency.

---

## eval-metric-escalation

**Label:** Escalation eval metric

| Field | Value |
|-------|-------|
| sets | add `escalation` to `eval_metrics` (merge with existing list) |
| requires | `has_gradeable_interactions=true` (i.e., a chat agent is scaffolded: `primary_chat_agent` in `[lg_agent, adk_agent, both]`) |
| adds | `evals/graders/heuristic/escalation.py`, `evals/graders/judges/escalation.py`, `evals/metrics/escalation.py` |

---

## eval-metric-friction

**Label:** Friction eval metric

| Field | Value |
|-------|-------|
| sets | add `friction` to `eval_metrics` |
| requires | `has_gradeable_interactions=true` |
| adds | `evals/graders/heuristic/friction.py`, `evals/graders/judges/friction.py`, `evals/metrics/friction.py` |

---

## eval-metric-intent

**Label:** Intent classification eval metric

| Field | Value |
|-------|-------|
| sets | add `intent` to `eval_metrics` |
| requires | `has_gradeable_interactions=true` |
| adds | `evals/graders/heuristic/intent.py`, `evals/graders/judges/intent.py`, `evals/metrics/intent.py` |

---

## eval-metric-language

**Label:** Language-match eval metric

| Field | Value |
|-------|-------|
| sets | add `language` to `eval_metrics` |
| requires | `has_gradeable_interactions=true` |
| adds | `evals/graders/heuristic/language.py`, `evals/graders/judges/language.py`, `evals/metrics/language.py` |

---

## integration-composio

**Label:** Composio integration (Gmail/Slack/GitHub + hundreds more)

| Field | Value |
|-------|-------|
| sets | add `composio` to `optional_features` |
| requires | `scaffold_full_project=true` |
| adds | Composio client scaffold in `{py_project_root}/{ai_source_root}/integrations/` |

---

## integration-n8n-webhook

**Label:** n8n inbound webhook receiver

| Field | Value |
|-------|-------|
| sets | add `n8n_webhook` to `optional_features` |
| requires | `scaffold_full_project=true` |
| adds | HMAC-verified `POST /webhooks/n8n` receiver |

---

## integration-web-research

**Label:** Web research (GPT-Researcher reports)

| Field | Value |
|-------|-------|
| sets | add `web_research` to `optional_features` |
| requires | `scaffold_full_project=true`; Python ≤ 3.13 (known upstream issue with 3.14+) |
| adds | GPT-Researcher client + report pipeline |

---

## integration-meeting-intelligence

**Label:** Meeting intelligence (transcript → action items/decisions)

| Field | Value |
|-------|-------|
| sets | add `meeting_intelligence` to `optional_features` |
| requires | `scaffold_full_project=true` |
| adds | Transcript ingestion + one-LLM-call action-items/decisions extractor |

---

## integration-marketing

**Label:** Marketing clients (Eventbrite/LinkedIn/Canva)

| Field | Value |
|-------|-------|
| sets | add `marketing` to `optional_features` |
| requires | `scaffold_full_project=true` |
| adds | Eventbrite, LinkedIn, Canva httpx clients |

---

## integration-promptfoo

**Label:** promptfoo eval harness

| Field | Value |
|-------|-------|
| sets | add `promptfoo` to `optional_features` |
| requires | `scaffold_full_project=true` |
| adds | `promptfoo.yaml` config + HTTP eval targets alongside the Python evals |

Note: `include_rag_agent=false` with promptfoo needs a compatible `/chat`
endpoint (LangGraph chat agent or custom backend) — see `add-capability/SKILL.md`.

---

## integration-ragas

**Label:** RAGAS LLM-judge grader

| Field | Value |
|-------|-------|
| sets | add `ragas` to `optional_features` |
| requires | `scaffold_full_project=true` |
| adds | RAGAS grader scaffold in `evals/` |

Known issue: ragas 0.4.3 import bug upstream — degrades gracefully, no real
scores until fixed.

---

## ml

**Label:** Classical ML/stats toolkit

| Field | Value |
|-------|-------|
| sets | add `ml` to `optional_features` |
| requires | `scaffold_full_project=true` |
| adds | Regression, time-series, A/B, clustering scaffold in `{py_project_root}/` |

---

## split-service

**Label:** Split frontend/backend deployment (`frontend_backend_topology=split_service`)

| Field | Value |
|-------|-------|
| sets | `frontend_backend_topology=split_service`, `include_frontend=true` |
| requires | `has_typescript=true`; `primary_backend_language` in `[both]` |
| conflicts_with | `ts_agent_framework=vercel_ai_sdk` (that path assumes the TS agent's own API routes ARE the backend; split_service adds a separate Python backend — mutually exclusive in practice) |
| companion_questions | none |
| adds | `frontend/` (Next.js), `{py_project_root}/{ai_source_root}/middleware/auth.py` (FastAPI JWT dependency), Edge middleware on frontend, Postgres RLS for tenant isolation |

This is FOIA-Fluent's proven production shape: Next.js (Vercel) + FastAPI
(Railway) sharing identity via Supabase Auth JWT.

---

## agent-reference-library

**Label:** Agent reference library (`.agents/skills/`)

| Field | Value |
|-------|-------|
| sets | `include_agent_reference_library=true` |
| requires | none — available in layering mode too |
| adds | `.agents/skills/` (ADK + LangGraph scaffolding patterns), `/new-agent` skill |

Off by default: its canonical home is the template. Opt in for
offline/team-portability cases where `.claude` global isn't available.

---

## ts-agent-framework

**Label:** Vercel AI SDK TypeScript agent

| Field | Value |
|-------|-------|
| sets | `ts_agent_framework=vercel_ai_sdk` |
| requires | `has_typescript=true`; `scaffold_full_project=true` |
| conflicts_with | `frontend_backend_topology=split_service` |
| adds | TypeScript agent loop (Vercel AI SDK `streamText` + `tool()`) in the TS backend service |

Use when deploying a TS-native assistant (e.g. a Vercel-hosted frontend's own
API routes) rather than calling out to a separate Python agent service.

---

## frontend-bundler-vite

**Label:** Vite + React SPA frontend (instead of Next.js)

| Field | Value |
|-------|-------|
| sets | `frontend_bundler=vite` |
| requires | `include_frontend=true`; `scaffold_full_project=true` |
| conflicts_with | `frontend_backend_topology=split_service` when the split relies on Next.js middleware for the auth boundary — a Vite SPA has no server to run Edge middleware, so the JWT check moves to the API |
| adds | `_scaffold/frontend-vite/{ts_project_root}/` — Vite + React 19 + Tailwind SPA (`vite.config.ts`, `vitest.config.ts`, `src/components/`, react-router entry), promoted to `frontend/` in place of the Next.js tree |

The default is `next`. Choose vite for a client-rendered console or dashboard
talking to a separate API (the `dssg/project-mgmt-ai` shape); stay on next when
pages must render server-side or the frontend IS the backend.

Switching an existing frontend flips the whole build toolchain — treat it as a
rewrite of `frontend/`, not an in-place upgrade.

---

## supabase-db

**Label:** Supabase as the application database (migrations + RLS)

| Field | Value |
|-------|-------|
| sets | `include_supabase_db=true` |
| requires | `scaffold_full_project=true` |
| companion_questions | none |
| adds | `_scaffold/supabase/migrations/` (tenancy + RLS starter), `_scaffold/supabase/tests/rls.test.sql`, `_scaffold/supabase/config.toml` — all promoted to `supabase/` at the repo root |

Distinct from the two Supabase touchpoints that already exist: **auth**
(`@supabase/ssr` in the frontend, JWT middleware in the split_service backend)
and **`vector_backend=postgres`** (pgvector as a RAG store). Neither of those
gives a project row-level tenant isolation or a migration history — this does.

Add when Postgres IS the application database and tenant isolation is enforced
in the database rather than the application layer.

---

## Notes for `/add-capability` detection

When evaluating whether a capability is addable, read `.copier-answers.yml`
and classify each entry above into one of three buckets:

1. **Already on** — the `sets` variable(s) are already at the target value.
2. **Addable now** — all `requires` conditions are satisfied.
3. **Blocked** — one or more `requires` conditions are not met. Report
   specifically which condition blocks it (e.g. "blocked: `scaffold_full_project`
   is false — this project is in layering-only mode").

Multiselect variables (`agent_tools`, `eval_metrics`, `optional_features`) are
**additive** — read the current list from `.copier-answers.yml` and merge; do
not clobber existing entries.

For `conflicts_with`: if a conflict is present, warn before running. The
conflict is documented guidance, not a hard copier invariant — a `-d` override
that violates it is sometimes exactly what CI needs.
