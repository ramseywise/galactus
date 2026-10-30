# Guard hooks — fire in every session, not only galactus-rooted ones

Status: PLANNED
Date: 2026-10-30
Issue: — (none yet)

Sibling of `2026-10-30-setup-hygiene.md`. Depends on nothing; can land first.

## Research

Direct inspection, 2026-10-30.

| # | Finding | Evidence |
|---|---------|----------|
| R1 | The guards protect galactus sessions only | `galactus/.claude/settings.json` registers all hooks as `$CLAUDE_PROJECT_DIR/.claude/hooks/<name>`. `~/.claude/settings.json` has no `hooks` key |
| R2 | Other repos have weaker or no guards | atlas, librarian, listen-wiseer carry their own hook sets; kiez and sisyphus have none; guacamayo registers only session-wake-nudge, dream-ledger-gate, worktree-cleanup, and only in untracked `settings.local.json` |
| R3 | Settings layers merge, so registering in both places double-fires | documented as galactus#20 in `.claude/hooks/lib.sh` (lines 97–101, 189–192) |
| R4 | The template ships a different guard set from root | `template/.claude/hooks/` has `risky_git_guard.sh`, `branch_guard.sh.jinja`, `stop_checks.sh`; root has `destructive_cmd_guard.sh`. Only `lib.sh`, `docs_hygiene.sh`, `secrets_scan.sh` are symlinks into root |
| R5 | `lib.sh` copies have drifted | atlas, librarian, listen-wiseer `lib.sh` differ from galactus's by about 335 lines |
| R6 | Plan-doc validation fires only on Write/Edit | a Bash heredoc into `.claude/docs/plans/` is not validated |

## Plan

Based on: direct codebase inspection (Research above).

**S1. Pick the global set.** Repo-agnostic guards only:
`destructive_cmd_guard.sh`, `pip_guard.sh`, `secrets_scan.sh`. Everything plan-doc or
galactus-specific stays project-level.

**S2. Make the three hooks root-independent.** Read each for `$CLAUDE_PROJECT_DIR` or
relative paths into galactus. Each must source `lib.sh` by its own directory
(`"$(dirname "$0")/lib.sh"`), not by project dir. `pip_guard.sh` must not block repos
that are not `uv` projects. Decide in refine whether it scopes itself to directories with a
`uv.lock`.

**S3. Register globally.** Back up `~/.claude/settings.json`, then add the three under
`hooks` with absolute paths: `/Users/ramsey-wise/workspace/galactus/.claude/hooks/<name>`.

**S4. Remove the project-level duplicates.** Drop those three entries from
`galactus/.claude/settings.json` so a galactus session fires each once (R3). The rest of
galactus's hooks stay.

**S5. Retire the per-repo copies of the same three.** In atlas, librarian, and
listen-wiseer, remove registrations that duplicate the global three. Leave their
repo-specific hooks and their `lib.sh` alone; the drift (R5) is noted, not fixed here.

**S6. Record the template divergence (R4).** No code change. Add a line to
`template/.claude/hooks/README.md`: generated projects carry their own guards because
they must work on a machine without galactus.

### Verification

- In a session rooted at `~/workspace/kiez`: `rm -rf /tmp/x-guard-test` is blocked by
  `destructive_cmd_guard`; `pip install requests` is blocked by `pip_guard`.
- In a galactus session, one blocked command produces one block message, not two.
- `jq '.hooks' ~/.claude/settings.json` lists exactly the three.
- galactus `uv run pytest -q` still green.

### Open Questions

- Q1: Should `plan_status_validate.sh` also cover guacamayo's `workflow-*` plan docs?
  Their plan docs are untracked by decision, so the value is low. Recommendation: no.
- Q2 (S2): scope `pip_guard` to `uv` projects, or block `pip install` everywhere?
  Recommendation: everywhere, matching the global rule.
