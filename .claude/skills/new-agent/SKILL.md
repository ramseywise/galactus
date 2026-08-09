---
name: new-agent
description: >
  Scaffold a new AI agent — Google ADK or LangGraph. Decides the framework (via
  framework-selection, if not specified), then scaffolds using references/.
  Triggers on: "scaffold a new agent", "build me an agent for X", "new ADK agent",
  "new LangGraph agent", "/new-agent <name>".
---

# /new-agent

Orchestrator — all framework-specific knowledge and code templates live in
`references/` (sibling to this file). Capability specs (`cap-*.md`) are code-generation
templates; framework/scaffold docs are workflow guides.

## Usage

```
/new-agent <name> [--framework adk|langgraph] [--domain <string>] [--output path/to/dir]
```

| Arg | Default | Description |
|-----|---------|-------------|
| `<name>` | required | snake_case agent name, e.g. `order_support`, `insights_agent` |
| `--framework` | ask via `framework-selection` | `adk` or `langgraph` |
| `--domain` | `general` | Free-form label injected into prompts/README |
| `--output` | framework default (see below) | Override the output directory |

## Steps

### Step 1 — Parse arguments

- Validate `name` matches `^[a-z][a-z0-9_]*$` — error if not.
- If `--framework` is missing, don't guess — go to Step 2.
- If `--output` is missing, let the framework-specific scaffold pick its own
  default (ADK: `agent-starter-pack`'s project-directory convention; LangGraph:
  typically `{source_root}/agents/{name}` — confirm the source directory name from
  the project layout if it isn't obvious).

### Step 2 — Decide the framework (if not given)

Read `references/framework-selection.md` and walk its decision table with
the user, or infer from project context (existing agent code, deployment target
mentioned) and confirm before proceeding. Do not silently default.

### Step 3 — Scaffold

**If framework == `adk`:**
1. Read `references/adk-scaffold.md` and follow it exactly — it drives
   requirement-gathering, `DESIGN_SPEC.md`, and the `agent-starter-pack` CLI invocation.
2. Then read `references/adk-dev-guide.md` for the development workflow
   before writing any agent logic.

**If framework == `langgraph`:**
1. Read `references/langgraph-scaffold.md` and follow it — it drives
   requirement-gathering, `DESIGN_SPEC.md`, and the file scaffold.
2. Read `references/langgraph-fundamentals.md` before writing graph code.
3. If the spec calls for cross-turn memory, also read
   `references/langgraph-persistence.md`.
4. If the spec calls for approval/pause-for-input steps, also read
   `references/langgraph-human-in-the-loop.md`.

### Step 4 — Apply capability templates

For each capability the agent needs, read the matching `references/cap-*.md` and
generate the corresponding files. Available capabilities:

| Reference | Capability |
|-----------|-----------|
| `cap-rag.md` | Retrieval-augmented generation |
| `cap-kg.md` | Knowledge graph (Neo4j) |
| `cap-search.md` | Web/agentic search |
| `cap-a2a.md` | Agent-to-agent protocol |
| `cap-batch.md` | Batch processing |
| `cap-cluster.md` | Clustering/segmentation |
| `cap-finetune.md` | Fine-tuning pipeline |
| `cap-forecast.md` | Forecasting/prediction |
| `cap-genai.md` | Generative AI patterns |
| `cap-hitl.md` | Human-in-the-loop |
| `cap-langchain.md` | LangChain integration |
| `cap-rlhf.md` | RLHF pipeline |
| `cap-streaming.md` | Streaming responses |
| `cap-vision.md` | Vision/multimodal |

### Step 5 — Core files + infra

Read and apply these references for every agent:
- `references/core.md` — schema, output contract
- `references/eval.md` — eval harness scaffold
- `references/test.md` — test scaffold
- `references/docs.md` — README and docs
- `references/infra.md` — deployment config

### Step 6 — Report

Report what was created (files written, commands run) and call out anything the
requirements-gathering step surfaced that the scaffold doesn't yet support — be
explicit, don't silently drop requirements.

## Notes

- ADK scaffolding delegates to Google's `agent-starter-pack` CLI (real, maintained
  tooling). LangGraph scaffolding is hand-written since no equivalent official CLI
  exists — expect to iterate on the generated files more than you would with ADK's
  `enhance` command.
- All `references/` paths are relative to this skill's directory. Claude Code
  resolves them automatically when the skill loads.
