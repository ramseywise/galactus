---
name: workflow-review
description: "Phase 4 review — plan fidelity + multi-reporter code review + DoD assessment + merge verdict. Run BEFORE committing (pre-commit quality gate) so fixes avoid amend/fixup commits. Also usable for PR reviews. Triggers: 'review PR #42', '/workflow-review', '/workflow-review my-feature', 'check the PR', 'review the diff', 'code-pr 42'."
skills: [review-shared]
allowed-tools: Read Grep Glob Bash Agent
---

Review implementation against plan (if one exists) AND review code quality via
multi-reporter orchestration. Primary use: pre-commit quality gate after `/workflow-execute`
(review before committing so fixes are clean, not amend/fixup). Also handles standalone PR reviews.

`$ARGUMENTS` — one of:
- A PR number or URL (`42`, `#42`, `https://...`) → PR review mode
- A work-item slug (`my-feature`) → plan-doc review mode
- Empty → discover: match `^Status:[[:space:]]*IN_PROGRESS`, else `gh pr list`

## Target repo

All paths resolve against a **target repo**:

1. A `repo:<name-or-path>` token anywhere in `$ARGUMENTS` (strip before routing)
   — bare name resolves to `~/workspace/<name>`.
2. Otherwise, the repo containing the cwd.
3. In a meta/workspace-root session with no `repo:` token, ask which repo.

Run commands with the target as working dir. Artifacts land in the TARGET repo's
`.claude/docs/plans/` so that repo's own sessions find them.

---

## Stage 0: Scope Detection

Before gathering context, determine the review scope from the branch and repo state:

1. **Check branch prefix**: `bug/` or `spike/` → lightweight. Feature branch with plan doc → full.
2. **Check for plan doc**: `find .claude/docs/plans/ -name "*$(branch-slug)*"`. Present → full. Absent → lightweight.
3. **Check commit types**: if all commits are `chore`, `style`, `fix`, `docs` → lightweight. Any `feat` → full.

| Scope | What runs | What's skipped |
|-------|-----------|----------------|
| **Full** | All stages (1-8) | Nothing |
| **Lightweight** | Context brief (slim), lint/tests, worktree check, DoD, verdict | akira-scan, SANYI, plan fidelity |

The review artifact is always written regardless of scope — `check-review` in `make ship` gates on it.

## Stage 0.5: Worktree & Branch Cleanup Check

Before reviewing code quality, verify the workspace is clean:

1. **Leftover worktrees**: `git worktree list` — any worktrees beyond the main checkout are leftovers from agent runs. Flag as `merge_impact: important` finding if they contain uncommitted changes, `nit` if empty.
2. **`worktree-agent-*` branches**: `git branch --list 'worktree-agent-*'` — these are auto-generated branches from `isolation: "worktree"` that bypassed the branch convention. Flag as `merge_impact: blocker` — commits on these branches must be cherry-picked onto a named `{PREFIX}-{NUM}-slug` branch before review can proceed.
3. **Unmerged agent branches**: check for branches matching the current work item that haven't been merged into the current branch (e.g. `GUA-18-*` branches when reviewing `GUA-23-*`). Flag unmerged branches as `merge_impact: blocker`.
4. **Stale tracking branches**: `git branch -vv | grep ': gone]'` — remote-deleted branches still tracked locally. Flag as `nit`.

Report findings in Stage 7 under a "Workspace Hygiene" subsection.

## Stage 1: Context Brief

Produce a context brief (per `review-shared/references/context-brief.md`). Gather:

1. **PR metadata** (if PR mode): `gh pr view <number> --json title,body,headRefName,baseRefName,labels,reviewRequests`
2. **Diff**: `gh pr diff <number>` (PR mode) or `git diff main...HEAD` (plan mode)
3. **Changed files**: from PR or git diff
4. **Repo context**: read CLAUDE.md, check for SANYI.md, check for Refs: line
5. **CI status** (PR mode): `gh pr checks <number>`
6. **Callers of changed symbols**: Grep for function/class names from the diff
7. **Review profile**: infer `general` or `agent-system` from imports and file paths.
   Agent-system if any changed file imports LLM/agent frameworks or lives under `agents/`,
   `*_agent/`, `prompts/`.
8. **Plan doc** (if exists): find matching `.claude/docs/plans/*.md` by slug or branch name.
   If found, read `## Plan` section for fidelity check.

Fill the context brief template. Unknown fields = "unknown", not guessed.

## Stage 2: Plan Fidelity (conditional — skip if no plan doc)

For each plan step:

| Plan said | Code shows | Tests | Status |
|-----------|-----------|-------|--------|
| Step 1: ... | [actual] | PASS/FAIL | Match / Deviation / Missing |

### Stub detection

Check key files for: `TODO`, `NotImplementedError`, `return None`, `pass` on critical
paths. Blocker if on critical path, warning otherwise.

Deviations become findings with `merge_impact: important` (justified deviation) or
`blocker` (unjustified omission).

## Stage 3: Dispatch Reporters

### Dimension scan (quality + contracts + wander)

Dispatch the reporters as subagents, **all in one message so they run concurrently**.
Each gets the Stage 1 context brief; none of them re-derives the diff.

| Reporter | Agent | Dispatch when |
|---|---|---|
| Quality | `akira-scan` | Always |
| Questions | `akira-wander` | Diff scope is non-empty |
| Contracts | `sanyi-review` | `SANYI.md` exists at the repo root |

This is a fan-out/fan-in: three nodes with distinct specialties, different context, and
read-only tools, joined by this skill. The separation is the point — **the reporters
never see each other's findings, and none of them grades its own work.** You are the
orchestrator; you do not also report.

Pass each reporter: the changed-file list, the diff, the review profile, and the
repo-context facts from Stage 1. Require findings in `review-shared`'s schema.

**If a reporter returns nothing, that is a dispatch result you must distinguish from a
clean scan.** A reporter that errored, timed out, or received an empty file list has not
approved anything. Record it as a dispatch failure — Stage 6 turns any unexplained
reporter silence into `insufficient_context`, never into an approval.

Plan-fidelity findings (Stage 2) are not dispatched — they stay in-session and merge in
at Stage 4.

### Lint and tests
Run `make lint` / `make test` if available; fallback to stack-specific commands
(`uv run pytest --tb=short -q`, `npx tsc --noEmit`, etc.).
Record pass/fail. Test failures become findings with `merge_impact: blocker`.

## Stage 4: Merge

1. Collect findings from every reporter that returned.
2. **Dedupe by `(file, lines, claim.title)`.** Two reporters flagging the same line is
   corroboration, not two problems — keep one finding and record both sources. Never
   drop a finding whose location merely *overlaps* another; only exact-location matches
   on the same claim collapse.
3. Prepend plan-fidelity findings from Stage 2 (they have no reporter).
4. Prepend lint/test failure findings.
5. Re-rank: blockers, important, suggestion, nit.

Preserve each finding's `severity.source_native` verbatim through the merge. You may
adjust `merge_impact` when cross-reporter context changes the picture — a `hypothesis`
from one reporter corroborated by another's `verified` finding is stronger than either
alone. Say so in the report when you do; a silently adjusted severity is unreviewable.

Then append each finding as one JSON line to `.claude/docs/review-findings.jsonl` per
the persistence format in `review-shared/references/finding-schema.md`. Append-only —
never rewrite earlier rows.

## Stage 5: DoD Assessment

Assess each item as met / gap / n/a. A repo-specific DoD in `CLAUDE.md` or the plan doc
overrides this default list:

| Item | Met when |
|---|---|
| Tests | New behavior has a test that fails without the change |
| Lint | `make lint` (or stack equivalent) is clean |
| Docs | Docs contradicting the new behavior are updated, not just appended to |
| Config | No new hardcoded tunable that belongs in config or env |
| Errors | New failure paths are handled, not swallowed |
| Reversibility | The change can be rolled back without a data migration, or the migration is written |

Gaps become findings with appropriate merge_impact.

If a plan doc exists, also check:
- All plan steps accounted for (from Stage 2)
- Status line present and correct
- Acceptance criteria from the plan/issue met

## Stage 6: Judge — Merge Verdict

The verdict is **computed, not judged.** Apply this ladder to the Stage 4 combined list
(reporter + plan-fidelity + lint findings) in order, and stop at the first match:

1. Any reporter/dispatch failure that could mask blockers → `insufficient_context`
2. Any `merge_impact: blocker` → `request_changes`
3. Any `merge_impact: important` → `comment`
4. Otherwise → `approve`

Rule 1 comes first on purpose. A review that could not see part of the diff has not
approved it, and "no findings" from a reporter that never ran is the single easiest way
for a broken review to read as a passing one.

You do not get to weigh the findings against each other here. If you believe a blocker is
overstated, the fix is to argue it down to `important` in Stage 4 — visibly, with a
reason — not to compute `approve` over the top of it.

## Stage 7: Report

Produce the unified report:

```markdown
# Review — #<number> <title> (or <slug>)

## 1. Overall Understanding
[1-3 sentences]

## 2. Review Contract
[From context brief]

## 3. Plan Fidelity
[Plan step table — only if plan doc exists. Otherwise: "No plan doc — standalone review."]

## 4. What Looks Strong
[Genuine positives, not filler]

## 5. Blocking Findings
[merge_impact: blocker findings with canonical IDs]

## 6. Important Findings
[merge_impact: important]

## 7. Questions and Hypotheses
[merge_impact: question + hypothesis-state findings]

## 8. Suggestions and Nits
[merge_impact: suggestion | nit]

## 9. Testing and Evaluation Assessment
[Coverage, gaps, repeated-run consideration for agent code]

## 10. Definition of Done Assessment
[DoD checklist table: item | status | note]

## 11. Reporter Dispatch Summary
| Reporter | Status | Findings |
|----------|--------|----------|
| plan-fidelity | ran/skipped | N findings |
| akira-scan | dispatched/skipped | N findings |
| SANYI | dispatched/skipped | N findings |
| lint/tests | ran/skipped | pass/fail |

## 12. Merge Verdict
**approve** | **comment** | **request_changes** | **insufficient_context**
[1-2 sentence rationale]
```

If plan doc exists, append the review section to the plan doc and set `Status: EXECUTED`
on approval, plus `Review: pending` on the next line (`Review: passed` once the verdict is
a pass). `Status:` carries exactly one enum member — no suffix.

## Stage 8: Action (read-only default)

Report the verdict to the user. Do NOT run `gh pr review` unless explicitly authorized.

> "Verdict: **[verdict]**. Want me to submit this as a GH review?"

If authorized:
- `approve` → `gh pr review <number> --approve -b "<summary>"`
- `request_changes` → `gh pr review <number> --request-changes -b "<summary>"`
- `comment` → `gh pr review <number> --comment -b "<summary>"`

For plan-doc mode (no PR): append `## Review` section to plan doc, and set `Status:` to a
canonical enum member — `EXECUTED` + `Review: passed` when the verdict is `approve`,
`EXECUTED` + `Review: pending` otherwise. Never write a free-text status.

## Boundaries

- Never commit, push, or merge — Ramsey commits.
- Never auto-fix findings — report only. Recommend `/akira dao` for safe fixes.
- Read-only by default; GH review submission requires explicit authorization.
- Per-reporter failures are reported (not retried infinitely), noted in dispatch summary.
- Max 3 review rounds — if issues persist, escalate to user.

## Exit

When the review verdict is **approve**:

1. **Label sync** — issue stays `in-review` until PR merges. On merge, close the issue.

2. **Compact** — call `/compact "phase: review → ship"` to shed review context.

3. **Print exit block**:

```
──────────────────────────────────────
✅ Review complete — approved.
👉 Next: git commit, then make ship
🧠 Model: n/a (user action)

After merge:
  gh issue close <N> --comment "Shipped via PR #<M>."
──────────────────────────────────────
```

When the verdict is **request_changes**:

1. **Label sync** — keep `in-review` (changes are part of the review cycle).

2. **No compact** — stay in the same session to fix findings.

3. **Print exit block**:

```
──────────────────────────────────────
🔄 Review complete — changes requested.
👉 Next: fix findings, then /workflow-review <slug>
🧠 Model: (same session)
──────────────────────────────────────
```
