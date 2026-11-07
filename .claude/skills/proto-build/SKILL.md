---
name: proto-build
description: "Drive one work item through BUILD without typing each phase: routes research → plan → refine, then (after Ramsey's go) execute → review → fix, running research/plan/execute/fix in Sonnet proto-worker agents so the main context holds summaries only. Triggers: 'take this to ready', 'plan this properly', 'build this', 'scope and plan', 'execute and review', '/proto-build <slug|plan-path>'."
allowed-tools: Read Grep Glob Bash Edit Write Agent AskUserQuestion
---

# /proto-build

The BUILD orchestrator. The phase skills stay the procedure; this skill decides which one
runs next, runs it in the cheapest place, checks the artifact on disk, and stops at the
human seats. It is the only BUILD entry Claude reaches for on its own — the phase skills
carry `disable-model-invocation`.

**Where each phase runs, and why:**

| Phase | Runs in | Why |
|---|---|---|
| research | `proto-worker` (sonnet) | reading-heavy; only the conclusion matters here |
| plan | `proto-worker` (sonnet) | after the goal seat is answered here |
| refine | **this context** | it is the READY gate, and it dispatches `fog-advisor` (a worker cannot nest agents) |
| execute | `proto-worker` (sonnet) | edit-heavy; after Ramsey's go |
| review | **this context**, via `/proto-review` | it fans out to `review` agents itself |
| fix | `proto-worker` (sonnet) | bounded by the findings list |

## Usage

```
/proto-build <slug | plan-path>          # route from whatever state the doc is in
/proto-build <slug> "<one-line ask>"     # no doc yet: create it, then route
/proto-build <slug> --to ready           # stop after refine (default)
/proto-build <slug> --to done            # continue through execute → review after the go
```

## Step 0 — Is this BUILD at all?

Check the routing table in `CLAUDE.md` first. A one-file fix, a rename, or a question
does not get a plan doc — say so and just do it. No design yet → `/proto-scope`. An
afternoon thesis → `/spike`. Only continue when the work spans sessions or touches hooks,
`template/`, or the reference run.

## Step 1 — Locate or create the plan doc

Resolve a slug to `.claude/docs/plans/YYYY-MM-DD-<slug>.md`. If none exists, create it
with **no `From:` line** (the hook rejects `From:` on an origin write):

```
# <title>

Status: RESEARCH
Date: <today>
Done target: <one paragraph — what is true when this is finished>
```

## Step 2 — Assess state deterministically

Do not read the state by eye. Ask the router:

```bash
python3 -c "import json,sys;print(json.dumps({'doc':open(sys.argv[1]).read()}))" \
  <plan-path> | uv run python -m review.cli derive-phases
```

`phases.active` is the remaining route; `phases.skipped` says why each other phase is out.
`unroutable: true` → stop and show the reason.

**The one judgment the router does not make: skip research?** Skip it (go
`RESEARCH → PLANNED` directly, a legal edge) when the ask already names the approach, the
scope boundary and the acceptance check — a bug with a repro, a refactor with a known
target, a chore with a done-when. Do research when the area is unfamiliar, several
approaches are plausible, or an external system needs checking. Say which you chose and
why, in one line.

Log the route (one line, gitignored dir):

```bash
echo '{"ts":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","plan":"<path>","status":"<status>","route":"<phases csv>","skip_research":<true|false>,"event":"routed"}' >> .claude/logs/build-decisions.jsonl
```

## Step 3 — Run the route

### Dispatching a worker

```
Agent(subagent_type: "proto-worker", run_in_background: false)
prompt: |
  Stage: <research|plan|execute|fix>
  Skill: .claude/skills/proto-<stage>/SKILL.md      # none for fix
  Plan: <plan-path>
  Repo: <repo-path>
  Answers: <human-seat answers collected in this context, verbatim and dated>
  Findings: <fix only: the non-blocker findings, verbatim>
  Constraint: one stage only; return the fixed report.
```

Handle the report's `RESULT:`:

- `DONE` → verify on disk (below), then next phase.
- `NEEDS_HUMAN` → ask Ramsey those questions here (`AskUserQuestion`), then re-dispatch
  the **same** stage with the answers added. This does not count as a retry.
- `NEEDS_DISPATCH` → dispatch the named agent here, then re-dispatch the stage with its
  output path in `Constraint:`. Does not count as a retry.
- `FAILED`, or verification fails → **one retry** with the gap named in `Constraint:`.
  A second failure → stop dispatching; read the partial artifact and resolve the stage
  in this context. Two tries means the problem needs judgment, not repetition.

**Verify every worker stage against the doc, not the report:**

| Stage | Verified when |
|---|---|
| research | `## Research` present; `Track:` is `ml` or `agent`; `Status:` advanced to `RESEARCHED` or `PLANNED` |
| plan | `## Plan` with steps and a verification line; `Status: PLANNED` |
| execute | `Status: IN_PROGRESS` or `EXECUTED`; `git diff --stat` non-empty |
| fix | each finding addressed or returned as `NEEDS_HUMAN`; named tests pass |

### Human seats — asked here, never by a worker

1. **Track** — before research, if the ask is ambiguous between fitting a model (`ml`)
   and calling one (`agent`). Ask; never default.
2. **Goal** — before plan. Ask 1–3 questions per `proto-plan`'s Goal elicitation, plus
   sign-off on the key decisions. Pass the answers as `Answers:`. If the research section
   already states the goal, restate it and ask yes/no.
3. **Go** — after refine. Show the verdict block. Continue to execute only on an explicit
   yes and only with `--to done`; otherwise stop here.
4. **Commit** — never. The build ends staged.

### Refine (this context)

Read `.claude/skills/proto-refine/SKILL.md` and follow it here, including its Stage 3
failure-pass dispatch. It remains the only writer of `REFINED` / `READY`. Do not trim its
gate to save tokens — the Light path in its Stage 0 already does that, honestly.

### Review → fix loop (this context, max 3 rounds)

After execute verifies, run `/proto-review <slug>` here. Route on its verdict:

- approve / comment → done (Step 4).
- request changes, **no blockers** → dispatch `fix` with the findings; next round.
- **any blocker** → stop and show the blockers. Never auto-fix a blocker.
- round 3 still requesting changes → stop and list what remains.

Log each round to `build-decisions.jsonl` with `"event":"review","round":N,"verdict":"…"`.

## Step 4 — Exit

```
──────────────────────────────────────
  /proto-build — <stopped at READY | ship-ready | blocked | needs you>
  Plan: <path>
  Status: <before> → <after>
  Ran: <phase (where)>, …
  Next: <the single next action, or the question>
──────────────────────────────────────
```

Append the exit to `build-decisions.jsonl` (`"event":"exit","outcome":"…"`). Then
`git status` and a suggested commit message — staged only.

## Boundaries

- Never commit, push, or open a PR.
- Never write `READY` outside `/proto-refine`'s procedure, and never execute without the go.
- Never route around a seat to save a round-trip; a seat is cheap to ask and expensive
  to guess.
- One work item per run. Batch triage is not this skill.
