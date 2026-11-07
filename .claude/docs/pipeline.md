# The pipeline — bands, state machine, tools

Reference detail moved out of `CLAUDE.md` on 2026-11-07, so it no longer loads into every
session. `CLAUDE.md` holds the routing table that decides *whether* to enter this pipeline.
This file describes how the pipeline works once you are in it.

Four bands. FRAME decides what to build, BUILD builds it, REVIEW judges it against the
plan, and CROSS attacks any artifact from any band.

| Band | Skill | Entered when | Writes |
|---|---|---|---|
| Frame | `/proto-scope discovery` | a pain point, no design vocabulary yet | Project Profile |
| Frame | `/proto-scope` | scope not yet pinned | `DESIGN.md` |
| Frame | `/proto-design` | a requirement needs an agent spec | five-layer spec |
| Build | `/proto-build` | any of the BUILD rows below, routed for you | drives the phases in Sonnet workers; never writes `READY` itself |
| Build | `/proto-research` | spec exists, unknowns remain | `## Research`, `Track:`; grounds findings in the course via Librarian (`### Course grounding`, hook-enforced at `RESEARCHED`) |
| Build | `/proto-plan` | research reviewed | `## Plan` |
| Build | `/proto-refine` | plan written | the only writer of `REFINED` / `READY` |
| Build | `/proto-execute` | plan is `READY` | code; flips `Status:` |
| Review | `/proto-review` | before the first commit | verdict against `## Plan` |
| Cross | `/assumption-audit` | any artifact resting on load-bearing guesses | ranked assumptions + cheapest check |
| Cross | `/review-defense` | a plan about to ship | attack findings + mitigations + go/no-go (global; owned by guacamayo) |
| Cross | `/fog` | a design that must handle not-knowing | ranked collapse sites (global; owned by guacamayo) |

**Who can call what.** The phase skills (`proto-design`, `-research`, `-plan`, `-refine`,
`-execute`, `/new`, `ml-*`) carry `disable-model-invocation: true`: you type them, or
`/proto-build` hands them to a `proto-worker` agent, which reads the `SKILL.md` and
follows it. `/proto-build` is the one BUILD entry Claude reaches for on its own. CROSS
skills, `/proto-review`, `/proto-harden`, `/spike` and `/proto-scope` are model-visible.

**FRAME is a band, not a sequence.** Entered by intent, not in fixed order. The chain when
starting from nothing is `/proto-scope discovery` → `/proto-scope` → `/proto-design`, but
a session that already has a `DESIGN.md` enters at `/proto-design`, and one that already
has a spec skips FRAME entirely.

**`/new` is the front door, before any band.** It routes AI vs ML and picks where the
work lands: a run (a subdirectory under `runs/ai/` or `runs/ml/`, which then enters FRAME)
or a standalone repo rendered from this repo's copier template (`copier.yaml` +
`template/`, Python or TypeScript). See `TEMPLATE.md` for the template itself.

**`/spike` is the side door.** One question, a `spike/*` branch, no plan doc and no bands,
then one light review. The plan-doc hooks stand down on `spike/*`; the guards and the Stop
hook do not. Graduating a spike means entering FRAME with it as evidence.

`runs/_index/` is reserved for run records — one per training execution, a different grain
from the run directory that produced it, which is why the name is prefixed: `_index` can
never collide with a run. **Runs do not define the record shape.** It lives in the root
`experiments/` module, which the template also ships (`record`, `provenance`, `fingerprint`,
with a `NotApplicable` sentinel so a missing metric never reads as `0.0`); runs consume it.
Nothing writes here yet — a run's result currently lives as a `summary.json` under its own
`docs/`, which is why the lending baseline could be overturned but not reproduced.

## BUILD and the state machine

**BUILD runs in order**, with the plan doc in `.claude/docs/plans/` as the bus between
phases. `Status:` is a state machine, not a label — a hook rejects values outside
`RESEARCH → RESEARCHED → PLANNED → REFINED → READY → IN_PROGRESS → EXECUTED → COMPLETE`
(plus `SUPERSEDED`). One work item per plan doc.

Hook rules a writer trips over:

- A **new** plan doc must not carry `From:` — there is no prior state to come from.
- Every later `Status:` change should declare `From: <prior>`; the PreToolUse hook checks
  it against the state on disk, the PostToolUse hook against the legal-edge table.
- `RESEARCHED` requires `### Course grounding` under `## Research`.
- `EXECUTED` requires `Review:`; `COMPLETE` requires `Review: passed` and `Completed:`;
  `SUPERSEDED` requires `Superseded-by:`.

`Track:` is the other validated field — `ml` or `agent`. `/proto-research` is its only
writer, and it routes on what the work *fits*, not what it is called: fitting a model is
`ml`, calling one is `agent`. The tracks are not symmetric, so the ambiguous case is asked
rather than defaulted — an ML problem on the agent track produces a confident metric
nobody checked.

## CROSS

**CROSS skills are capabilities, not phases.** They take an artifact — plan, spec,
`DESIGN.md`, diff — and return a judgment. They never write the artifact they attack, never
appear as a pipeline step, and **never touch `Status:`** — they write to
`.claude/docs/decisions/`, a different tree from the one `plan_status_validate.sh` guards,
so the state machine cannot be tripped by a capability. `decide-shared` is their shared
contract, as `review-shared` is for the eleven review dimensions, which live in it as
reference files (`review-shared/dimensions/`), not as skills.

## Tools, called from inside a band

These are not phases and have no position:

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

## Agents

| Agent | Model | Dispatched by | Does |
|---|---|---|---|
| `proto-worker` | sonnet | `/proto-build` | Runs one BUILD phase per dispatch; returns a fixed short report |
| `research-scout` | haiku | `/proto-research fan-out`, routing table | One research angle, one findings file |
| `review` | haiku | `/proto-review` | One review dimension per dispatch |
| `wander` | haiku | `/proto-review` | Questions, not findings |
| `fog-advisor` | haiku | `/fog` | Worst-plausible-case pass, without the author's rationale |
