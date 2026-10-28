---
name: template-update
description: >
  Guide a scaffolded project through a copier update from the upstream template.
  Explains what changed, previews diffs, and helps resolve conflicts. Use when:
  updating a project to latest template, checking what template changes are available,
  or resolving copier update conflicts. Triggers on: "template update", "update from
  template", "copier update", "what changed in the template", "pull template changes",
  "sync with template".
---

# template-update

Walk a scaffolded project through `copier update` safely — preview what changed,
explain the impact, and resolve conflicts.

## Before you start

Verify prerequisites:
1. Current directory is a copier-managed project (`.copier-answers.yml` exists)
2. `copier` is installed (`command -v copier`)
3. Working tree is clean (`git status` — refuse if dirty; user must commit or stash first)

Read `.copier-answers.yml` to determine:
- `_src_path` — the template source
- `_commit` — the template version this project was last updated from
- All answered parameters (the project's current configuration)

## Process

### Step 1: Check what's available

```bash
copier update --pretend --diff
```

If no changes available, report "You're up to date" and stop.

### Step 2: Summarize changes

Categorize the diff into:

| Category | Impact | Action needed |
|----------|--------|---------------|
| **New files** | Low — adds functionality | Review; delete if unwanted |
| **Modified templates** | Medium — may conflict with local edits | Review conflicts |
| **New/changed parameters** | Medium — may need answers | Answer new questions |
| **Removed files** | High — may remove code you depend on | Check before accepting |
| **Infrastructure changes** | High — CI, Docker, configs | Test after update |

For each category, list the specific files and explain in plain language what the
template change does and why.

### Step 3: Flag potential conflicts

Compare the diff against local modifications:
- Files in the diff that the project has also modified (git log --follow)
- New parameters that interact with existing answers
- Removed features that the project currently uses

For each conflict, recommend one of:
- **Accept template** — the template version is better or the local change was a workaround
- **Keep local** — the local change is intentional and should be preserved
- **Merge** — both changes are needed; show how to combine

### Step 4: Execute the update

```bash
copier update --trust
```

If conflicts arise (`.rej` files or merge markers):
1. List each conflict file
2. Show the template's intent vs. the local intent
3. Propose a resolution
4. Apply the resolution (edit the file, remove `.rej`)

**Watch the update output for `[migration]` lines.** The template's `_migrations` clean up
structural moves copier's file-level merge can't (e.g. `core/*.py` → `core/pipelines/corpus/*.py`).
A `[migration] removed stale …` line is informational. A `[migration] WARN …` line means a file you
hand-edited was left in place: surface it to the user, and offer to port the local edits into the new
location and repoint the imports the warning names.

### Step 5: Verify

After update completes:
- Run the project's test suite if available (`make test` or equivalent)
- Check that the dev server starts (`make dev` or equivalent)
- Verify `.copier-answers.yml` reflects the new commit

Report: what was updated, what conflicts were resolved, what the user should manually check.

## Output

No persistent artifact — this is an interactive guidance session. The output is the
updated project with conflicts resolved.

If the update is complex (>5 conflicts), write a summary to `.claude/docs/template-update-log.md`:

```markdown
# Template Update — [date]
From: [old commit hash]
To: [new commit hash]

## Changes applied
- [category]: [summary]

## Conflicts resolved
- [file]: [resolution chosen + rationale]

## Manual verification needed
- [ ] [thing to check]
```

## Common scenarios

### "I want to see what changed but not apply it yet"
Run only Steps 1-3. End with a summary of what would change.

### "I answered a parameter wrong during initial scaffold"
This isn't a template update — use `copier recopy --trust` with corrected `-d` flags.
Show the user which parameter to change and what the effect will be.

### "The update adds a feature I don't want"
After update, delete the unwanted files and add them to `.copier-exclude` (if the
template supports it) or note in `.copier-answers.yml` the relevant feature flag
set to false, then `copier recopy --trust`.

### "I'm many versions behind"
Recommend updating incrementally if the template has breaking changes between versions.
Check the template's CHANGELOG or commit history for migration notes.

## Rules

- Never run `copier update` on a dirty working tree — data loss risk
- Always `--pretend --diff` first — no surprises
- Conflict resolution preserves local intent over template defaults
- If a conflict is ambiguous, ask the user rather than guessing
- After update, the project must still pass its existing tests

---

**Upstream:** Template repository releases / commits
**Next:** Run tests, verify dev server, commit the update
