---
name: design-roadmap
description: "EM role — takes an agreed backlog and files it as real GitHub issues: milestones created, issues opened with acceptance criteria, dependencies wired as task checklists, labels applied. The last design stage before /workflow-triage. Triggers on: 'file the backlog', 'create the issues', 'open tickets for this', 'set up the milestones', '/design-roadmap'."
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
---

# /design-roadmap

Turn an agreed backlog into the GitHub issues the build pipeline consumes.

`/design-initiative` proposes the backlog; this skill **commits it**. That split is
deliberate — issue creation is the first irreversible step in the pipeline (other people
see it, it generates notifications, and a botched batch takes manual cleanup), so it
lives behind its own invocation rather than firing at the end of a scoping pass.

## Usage

```
/design-roadmap                            # no arg → .claude/specs/design-scope.md
/design-roadmap <backlog-doc-path>
/design-roadmap <initiative-slug>          # resolves .claude/docs/milestones/<slug>.md
/design-roadmap --dry-run <path>           # print what would be filed, create nothing
```

## Target repo

**Issues live in the repo they change**, not in whichever repo the session runs in.

> **Set `<owner>/<repo>` before running.** Read it from `git remote -v` or ask the user.
> Replace `<owner>/<repo>` here and in any related git skills.
>
> **Never invent a remote.** A `gh` call against a guessed repo either fails or, worse,
> files issues somewhere they do not belong.

## HITL Gates

This skill has four mandatory pause points. Do not proceed past any without
explicit user approval. **Issue filing is the LAST step, not the default outcome.**

### Gate 1 — Build-state verification

After Step 2's reconciliation, before any milestone or issue is drafted. **This gate
exists because the roadmap's sequencing is only as good as its build-state inputs, and
those inputs decay silently.** A prior project (diskoe) re-sequenced an entire window
after discovering four capabilities marked shipped did not exist and one that existed
was in no document.

1. Present the reconciliation table — one row per capability the backlog treats as already
   built, with **the file path that proves it** or `ABSENT`:

   | Capability | Backlog/doc says | Tree says | Path or ABSENT | Effect on sequence |
   |---|---|---|---|---|

2. Call out separately, because each changes the plan in a different direction:
   - **Marked built, actually absent** — work returns to the roadmap. This is the
     expensive case: an item dropped as "already done" is one that never gets planned again.
   - **Marked absent, actually built** — work leaves the roadmap, and the doc that was
     wrong gets a correction filed.
   - **`PARTIAL`** — names its missing field or unmet criterion, or it is not a verdict.
     A capability whose shape shipped without its field list is not built.
   - **Could not verify** — listed as `UNVERIFIED`, never resolved to an optimistic
     marker to keep the table tidy.

3. **Stop and ask:** "N capabilities verified against the tree, M disagree with the
   backlog. Confirm these corrections before I draft milestones — every sequencing
   decision below inherits them."

4. Do NOT draft milestones or issues until the user approves. If a correction invalidates
   the upstream doc, say which doc and which section: it is fixed there, not silently
   worked around here.

### Gate 2 — Draft issue backlog review

After creating the draft issue backlog (Step 2-3), and only after Gate 1:

1. Present the milestone structure, issue list, ownership, and dependency map
2. Call out any scope gaps, ownership ambiguities, or dependency cycles
3. **Stop and ask:** "Draft issue backlog is ready for review. Check the milestones
   and issues above — adjust ownership, scope, or ordering before I render to HTML."
4. Do NOT render HTML until the user approves

### Gate 3 — Full HTML review

After rendering the Roadmap tab to the HTML (Step 4):

1. Confirm what was added: milestones table, delta table, issue backlog section
2. **Stop and ask:** "Roadmap tab rendered to the design record. Open the full HTML
   and review all tabs end-to-end before I file GitHub issues."
3. Do NOT file issues until the user approves the complete HTML

### Gate 4 — Issue filing confirmation

After the user approves the full HTML (Step 5):

1. Run `--dry-run` to print exactly what would be filed
2. **Stop and ask:** "Ready to file N issues across M milestones. Proceed?"
3. Only then create GitHub milestones and issues

## Step 1 — Read the backlog and check the gate

Read the backlog doc — `.claude/specs/design-scope.md` from `/design-initiative` unless a path was passed
— specifically **Section 6 (GitHub hierarchy)** and **Section 4 (summary table + critical
path)**, plus the milestone doc at `.claude/docs/milestones/<slug>.md`.

Refuse to file if any of these hold — say which, and stop:

| Gate                                          | Why it blocks                                                                  |
| --------------------------------------------- | ------------------------------------------------------------------------------ |
| No milestone doc                              | Issues with no milestone are orphans; the backlog is unsequenced               |
| A task attaches to no milestone               | Either scope creep or a missing checkpoint — resolve upstream, don't orphan it |
| A task has no acceptance criteria             | It cannot pass DoR, so `/workflow-triage` will bounce it                        |
| A task has no deliverable, only "implement X" | Not a task, a wish                                                             |
| The backlog was never reviewed with the user  | Filing unagreed scope is the failure this skill exists to prevent              |
| The PRD's Q0-Q5 ladder has a level marked Required with no owner | File the owner-assignment issue first (see Step 4) — an unowned gate never runs |

## Step 2 — Reconcile against what already exists

Never file blind. A re-run must be idempotent — this is the single most common way an
issue tracker gets polluted.

```bash
gh issue list -R <owner>/<repo> --state all --limit 200 --json number,title,labels,milestone
gh api repos/<owner>/<repo>/milestones --jq '.[] | {number,title,state}'
```

Match each backlog task against existing issues by title similarity. Classify every task
as **new**, **existing** (skip it), or **ambiguous** (ask). Print the classification and
get sign-off before creating anything.

### Reconcile against the tree, not just the tracker

The tracker records intent; only the tree records state. Before sequencing, verify each
"already built" claim against a file path. **An item removed from the roadmap because it
is "already done" is the item that will never be planned again.**

**This is Gate 1.** Present the verification table and stop for approval before drafting
milestones — the gate's full shape is above.

### Enforcement lands after the thing it enforces, never before

A gate that runs against checks nobody wrote turns CI red on absence rather than on
defect, and the fix is always to disable the gate. Order every enforcement item
explicitly: **write the graders and fixtures, then uncomment the gate — in that order.**
A prior project (diskoe) declared 13 metrics gated at 1.0 that nothing computed, so the
invariant "every scoring dimension needs an eval metric" was unenforceable while every
dimension shipped without one.

The same ordering applies to any drift check, contract test, or lint rule introduced
alongside the thing it governs. If the gate can be filed as a separate item from its
checks, it is sequenced wrong.

### Items that cannot be resequenced are marked, not just ordered

Some items lose their value entirely if they slip — anything whose data is generated by
traffic (instrumentation, holdout slices, pre-registration). These carry **`UNRECOVERABLE`**
in the roadmap row and ship in the same commit as the feature they observe. Do not file
instrumentation as its own downstream item: a separately-filed instrumentation item is one
that gets trimmed in week three by someone who is right about everything except
recoverability.

## Step 3 — Create milestones

One GitHub milestone per Phase-2 checkpoint, in order. A milestone is a **verifiable
system state**, so its description carries the done-condition:

```bash
gh api repos/<owner>/<repo>/milestones -f title="M1 — <named system state>" \
  -f description="Done when: <verifiable condition>" \
  -f due_on="<ISO date>"     # only for externally-driven dates; omit otherwise
```

Only externally-driven milestones get dates. The rest carry sequence position in the
title — a fabricated due date is worse than none, because it reads as a commitment.

## Step 4 — Render the Roadmap tab to HTML

**Only after Gate 2 approval.** Add/update the Roadmap tab (`#delta`) in
`docs/<project>-system-design.html`. This tab owns:

- **Milestones table** — M0-MN with name, "what it proves", lead, workstream
- **Delta table** — the full build queue from `.claude/specs/roadmap.md`
- **Decision register** — unratified decisions with blockers
- **PRD coverage table** — every PRD § with coverage state
- **Issue backlog section** — the draft issues grouped by milestone, with ownership
  and dependency columns

Do NOT touch tabs owned by other skills (Overview, Architecture, Components, Platform).

After rendering, add a sidebar TOC link for the issue backlog section if one doesn't
exist, and update the hash router's `TAB_OF` map for any new section IDs.

**HITL Gate 3** — stop and ask the user to review the full HTML before proceeding.

## Step 5 — File the issues

**Only after Gate 3 approval.** For each **new** task, in critical-path order so issue numbers roughly track sequence:

```bash
gh issue create -R <owner>/<repo> \
  --title "<imperative task title>" \
  --milestone "M1 — <state>" \
  --label backlog \
  --body "$(cat <<'EOF'
## Goal
<what decision or capability this unlocks — not a restatement of the title>

## Deliverable
<concrete artifact: a running endpoint, a migration, a document>

## Acceptance criteria
- **Given** <state> **When** <action> **Then** <observable result>
- Metric: <how we know it worked, with a number>
- Integration: <what must still work after this lands>

## Key work
- <bullet>

## Traces to
Failure mode #<n>: <root cause → symptom>
Delta row: <delta-ID from the design record, if one exists>

## Quality level
<Q0-Q5 from the ladder — the highest level this work must satisfy before it can close,
and who owns that check. "Q0 — Engineer" for most; name the owner explicitly for Q3+.>

## Risks / open questions
- <bullet, or "None">

Size: <S|M|L|XL>
EOF
)"
```

Label with `backlog` only. `ready` is the triage skill's to grant after the DoR gate —
this skill never pre-grants it, or the DoR check becomes ceremonial.

### The quality ladder is filed, not assumed

The PRD's Q0-Q5 ladder (`.claude/specs/design-requirements.md` §15) names what each level
proves and whether it gates. It does **not** name an owner or a current state per level —
so a level with no owner is invisible after the PRD is written, which is the exact failure
the ladder exists to prevent. **Q3 (adversarial / safety) is the level nobody volunteers
for**, and it is currently unowned.

While filing, do two things:

1. **Give every issue a `## Quality level`** naming the highest ladder level it must
   satisfy and that level's owner. An issue that touches an agent path is Q1 at minimum;
   anything holding a credential or crossing a tenancy boundary is Q3.
2. **File an issue for every ladder level that has no owner**, titled
   `Assign an owner for Q<n> — <check>`, with the ladder row as its goal. A level marked
   "Required" in the PRD with no owner and no issue is a gate that will never run.

Report the ladder's coverage in Step 6: for each of Q0-Q5, its owner, its state
(BUILT / PARTIAL / GAP), and the issue that moves it. Say plainly which levels are
unowned rather than letting them pass silently.

## Step 6 — Wire dependencies

Dependencies are **task checklists inside the blocked issue**, never sub-issues and never
extra branches:

```markdown
## Blocked by

- [ ] #<n> — <title>
```

When work needs several sessions, it stays **one issue, one branch, one PR** with a
`- [ ]` task list in the body naming each slice. Splitting into sub-issues adds tracking
overhead and nothing else.

Cross-repo references are **fully qualified** (`<owner>/<repo>#65`, not `#65`) —
a bare `#N` silently rebinds to the destination repo if the issue is ever transferred.

## Step 7 — Write the roadmap doc and report

Write `.claude/docs/milestones/<slug>-roadmap.md`:

```markdown
# Roadmap — <initiative>

Date: <YYYY-MM-DD>
Repo: <owner>/<repo>

| Milestone    | Done when   | Issues        |
| ------------ | ----------- | ------------- |
| M1 — <state> | <condition> | #12, #13, #14 |

## Critical path

#12 → #13 → #17

## Not filed

- <task> — <why: existing #N / deferred / unresolved question>
```

Then print:

```
--------------------------------------
  Roadmap filed — <owner>/<repo>
  Milestones: <n>   Issues: <n>   Skipped: <n>
  Critical path: #<a> → #<b> → #<c>

Next: /workflow-triage #<first> → /workflow-build #<first>
--------------------------------------
```

## Boundaries

- **`--dry-run` prints, creates nothing.** Use it by default on a backlog of more than
  ~10 tasks — a bad batch is tedious to unwind.
- **Never file an issue the user has not agreed to.** This is the irreversible step.
- **Never label `ready`** — that is the DoR gate's decision.
- **Never create branches, PRs, or sub-issues.** Branches belong to the build skill's
  caller; sub-issues are banned by convention.
- **Never close or edit issues you did not just create**, except to add a `Blocked by`
  checklist to one you filed in this run.
- Re-running on the same backlog files nothing new — reconcile first, always.

---

## Tab ownership

This skill owns the **Roadmap tab** in the design record HTML:
milestones, delta table, decision register, PRD coverage, issue backlog.

It must not touch tabs owned by other skills:

| Skill | Owns |
|---|---|
| `/design-product` | Overview |
| `/design-system` | Architecture, Components, Platform |
| `/design-roadmap` (this) | Roadmap (milestones, delta, decisions, PRD coverage, issues) |

---

**Upstream**: `/design-product` (PRD + Overview tab) → `/design-system` (specs + Architecture/Components/Platform tabs).
**Next**: `/workflow-triage #N` takes an issue to READY; `/workflow-build #N` builds it.
