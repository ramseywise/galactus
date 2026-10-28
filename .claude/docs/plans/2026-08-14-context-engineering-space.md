# Context engineering space — skills, agents, hooks, specs

Status: EXECUTED
Review: pending
Track: agent
Issue: #4 (phase 3)
Branch: GAL-3-leakage-unrun-not-clean

> **Executed 2026-08-14.** Two research-stage conclusions were revised during execution,
> both by reading the skills rather than the plan's summary of them:
>
> 1. **FRAME is four skills, not six.** `design-sprint` and `design-initiative` were
>    archived, not wired. Both are the PM/roadmap lens — a role galactus does not have —
>    and `design-initiative` terminates in `/doc-to-linear-tickets`, which does not exist
>    in this repo. See `.claude/skills/archived/`.
> 2. **FRAME's order is discovery → scope → genesis**, not discovery → genesis → scope as
>    the band diagram below shows. The skills agree with each other on this
>    (`project-discovery` names the chain explicitly); the diagram was wrong.
>
> The routing table that shipped is in `CLAUDE.md`, and it is authoritative over the
> draft table below.

## Purpose

Galactus has 34 skills, 4 agents, 10 hooks, and 16 specs. Only two of those four
surfaces are wired to anything. This doc names the shape the four surfaces make
together, gives the unwired skills an entry point, and resolves the
`design-prototype` retirement question the tooling ledger left open.

---

## Research

### The finding that reframes everything

**There is no galactus session directory.** `~/.claude/projects/` holds dirs for
`workspace`, `guacamayo`, `ai-project-template`, `librarian`, `dssg`, `forecast`,
`puffin`, `job-system` — and none for galactus. Every galactus skill has a
lifetime invocation count of zero because **no session has ever run in this repo**,
not because the skills were tried and abandoned.

Galactus is 5 days old: first commit 2026-08-09, 38 commits total.

### The ledger row is void, not pending

`guacamayo/.sounding/tooling-ledger.md` carries:

> 2026-07-30 | R6 F6: design-* skills (sprint/initiative/milestones/prototype) —
> 0 invocations across 261 sessions / 3 retro windows; decision: retire (a),
> consolidate (b), or document (c) | workflow |
> `presence:design-skill-invoked within 3 design-heavy sessions OR
> documented-retirement in log` | hypothesis — pending Ramsey decision | due 2026-08-17

Three independent defects:

1. **Wrong population.** The 261 sessions were guacamayo and workspace sessions,
   where `workflow-*` is the correct pipeline and `design-*` is not installed.
   Measuring galactus skills against guacamayo sessions is a category error.
2. **Predates the repo.** The row was written 2026-07-30; galactus's first commit
   is 2026-08-09. All three retro windows closed before the skills had a home.
3. **Unsatisfiable metric.** `design-prototype`, `design-sprint`,
   `design-initiative`, `design-system`, `fog`, `war-game`, `assumption-audit`,
   `ml-select`, `ml-transform`, and all five `proto-*` skills carry
   `disable-model-invocation: true`. They *cannot* self-trigger; they run only when
   typed. `presence:design-skill-invoked` can never be satisfied by model
   invocation, which is what the metric counts.

**Decision: void the row.** Do not action (a)/(b)/(c) on 2026-08-17 — the evidence
behind the choice does not support any of them. Replace with a metric measured in
galactus sessions after the dogfood run (see Verification).

### Real invocation data (whole transcript corpus)

Counted via `"skill":"<name>"` in tool calls plus `<command-name>/<name>`, across
every project dir:

| Skill | Invocations | Home |
|---|---|---|
| `workflow-plan` | 45 | guacamayo |
| `workflow-research` | 39 | guacamayo |
| `workflow-refine` | 38 | guacamayo |
| `workflow-review` | 31 | guacamayo |
| `workflow-execute` | 22 | guacamayo |
| `grow` / `dream` / `wake` | 20 / 12 / 7 | guacamayo |
| `proto-*` (all five) | 1 each, at most | galactus |
| every `review-*` | 0 | galactus |
| every `design-*`, `project-*`, `scope-poc` | 0–1 | galactus |

The guacamayo pipeline is heavily exercised. The galactus pipeline is not
exercised at all. **These are the same lineage at two different ages**, not a
working tool and a failing one.

### The four surfaces today

**Skills (34)** cluster into four groups with very different wiring:

- **`proto-*` (5)** — research → plan → refine → execute → review. The only
  cluster CLAUDE.md's pipeline table documents. Wired.
- **`review-*` (12)** — dimension skills, each loaded by one dispatch of the
  generic `review.md` agent, N in parallel from `/proto-review`. Wired, and the
  cleanest architecture in the repo: one generic agent, N swappable remits.
- **Frame skills (6)** — `project-discovery`, `project-genesis`, `scope-poc`,
  `design-sprint`, `design-initiative`, `design-system`. **Unwired.** Nothing in
  CLAUDE.md routes to them and `disable-model-invocation` stops them routing
  themselves.
- **Cross-cutting reasoning (4)** — `fog`, `war-game`, `assumption-audit`,
  `decide-shared`. **Unwired**, and structurally different from the rest: they
  consume an artifact and emit a judgment rather than producing a work product.
  `decide-shared` says so in its own first heading: *"Capability, not phase."*

Plus 3 utilities (`docs-check`, `new-agent`, `skill-creator`, `mcp-builder`) and
2 ML helpers (`ml-select`, `ml-transform`).

**Agents (4)** — `review` (generic, one dimension per dispatch),
`fog-advisor` (worst-plausible-case, deliberately denied the author's
justification), `plan-research-scout` (breadth-first fan-out),
`wander` (asks questions, returns questions not findings). All `model: haiku`,
all read-only tools. The `skills:` frontmatter field is how an agent binds to a
contract — `review` → `review-shared`, `fog-advisor` → `decide-shared`.

**Hooks (10)** — split by enforcement strength:
- *Blocking*: `destructive_cmd_guard`, `pip_guard`, `secrets_scan` (PreToolUse);
  `task_complete_check` (Stop — blocks until lint + tests pass).
- *Validating*: `plan_status_validate` (PostToolUse — rejects `Status:` outside
  `RESEARCH → RESEARCHED → PLANNED → REFINED → READY → IN_PROGRESS → EXECUTED →
  COMPLETE` + `SUPERSEDED`, and `Track:` outside `{ml, agent}`).
- *Advisory*: `function_complexity_warning`, `docs_hygiene`, `docs_drift_warn`,
  `todo_write_nudge` (always exit 0).

**Specs (16)** — `agent-*` convention refs (11) + stack bindings (`python`,
`typescript`, `langgraph`, `google-adk`, `adk-vercel`). Read-on-demand, indexed by
`agent-architecture.md` against the five-layer stack. This surface is healthy.

### The actual gap

The gap is **not** a missing skill. It is a missing *band* in the documented
pipeline, and a missing *invocation model* for skills that aren't phases.

CLAUDE.md's pipeline table starts at Design → `/design-system`. But six skills form
a real sequence *before and around* that entry, and the table names only one of
them. They are not redundant with each other:

- `project-discovery` — intake interview, org/pain-point/archetype profile
- `project-genesis` — repo scaffold, re-entrant
- `scope-poc` — DESIGN.md: problem, success criteria, actors, C4 L1, MVP scope
- `design-sprint` — blank-page problem framing (IDEO-style), PM lens
- `design-initiative` — milestones then task backlog, PM+EM lens
- `design-system` — requirement → agent system spec across five layers, then stress

That is intake → scaffold → scope → frame → break-down → spec. Six distinct
outputs. They read as "dead" only because no document points at them.

Separately, `fog` / `war-game` / `assumption-audit` share a stage structure —
extract, find the load-bearing ones, dispatch isolated adversaries, merge, rank —
and all attack an artifact rather than produce one. Slotting them into a phase is
the wrong model; they need to be invocable *at* any phase.

### `design-prototype` — the substance

Unique and worth keeping:
- The **ML-vs-agentic routing rule**, including the asymmetric-cost argument:
  the standard loop has no stage that catches a leak, so an ML problem routed to
  it yields a confident metric nobody checked, while an agentic problem routed to
  the ML variant merely runs a profiling stage that finds nothing. Explicitly
  *"do not default to the agentic path to resolve the ambiguity."*
- The **ML quick-start variant** — profiling before framing; baseline metric plus
  passing leakage check as the stage-4 contract.

Overlapping and not worth keeping standalone:
- Default mode ("clarify the question, write minimum code, observe, document,
  decide adopt/adapt/discard") is what `proto-research` → `proto-plan` already do.
- Its own Output section hands off to `/proto-plan` → `/proto-execute`.
- CLAUDE.md's pipeline table does not list it.

**Verdict: partial fold.** The routing rule and ML variant move into
`proto-research` (which owns the front of the build band and currently has no
track-routing logic, despite `Track: {ml, agent}` already being a validated plan-doc
field). The rest retires. This is the ledger's option (b), reached on evidence the
ledger row did not have.

---

## The design

### Four bands, one bus

```
FRAME    /project-discovery → /scope-poc → /project-genesis    [order corrected]
         /design-system                    [design-sprint, design-initiative archived]
              ↓ writes DESIGN.md + the spec
BUILD    /proto-research → /proto-plan → /proto-refine → /proto-execute
              ↓ plan doc is the bus; Status: is the state machine
REVIEW   /proto-review → review.md agent ×N (12 review-* dimensions, parallel)
              ↓ verdict against ## Plan
CROSS    /fog  /war-game  /assumption-audit     ← any artifact, any band
```

The plan doc in `.claude/docs/plans/` remains the bus between BUILD phases, with
`Status:` as the hook-validated state machine. FRAME's output (DESIGN.md, the
system spec) is the input to `proto-research`, not a plan doc — that is the seam
that currently has no name.

### Rules the design adds

1. **FRAME is a band, not a phase.** Its six skills are entered by intent, not in
   fixed order. `project-discovery` and `project-genesis` run once per project;
   `scope-poc`, `design-sprint`, `design-initiative`, `design-system` run per
   initiative. CLAUDE.md gets a routing table (below), which is the entry point
   they currently lack.

2. **CROSS skills are capabilities.** They take an artifact — plan, spec,
   DESIGN.md, diff — and return a judgment. They are never a pipeline step and
   never write the artifact they attack. `decide-shared` is their shared contract,
   exactly as `review-shared` is for `review-*`.

3. **One generic agent per contract family.** `review.md` + `review-shared` is the
   pattern that works; `fog-advisor` + `decide-shared` already follows it. Do not
   add per-dimension agents (that is the previous generation still sitting in
   guacamayo's `.claude/agents/`).

4. **`disable-model-invocation: true` is a deliberate choice, not a default.**
   It belongs on skills that spend real effort or write artifacts (all of FRAME,
   all of BUILD). It does *not* belong on CROSS skills — those are cheap,
   read-only, and are exactly what the model should be able to reach for when it
   notices a load-bearing assumption. **Change: drop the flag from `fog`,
   `war-game`, `assumption-audit`.** This is the one wiring change that converts
   three skills from unreachable to useful.

5. **Track routing enters at `proto-research`.** `Track: {ml, agent}` is already
   validated by `plan_status_validate.sh` but nothing sets it. `proto-research`
   absorbs `design-prototype`'s routing rule and becomes the writer of `Track:`,
   including the "when genuinely ambiguous, ask" clause and the asymmetric-cost
   default.

### CLAUDE.md routing table (replaces the current pipeline table)

| Band | Skill | Entered when | Writes |
|---|---|---|---|
| Frame | `/project-discovery` | new client/project, nothing exists | Project Profile |
| Frame | `/scope-poc` | profile exists, scope not yet pinned | `DESIGN.md` |
| Frame | `/project-genesis` | design agreed, repo does not exist | repo scaffold |
| Frame | `/design-system` | requirement → agent spec | five-layer spec |
| Build | `/proto-research` | spec exists, unknowns remain | `## Research`, `Track:` |
| Build | `/proto-plan` | research done | `## Plan` |
| Build | `/proto-refine` | plan written | `REFINED` / `READY` |
| Build | `/proto-execute` | plan is `READY` | code, flips `Status:` |
| Review | `/proto-review` | before first commit | verdict vs `## Plan` |
| Cross | `/assumption-audit` | any artifact with load-bearing guesses | ranked assumptions |
| Cross | `/war-game` | plan about to ship | attack findings + mitigations |
| Cross | `/fog` | design that must handle not-knowing | collapse sites |

### What changes, concretely

| Change | Surface | Effort |
|---|---|---|
| Add FRAME + CROSS bands to CLAUDE.md routing table | doc | S |
| Drop `disable-model-invocation` from `fog`, `war-game`, `assumption-audit` | skills | S |
| Fold `design-prototype` routing rule + ML variant into `proto-research`; retire the rest | skills | M |
| `proto-research` becomes writer of `Track:` | skill | S |
| Void the ledger row; open a galactus-measured replacement | guacamayo ledger | S |

Not changing: all 12 `review-*`, all 4 agents, all 10 hooks, all 16 specs. Those
surfaces are sound.

---

## Verification — dogfood on Issue #4 Phase 4

Phase 4 (dry-run modes) is the natural first exercise: mode 4a runs the
prototyping chain end-to-end and records where it breaks; mode 4b writes a real
poc. **Decision D2 is resolved: 4b may write to `pocs/`.** That unblocks Phase 4
from `PLANNED` to step-plannable.

Running Phase 4 against the redesigned space produces the first genuine galactus
invocation data — which is the metric the void ledger row was reaching for and
could never have obtained.

Replacement ledger row:

```
| 2026-08-14 | Galactus FRAME+CROSS bands wired; design-prototype folded into
proto-research | workflow | `presence:frame-or-cross-skill-invoked within 3
galactus sessions` | hypothesis — due 2026-09-14 |
```

Measured in galactus sessions only, against skills that can actually be reached.

## Open decisions

None blocking. D2 (Phase 4 may write to `pocs/`) resolved by operator 2026-08-14.
