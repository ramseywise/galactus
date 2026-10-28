# Research: multi-agent/automation tooling parity

Date: 2026-07-14
Context: two adjacent projects want to build on `ai-project-template`, each proposing a
tool stack the template doesn't fully cover today. Rather than design one-off, this
research compares both stacks against the template's *actual current state* (verified
by reading `copier.yaml`/`template/_scaffold/` directly, not from memory) to find the
overlap worth prioritizing.

- **project-mgmt-ai** (hackathon coordination, nonprofit-facing): n8n, CrewAI, Supabase
  (Postgres+pgvector), Google Calendar API, Eventbrite API, LinkedIn API, Canva API,
  meeting-transcription (Granola/Fireflies).
- **grant-fundraising-ai** (nyc-dssg, new repo, not yet created): CrewAI, AutoGen,
  LangGraph (orchestration); LangChain, LlamaIndex (agent/RAG framework); n8n, Composio
  (automation); GPT-Researcher, Browser-use, You.com SDK (web research); Ragas,
  Pydantic-AI, Promptfoo (eval/guardrails); Supabase (Postgres+pgvector).

## Method

For each tool/capability: grepped `copier.yaml`, `template/_scaffold/`, `.claude/hooks/`,
`.claude/skills/`, `.agents/skills/` for existing support, partial patterns, or zero
references. Classified as **have** / **partial** (an existing pattern that generalizes)
/ **gap** (no pattern to build from — net-new).

## Overlap matrix

| Capability | project-mgmt-ai | grant-fundraising-ai | Template status |
|---|---|---|---|
| LangGraph orchestration | — | ✓ | **Have** — `lg_agent`, full persistence/HITL/streaming skill docs |
| Google ADK orchestration | — | — | **Have** — `adk_agent` (not requested by either, but available) |
| CrewAI (role-based crews) | ✓ | ✓ | **Gap** — zero references anywhere in template. Shared by both projects — highest-leverage gap |
| AutoGen | — | ✓ | **Gap** — zero references. Unique to grant-fundraising-ai |
| LangChain | (implicit, via n8n glue) | ✓ | **Partial** — not a direct dep, but LangGraph is built on `langchain-core` primitives already (`langchain-mcp-adapters` dep exists); most "LangChain-shaped" needs (tool-calling, retrievers) are already served by `lg_agent`'s existing patterns |
| LlamaIndex | — | ✓ | **Gap** — zero references. `rag_agent`'s RAG is hand-rolled (embeddings + vector index), not LlamaIndex-based |
| n8n (workflow automation) | ✓ | ✓ | **Gap** — zero references anywhere: no webhook scaffold, no n8n-callable endpoint pattern. Shared by both — high-leverage gap |
| Composio (tool-execution SaaS) | — | ✓ | **Gap**. Unique to grant-fundraising-ai |
| Supabase / Postgres+pgvector | ✓ | ✓ | **Partial** — real head start exists: `agents/lg_agent/checkpointer.py` already stubs a `PostgresSaver` branch (`NotImplementedError`, points at `.agents/skills/langgraph-persistence/SKILL.md`) and `vector_backend`'s factory (`get_vector_index()`, `@lru_cache` singleton) already demonstrates the exact extension shape used to add OpenSearch — a `postgres`/`supabase` branch is the same pattern, not a new one. No `psycopg`/`asyncpg`/`pgvector` dep exists yet. Shared by both — high-leverage gap, and the cheapest of the three "shared" gaps given the existing stub |
| Google Calendar API | ✓ | — | **Gap**. Unique to project-mgmt-ai |
| Eventbrite / LinkedIn / Canva APIs | ✓ | — | **Gap**, no pattern. Unique to project-mgmt-ai. Closest existing precedent: the MCP server's `httpx` + `try/except HTTPError` call pattern (calling `rag_agent`'s own `/api/v1/retrieval`) — generalizable to "call an external REST API from a tool," but nothing calendar/event-specific exists |
| Meeting transcription ingestion (Granola/Fireflies) | ✓ | — | **Gap**. Unique to project-mgmt-ai. No transcript-to-structured-action pipeline exists; closest analog is `rag_agent`'s document-ingestion pipeline (`build_index.py`) but that's chunk-and-embed, not extract-actions-from-transcript |
| GPT-Researcher / Browser-use / You.com SDK (web research) | — | ✓ | **Gap**. Unique to grant-fundraising-ai. No web-search or browser-automation tool exists in any agent today |
| Ragas (RAG eval) | — | ✓ | **Partial** — the template already has a heuristic + W&B eval suite (`evals/pipelines/run.py.jinja`, hit-rate/MRR/answer-overlap graders) generalized across retrieval backends (this session's #2 item). Ragas would slot in as an *additional* grader alongside the existing ones, not a replacement — the grading-pipeline shape already supports adding a new grader function |
| Promptfoo (prompt/output eval) | — | ✓ | **Gap** — no promptfoo config/harness exists. Different tool than the Python-native eval suite (promptfoo is a separate CLI/config-driven tool); would run alongside, not replace |
| Pydantic-AI (structured agent output + validation) | — | ✓ | **Partial** — CLAUDE.md already mandates "Pydantic models at API boundaries" as a hard convention; agents already use Pydantic (confirmed: `AssistantResponse`-shaped models referenced in earlier session work). Pydantic-AI specifically (the agent-framework, not just the validation library) is a gap, but the boundary-validation *discipline* it would reinforce is already in place |
| Docker / deployment | ✓ (implicit) | ✓ (implicit) | **Partial** — `docker-compose.yml` + `Dockerfile` exist but scoped only to `lg_agent`; not generalized to `adk_agent`, `rag_agent`, the TS backend, or a to-be-added CrewAI service |

## What this means for prioritization

Three gaps are shared by both projects and have the highest leverage per unit of work:

1. **Supabase/Postgres+pgvector** — cheapest of the three, because two real stubs
   already exist to extend (`checkpointer.py`'s `PostgresSaver` branch,
   `get_vector_index()`'s factory pattern). This isn't "add a new subsystem," it's
   "finish two half-built extension points using a pattern the template already
   proved out for OpenSearch."
2. **n8n** — no existing pattern at all. The right shape isn't "run n8n itself" (that's
   an external service, out of scope for a Copier template to install) but "make the
   template's agents/services *callable by* n8n" — i.e., ensure every agent exposes a
   plain HTTP endpoint n8n's HTTP Request node can hit, and optionally a signed-webhook
   receiver pattern for the reverse direction (n8n calling back into the project). This
   is closer to a documentation + thin-endpoint pattern than new infrastructure.
3. **CrewAI** — no existing pattern. Architecturally this is the biggest of the three:
   it's a second agent-orchestration framework alongside LangGraph/ADK, meaning it
   follows the same shape as `primary_chat_agent`'s existing framework-choice toggle,
   not a bolt-on. Expect it to be comparable in size to the TypeScript-backend item from
   this session's backlog (a new toggle + a new staged agent tree + Makefile/hook
   wiring), not a quick addition.

Gaps unique to one project (Calendar/Eventbrite/LinkedIn/Canva/meeting-transcription for
project-mgmt-ai; AutoGen/Composio/GPT-Researcher/Browser-use/Ragas/Promptfoo/LlamaIndex
for grant-fundraising-ai) are real but lower-leverage for the *template* specifically —
several of them (the four SaaS APIs, GPT-Researcher/Browser-use) are plain "call an
external REST API with an API key" integrations that don't need template-level toggles
so much as one clearly-documented pattern + example (the MCP server's existing
`httpx`/`HTTPError` call shape already generalizes to this) rather than N separate
bespoke integrations.

## Explicitly not recommended

- Don't add n8n *itself* to the template (it's a hosted/self-hosted external service,
  not something Copier scaffolds) — only the "be callable by n8n" contract.
- Don't try to make CrewAI and LangGraph interchangeable via one abstraction layer —
  that's the kind of premature multi-backend abstraction the project's own conventions
  warn against when nobody's asked for it; treat them as two independently-selectable
  frameworks (like `primary_chat_agent`) instead.
- Don't chase full parity on the "unique" gaps (Calendar/Eventbrite/LinkedIn/Canva,
  AutoGen, Composio, GPT-Researcher, Browser-use, Ragas, Promptfoo, LlamaIndex) inside
  this template pass — document one general external-API-integration pattern and let
  each project wire its own specific APIs on top, the same way `include_mcp_server`
  ships one worked example rather than a connector for every possible tool.
