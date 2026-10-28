# galactus

Contract-bounded LLM generation. `runs/ai/marketing-comms/` holds the reference implementation: a FastAPI
service that generates length-constrained marketing copy grounded in uploaded PDFs.

**Thesis:** counting characters is a job for code; the model's job is content.

## Stack

Python 3.12, `uv` (never `pip` — a hook blocks it), FastAPI, Pydantic v2, Anthropic SDK,
structlog. Tests live at `runs/ai/marketing-comms/tests/`, evals at `runs/ai/marketing-comms/evals/`.

```bash
uv sync                              # install
uv run pytest runs/ai/marketing-comms/tests -q           # tests
uv run python runs/ai/marketing-comms/evals/run.py --dry-run   # evals, no API spend
uv run uvicorn api:app --app-dir runs/ai/marketing-comms/src --port 8000   # serve the demo
```

## Specs

`.claude/specs/agent-*.md` are the convention refs — read the relevant ones **before**
writing agent code, not after. Each opens with a durable question it answers. Start with
`agent-architecture.md`; it indexes the rest against the five-layer stack.

`agent-uncertainty.md` cuts across all of them: what the system does when it does not
know. Read it alongside the layer ref, not instead of one — it owns abstention,
asymmetric cost, and reversibility, which no single layer does.

`agent-voice.md` applies only to duplex/streaming designs — audio flowing both directions
at once. Where it applies, read it *instead of* the §4 Loop guidance, not alongside: a
duplex loop has no turn boundary, so the loop rules are not stricter there, they are
inapplicable. Where the design is request → response → done, ignore it entirely.

`langgraph.md`, `python.md`, `typescript.md` are stack bindings — read after the
`agent-*` refs, never instead of them.

## The pipeline

Four bands. FRAME decides what to build, BUILD builds it, REVIEW judges it against the
plan, and CROSS attacks any artifact from any band.

| Band | Skill | Entered when | Writes |
|---|---|---|---|
| Frame | `/proto-scope discovery` | a pain point, no design vocabulary yet | Project Profile |
| Frame | `/proto-scope` | scope not yet pinned | `DESIGN.md` |
| Frame | `/proto-design` | a requirement needs an agent spec | five-layer spec |
| Build | `/proto-research` | spec exists, unknowns remain | `## Research`, `Track:` |
| Build | `/proto-plan` | research reviewed | `## Plan` |
| Build | `/proto-refine` | plan written | the only writer of `REFINED` / `READY` |
| Build | `/proto-execute` | plan is `READY` | code; flips `Status:` |
| Review | `/proto-review` | before the first commit | verdict against `## Plan` |
| Cross | `/assumption-audit` | any artifact resting on load-bearing guesses | ranked assumptions + cheapest check |
| Cross | `/war-game` | a plan about to ship | attack findings + mitigations + go/no-go |
| Cross | `/fog` | a design that must handle not-knowing | ranked collapse sites |

**FRAME is a band, not a sequence.** Entered by intent, not in fixed order. The chain when
starting from nothing is `/proto-scope discovery` → `/proto-scope` → `/proto-design`, but
a session that already has a `DESIGN.md` enters at `/proto-design`, and one that already
has a spec skips FRAME entirely.

**`/new` is the front door, before any band.** It routes AI vs ML and picks where the
work lands: a run (a subdirectory under `runs/ai/` or `runs/ml/`, which then enters FRAME)
or a standalone repo rendered from this repo's copier template (`copier.yaml` +
`template/`, Python or TypeScript). See `TEMPLATE.md` for the template itself.

`runs/_index/` is reserved for run records — one per training execution, a different grain
from the run directory that produced it, which is why the name is prefixed: `_index` can
never collide with a run. **Runs do not define the record shape.** It lives in the root
`experiments/` module, which the template also ships (`record`, `provenance`, `fingerprint`,
with a `NotApplicable` sentinel so a missing metric never reads as `0.0`); runs consume it.
Nothing writes here yet — a run's result currently lives as a `summary.json` under its own
`docs/`, which is why the lending baseline could be overturned but not reproduced.

**BUILD runs in order**, with the plan doc in `.claude/docs/plans/` as the bus between
phases. `Status:` is a state machine, not a label — a hook rejects values outside
`RESEARCH → RESEARCHED → PLANNED → REFINED → READY → IN_PROGRESS → EXECUTED → COMPLETE`
(plus `SUPERSEDED`). One work item per plan doc.

`Track:` is the other validated field — `ml` or `agent`. `/proto-research` is its only
writer, and it routes on what the work *fits*, not what it is called: fitting a model is
`ml`, calling one is `agent`. The tracks are not symmetric, so the ambiguous case is asked
rather than defaulted — an ML problem on the agent track produces a confident metric
nobody checked.

**CROSS skills are capabilities, not phases.** They take an artifact — plan, spec,
`DESIGN.md`, diff — and return a judgment. They never write the artifact they attack, never
appear as a pipeline step, and **never touch `Status:`** — they write to
`.claude/docs/decisions/`, a different tree from the one `plan_status_validate.sh` guards,
so the state machine cannot be tripped by a capability. They are also the only skills the
model may reach for on its own: cheap, read-only, and exactly what should be available the
moment a load-bearing assumption shows up. `decide-shared` is their shared contract, as
`review-shared` is for the thirteen `review-*` dimensions.

**Tools, called from inside a band.** These are not phases and have no position:

| Skill | Called by | Does |
|---|---|---|
| `/ml-transform` | `/proto-research` on `Track: ml` | Profiles a frame; emits the ColumnPlan. Advisory — never transforms silently |
| `/ml-select` | `/proto-research` on `Track: ml` | The `(family, output)` pair + training config. Refuses to run before profiling |
| `/new-agent` | `/proto-execute` | Scaffolds an ADK or LangGraph agent |
| `/template-update` | inside a generated project | Walks a `copier update` from this template |
| `/mcp-builder` | `/proto-execute` | Reference for writing an MCP server. Vendored; carries its own LICENSE |
| `/proto-harden` | after `/proto-execute`, before `/proto-review`; or any run about to demo | Walks the marketing-comms hardening checklist against a run dir and fixes gaps in-session. Never touches `Status:` |
| `/skill-creator` | any | Creates or edits a skill in this repo |

Retired skills live in `.claude/skills/archived/`, one `ARCHIVED.md` each explaining what
moved where and what is worth reviving. They are one directory below where the loader
looks, so they are not invocable.

## Rules

- **`uv add`, never `pip install`.** Enforced by `pip_guard.sh`.
- **Never commit on `main`.** Work happens on `{PREFIX}-{NUM}-{slug}`, `bug/{slug}`, or
  `spike/{slug}`.
- **Runs under `runs/` are working code, not frozen exhibits.** Refactor, fix, and bring
  them to convention like anything else here. `runs/ai/marketing-comms/` is the reference
  implementation, so changes to it should be deliberate and keep its 318 tests green —
  but "it is the case study" is not a reason to leave drift in place.
- **A new test directory under `runs/` must be added to `testpaths` in `pyproject.toml`.**
  Omitting it does not fail; it collects zero tests, which reads exactly like passing.
- **A rule you rely on belongs in a hook, not here.** This file is a table of contents.
  If an agent can ignore a line here with no consequence, that line is documentation —
  encode it at the strongest available layer instead (hook > linter > test > tool schema
  > instruction).

## Vendoring exception

`.claude/skills/` and `.claude/specs/` deliberately duplicate names from the operator's
global `~/.claude/`. Normally that is a double-load blocker. Here it is intentional:
galactus is a self-contained showcase — anyone who clones it gets a working setup with no
access to a private home directory. **Canon remains `~/.claude/`;** the copies here are
rendered payload. Fix generic skills upstream, then re-vendor.

**`.claude/hooks/` is payload too — and unlike the skills, it is payload that does not
run.** `settings.json` registers hooks as `$CLAUDE_PROJECT_DIR/.claude/hooks/<name>`, and
in this workspace `~/workspace/.claude` is a symlink to `~/.claude`. On a session rooted
at `~/workspace`, that path resolves to the operator's global hooks — never to the files
in this directory. A fresh clone of galactus gets the working setup the vendoring exists
for; here, editing `.claude/hooks/` changes nothing at runtime.

This is the root of galactus#20: the global copies were behind, and the repo-local ones
everybody was editing were never invoked. **Fix a hook in `~/.claude/hooks/` first, then
re-vendor, and keep the two byte-identical.** Parity is enforced by
`hook_parity_check.sh` (fires once per session on `UserPromptSubmit`), which iterates
the vendored set and warns on any `cmp` mismatch or missing global counterpart.
