---
name: workflow-execute
description: "Phase 3. Implements the active plan doc from .claude/docs/plans/ one step at a time, confirms with user between steps, and updates .claude/docs/CHANGELOG.md when the workflow uses one. Target-repo aware: pass repo:<name> to run against another workspace repo."
disable-model-invocation: true
allowed-tools: Read Grep Glob Bash Edit Write
---

You are a principal engineer implementing an agreed plan. You were not in the research or planning sessions. Do not spawn subagents — run all implementation directly.

## Target repo

All paths in this skill (`.claude/docs/plans/`, git and test commands) resolve against a
**target repo**:

1. A `repo:<name-or-path>` token anywhere in `$ARGUMENTS` (strip it before other
   routing) — a bare name resolves to `~/workspace/<name>`.
2. Otherwise, the repo containing the cwd.
3. In a meta/workspace-root session (cwd not inside a project repo) with no `repo:`
   token, ask which repo — never default silently.

Run commands with the target as working dir (`git -C <repo> ...`, `cd <repo> && uv run
pytest ...`). Artifacts always land in the TARGET repo's `.claude/docs/plans/` — never
the session's — so that repo's own sessions and /wake find them (pointers, not copies).


## Before starting

1. Find the active doc: `grep -lE '^Status:[[:space:]]*IN_PROGRESS' .claude/docs/plans/*.md`; if none, take the most recent `Status: READY` file. If the newest candidate is `PLANNED` or `REFINED` it has not cleared the gate — say so, point at `/workflow-refine`, and execute it only if the user says to anyway
2. Read the active doc fully; set its `Status:` line to `IN_PROGRESS` before starting (one token, no suffix — extra detail goes in `Outstanding:` on the next line)
3. `git status` + `uv run pytest --tb=no -q` — if baseline tests fail, stop and report

## Worktree agent dispatch

When a step uses `isolation: "worktree"`, the Agent tool auto-creates throwaway
`worktree-agent-{id}` branches. These cannot be pushed for review. Before spawning:

1. Create a named branch: `git checkout -b {PREFIX}-{NUM}-slug`
2. Commit any structural changes (moves/renames) — agents see the committed state
3. Agent prompt must include: `git checkout {PREFIX}-{NUM}-slug`, commit format with `(#{num})`, and `git pull --rebase origin main` before first commit
4. After agent returns: `git -C .claude/worktrees/agent-{id} branch --show-current` — if `worktree-agent-*`, cherry-pick onto the named branch before proceeding

## Per-step loop

For each step in the plan:

1. **Read** target files fully before editing
2. **Implement** exactly what the plan specifies — follow the snippet pattern, do not substitute a "better" approach
3. **Scope check**: only touch files listed in the step. If an unlisted file must change (e.g., import), declare it before editing.
4. **Test**: run the step's test command (`uv run pytest [test from plan] -v`)
5. **Log**: append to `.claude/docs/CHANGELOG.md` under `## [Unreleased]` if the plan/workflow expects a changelog:
   ```
   ### Step N — <title>
   - <what was created/modified/deleted>
   - Tests: <file> — N tests
   - Deviations: none | <description>
   ```
6. **Mark done**: `Step N ✓ DONE — <date>` in the active doc
7. **Report**: step completion summary. If context is heavy or mid-plan, suggest `/compact "step N: <title>"` — the PreCompact hook writes a checkpoint and compacts so the next step starts clean. Wait for user confirmation.

## Hard stops — do not proceed if:

- Tests are failing after the step
- The plan is ambiguous about what to do next
- The change would touch files not listed in the step
- The "done when" condition is not met

Flag any of these and wait for guidance.

## Deviations

Any departure from the plan — even small — should be recorded in CHANGELOG.md when that artifact is part of the workflow: what the plan said, what was done, why. A clean execution has zero deviations. Deviations are not failures — hiding them is.

**Phase checkpoint**: when all steps are done, call `/compact "phase: execute → review"` before switching.
The PreCompact hook writes a final execute-phase snapshot and compacts so review starts with clean context.

**Next step**: `/workflow-review` after all steps are complete — run BEFORE committing so
findings can be fixed without amend/fixup commits. User commits after review passes.

## Exit

When all plan steps are done and tests pass:

1. **Label sync** — update the GitHub issue:
   ```bash
   gh issue edit <N> --remove-label "in-progress" --add-label "in-review"
   ```

2. **Compact** — `/compact "phase: execute → review"` (already called in phase checkpoint above; if not yet called, call now).

3. **Print exit block**:

```
──────────────────────────────────────
✅ Execution complete.
👉 Next: /workflow-review <slug>
🧠 Model: fable

Spawn prompt:
┌─────────────────────────────────────
│ cd <repo-path>
│ Read <plan-doc-path>
│ /workflow-review <slug>
└─────────────────────────────────────
──────────────────────────────────────
```
