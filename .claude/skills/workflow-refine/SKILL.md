---
name: workflow-refine
description: "Readiness gate between plan and execute. Applies PM / designer / EM lenses to one planned work item, checks it against the Definition of Ready, dispatches an isolated failure pass when the plan is risky, and either advances Status: PLANNED → REFINED → READY or says exactly what is missing. Triggers: 'is this ready', 'refine the plan', 'DoR check', 'ready to execute', 'gate this', '/workflow-refine'."
disable-model-invocation: true
allowed-tools: Read Grep Glob Bash Edit Agent
---

You are running the readiness gate. One plan doc, one verdict: **ready to execute, or
not — and if not, exactly what is missing.**

This is the only skill that writes `REFINED` and `READY`. Without it those two states are
unreachable and the state machine has a hole where its quality gate should be.

**Single item, not a batch.** This repo is one-work-item-per-plan-doc. If you find
yourself ranking items against each other, you are in the wrong skill — that is
portfolio triage, and it does not apply here.

## Input

`$ARGUMENTS` is a plan doc path or slug. Resolve a slug against
`.claude/docs/plans/YYYY-MM-DD-<slug>.md`. With no argument, use the most recently
modified plan doc and say which one you picked.

**Preconditions, checked before any lens work:**

| Condition | Response |
|---|---|
| No plan doc found | Error. Stop. Do not gate an imaginary plan. |
| `Status:` is `RESEARCH` or `RESEARCHED` | Stop — there is no plan to gate yet. Point at `/workflow-plan`. |
| `Status:` is `IN_PROGRESS` or later | Stop — the gate is behind you. Point at `/workflow-review`. |
| Doc exists but has no `## Plan` section | Error, not a failed gate. The input is malformed. |

An unreadable or empty target is an **error, not a failed gate**. A gate that reports
"not ready" when it could not read the plan has told you nothing about the plan.

---

## Stage 1 — The trio, as three lenses

Three perspectives, one mind, one verdict. **Do not dispatch these as agents** — they are
not adversarial to each other, they grade different axes, so their agreement was never
evidence (`decide-shared`, "when a lens earns agenthood"). Running them inline is the
correct shape *and* the cheap one.

| Lens | Owns | Asks | Risk it catches |
|---|---|---|---|
| **PM** | Problem and value | Who needs this? Does the problem justify the effort? What happens if we ship nothing? | **Product risk** — building the wrong thing |
| **Designer** | Fit and interaction | Does this compose with existing patterns, or fight them? Who uses the output, and is its shape right for them? | **Usability risk** — right thing, unusable shape |
| **EM** | Feasibility | Can one session build this? What are the dependencies? What breaks if we get it wrong? | **Engineering risk** — can't build it reliably |

Write one card:

```markdown
**PM**: <who benefits, how much, versus the cost of building it>
**Designer**: <architectural fit — composes, or fights the system>
**EM**: <feasibility — one session? dependencies? blast radius if wrong?>
```

Each lens gets one to three sentences grounded in the plan's actual text — quote or cite
`file:line`. A lens that produces only generic praise has not been applied; either find
the specific thing or say the lens found nothing, which is a real answer.

**When the lenses disagree, that is the finding.** PM says high value, EM says three
sessions — that tension is the decision the human needs to make, and burying it in an
averaged verdict destroys the one thing this stage produces. Surface it explicitly.

## Stage 2 — Definition of Ready

Seven checks. Each is `pass`, `fail`, or `n/a` with one line of evidence.

| # | Check | Fails when |
|---|---|---|
| 1 | **Problem stated** | The doc describes a solution with no problem, or the problem is "X exists and should be better" |
| 2 | **Scope bounded** | No statement of what is explicitly *out* of scope |
| 3 | **Acceptance is checkable** | "Works correctly" with no deterministic check behind it |
| 4 | **Fits one session** | Plan implies multiple sessions and names no split |
| 5 | **Dependencies named** | Depends on unfinished work, an unmade decision, or an unavailable credential, unstated |
| 6 | **Verification named** | No statement of which command or test proves it worked |
| 7 | **Rollback exists** | Touches persistent state or external effects with no way back |

Checks 3 and 7 are the ones that get faked. For 3, a plan that says "tests pass" must
name *which* tests, or it is asserting a check it has not identified. For 7, "we could
revert the commit" is not rollback for anything that wrote to a database, sent a
message, or deleted a file — name the branch, the backup, the retention window, or mark
it `fail`.

Check 4's failure is a **split**, not a rejection. If the plan is two sessions of work,
say where the seam is; that is more useful than "too big."

## Stage 3 — Dispatch the failure pass (conditional)

**Only when the plan is risky.** Dispatch `fog-advisor` when any of these hold:

- Check 7 failed or is `n/a` because the work touches persistent state.
- The plan introduces a new probabilistic step that something downstream consumes.
- EM's lens flagged blast radius.
- Any DoR check failed at all and the plan is being pushed through anyway.

Otherwise skip it and say you skipped it, with the reason. A gate that dispatches an
advisor on every trivial plan trains people to ignore the advisor.

**Give it the plan. Not your trio card, not your DoR results.** An advisor who reads your
assessment grades your assessment; the independence is the entire value of the dispatch
(`/fog` makes the same argument at more length). If the dispatch fails or returns nothing,
that is a **dispatch failure** — record it and do not report a verdict as though the pass
ran.

## Stage 4 — Verdict

One of four. The verdict is computed from Stages 1–3, not felt:

| Verdict | When | `Status:` becomes |
|---|---|---|
| **READY** | All DoR checks pass; no unresolved trio disagreement | `READY` |
| **REFINED** | Substantive gaps closed, one or more checks still open but non-blocking | `REFINED` |
| **NEEDS-SPLIT** | Check 4 failed; name the seam | unchanged |
| **NOT-READY** | Any of checks 1, 3, 5, or 7 failed | unchanged |

Checks 1, 3, 5, and 7 are blocking because each makes execution *unverifiable* rather
than merely harder: no problem, no acceptance test, a missing dependency, or no way back.
Checks 2, 4, and 6 are recoverable mid-session.

**Never advance `Status:` on a NOT-READY or NEEDS-SPLIT verdict**, including when the
user asks you to. An overridden gate is a gate that reports what it was told to report;
if the human wants to proceed anyway that is their call to make explicitly, in the doc,
in their own words — not by having this skill write a state the evidence does not support.

Write `Status:` with a single Edit to the existing line. It must remain exactly one
canonical token — `plan_status_validate.sh` rejects suffixes, so
`READY (pending review)` blocks the write.

## Output

```markdown
## Refinement — <slug>

**Verdict**: READY | REFINED | NEEDS-SPLIT | NOT-READY
**Status**: PLANNED → <new state, or "unchanged">

### Trio
PM / Designer / EM cards. Disagreements stated, not averaged.

### Definition of Ready
The seven checks, each pass/fail/n-a with one line of evidence.

### Failure pass
`fog-advisor` findings, or "skipped — <reason>", or "dispatch failed".

### What is missing
Only on REFINED / NEEDS-SPLIT / NOT-READY. Each item concrete enough to act on
without re-reading the plan. "None" on READY — do not manufacture items.
```

Then the exit block:

```
──────────────────────────────────────
Refinement complete. Verdict: <verdict>
Next: /workflow-execute <slug>   (READY only)

Spawn prompt (execute — fresh session):
┌─────────────────────────────────────
│ cd <repo-path>
│ Read <plan-doc-path>
│ /workflow-execute <slug>
└─────────────────────────────────────
──────────────────────────────────────
```

Omit the spawn prompt on any verdict other than READY. Offering the next step after a
failed gate is how gates get skipped.

## Failure modes of this skill

- **Rubber-stamping.** A gate that has never returned NOT-READY is not a gate. If every
  check passes on first read, re-read checks 3 and 7 specifically — they are the ones a
  plausible-looking plan fakes.
- **Averaging the trio.** Three lenses producing one bland verdict loses the disagreement,
  which was the most valuable output.
- **Gating a plan you could not read.** An unreadable target is an error. Reporting
  NOT-READY implies you assessed something.
- **Dispatching the advisor on everything.** Stage 3 is conditional for a reason.
- **Advancing `Status:` to be helpful.** The state machine is the record of what actually
  passed. Writing READY on a failed gate corrupts the one field downstream skills trust.
