---
name: proto-refine
description: "Readiness gate between plan and execute. Applies PM / designer / EM lenses to one planned work item, checks it against the Definition of Ready, dispatches an isolated failure pass when the plan is risky, and either advances Status: PLANNED → REFINED → READY or says exactly what is missing. Triggers: 'is this ready', 'refine the plan', 'DoR check', 'ready to execute', 'gate this', '/proto-refine'."
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
| `Status:` is `RESEARCH` or `RESEARCHED` | Stop — there is no plan to gate yet. Point at `/proto-plan`. |
| `Status:` is `IN_PROGRESS` or later | Stop — the gate is behind you. Point at `/proto-review`. |
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

This dispatch is a **CROSS** call: an adversarial capability aimed at the artifact, with
context deliberately withheld. Its outcome is what the `Epistemic:` axis records.

**Which capabilities are live here is derived, not recalled.** Ask the router rather than
working from this list — the list is documentation and can drift; the derivation reads the
doc's own state:

```bash
python3 -c "import json,sys;print(json.dumps({'doc':open(sys.argv[1]).read()}))" \
  <plan-doc-path> | uv run python -m review.cli derive-phases
```

`capabilities.active` names what is callable at this point in the pipeline; `refine` is
the scheduled call site for `assumption_audit` and `fog`. Every capability not active
comes back in `capabilities.skipped` **with a reason** — the two halves are mandatory-
complete, so a capability cannot silently vanish from the table. Exit 1 means the doc did
not route at all: that is a derivation failure, not "no capabilities apply," and it must
not be recorded as a clean skip.

The risk conditions above still gate whether you *dispatch*. Derivation says what is
callable; the conditions say whether calling is warranted.

### Write the epistemic state

Whatever happens in this stage — dispatched, skipped, or failed — write the result to the
plan doc before Stage 4:

```
Epistemic: UNTESTED | NO_CONFLICT | CONFLICTED | BLOCKED
Epistemic-by: <the capability, or `skipped — <reason>`, or `dispatch failed`>
Epistemic-at: YYYY-MM-DD
Epistemic-findings: <count>
```

| Outcome | Value |
|---|---|
| Dispatched, nothing unresolved | `NO_CONFLICT` |
| Dispatched, open findings nobody closed | `CONFLICTED` |
| Dispatched, a finding severe enough that advancing is a mistake | `BLOCKED` |
| Skipped (plan not risky) or dispatch failed | `UNTESTED` |

`NO_CONFLICT` is not `correct` — it means the applicable adversarial checks found no
unresolved contradiction. Never upgrade "nothing was found" into "this is sound."

**You may not write `READY` without a fresh `Epistemic:` from this run.** A value left by
an earlier run is stale and does not satisfy this — re-dispatch or record the skip. The
hook enforces coherence (it rejects `READY` + `CONFLICTED`/`BLOCKED`) but it cannot tell
fresh from stale; that guarantee lives here, at the writer. `UNTESTED` + `READY` is legal
and deliberately visible — it is the honest record of "ready by default, nothing checked
it," and hiding it behind a required-field regime is what produces compliance theater.

## Stage 4 — Verdict

One of four. The verdict is computed from Stages 1–3, not felt:

| Verdict | When | `Status:` becomes |
|---|---|---|
| **READY** | All DoR checks pass; no unresolved trio disagreement | `READY` |
| **REFINED** | Substantive gaps closed, one or more checks still open but non-blocking | `REFINED` |
| **NEEDS-SPLIT** | Check 4 failed; name the seam | `SUPERSEDED` + `Superseded-by:` naming the split docs |
| **NOT-READY** | Any of checks 1, 3, 5, or 7 failed | unchanged |

Checks 1, 3, 5, and 7 are blocking because each makes execution *unverifiable* rather
than merely harder: no problem, no acceptance test, a missing dependency, or no way back.
Checks 2, 4, and 6 are recoverable mid-session.

**Never advance `Status:` toward `READY` on a NOT-READY or NEEDS-SPLIT verdict**, including
when the user asks you to. An overridden gate is a gate that reports what it was told to
report; if the human wants to proceed anyway that is their call to make explicitly, in the
doc, in their own words — not by having this skill write a state the evidence does not
support.

**`SUPERSEDED` on NEEDS-SPLIT is not an advance — it is an exit.** Work that needs dividing
has nowhere legal to go otherwise, so the operator hand-edits `Status:` to unblock the
pipeline and the record of where the work went is destroyed. `SUPERSEDED` is terminal for
*this doc* but not for the work: `Superseded-by:` must name the split docs, which is the
record a hand-edit loses. Write it only when you can name them — if you cannot, the verdict
is NOT-READY and `Status:` stays unchanged.

Write `Status:` with a single Edit to the existing line. It must remain exactly one
canonical token — `plan_status_validate.sh` rejects suffixes, so
`READY (pending review)` blocks the write.

Write `From:` alongside it, naming the state you are advancing *from* — `From: PLANNED`
for `PLANNED → REFINED`, `From: REFINED` for `REFINED → READY`. The hook validates the
pair against the legal-edge table and rejects a skipped state.

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
Next: /proto-execute <slug>   (READY only)

Spawn prompt (execute — fresh session):
┌─────────────────────────────────────
│ cd <repo-path>
│ Read <plan-doc-path>
│ /proto-execute <slug>
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
