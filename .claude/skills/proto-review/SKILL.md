---
name: proto-review
description: "Phase 4 review — plan fidelity + multi-reporter code review + DoD assessment + merge verdict. Run BEFORE committing (pre-commit quality gate) so fixes avoid amend/fixup commits. Also usable for PR reviews. Triggers: 'review PR #42', '/proto-review', '/proto-review my-feature', 'check the PR', 'review the diff', 'code-pr 42'."
skills: [review-shared]
allowed-tools: Read Grep Glob Bash Agent
---

Review implementation against plan (if one exists) AND review code quality via
multi-reporter orchestration. Primary use: pre-commit quality gate after `/proto-execute`
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

**First — the resolution path.** If the active plan doc is already `Status: EXECUTED` with
`Review: pending`, this is a *re-invocation to resolve a pending review*, not a request to
review again. Resolve it and stop:

```
Review: passed
Completed: YYYY-MM-DD
Status: COMPLETE
From: EXECUTED
```

Write all four lines in **one** Edit. The hook validates `COMPLETE` by value, not presence —
it rejects `COMPLETE` unless `Review:` reads `passed` and a `Completed:` date is present — so
an edit that lands `Status: COMPLETE` before flipping `Review:` is blocked rather than
leaving a doc that reads "done" over a review that never resolved.

Confirm the pending review's findings were addressed before writing `passed` — if they were
not, say so and leave `Status:` at `EXECUTED`. Never write `COMPLETE` in the same pass that
writes `EXECUTED`: a skill cannot write both ends of an edge it is the midpoint of, and the
`EXECUTED → COMPLETE` edge means "a human read the review and accepted it."

Otherwise, determine the review scope from the branch and repo state:

1. **Check branch prefix**: `bug/` or `spike/` → lightweight. Feature branch with plan doc → full.
2. **Check for plan doc**: `find .claude/docs/plans/ -name "*$(branch-slug)*"`. Present → full. Absent → lightweight.
3. **Check commit types**: if all commits are `chore`, `style`, `fix`, `docs` → lightweight. Any `feat` → full.

| Scope | What runs | What's skipped |
|-------|-----------|----------------|
| **Full** | All stages (1-8) | Nothing |
| **Lightweight** | Context brief (slim), lint/tests, worktree check, DoD, verdict | conditional dimensions, plan fidelity |

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

### Dimension scan

**First, compute which dimensions are active.** Do not decide this by reading the diff
yourself:

```bash
# stdin: the changed-file list as a JSON array of paths
echo '["path/one.py", "path/two.ts"]' | uv run python -m review.cli detect-signals
```

It returns `{signals, active, skipped, injection_hits}` — the active dimension list, a
`skipped` map of `dimension → reason`, and any injection hits found in the changed files.
**Keep `injection_hits`**: Stage 6 needs it, and it is not recomputed there. Seven
dimensions are always on (`intent`, `correctness`, `silent_failure`, `testing`, `safety`,
`architecture`, `performance`); `runtime` and `safeguards` activate on agent-system signal,
`contracts` on a `SANYI.md` at the repo root, and `leakage` on an ML-code signal. **Carry the
skipped map forward verbatim** — Stage 7 §11 must account for all eleven dimensions, and a skip
without its reason is indistinguishable from an omission.

**Then dispatch `review` once per active dimension — every dispatch in a single message,
`run_in_background: false`.** One message is what makes them concurrent; the foreground
qualifier is what makes you wait for them. Background dispatches let Stage 4 merge before
the reporters return, which reads as a clean review of findings that had not arrived yet.

Each dispatch gets **exactly one** `review-*` dimension skill, named explicitly, plus the
Stage 1 context brief. Never load two dimensions into one dispatch — the ID prefix is what
proves which skill loaded, and a dispatch carrying two has no unambiguous prefix.

| Input to each dispatch | Value |
|---|---|
| Dimension skill | exactly one `review-*` skill, by exact name (table below) |
| Files | the changed-file list — **the pre-screened subset** for conditional dimensions |
| Diff | from Stage 1; the reporter never re-derives it |
| Repo context | review profile + repo-context facts from Stage 1 |

The eleven dimensions, their skills, and what activates each:

| Dimension | Skill to load | Active when |
|---|---|---|
| intent | `review-intent` | always |
| correctness | `review-correctness` | always |
| silent_failure | `review-silent-failure` | always |
| testing | `review-testing` | always |
| safety | `review-safety` | always |
| architecture | `review-architecture` | always |
| performance | `review-performance` | always |
| runtime | `review-runtime` | agent-system signal |
| safeguards | `review-safeguards` | agent-system signal |
| contracts | `review-contracts` | `SANYI.md` at repo root |
| leakage | `review-leakage` | ML-code signal |

`detect-signals` decides the right-hand column — do not re-derive it by eye. The skill
name is hyphenated even where the dimension is underscored: `silent_failure` loads
`review-silent-failure`.

Conditional dimensions get the file subset that triggered them, not the full list:
`runtime` and `safeguards` see the agent-system files, `contracts` sees the files covered
by contract entries. Handing a conditional dimension the whole diff invites findings from
outside the remit that activated it.

This is a fan-out/fan-in: N nodes with distinct remits, different context, and read-only
tools, joined by this skill. The separation is the point — **the reporters never see each
other's findings, and none of them grades its own work.** You are the orchestrator; you do
not also report.

**When the diff exceeds 25 changed files**, say so in the report and treat dimension
coverage as degraded: per-dimension attention thins as the file count grows, so an
`approve` on a large diff is a weaker claim than the same verdict on a small one. Consider
splitting the review rather than raising the ceiling.

### Recording dispatch outcomes

Every dispatch ends in exactly one of three states, and the distinction is load-bearing:

| State | When | What Stage 6 does with it |
|---|---|---|
| `completed` | returned a valid findings array — **including an empty one** | reads the findings; zero is a real result |
| `failed` | errored, timed out, returned malformed output, or never returned | can mask blockers |
| `skipped` | `detect-signals` did not activate it | carries its reason to §11 |

**An empty array is `completed`, not `failed`.** A dimension that looked and found nothing
has reported a clean result. Marking it `failed` trips rung 1 of the ladder — which is
unconditional — so the injection conjunction at rung 0 never runs, and a poisoned review
gets the same verdict as a busy one. Distinguishing silence-from-cleanliness from
silence-from-poison is `verdict.py`'s job, computed from the injection hits and the
completed-empty set together. It is not yours to pre-judge.

Only a dispatch that produced no usable answer is `failed`.

**Validation failures: retry once, then record.** If `review/validate.py` rejects a
dispatch's findings (bad prefix, missing `quoted_span`, absent `spec_citation`), re-dispatch
that dimension once with the rejection reason included. If the second attempt also fails
validation, record the dimension as `failed` with the validation reason and move on. Never
hand-repair a reporter's findings into schema compliance yourself — that makes you the
reporter, and the prefix check exists precisely to catch findings that did not come from
the skill they claim.

### Bounded corrective round (F6)

If the always-on dimensions surface agent-system signal that `detect-signals` missed — an
LLM call, a tool definition, a prompt template in a file the detector did not classify —
dispatch `runtime` and `safeguards` **once, with the newly-identified files.** 

This round is entered **at most once per review and is never re-entered.** Findings from
the corrective round do not trigger another corrective round, however much new signal they
surface. Record in §11 that the corrective round ran and what triggered it. An unbounded
"one more look" loop is how a review stops terminating.

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

A `contracts` finding is the one exception: its `merge_impact` is fixed by its
`violation_code` through `_MERGE_IMPACT` in `review/validate.py` and is not adjustable
here. Arguing a `BY-2` down to a nit is exactly what that table exists to prevent.

The merged list is **session state, not a durable record.** Nothing is written to disk —
the review artifact in Stage 7 is the output. Do not append findings to a JSONL log or
any other store; this subsystem has no persistence layer by design.

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

The verdict is **computed, not judged** — and computed by *running* the ladder, not by
reading it and deciding for yourself:

```bash
uv run python -m review.cli verdict < review.json
```

where `review.json` is the payload you assemble from the stages above:

```json
{
  "findings": [ ... ],             // the Stage 4 merged list
  "dispatch": [ ... ],             // one entry per dimension — see the entry shape below
  "injection_hits": [ ... ],       // carried from Stage 3's detect-signals — not recomputed
  "validation_failures": 0         // an integer: dimensions that failed validation twice
}
```

Each `dispatch` entry uses the field names in `ReporterDispatchEntry`
(`review/models.py`) — not the prose labels this skill uses elsewhere:

```json
{
  "reporter": "safety",            // the dimension name, not "dimension"
  "status": "completed",           // completed | skipped | failed | dropped — not "state"
  "finding_count": 0,              // findings this dimension contributed after validation
  "skip_reason": null              // required, non-empty, when status is "skipped"
}
```

All eleven dimensions get a row every run, including the skipped ones — an eleven-row table is
what Stage 7 reports, and rung 1 reads `status` across every row. `validation_failures` is
a **count**, not a list; passing a list crashes the CLI rather than being rejected cleanly.

It returns `{"merge_decision": "..."}`. That value is the verdict. Write it into the
report as returned.

**Do not reimplement the ladder in prose here, and do not adjust its output.** The rungs
live in `review/verdict.py` as a pure function precisely so the decision is reproducible
and testable rather than re-derived by a model each run. Rung 0 in particular — the
conjunction of an injection hit *and* at least one completed-but-empty dispatch — is not
something to eyeball; that is the whole reason it is code.

If the CLI errors or the payload will not validate, the review is `insufficient_context`.
A verdict you could not compute is not an approval.

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

## 11. Dimension Dispatch Table
| Dimension | Status | Findings |
|----------|--------|----------|
| intent | dispatched / skipped (reason) / failed (reason) | N findings |
| correctness | ... | N findings |
| silent_failure | ... | N findings |
| testing | ... | N findings |
| safety | ... | N findings |
| architecture | ... | N findings |
| performance | ... | N findings |
| runtime | ... | N findings |
| safeguards | ... | N findings |
| contracts | ... | N findings |
| leakage | ... | N findings |
| plan-fidelity | ran / skipped | N findings |
| lint/tests | ran / skipped | pass/fail |

**All eleven dimensions get a row, every run — no exceptions.** A dimension that did not
run is `skipped` with the reason `detect-signals` gave, or `failed` with what went wrong.
Silently omitting a row is the failure this table exists to prevent: a review that covered
seven dimensions and a review that covered eleven look identical if only the ones that ran are
listed. Note here if the bounded corrective round ran and what triggered it.

## 12. Merge Verdict
**approve** | **comment** | **request_changes** | **insufficient_context**
[1-2 sentence rationale]
```

If plan doc exists, append the review section to the plan doc and set `Status: EXECUTED`
on approval, plus `Review: pending` on the next line (`Review: passed` once the verdict is
a pass). `Status:` carries exactly one enum member — no suffix.

Write `From: IN_PROGRESS` alongside it — this pass closes the `IN_PROGRESS → EXECUTED`
edge, the second half of the execute→review handoff. If the doc is not at `IN_PROGRESS`,
name the state it is actually at rather than the one expected; a rejected edge is the
gate reporting that `/proto-execute` never recorded the work starting.

`EXECUTED` is where this pass stops. Advancing to `COMPLETE` happens on a later
re-invocation, via the resolution path in Stage 0.

## Stage 8: Action (read-only default)

Report the verdict to the user. Do NOT run `gh pr review` unless explicitly authorized.

> "Verdict: **[verdict]**. Want me to submit this as a GH review?"

If authorized:
- `approve` → `gh pr review <number> --approve -b "<summary>"`
- `request_changes` → `gh pr review <number> --request-changes -b "<summary>"`
- `comment` → `gh pr review <number> --comment -b "<summary>"`

For plan-doc mode (no PR): append `## Review` section to plan doc, and set `Status:` to a
canonical enum member — `EXECUTED` + `Review: passed` when the verdict is `approve`,
`EXECUTED` + `Review: pending` otherwise, with `From: IN_PROGRESS` alongside (Stage 7).
Never write a free-text status.

A doc left at `EXECUTED` + `Review: pending` is *waiting*, not finished — re-invoking this
skill on it takes the Stage 0 resolution path to `COMPLETE`.

## Boundaries

- Never commit, push, or merge — Ramsey commits.
- Never auto-fix findings — report only. Fixes are the operator's call.
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
👉 Next: fix findings, then /proto-review <slug>
🧠 Model: (same session)
──────────────────────────────────────
```
