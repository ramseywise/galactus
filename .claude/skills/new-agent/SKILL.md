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
| `--framework` | ask via `framework-selection` | `adk` or `langgraph`. A duplex/voice design is not scaffolded here — see Step 2. |
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

Read `~/workspace/galactus/.claude/skills/framework-selection/SKILL.md` and walk its decision table with
the user, or infer from project context (existing agent code, deployment target
mentioned) and confirm before proceeding. Do not silently default.

**If the answer is realtime/duplex, stop scaffolding.** This skill produces a
request/response agent, and its templates assume a turn that ends. A duplex design
needs a voice runtime that owns turn-taking and barge-in; what this skill can scaffold
is the *graph behind it*, called per finalized turn — so pick that framework from the
same table and scaffold only that half, saying plainly which half is missing. Read
`~/workspace/galactus/.claude/specs/agent-voice.md` before designing the audio loop.

### Step 3 — Scaffold

**If framework == `adk`:**
1. Read `~/workspace/galactus/.claude/skills/adk-scaffold/SKILL.md` and follow it exactly — it drives
   requirement-gathering, `DESIGN_SPEC.md`, and the `agent-starter-pack` CLI invocation.
2. Then read `~/workspace/galactus/.claude/skills/adk-dev-guide/SKILL.md` for the development workflow
   before writing any agent logic.

**If framework == `langgraph`:**
1. Read `~/workspace/galactus/.claude/skills/langgraph-scaffold/SKILL.md` and follow it — it drives
   requirement-gathering, `DESIGN_SPEC.md`, and the file scaffold.
2. Read `~/workspace/galactus/.claude/skills/langgraph-fundamentals/SKILL.md` before writing graph code.
3. If the spec calls for cross-turn memory, also read
   `~/workspace/galactus/.claude/skills/langgraph-persistence/SKILL.md`.
4. If the spec calls for approval/pause-for-input steps, also read
   `~/workspace/galactus/.claude/skills/langgraph-human-in-the-loop/SKILL.md`.

### Step 4 — Apply capability templates

Before generating a capability, look for a worked example. If it maps to a pattern from the manifest vocabulary
(`retrieval`, `judge`, `loop`, `graph`, `tool-agent`, `guardrail`, `budget`, `finetune`, `eval`),
read `<pillar>/practice/manifest.yaml` from the course checkout at
`${LEARN_AI_DIR:-~/workspace/learn-ai-engineering}`, using `search_wiki(query, domain="course")` to find
the pillar when it is not obvious. Take the entry with the matching `pattern` and, among twins, the
project's `language`. When its `verified_by` is not `none`, start from its `path` (relative to the pillar;
`verified_by` runs from its `practice/` folder). That is a reference to start from: only `licence: course`
code may be copied, and even that has no stated licence yet, so never present it as free to redistribute.
If the checkout or Librarian is absent, say so and proceed.

When a `references/cap-*.md` ref has a `## Start here` section, start from the example it links and move to
the ref's templates only when its `Go further only if` condition holds.

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

Blank templates for agents that run across sessions or in a loop. Fill them in only when the design calls for one:

| Reference | Use |
|-----------|-----|
| `references/harness/` | Startup script, feature list and schema, progress log, session handoff |
| `references/loop/` | Maker and checker prompts, loop contract, loop state |
| `references/generate-then-verify.py` | LangGraph generate, validate, review graph with an attempt bound |

Keep the source comment on anything copied from these. `references/THIRD_PARTY.md` lists origins and licences.

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
