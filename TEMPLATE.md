# AI-Eng Claude Template

A [Copier](https://copier.readthedocs.io/en/stable/) template that drops the Claude Code AI-engineering tooling from my agentic `playground` repo — a research→plan→execute→review skill pipeline, hook-based code-quality enforcement, and an optional parameterized MCP server — into a new or already-existing project.

## What you get

Three tiers — not one flat bundle. The interview no longer walks the tiers question-by-question:
it runs in **phases** (see "The interview" below), and the tiers describe what lands on disk:

1. **Always scaffolded**: `CLAUDE.md` (style conventions, hook-enforced standards, commit convention, a
   placeholder for project-specific hard rules — plus a data-classification hard rule driven by
   `data_sensitivity`), `LIFECYCLE.md` (Discovery → Delivery → Deployment phase/gate status,
   maintained by `/gate-check` — the status contract project-mgmt-ai reads),
   `DEPLOYMENT.md` (the Phase-3 runbook — staged rollout, rollback criteria, monitoring;
   pre-flighted by `/deploy-check`),
   `.claude/settings.json` (hook wiring: secrets scan, branch naming, code quality,
   test coverage, SDK-pattern checks, docs hygiene, memory-duplication guard, commit gates), and
   `.claude/hooks/*.sh` + `.claude/skills/` (26 workflow skills — see `.claude/skills/README.md` in
   the generated project for the full map).
2. **Independent toggles** (available even with `scaffold_full_project=false`, i.e. layering-only mode
   onto an existing repo): `.agents/skills/` (`include_agent_reference_library`) — a tool-agnostic
   ADK/LangGraph reference library that `/new-agent` orchestrates — and `mcp_servers/<slug>/`
   (`include_mcp_server`) — a FastMCP server scaffold, ready to extend.
3. **One all-or-nothing bundle** behind `scaffold_full_project`: `pyproject.toml`, `core/` (the general
   data/ETL home — `core/pipelines/corpus/` holds the markdown→JSONL→DuckDB-FTS corpus pipeline when a
   retrieval example agent is present; see "Shape examples" below),
   `evals/`, `infrastructure/`, `tests/`, CI, `.pre-commit-config.yaml` (ruff-pre-commit, reads the same
   `[tool.ruff]` config as everything else — real git-level enforcement alongside the Claude-session
   hooks) and `renovate.json` (automated dependency-update PRs, with the fast-moving AI framework deps
   held back from automerge) — plus the sub-gated `include_dev_companion` toggle within
   this tier. Working example agents are minimal by default and **derived from `project_type`**, not asked:
   `primary_chat_agent` picks the user-facing chat agent — `lg_agent` (LangGraph, BM25 — the default for
   chat/agent/workflow/prototype shapes), `adk_agent` (Google ADK), `both`, or `none` — and `rag_agent`
   (embedding-based retrieval behind `/api/v1/retrieval`) ships default-on only for the `rag` shape. Both
   are now `-d`-only capabilities: a second framework or `include_rag_agent=true` is a `copier update -d`
   away (the `/add-capability` path), never a genesis question. `langgraph`/`langchain-core` stay installed
   regardless — the chat agents depend on them; only the chosen chat agent's
   own framework-specific deps (`langchain-mcp-adapters` for `lg_agent`, `google-adk`+`mcp` for
   `adk_agent`) actually toggle. The retrieval golden-QA eval grades every backend independently (see
   `evals/README.md` in the generated project) and ships alongside the corpus pipeline; a non-retrieval
   shape (mcp_server/eval_suite/ai_backend/adk-only) gets an empty `core/` ETL home and keeps only the
   interaction-eval suite.

This repo's own `.github/workflows/test-render.yml` renders a representative config matrix (defaults,
layering-only, each `project_type`/`primary_chat_agent` value, and a `no-corpus-ai_backend` row that
proves the empty-`core/` non-retrieval render's tests pass) on every push/PR and checks for leftover
Jinja + a clean `ruff check`/`format --check` — the automated version of this session's manual
verification loop.

## Quick start

**Recommended sequence (two skills, both live in galactus's `.claude/skills/`):**

1. `/proto-scope` — system design interview. Asks about actors, problem, MVP scope, and key
   architectural decisions before touching infrastructure. Produces `DESIGN.md`. Start with
   `/proto-scope discovery` when all you have is a pain point.

2. `/new` — routes AI vs ML, picks run-in-galactus vs standalone repo, asks the language
   (Python, TypeScript or both), then for a repo runs the infrastructure interview and writes
   a copier answers file. Reads `DESIGN.md` if it exists. Architecture (agent framework,
   vector backend, MCP, integrations, eval metrics) is derived from `project_type` and added
   later as capabilities via `copier update -d` (`/add-capability`).

Running `/new` alone (skipping `/proto-scope`) is valid — the generated project includes a
blank `DESIGN.md` stub as a reminder to fill in the design before sprint 1.

**Power-user/scriptable path** — the same copier prompts directly:

```bash
make new_project output_dir="~/Workspace/my-project" project_name="My Project"
```

This prompts through the phased interview (see below) and renders the result into `output_dir`. Use
`make new_project_dev` instead while iterating on the template itself, so it renders from your dirty
working tree rather than requiring a commit first.

## The interview

Questions are ordered around **discovery, not implementation** — you say what you're building first,
and the implementation choices either derive their defaults from that or aren't asked at all:

1. **Phase 1 — Project scoping** (always asked): name/slug/description, `project_type` (chat app /
   autonomous agent / workflow automation / RAG / MCP server / AI backend / eval suite / research
   prototype / layer-onto-existing-repo), `primary_users`, `primary_backend_language`,
   `external_systems` (multiselect: Slack, GitHub, Google Workspace, Calendar, Email, Database, Web),
   `deployment_target`.
2. **Phase 1b — The AI system itself** (agent-shaped projects only): `agent_tools` (multiselect),
   `agent_memory` (none / conversation / long-term), `human_approval` (none / sometimes / always).
   These land in the generated `DESIGN.md`'s Key Decisions table and seed architecture defaults
   (MCP on when tools include MCP; postgres checkpointer on for long-term memory).
3. **Phase 4 — Team conventions**: `data_sensitivity` (default follows `primary_users` —
   customer/public-facing → `restricted`), `ticket_prefix`, `enable_macos_notifications`.

That's the whole interview — 11 questions (14 for agent-shaped projects). **Architecture is no longer
asked.** What used to be Phase 2 (chat-agent framework, vector backend, TS agent loop, frontend/backend
topology, MCP server, MCP language) and Phase 3 (the optional-features and eval-metrics multiselects) is
now **derived from `project_type` and `-d`-only** — `project_type` picks the one shape example, and each
of those components is a mid-project capability you add later with `copier update -d include_<x>=…` (the
`/add-capability` path). This shrinks genesis to scoping + conventions and moves lifecycle decisions to
when they're actually made.

### Shape examples — one per `project_type`

The render ships exactly one shape example, chosen by `project_type` — no cross-shape leakage:

| `project_type` | Shape example that lands |
|---|---|
| `chat_app` / `agent` / `prototype` | one LangGraph chat agent (`lg_agent`) + corpus pipeline + retrieval eval |
| `workflow` | `lg_agent` + corpus + n8n webhook receiver |
| `rag` | `rag_agent` (embedding retrieval) + corpus + retrieval eval + structure guard |
| `mcp_server` | MCP server scaffold (`mcp_servers/<slug>/`), no chat agent |
| `eval_suite` | eval machinery only, no chat agent |
| `ai_backend` | FastAPI service only — no chat agent, empty `core/` ETL home, interaction evals only |
| `existing_repo` | layering-only: `.claude/`/`.agents`/`mcp_servers`, nothing else |

The corpus data pipeline (`core/pipelines/corpus/`, `data/corpus/`, the retrieval golden-QA eval, and
`tests/unit/core/`) ships **only when a retrieval example agent is present** (`lg_agent` BM25 or
`rag_agent`). Other shapes get `core/` as an empty ETL home; add corpus with
`copier update -d include_rag_agent=true`.

Everything else is **inferred, never asked**: `source_root` (`src`), `eval_root`/`eval_allowed_dirs`,
`enable_structure_guard` (on only for eval-suite/RAG shapes), `python_version` (3.12), `aws_region`,
`ts_source_root`/`ts_project_root`, `mcp_server_name`/`mcp_server_slug` (plus the
`py_mcp_server_slug`/`ts_mcp_server_slug` pair derived from it), `scaffold_full_project`
(false only for the layer-onto-existing-repo project type), `has_typescript`, `has_corpus_pipeline`, and
the derived architecture + `include_*` toggles above. Every inferred/`-d`-only value remains overridable
non-interactively — `-d source_root=lib`, `-d primary_chat_agent=both`, `-d include_mcp_server=true`,
`-d include_ml=true` all still work, which is how CI and `/new` drive the template.

## Updating a project that already used this template

Copier tracks the answers it was given in `.copier-answers.yml`. Re-run `copier update` from inside the
generated project to pull in template changes — see the
[Copier update docs](https://copier.readthedocs.io/en/stable/updating/).

Template `_migrations` run automatically after each `copier update` to clean up structural moves that
copier's file-level merge can't do on its own. The current migration handles the `core/*.py` →
`core/pipelines/corpus/*.py` restructure: unmodified stale modules are removed automatically, but any
`core/*.py` you had **hand-edited** is left in place with a `[migration] WARN` telling you to port your
changes into `core/pipelines/corpus/` and repoint `from core.<module> import …` references. Migrations are
idempotent — re-running `copier update` re-checks and only warns about files you haven't resolved yet.

## Options

**Asked** (the whole interview — Phase 1 scoping + Phase 4 conventions; agent-shaped projects also get
the three Phase-1b questions):

| Question | Default | Notes |
|---|---|---|
| `project_type` | `chat_app` | What you're building — drives the one shape example and every derived architecture default. `existing_repo` = layering-only mode |
| `primary_users` | `internal` | `internal`/`customers`/`developers`/`public_api` — seeds `data_sensitivity` and DESIGN.md's actor table |
| `primary_backend_language` | `python` | `python`/`typescript`/`both` — `typescript`/`both` scaffold a real Node/TS backend service at `ts_project_root` (package.json, tsconfig, eslint, Jest), not just frontend hooks |
| `external_systems` | *(none)* | Multiselect: Slack/GitHub/Google Workspace/Calendar/Email/Database/Web — seeds integration + vector-store defaults |
| `deployment_target` | `local` | `local`/`docker`/`cloud`/`serverless` — recorded in DESIGN.md's Key Decisions |
| `agent_tools` | seeded from `external_systems` (GitHub/Database), else empty | Agent-shaped projects only. Multiselect; explicitly selecting `mcp` (a declared MCP host consumer) seeds `include_mcp_server`; recorded in DESIGN.md |
| `agent_memory` | `conversation` | Agent-shaped projects only. `long_term` seeds `enable_postgres_checkpointer=true`; recorded in DESIGN.md |
| `human_approval` | `sometimes` | Agent-shaped projects only. Recorded in DESIGN.md — constrains tools that write to external systems |
| `data_sensitivity` | `internal` (`restricted` for customer/public-facing) | `public`/`internal`/`restricted`/`secret` — drives a `CLAUDE.md` hard rule and (when `scaffold_full_project`) a Terraform resource tag |
| `ticket_prefix` | `LIN` | Drives branch-naming enforcement and the Linear-ticket skill |
| `enable_macos_notifications` | `true` | Turn off on Linux/CI |

**Derived architecture / `-d`-only** (A3: no longer asked at genesis — derived from `project_type`, the
one shape example; each is a mid-project capability, added later with `copier update -d <name>=…` via
`/add-capability`. Still overridable at genesis with `-d`):

| Variable | Default | Notes |
|---|---|---|
| `primary_chat_agent` | `lg_agent` for chat/agent/workflow/prototype shapes, else `none` | `lg_agent`/`adk_agent`/`both`/`none` — one working example; a second framework is a `-d` / `copier update` away |
| `include_rag_agent` | `true` only for the `rag` shape | Prebuilt LangGraph retrieval backend behind `/api/v1/retrieval`; flips on `has_corpus_pipeline` (corpus + retrieval eval) |
| `vector_backend` | `duckdb` (`postgres` if Database selected) | `rag_agent`'s store. `opensearch` adds `opensearch-py`; `postgres` (pgvector — works with Supabase) adds `psycopg`/`pgvector` |
| `ts_agent_framework` | `vercel_ai_sdk` for TS-only chat/agent projects, else `none` | Stages a real streamText + tool() loop at `<ts_project_root>/src/agent/` |
| `frontend_backend_topology` | `single` | `split_service` = Next.js (Vercel) + FastAPI (Railway) sharing Supabase-JWT identity |
| `include_mcp_server` | `true` only when project is an MCP server, or MCP was explicitly selected in `agent_tools` | Scaffolds `mcp_servers/<slug>/` — a thin adapter over the REST boundary |
| `mcp_server_language` | follows `primary_backend_language` | `python` (FastMCP) or `typescript` (official MCP TS SDK) |
| `optional_features` | `[dev_companion]` + seeded | The optional-add-ons list — see "Optional features" below; add more with `-d optional_features=[…]` |
| `eval_metrics` | `[escalation, friction]` for agent-shaped, else `[]` | Interaction-eval metrics; add with `-d eval_metrics=[…]` (`/add-eval-metric`) |

**Optional features** (values of the `optional_features` variable; each maps to a derived
`include_*` variable that `-d` can still override individually):

| Value | Derived variable | What it scaffolds |
|---|---|---|
| `dev_companion` (default on) | `include_dev_companion` | A living "how we work on this project" doc (transforms, not appends) plus a `/dream` maintenance-audit skill |
| `promptfoo` (seeded by `eval_suite`) | `include_promptfoo` | `promptfoo.config.yaml` — config-driven eval harness (`npx promptfoo eval`) hitting `rag_agent`'s `/chat` endpoint, alongside the Python eval suite |
| `ragas` | `include_ragas_grader` | ragas-based LLM-judge grader. **Known issue** (verified 2026-07-14): `ragas` 0.4.3 has a broken import upstream — degrades gracefully, no real scores until fixed |
| `web_research` (seeded by Web) | `include_web_research` | `integrations/web_research.py` — autonomous web research + reports via GPT-Researcher (needs Python ≤ 3.13) |
| `meeting_intelligence` | `include_meeting_intelligence` | `integrations/meeting_intelligence.py` — transcript → structured action items/decisions via one LLM call |
| `marketing` | `include_marketing_integrations` | `integrations/{eventbrite,linkedin,canva}.py` — thin clients for publishing events, posting updates, generating assets |
| `n8n_webhook` (seeded by `workflow`) | `include_n8n_webhook` | HMAC-verified inbound webhook receiver (`POST /webhooks/n8n`), auto-mounted on every present agent's FastAPI app |
| `composio` (seeded by Slack/GitHub/Email/Workspace) | `include_composio` | `integrations/composio.py` — third-party app actions via Composio's unified tool API |
| `ml` | `include_ml` | `ml/` — classical ML/stats toolkit (regression, time-series, A/B testing, feature engineering, model comparison, clustering) |

`include_calendar_integration` (`integrations/google_calendar.py`, pre-obtained OAuth2 refresh token)
isn't in the multiselect — it derives directly from Calendar in `external_systems`.

**Inferred, never asked** (all overridable with `-d name=value`):

| Variable | Default | Notes |
|---|---|---|
| `scaffold_full_project` | `true` unless `project_type=existing_repo` | The old top-level toggle — `false` = layering-only mode |
| `has_typescript` | from `primary_backend_language` | Adds TS quality + typecheck hooks; `-d has_typescript=true` for a frontend-only layering project |
| `source_root` / `ts_source_root` / `ts_project_root` | `src` / `src` / `<project_slug>` | Directory layout |
| `eval_root` / `eval_allowed_dirs` | `evals` / `graders metrics pipelines reports utils` | Eval-suite layout |
| `enable_structure_guard` | on only for `eval_suite`/`rag` shapes | Canonical eval-suite directory enforcement |
| `has_corpus_pipeline` | `lg_agent`/`both` present, or `include_rag_agent` | Ships `core/pipelines/corpus/` + `data/corpus/` + the retrieval golden-QA eval + `tests/unit/core/`; off = empty `core/` ETL home |
| `enable_postgres_checkpointer` | `vector_backend=postgres` or `agent_memory=long_term` | Adds `langgraph-checkpoint-postgres`; runtime default stays `memory` either way |
| `python_version` / `aws_region` | `3.12` / `eu-central-1` | pyproject floor / Terraform default region |
| `mcp_server_name` / `mcp_server_slug` | `<project_slug>` | MCP server naming. `mcp_server_slug` is the seed for `py_mcp_server_slug` / `ts_mcp_server_slug` — the chosen language renders at the real slug, the other gets an `__unchosen_*` suffix that `_tasks` prunes |
| `expensive_command_patterns` | *(blank)* | Regex for commands that should nudge `--dry-run`; blank disables the hook |
| `include_agent_reference_library` | `false` | `.agents/skills/` (ADK + LangGraph reference library) + `/new-agent` — opt in for offline/team-portability; canonical home stays this template |
| `global_skills_source` | `vendored` | Maintainer knob — `vendored` ships the payload in `template/.claude/skills/`, `none` strips it at render. The payload is now maintained by hand: `tools/template/sync-global-skills.sh` was retired 2026-08-11 when global stopped being the skill reservoir. |

## Repository layout

Only `template/` is rendered into target projects (`_subdirectory: template`); everything else is
template-maintainer material.

| Path | What it is |
|---|---|
| `copier.yaml` | The whole interview + derivation logic + `_tasks` post-processing. The comments in it are load-bearing — read them before changing any toggle. |
| `template/CLAUDE.md.jinja`, `DESIGN.md.jinja`, `LIFECYCLE.md.jinja`, `DEPLOYMENT.md.jinja`, `DELIVERY.md.jinja`, `RELEASE.md.jinja`, `design.yaml.jinja` | Rendered to the project root in every mode (including layering-only). LIFECYCLE.md is the phase/gate status contract maintained by `/gate-check` and read by DSSG's project-mgmt-ai; DEPLOYMENT.md is the Phase-3 runbook (staged rollout, rollback, monitoring), pre-flighted by `/deploy-check`; DELIVERY.md and RELEASE.md cover delivery process and release notes. |
| `template/.claude/` | Hooks, skills, agent defs, settings — the always-on Claude tooling tier. Ships in every mode. |
| `template/.agents/` | Tool-agnostic ADK/LangGraph reference library (`include_agent_reference_library`). |
| `template/mcp_servers/` | Python FastMCP server scaffold (`include_mcp_server`); swapped for the TS tree when `mcp_server_language=typescript`. |
| `template/_scaffold/` | **Staging dir** for the full-project tier. Copier renders it verbatim, then `_tasks` prunes unselected features and `mv`s the survivors to the project root. Never collides with a pre-existing repo — layering-only mode discards it wholesale. |
| `template/_scaffold/configs/` | Environment config files (dev.yaml, prod.yaml) — rendered into project root by `_tasks`. |
| `tools/template/` | Maintainer utilities (see `tools/template/README.md`). |
| `.claude/docs/` | This repo's own plan/research docs (local-only, git-ignored by policy). |
| `.github/workflows/test-render.yml` | CI render matrix — leftover-Jinja + ruff checks per config. |

## Design notes

- Everything here was extracted from `playground/.claude/`, stripped of client- and domain-specific
  content (no client names, no music-KB domain logic, no project package paths).
- Unlike `ds-python-project-template`, there's no `git init`/initial-commit task — this template is meant
  to be layered onto a project that may already exist and already have its own git history.
- All Python-stack assumptions (`uv`, `pytest`, `ruff`, `pyright`) are load-bearing defaults, not yet
  optional — this template currently targets Python (+ optional TypeScript) projects.
- Rendered projects plug into a machine-level review ladder if present (workspace Makefile +
  global `/review-sweep`, refs, and agent defs in `~/.claude/`) — the template ships only the
  per-repo halves: Makefile lint/test targets and `Refs:` lines in CLAUDE.md.
