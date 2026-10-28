---
name: spike
description: "The fast lane: try an idea on a spike/* branch with no plan doc, no Status: state machine and no FRAME/BUILD bands, then one light review at the end. For an afternoon thesis, a library trial or a demo you might throw away. Triggers: 'spike this', 'quick spike', 'just try it', 'vibe code', '/spike <idea>'."
allowed-tools: Read Grep Glob Bash Edit Write
---

# Spike

A spike answers one question fast. It skips the pipeline on purpose: no `DESIGN.md`,
no plan doc in `.claude/docs/plans/`, no `/proto-*` bands. The plan-doc hooks
(`plan_status_validate.sh`, `plan_transition_validate.sh`) stand down on `spike/*`
branches, so nothing will block for a missing or half-written `Status:`.

What it does not skip: `uv` over `pip`, the secrets scan, the destructive-command
guard, and the Stop hook's lint + tests on changed files. Those are cheap and catch
the mistakes that cost the most when you are moving fast.

## 1. Pin the question (one message, no doc)

Restate `$ARGUMENTS` as a single question the spike must answer, and the evidence
that would answer it: a passing test, a printed number, a screenshot, a working
`curl`. If you cannot name the evidence, ask once. A spike without a question is
just unreviewed code.

## 2. Branch and place it

- `git switch -c spike/<slug>` from the current branch. Never on `main`.
- Where the code lives: a new dir under `runs/ai/` or `runs/ml/` in galactus (the
  default; see `/new` for the run-vs-repo call), or the current repo if the spike is
  about that repo. A new test dir under `runs/` goes in `testpaths` in
  `pyproject.toml`, or it collects zero tests and reads as passing.
- Model calls: the role IDs in `versions.toml` `[models]`. Do not send `temperature`,
  `top_p` or `top_k`; every current Claude model rejects them.

## 3. Build ugly, end to end

Hardcode what you could defend later. One happy-path test that produces the
evidence from step 1 beats five unit tests of helpers. Keep a running note in the
session (not a file) of the shortcuts taken: they become the review's "known
shortcuts" list.

## 4. Light review (the only review a spike gets)

Run once, at the end, before reporting:

1. **Diff scope**: `git status --porcelain` plus `git diff main...HEAD --name-only`.
2. **Mechanical**: `make lint` if the target exists, else `uv run ruff check <changed>`;
   `make test` / `uv run pytest -q <changed test dirs>`. Record pass or fail; never
   install anything.
3. **Real problems only**: read the diff for secrets, a live API call in a test,
   swallowed exceptions that hide the answer, and anything that makes the evidence
   lie (a test that cannot fail, a metric on training data). Style is the linter's job.
4. **Doc flags**: if the change contradicts `CLAUDE.md` or a `.claude/` file, flag it.
   Do not edit docs.

Report in the session, not a file:

```markdown
## Spike — <question>
Answer: yes / no / partly — <evidence, with the command that reproduces it>
Lint: PASS/FAIL · Tests: PASS/FAIL
Findings: <ranked, file:line, or "none">
Known shortcuts: <from step 3>
Next: throw away | keep as a run | graduate (→ /proto-scope, or /new for a repo)
```

## Boundaries

- Never commit or push unless asked. Never merge a spike branch to `main` directly:
  graduating means starting the pipeline (`/proto-scope`) with the spike as evidence.
- No plan doc. If the spike turns into real work, that is the moment to write one,
  on a `{PREFIX}-{NUM}-{slug}` branch, where the state machine applies again.
