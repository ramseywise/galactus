# Claude setup — from a typed pipeline to intent routing

Status: IN_PROGRESS
From: READY
Ready-by: Ramsey's go ("ok lets implement this", 2026-11-07); `/proto-refine` not run
Track: agent
Date: 2026-11-07
Issue: — (none yet)
Supersedes-in-part: `2026-08-14-pipeline-orchestration.md` (asked the same question, never
reached a plan; its F1–F4 findings still stand and are not repeated here)

Asked 2026-11-07 (Ramsey): the setup is behind guacamayo and kiez. Research → plan → refine
should not be a sequence the user types. Claude should know when a skill or a subagent is
worth it, and the main reason is token usage.

## Research

Inspected directly on 2026-11-07: galactus `.claude/` (skills, agents, hooks, settings,
plan corpus), guacamayo `.claude/` (the `workflow-*` orchestrators and their scouts), kiez
`.claude/`, `~/.claude/settings.json`, and `~/.claude/history.jsonl`.

### Course grounding

Not queried. The librarian MCP failed to connect this session (`CONNECTION_CLOSED`). This
is a tooling change, not an agent design, so the course has less to say than usual. Re-run
before `RESEARCHED` if the routing table (S3) is meant to cite course material.

### Findings

| # | Finding | Evidence | Confidence |
|---|---------|----------|------------|
| R1 | **Claude cannot reach any BUILD skill.** All 9 phase and track skills set `disable-model-invocation: true`, so they run only when typed. That makes "Claude knows when" impossible by construction | `proto-design`, `proto-research`, `proto-plan`, `proto-refine`, `proto-execute`, `new`, `ml-select`, `ml-transform` frontmatter. Only CROSS, `proto-review`, `proto-harden`, `spike` and `proto-scope` are model-visible | High |
| R2 | **There is no orchestrator.** Guacamayo solved this with two model-invocable drivers, `workflow-scope` (issue → READY) and `workflow-build` (READY → execute → review → fix, max 3 rounds). Each runs every stage as a Sonnet subagent, verifies the artifact on disk, retries once, then hands the decision back to the main model. Its phase skills stay `disable-model-invocation`, so the drivers are the only model-reachable entry | `guacamayo/.claude/skills/workflow-{scope,build}/SKILL.md`, agents `plan-refine-scout`, `build-scout` (`model: sonnet`) | High |
| R3 | **Every phase runs inline in the main (Opus) context.** One session doing research → plan → refine loads 254 + 182 + 360 lines of skill body, plus each phase's file reads, and carries all of it forward. `proto-execute` explicitly forbids subagents. Fan-out exists only as an opt-in (`proto-research fan-out`), in review (one dispatch per dimension), and in refine's failure pass | `proto-execute/SKILL.md:8`; `proto-research/SKILL.md:186-200` | High |
| R4 | **There is no mid-tier worker agent.** All 4 galactus agents are Haiku reporters: `review`, `wander`, `fog-advisor`, `research-scout`. Nothing is suited to running a whole phase. Guacamayo has two Sonnet workers | `.claude/agents/*.md` frontmatter | High |
| R5 | **Every session pays a fixed cost for things this repo does not use.** The global `vercel` and `figma` plugins add about 60 skill descriptions to every session in a Python repo. CLAUDE.md is 9.4 KB (about 2.4k tokens), and most of it describes the pipeline rather than routing. Five galactus descriptions are over 500 characters | this session's skill listing; `~/.claude/settings.json` `enabledPlugins`; `wc -c CLAUDE.md` | High (presence), Medium (size of the saving) |
| R6 | **Usage suggests nobody types the pipeline.** `history.jsonl` records one typed `/proto-*` call (it is partial, up to 2026-11-04). Guacamayo's drivers logged 14 scope and 3 build decisions, the last on 2026-08-20. Real work arrives as plain requests, like this one | `grep '/proto-' ~/.claude/history.jsonl`; `guacamayo/.sounding/telemetry/{scope,build}-decisions.jsonl` | Medium. History is incomplete |
| R7 | **The plan corpus is a backlog, not a record.** Of 34 docs, 16 are open (11 `PLANNED`, 2 `READY`, 1 `REFINED`, 1 `IN_PROGRESS`, 1 `RESEARCH`), some open since August. Any skill that globs `plans/` reads stale intent | `grep -m1 '^Status:' .claude/docs/plans/*.md` | High |
| R8 | **kiez shows the light end works.** It has no skills and no hooks. Its plan header is free-form: `Status: BUILT …`, `Lanes:`, and a one-paragraph `Done target:`. Ramsey ships steadily there. The part worth keeping is the done target; the state machine adds cost on small items | `kiez/.claude/docs/plans/2026-11-07-taste-itineraries.md` | Medium |
| R9 | **Docs have drifted.** CLAUDE.md names `/war-game`, which does not exist (it is `review-defense`, owned by guacamayo, symlinked globally). (Corrected 2026-11-07: "eleven review dimensions" is right; the twelfth file in `review-shared/dimensions/` is the vendored `contracts` violations reference.) `.claude/logs/hook-log.jsonl` (300 KB, gitignored) has not been written since 2026-08-14, because hook telemetry moved to `guacamayo/.sounding/telemetry`. A new plan doc must not carry `From:`; the hook rejects it, and nothing documents that | `CLAUDE.md`; `ls review-shared/dimensions`; `lib.sh:78`; `plan_transition_validate.sh` | High |
| R10 | **Advisory hooks add text on every edit.** Four PostToolUse hooks run on every Write/Edit. `docs_drift_warn` fires on any code edit with a README nearby. Whether it repeats itself within one session is not yet checked | `.claude/settings.json`; `docs_drift_warn.sh` | Low. Unmeasured |

### What is not the problem

- **The human seats are right.** `pipeline-orchestration.md` Q5 named them: goal
  elicitation (plan), the `READY` gate (refine is the only writer), track ambiguity
  (research asks), and the merge decision. Routing must route *around* the human as a
  message bus, never around these four seats.
- **The phase skills are not wrong.** They are the right content in the wrong place, the
  main context. Per the 2026-10-29 decision, `proto-*` and `workflow-*` stay separate
  tools. Port the driver pattern; do not adopt guacamayo's skills.

### Assumptions to check before building

- **A1.** A subagent can follow a `disable-model-invocation` skill by reading its
  `SKILL.md` directly, which is what guacamayo's scouts do. If the flag also blocks a
  `Read`-and-follow, S4 needs a different hand-off. Check: one dispatch in S5.
- **A2.** `enabledPlugins: {…: false}` in project `.claude/settings.json` overrides the
  global enable. Check: open a fresh session and look at the skill listing.
- **A3.** Sonnet workers produce phase artifacts that pass the hooks at a usable rate.
  Guacamayo's 17 logged decisions are too few to show it. S6 measures it.

## Plan

Based on: direct inspection (Research above). Order: S1 and S2 are independent, cheap
cleanups that land first. S3 to S5 are the routing change. S6 runs throughout. Everything
is staged only; Ramsey commits.

**S1. Fix the drift (R7, R9).**
- In CLAUDE.md and any skill that cites `/war-game`, change it to `/review-defense`. Fix
  the dimension count, or drop the number so it cannot drift again.
- `rm .claude/logs/hook-log.jsonl` (gitignored, orphaned).
- Triage the 16 open plans (R7) with Ramsey: each goes to `SUPERSEDED` (with
  `Superseded-by:`), stays open, or moves to `.claude/docs/plans/archive/`. Set
  `pipeline-orchestration.md` to `SUPERSEDED` → this doc.

Verify: `grep -rn war-game .claude CLAUDE.md` returns nothing outside `docs/`. The hook
accepts every Status edit.

**S2. Cut the fixed per-session cost (R5, R10).**
- Disable `vercel` and `figma` in project `.claude/settings.json` (A2).
- Rewrite skill descriptions longer than 350 characters so the trigger phrases come
  first and the mechanism is left to the body.
- Make `docs_drift_warn` fire at most once per README per session, using the same
  session-id stamp `todo_write_nudge` uses.

Verify: a fresh session's skill listing has no `vercel:*` or `figma:*` entries. Record
the description character totals before and after in this doc.

**S3. Replace the band narrative with an intent → action table (R6, R8).**
CLAUDE.md drops to about 5 KB. The full band and state-machine prose moves to
`.claude/docs/pipeline.md`, linked once. The table tells Claude what each kind of request
deserves and at what cost tier:

| Request looks like | Do | Tier |
|---|---|---|
| Clear bug with a repro; a rename; a one-file change | Just do it. No plan doc | inline |
| Unfamiliar area, several plausible approaches | `research-scout` fan-out, then summarise | Haiku ×N |
| Work spanning more than one session, or touching hooks, template, or the reference run | Plan doc via `/proto-drive` (S4) | Sonnet workers |
| A plan or spec resting on a guess | `/assumption-audit` | CROSS |
| A plan about to ship | `/review-defense` | CROSS |
| "Is this done?" before commit | `/proto-review` | Haiku ×dims |
| An afternoon thesis | `/spike` | inline |

The plan-doc threshold uses kiez's light header for small items (`Status`, `Done target`,
steps). `RESEARCH → PLANNED` is already a legal edge, so nothing in the hook changes.

**S4. Add `/proto-drive`, a model-invocable orchestrator (R1, R2, R3).** Port
`workflow-scope`'s loop, written for galactus's state machine:
1. Assess the state from the plan doc on disk. `CLEAR` items skip research.
2. **Seat check in the main context:** ask the goal question, and the track question if
   ambiguous, *before* dispatching plan.
3. Dispatch each stage to `proto-worker` (S5). The prompt is the phase `SKILL.md` path,
   the plan path and the constraint. The worker returns the artifact path plus a summary
   of 15 lines or fewer, never file dumps.
4. Verify the artifact on disk (`Status:` advanced, section present). Retry once with the
   gap named, then resolve in the main context.
5. Stop at `REFINED`. Show the refine verdict, and write `READY` only on Ramsey's yes.

Phase skills keep `disable-model-invocation`, so they stay precise when typed by hand,
and `/proto-drive` is the one entry point Claude can reach. Its description lists the
triggers: "take this to ready", "plan this properly", "scope and plan".

A second step, after S6 shows the first works, is a build loop that ports
`workflow-build`: execute → `/proto-review` → fix, max 3 rounds, blockers escalated, never
commits. `proto-execute`'s "no subagents" rule stays for the step itself. The loop only
moves review and fix out of the main context.

Verify: run `/proto-drive` on one real open item from the S1 triage. The plan reaches
`REFINED` with every hook passing, and the main context holds summaries only.

**S5. Add the `proto-worker` agent (R4).** `model: sonnet`. Tools: Read, Grep, Glob, Bash,
Edit, Write, and the librarian read tools. One stage per dispatch. Its first instruction is
"read the SKILL.md you were given and follow it". It returns a fixed report: artifact
path, Status before → after, open questions. Settle A1 here first.

**S6. Measure, or do not claim the saving.** Log every `/proto-drive` route and verify
result to `.claude/logs/plan-transitions.jsonl`, which is live (78 rows). Add a tooling
ledger row via guacamayo `/track`: `ratio:` main-context tokens per work item, for driven
versus inline, from guacamayo's `sessions.db`. Keep the build loop only if the ratio
favours it after 5 items. Do not use a guessed threshold.

### Out of scope

- Merging `proto-*` into `workflow-*` (decided 2026-10-29: separate tools).
- The review-engine consolidation (`2026-10-30-review-engine-consolidation.md`).
- Changing the `Status:` state machine or its hooks.

### Open decisions for Ramsey

- **D1. Decided 2026-11-07:** `/proto-build`, matching `workflow-build` in the other
  repos. Read `/proto-drive` above as `/proto-build`.
- **D2.** Open. S1 plan triage: Claude proposed a disposition per doc (Execution log
  below); nothing has been changed except `pipeline-orchestration.md`.
- **D3.** Open. Defaulted to this repo only (reversible), pending the answer.

## Execution log

Branch `chore/claude-setup-intent-routing`, 2026-11-07. Staged, not committed.

**Deviations from the plan, decided while building:**
- **Refine and review run in the orchestrator's context, not in a worker.** A subagent
  cannot spawn subagents, and both phases dispatch their own (`fog-advisor`, the `review`
  reporters). Refine is also the READY gate, so it belongs next to the human. Research,
  plan, execute and fix go to `proto-worker`.
- **The build loop shipped with S4, not after S6.** One `-build` skill covers both
  halves. The second half only runs with `--to done` and after an explicit go, so it is
  opt-in per run. S6 can still argue for cutting it.
- **Routing uses the existing `review.cli derive-phases`** rather than a new state table.
  The only judgment left to the model is whether to skip research.
- **Route log is `.claude/logs/build-decisions.jsonl`, not `plan-transitions.jsonl`.**
  The latter is hook-owned and read by `transition-metrics`; a second row shape there
  would break it.
- **A1 resolved by construction:** `disable-model-invocation` gates the Skill tool, not
  `Read`. The worker reads the `SKILL.md` and follows it. It is still unproven in a live
  run (S4 verify).
- **S2 descriptions:** only model-visible skills were trimmed. Descriptions of
  `disable-model-invocation` skills never enter context, so trimming them saves nothing.
  Model-visible description total before: 6,685 chars.

| Step | State | Notes |
|---|---|---|
| S1 drift | done | `war-game` → `review-defense` in CLAUDE.md, decide-shared, assumption-audit, two specs; the claim-schema ID prefix is `RD-` (nothing emitted `WG-`). Orphan log removed. `review/` still calls the capability `war_game`; renaming it touches tests, so it is left |
| S1 triage | proposed | table below; `pipeline-orchestration.md` → `SUPERSEDED` |
| S2 cost | done | plugins off in project settings (A2 unverified until a fresh session); 8 descriptions rewritten to 182–274 chars; `docs_drift_warn` once per README per session (tested) |
| S3 routing | done | CLAUDE.md 9.4 KB → 5.8 KB; band and tool reference moved to `.claude/docs/pipeline.md` |
| S4 `/proto-build` | written | `.claude/skills/proto-build/SKILL.md`; not yet run on a real item |
| S5 `proto-worker` | written | `.claude/agents/proto-worker.md`; loads in the next session |
| S6 measure | open | needs a guacamayo `/track` row (gitignored `.sounding/`, Ramsey's call) and 5 driven items |

**Proposed triage (D2): nothing applied until Ramsey says so.**

| Doc | Now | Proposal | Why |
|---|---|---|---|
| `2026-08-10-ml-capability-parity` | IN_PROGRESS | supersede → `2026-08-18-ml-parity-consolidated` (or keep, blocked) | blocked on OQ8 and real data; the consolidated plan carries the execution |
| `2026-08-14-gal-14-observed-transitions` | PLANNED | verify, then close | the hook it plans exists (`plan_transition_validate.sh`) |
| `2026-08-15-fast-loop-borrowables` | RESEARCH | supersede → `2026-10-28-absorb-ai-project-template` | its source repo is being absorbed |
| `2026-08-15-gal-27-band-contract-hitl-gates` | REFINED | read against `/proto-build`, likely supersede → this doc | same HITL-gate and dispatch ground |
| `2026-08-18-ml-frame-sourcing` | PLANNED | keep, mark blocked | waits on auth to the licensed frames |
| `2026-08-20-resolve-capability-registry` | READY | verify, then close | `review.cli resolve-capability` exists |
| `2026-10-30-global-guard-hooks` | PLANNED | verify, then close | `~/.claude/settings.json` already runs both guards by absolute path |
| `2026-10-30-specs-canonical` | PLANNED | verify, then close | `~/.claude/refs/*` are symlinks into `.claude/specs/` |
| `2026-10-30-setup-hygiene` | PLANNED | keep | S2 (global settings) looks done; the CI repoint (S1) is still open |
| `2026-08-16-repo-hygiene-tracked-content`, `2026-10-28-absorb-ai-project-template`, `2026-10-30-review-engine-consolidation`, `2026-11-04-knowledge-grounded-prototyping`, `2026-11-04-prototyping-improvements-before-d1`, `2026-08-18-ml-parity-consolidated`, `2026-11-07-knowledge-graph-run-from-ontosmith` | various | keep | live work |

"Verify, then close" means confirm the work landed and set `SUPERSEDED` with
`Superseded-by:` naming the landing commit. `COMPLETE` needs `Review: passed`, which
these never got.
