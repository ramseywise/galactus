# GAL-23 — The HITL gradient: measuring where human involvement stops paying
Date: 2026-08-15
Status: EXECUTED
From: IN_PROGRESS
Review: pending
Track: agent
Issue: #23
Branch: GAL-23-hitl-gradient
Epistemic: UNTESTED
Epistemic-by: skipped — Light path (2 files, additive, no persistent-state or shared-config effect); none of Stage 3's four dispatch conditions held (check 7 passed, no new probabilistic step, EM named no specific damage, no blocking check failed). Note this is a *skip*, not the dispatch failure recorded by the 2026-08-15 REFINED pass: `resolve-capability fog` now returns exit 0 at `.claude/agents/fog-advisor.md`, because this session is rooted at `~/workspace/galactus` rather than `~/workspace`. The advisor was available and deliberately not called.
Epistemic-at: 2026-08-15
Epistemic-findings: 0

Supersedes: `.claude/docs/plans/2026-08-15-gal-23-proto-pipeline-dry-run.md`
(`Status: SUPERSEDED`). That doc framed the work as two discrete modes — HITL and
unattended — over a sequential chain. Both framings were wrong: the pipeline is
orchestrated from scope rather than sequential, and the human is present in every run.
Its research findings (F1–F9) survive and are cited here; its Mode A/Mode B structure does
not.

Reads: `.claude/docs/plans/2026-08-14-orchestrator-design.md` (issue #13, `EXECUTED`) —
§7 "The HITL → automated path", §3f "The pipeline shape, corrected", §5a "Loop
termination". This plan is the measurement that design asked for.

## Plan
Date: 2026-08-15
Based on: the superseded doc's `## Research`, the control-plane design (#13), and live
verification of the transition ledger.

### Goal

Measure **at which degree of human involvement the pipeline's output stops being
trustworthy**, by running the same work at four levels and comparing. The gradient replaces
the previous two-mode framing: involvement is a parameter, not a binary.

The measurement serves three decisions:

1. **Which seats must stay human** — `orchestrator-design.md` §7 asserts D1, D3, and
   D9-decision are permanent. That table is currently a judgment; the gradient tests it.
2. **Whether the graph is worth building** — §3d fixes the criterion in advance:
   `loop_backs_per_run ≥ ~0.5` over ≥ 5 real BUILD runs. This phase contributes runs
   toward that count and cannot pre-empt the verdict.
3. **What to fix when the arms diverge** — each divergence routes to a template gap, a
   missing gate, or an unencoded preference. That routing is the feedback loop.

### Open Questions

Resolved during planning (2026-08-15):

- **Q1 — Two modes or a gradient?** → **Gradient, four levels** (operator decision,
  2026-08-15). Both original modes had a human; the real variable was interrogation depth.
  A gradient makes the asked-vs-shown boundary an observation rather than a judgment: the
  level at which quality drops *is* the answer.

- **Q2 — Where does the decision trail live?** → **`runs/ml/fraud/docs/DESIGN.md`.**
  Corrects the superseded doc's run-root siting. Both existing instances
  (`runs/ml/lending/docs/`, `runs/ai/marketing-comms/docs/`) live under `docs/`; verified
  2026-08-15. Note the superseded plan's idempotency argument (its R3) does **not** hold at
  either path — `proto-scope/SKILL.md:40` resolves `--output` to repo-root or
  `.claude/docs/`, never a run directory. The siting is justified by convention-match
  alone, and R3's guarantee is withdrawn rather than relocated.

- **Q3 — Does this fold into GAL-27?** → **No; the two split along build-vs-measure.**
  GAL-27 ships the mechanism (band contract, `Workflow` dispatch, release checklists);
  GAL-23 consumes it and measures. Folding would have the comparison arm built by the work
  it evaluates. Sequencing: levels 1–3 need no dispatcher (a human types the commands) and
  can run now; **level 4 depends on GAL-27's `Workflow` dispatcher** and is gated on it.

- **Q4 — Is the invocation suppression a defect?** → **No — deliberate, and GAL-27 D2
  keeps it.** Eight skills carry `disable-model-invocation: true`; five are `proto-*`
  (also `ml-select`, `ml-transform`, `prototype-genesis`). Verified 2026-08-15. The
  superseded plan called this a loader defect in two places and undercounted it as "six
  BUILD-band `proto-*` skills". Both statements are void. No follow-up issue is opened.

- **Q5 — What may a run claim about how it ended?** → **See the evidence rule below.**
  The superseded plan's commitment #1 (unattended runs may never report *chain broke*) is
  **withdrawn**. It was unfalsifiable: the agent writing the report cannot emit a verdict
  it was instructed to suppress, so a real break and a clean run read identically. Replaced
  with an evidence rule that binds all four levels equally.

Deliberately left open (not blockers):

- **Q6 — Per-run level, or mid-run escalation?** `Deferred(after the first two runs)` —
  default: **level is fixed per run.** Escalation is more useful and matches §5a-ter's
  escalation edge, but a run that escalated sits at neither level cleanly, which costs the
  comparison its meaning. Revisit once two runs exist to compare.
- **Q7 — What does a no-list look like as an artifact?** `Deferred(first level-1 run)` —
  default: Step 2 reserves the section with a worked stub. No instance exists anywhere in
  the repo; the archived format named it first and contained none.

### The four levels

| Level | Human occupies | Seats per §7 | Dispatcher |
|---|---|---|---|
| **L1 — full control** | Every seat; every step interrogated | all | none needed |
| **L2 — ask all** | Every question raised, no volunteered interrogation | all | none needed |
| **L3 — ask vital** | Permanent seats only — D1, D3, D9-decision | §7's permanent set | none needed |
| **L4 — automated** | Nothing automatable | none | **GAL-27 `Workflow`** |

L3's seat set is taken from `orchestrator-design.md` §7, not invented here. That is what
makes L3 a test of the table: **a failure at L3 on a seat §7 marked handover-ready is a
finding against the design doc**, not against the run.

### The evidence rule (replaces the withdrawn commitment)

Any run, at any level, classifies its terminal state as **(a) chain broke**,
**(b) harness stopped**, or **(c) completed** — and must cite evidence the agent did not
author:

- the transition ledger (`~/workspace/galactus/.claude/logs/plan-transitions.jsonl` —
  absolute per Q9/F10: the relative name resolves by session rooting) — the furthest
  `Status:` reached, written by the hook, not by the agent;
- process exit code;
- for (b) specifically: `error_max_turns` or an empty result, which
  `~/.claude/rules/shell.md` documents as indistinguishable from a logic failure at the
  API level.

Where no such evidence exists, the run records **(d) undetermined** — a first-class
outcome, not a failure. Reproduction remains unavailable (`runs/_index/` is unpopulated and
galactus does not own the record shape; `ML_PACKAGE_ROOT` is unpinned), so (a) is claimed
from external signal rather than replay. `Deferred(when ai-project-template's experiments/
registry lands)` — at which point (a) can require replay instead.

**Amended post-L3 (2026-08-15):** the ledger path here, in Step 0, and in the Test Plan
row was absolutized per Q9/F10, and the trail's evidence rule v2 adds a discriminator on
(a) for designed guard-stops (Q8) plus a vacuity clause for the bet falsifiers (Q10).
The batch is recorded in the trail's
[Post-L3 amendments](../../../runs/ml/fraud/docs/DESIGN.md#post-l3-amendments--the-q8q9q10-batch)
section — pointer, not copy. All three arms were measured under v1, which stands there
as written; L4 runs under v2.

### Approach

Run the same target — `runs/ml/fraud/` — at each level, recording the trail in
`runs/ml/fraud/docs/DESIGN.md` and letting the transition ledger record the path
independently. Compare the arms; route each divergence to a fix.

The tradeoff: four runs cost more than two, and L1 versus L2 may prove a narrow gap. If
appetite is limited, **run L1 and L3** — the widest informative interval. L4 is gated on
GAL-27 regardless.

The subject is unchanged from the superseded plan and for the same reason: fraud *refuses*
rather than reporting a confident number, which is the more interesting path to drive a
pipeline over.

### Out of Scope

- **Building GAL-27's mechanism.** Band contract, `Workflow` dispatch, and checklists are
  27's deliverables. This plan consumes them.
- **Deciding the graph question.** §3d fixes the criterion at ≥ 5 runs; this phase supplies
  at most 4 and must not pre-empt the verdict.
- **Resolving `ML_PACKAGE_ROOT`** — a live specimen (F8); must survive.
- **Fixing the catboost skip** or reading `ai-project-template` to settle whether `skipped`
  gates `beats_baseline`. The unresolvability is the recorded finding (F4).
- **Populating `runs/_index/`** — galactus does not own the record shape.
- **Removing `disable-model-invocation` from any skill** — GAL-27 D2 forecloses this.
- **Any change to `runs/ai/marketing-comms/`** (reference implementation, 277 tests).
- **Reviving `archived/design-prototype/`.** Its format is extracted as a spec; the skill
  stays archived.

### Steps

#### Step 0: Preconditions

**Files**: none (verification only)

Re-derived 2026-08-15 on branch `GAL-23-proto-pipeline-dry-run` after rebase onto
`origin/main`. The superseded plan recorded these against the wrong branch — three of its
four were false.

- Branch rebased onto `origin/main`; tree clean.
- `grep -rn "pocs" runs/ --include="*.py"` returns **one** line — a comment at
  `runs/ml/fraud/src/run.py:50` narrating the completed rename. Not the two stale defaults
  the superseded plan asserted; **that repair already landed in `fecd27b`** and is better
  than the version planned (`RUN_ROOT`/`parents[1]` rather than `REPO_ROOT`/`parents[4]`
  plus a string literal).
- `~/workspace/galactus/.claude/logs/plan-transitions.jsonl` (absolute per Q9/F10) exists
  and holds **21 real transitions**;
  `loop_backs = 0`; `EXECUTED → COMPLETE` has fired 4 times.
- Both `DESIGN.md` instances live under `docs/`.

**Done when**: read. No action. Re-run if the branch moves.

---

#### Step 1: Record the level contract in the plan doc

**Files**: this doc (the four-level table and evidence rule above)

**What**: The level definitions and the evidence rule are the pre-registration. They are
written *before* any run, which is what makes them commitments rather than description.
L3's seat set must cite §7 rather than restate it, so that a change to §7 propagates.

**Test**: `grep -n "L3 — ask vital" .claude/docs/plans/2026-08-15-gal-23-hitl-gradient.md`
**Done when**: four levels defined with their seat sets; the evidence rule names at least
one agent-independent source per outcome; (d) undetermined is present as a valid outcome.

---

#### Step 2: Create `runs/ml/fraud/docs/DESIGN.md`

**Files**: `runs/ml/fraud/docs/DESIGN.md` (new)

**What**: The per-run trail. One section per level, written as runs happen. Structure from
`.claude/skills/archived/design-prototype/SKILL.md:183` — cited at its **actual** line;
the superseded plan cited `:114-168`, which is wrong.

Six elements are inherited from that block; **three are additions and are labelled as
such** rather than laundered through the citation:

| Element | Origin |
|---|---|
| Header (scale, date, "rules written before the run") | inherited |
| Pre-registered bets | inherited |
| Counted derivations (`N of M`) + do-not-over-read caveat | inherited |
| Asked-tier assessment | inherited |
| Negative results, recorded as such | inherited |
| No-list | inherited (Q7: stub) |
| **Severity** (`silent-verdict` > `silent-component` > `loud-surface`) | **added** |
| **Level** (which of L1–L4 produced the observation) | **added** |
| **Divergence routing** (template gap / missing gate / unencoded preference) | **added** |

Unresolved entries use `/proto-scope`'s vocabulary: Open Questions carry a concrete revisit
trigger; Key Decisions are `Deferred(<trigger>)` with the current default recorded. Per
`proto-scope/SKILL.md:51-53`, a `Deferred` **without** a trigger counts as Open — a
blocker. That is the template's built-in falsifier.

**Test**: `test -f runs/ml/fraud/docs/DESIGN.md && ! grep -q 'Deferred(<' runs/ml/fraud/docs/DESIGN.md`
**Done when**: file exists at the `docs/` path; all nine elements present; no unfilled
`Deferred(<...>)` placeholder remains.

---

#### Step 3: Seed the Findings table with the four specimens

**Files**: `runs/ml/fraud/docs/DESIGN.md` (Findings table)

**What**: All four were found **by inspection alone** — none required running the pipeline.
This is the evidence that the failure class is open, and it is what the scoped null rests
on: null for the two *named* breaks (both closed), open for the *class*.

The four specimens are **F3, F4, F8, and F9**, seeded into the Findings table of
[`runs/ml/fraud/docs/DESIGN.md`](../../../runs/ml/fraud/docs/DESIGN.md) — with their
severity, level, source, and the F9 rationale recorded **there and not restated here**.
Three are of the `silent-verdict` kind (F3, F4, F8); F9 is rated `loud-surface` because it
fails at file-open rather than producing a confident wrong number.

This step names *which* findings to seed and *what each row must carry*; the rows
themselves live in the trail. Executed 2026-08-15: the row text was previously duplicated
verbatim across both documents, which is the drift surface Step 5 exists to forbid —
its `Done when` requires that no finding text be duplicated across the two documents,
and a `grep` for the pointer passed while that condition was false.

**Test**: `grep -c "silent-verdict\|loud-surface" runs/ml/fraud/docs/DESIGN.md` — expect ≥ 4.
Scoped to `DESIGN.md`; the superseded plan's version of this check returned 11 against the
**plan doc itself**, so it was green on nothing.
**Done when**: four rows with severity, level, and source; the F9 rationale written out.

---

#### Step 4: Record the divergence-routing contract

**Files**: `runs/ml/fraud/docs/DESIGN.md` (a `## Divergence routing` section)

**What**: Where two levels disagree, exactly one of three is true, and each routes
somewhere different:

| Divergence | Means | Routes to |
|---|---|---|
| Lower level produced a worse artifact | the template does not carry what the human supplied | template fix (GAL-27 checklist, or a skill body) |
| Lower level made a call the human would have made differently | a seat was handed over that should not have been | §7's seat table — **a finding against `orchestrator-design.md`** |
| Human stated a preference no artifact records | preference is unencoded | a preference record; candidate for CLAUDE.md or a skill default |

**Test**: `grep -n "Divergence routing" runs/ml/fraud/docs/DESIGN.md`
**Done when**: all three routes present with their destinations named.

---

#### Step 5: Point this plan at the trail

**Files**: this doc (a `## Decision Trail` pointer)

**What**: A pointer, not a copy — two copies drift and the drift is invisible.

**Test**: `grep -n "runs/ml/fraud/docs/DESIGN.md" .claude/docs/plans/2026-08-15-gal-23-hitl-gradient.md`
**Done when**: the pointer resolves to an existing file and no finding text is duplicated
across the two documents.

### Test Plan

| Check | Command | Expect |
|---|---|---|
| Full baseline holds | `uv run pytest --tb=no -q` | `533 passed` |
| Fraud suite | `uv run pytest "runs/ml/fraud/tests" -q` | `35 passed, 3 skipped` |
| No stale paths | `grep -rn "pocs" runs/ --include="*.py"` | 1 line (the narrating comment) |
| Trail exists at the right path | `test -f runs/ml/fraud/docs/DESIGN.md` | exit 0 |
| No unfilled placeholder | `grep -c 'Deferred(<' runs/ml/fraud/docs/DESIGN.md` | 0 |
| No empty defer | `grep -cE 'Deferred\(\s*\)' runs/ml/fraud/docs/DESIGN.md` | 0 |
| Severity populated | `grep -c "silent-verdict\|loud-surface" runs/ml/fraud/docs/DESIGN.md` | ≥ 4 |
| Ledger readable | `wc -l < ~/workspace/galactus/.claude/logs/plan-transitions.jsonl` | ≥ 21 |

The two `Deferred` checks are the ones that matter: they are the template's own falsifier,
and they are stated as **two separate greps with numeric expectations** rather than one
alternation delegated to "manually verify". The superseded plan's version passed on its own
literal template text.

### Risks & Rollback

- **R1 — The frame is written but never exercised.** This phase produces the contract; the
  runs follow. *Mitigation:* the level contract and evidence rule are falsifiable — a run
  that violates them does so visibly. *Rollback:* additive; `git checkout runs/ml/fraud/`.

- **R2 — L4 is blocked on GAL-27.** If 27 slips, the gradient has three points, not four,
  and the automated end is unmeasured. *Mitigation:* L1–L3 are independently informative
  and need no dispatcher; the gradient degrades rather than fails.

- **R3 — `DESIGN.md` under `docs/` matches convention but has no skill that reads it.**
  `/proto-scope` will not find it there (Q2). *Mitigation:* stated as a known limitation
  rather than a guarantee; the superseded plan's idempotency claim is withdrawn, not
  relocated.

- **R4 — Severity and level are judgments, not measurements.** *Mitigation:* Step 3
  requires the rationale be written, so a reader can disagree without reverse-engineering.

- **R5 — The gradient's levels may not be cleanly separable in practice.** A human running
  L3 may interrogate reflexively, contaminating the arm. *Mitigation:* Q6 fixes level per
  run; the transition ledger records the path independently of the operator's self-report.

- **R6 — Contributing runs toward §3d's count could tempt an early graph verdict.** The
  criterion is ≥ 5 runs; this phase supplies at most 4. *Mitigation:* named in Out of Scope
  and in the Goal; the verdict stays deferred.

## Decision Trail

The per-run trail lives at [`runs/ml/fraud/docs/DESIGN.md`](../../../runs/ml/fraud/docs/DESIGN.md)
— findings, severities, counted derivations, no-list, and divergence routing are recorded
there and **not duplicated here**. This is a pointer, not a copy: two copies drift, and the
drift is invisible.

### Open Questions

Carried forward for `/proto-refine` — none block execute:

- **Q6 (per-run level vs mid-run escalation)** — `Deferred(after the first two runs)`,
  default: fixed per run.
- **Q7 (no-list shape)** — `Deferred(first level-1 run)`, default: stub reserved in Step 2.
- **Q2 follow-up** — whether a separate work item reads `ai-project-template`'s
  `run_classification` to settle whether `skipped` gates `beats_baseline`. Out of scope
  here; fraud's verdict stays UNVERIFIED until someone does.
- **Evidence-rule follow-up** — `Deferred(when experiments/ registry lands)`: at that
  point (a) can require replay rather than external signal.

---

**Next step**: `/proto-refine gal-23-hitl-gradient`
