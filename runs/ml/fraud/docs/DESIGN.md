# ml-fraud — the HITL gradient decision trail

Scale: four runs of the same target at four levels of human involvement (L1–L4).
Date: 2026-08-15
Plan: [`2026-08-15-gal-23-hitl-gradient.md`](../../../../.claude/docs/plans/2026-08-15-gal-23-hitl-gradient.md)
Issue: #23

**These rules were written before the run.** The level contract, the evidence rule, the
severity ladder, and the divergence routes below are pre-registration, not description.
A run that violates them does so visibly.

**One arm has since been run: L1, on 2026-08-15.** Everything above [The L1 arm](#the-l1-arm)
is the pre-registration as written before it; the arm section and the per-level rows in
Counted derivations / Asked-tier are the record of it. The pre-registration has not been
edited to fit the arm — where the arm sat awkwardly against it (see the terminal-state
entry), the awkwardness is recorded rather than smoothed.

---

## What this document is, and what it is not

This is the per-run trail for the HITL gradient: one section per level, written as runs
happen. It is the *record*, not the measurement — the measurement is the comparison
between arms, and it cannot begin until at least two arms exist.

**It is not the graph verdict.** `orchestrator-design.md` §3d fixes that criterion at
`loop_backs_per_run ≥ ~0.5` over **≥ 5 real BUILD runs**. This phase supplies at most 4.
No verdict may be read off this document.

---

## Pre-registered bets

Written before any run; each is falsifiable by the gradient itself.

| # | Bet | Falsified by |
|---|---|---|
| B1 | Quality drops somewhere between L2 and L4, not between L1 and L2 | An L1/L2 divergence at least as large as any L2/L3 or L3/L4 one |
| B2 | The permanent seats (D1, D3, D9-decision) are the ones whose handover costs quality | An L3 run that matches L2 on every artifact — i.e. §7's permanent set is over-drawn |
| B3 | Most divergences route to *template gap*, not to *seat table* | A majority routing to §7's seat table, which would be a finding against the design doc |

B2 is the load-bearing one: it is the test of `orchestrator-design.md` §7. **A failure at
L3 on a seat §7 marked handover-ready is a finding against the design doc**, not against
the run.

---

## The levels

Taken from the plan's level contract; L3's seat set cites `orchestrator-design.md` §7
rather than restating it, so a change to §7 propagates here.

| Level | Human occupies | Status |
|---|---|---|
| **L1 — full control** | Every seat; every step interrogated | **run 2026-08-15** — see [The L1 arm](#the-l1-arm) |
| **L2 — ask all** | Every question raised, no volunteered interrogation | not yet run |
| **L3 — ask vital** | §7's permanent set only — D1, D3, D9-decision | not yet run |
| **L4 — automated** | Nothing automatable | **BLOCKED on GAL-27** (`Workflow` dispatcher) |

---

## The evidence rule

Any run, at any level, classifies its terminal state as one of four, and must cite
evidence **the agent did not author**:

| Outcome | Agent-independent evidence required |
|---|---|
| **(a) chain broke** | Transition ledger (`.claude/logs/plan-transitions.jsonl`) — furthest `Status:` reached, written by the hook; and/or process exit code |
| **(b) harness stopped** | `error_max_turns` or an empty result, which `~/.claude/rules/shell.md` documents as indistinguishable from a logic failure at the API level |
| **(c) completed** | Ledger shows the terminal `Status:`; process exit code 0 |
| **(d) undetermined** | *None available.* First-class outcome, not a failure |

Reproduction is unavailable: `runs/_index/` is unpopulated, galactus does not own the
record shape, and `ML_PACKAGE_ROOT` is unpinned. So **(a) is claimed from external signal
rather than replay.** `Deferred(when ai-project-template's experiments/ registry lands)` —
at that point (a) can require replay instead.

---

## Severity ladder

*(Addition — not inherited from the archived format.)*

| Severity | Meaning |
|---|---|
| `silent-verdict` | Produces a confident wrong number. Worst: nothing surfaces |
| `silent-component` | A component drops out without failing; downstream reads as complete |
| `loud-surface` | Fails visibly at the surface — file-open, import, exit code |

---

## Findings

Severity, level, and source per row. **All four were found by inspection alone** — none
required running the pipeline. That is the evidence the failure class is open, and it is
what the scoped null rests on: null for the two *named* breaks (both closed), open for
the *class*.

| # | Finding | Severity | Level | Source |
|---|---|---|---|---|
| F3 | `refusal.*` nested, not flat — a check on the flat names reads `None` and inverts the finding | `silent-verdict` | pre-run | research F3; propagated into the superseded plan's own acceptance check |
| F4 | `catboost` silently dropped; `beats_baseline` computed over survivors with no gate on `skipped` | `silent-verdict` (unverified) | pre-run | research F4 |
| F8 | `ML_PACKAGE_ROOT` stale-but-importable → clean import, wrong numbers | `silent-verdict` | pre-run | research F-series; **preserve, do not fix** |
| F9 | `pocs/` default paths stale after rename | `loud-surface` | pre-run | repaired in `fecd27b` before this plan |

### Why F9 is rated below the others

F9 is rated `loud-surface` deliberately. It fails at file-open: the path does not exist,
the process dies, and the operator sees it. F3, F4, and F8 each produce a **confident
number that is wrong** — a check that reads `None` and inverts, a `beats_baseline`
computed over an incomplete field, an import that succeeds against a stale tree. Nothing
surfaces in any of the three.

Four specimens, **three** of the dangerous kind. The rationale is written out rather than
implied so a reader can disagree with the rating without reverse-engineering it.

F8 is a live specimen and **must survive** — fixing it destroys the only unfixed
`silent-verdict` instance available to run the gradient against.

F4's severity is marked `(unverified)`: settling whether `skipped` gates `beats_baseline`
requires reading `ai-project-template`'s `run_classification`, which is out of scope here.
Fraud's verdict stays UNVERIFIED until someone does. **The unresolvability is the recorded
finding.**

---

## Counted derivations

*(Inherited element. Populated per run; empty until the first run.)*

| Level | Derivation corrections | Of total shown | Notes |
|---|---|---|---|
| L1 | **2** | **of 9** | Both corrections were to *plan-asserted facts*, not to model output. See [Counted derivations, L1](#counted-derivations-l1) |
| L2 | — | — | not yet run |
| L3 | — | — | not yet run |
| L4 | — | — | blocked on GAL-27 |

**Do not over-read a zero.** Zero corrections across one run is consistent with a
well-drawn asked/shown boundary and equally consistent with an agreeable reviewer. The
count is the signal, and one sample does not establish it. This caveat is inherited from
the archived format and applies here unchanged.

---

## Asked-tier assessment

*(Inherited element. Populated per run; empty until the first run.)*

Per asked root: did it change a decision, or was it ceremony? A root that changes nothing
is kept only if it costs about a sentence.

| Level | Asked roots | Changed a decision | Ceremony |
|---|---|---|---|
| L1 | **4** | **2** | **2** — see [Asked-tier, L1](#asked-tier-l1) |
| L2 | — | — | — |
| L3 | — | — | — |

---

## Negative results

*(Inherited element. Recorded as results, not omissions.)*

- **One arm exists (L1). The gradient still has not been measured.** A gradient is a
  comparison; one point is not one. Every pre-registered bet (B1, B2, B3) remains untested,
  and no divergence routing has been exercised. Recorded so a reader cannot mistake one
  arm for a result.
- **L1 could not exercise the model run.** No toolkit (F8, unset `ML_PACKAGE_ROOT`) and no
  data (gitignored). The arm covered the verification chain and the trail; the modelling
  step was never entered by any arm. Whatever the gradient eventually shows, it will say
  nothing about behaviour *inside* `run_classification` unless a runnable frame appears.
- **L1 overturned no reasoning.** Two corrections, both bookkeeping (an uncut branch, a
  stale count); zero judgment corrections across 9 derivations. Consistent with a
  well-drawn boundary *and* with an agreeable reviewer — one arm cannot separate them.
- **L4 is unmeasured and will stay so until GAL-27 lands.** The gradient degrades to three
  points rather than failing; the automated end is simply unknown. **Not synthesized** —
  see the no-list.

---

## No-list

*(Inherited element. `Deferred(first level-1 run)` — worked stub below; no instance of
this artifact exists anywhere in the repo, and the archived format named it first while
containing none.)*

What the run declined to do, and why. Worked stub showing the intended shape:

> **Did not** fix `ML_PACKAGE_ROOT` (F8).
> **Because** it is the live specimen the gradient measures against; fixing it removes the
> subject.
> **Would reconsider if** a second unfixed `silent-verdict` specimen appears.

Shape: *did not* / *because* / *would reconsider if*. The third line is what separates a
no-list from a list of omissions — it names the trigger that would flip the decision.

**Q7 has since been resolved by the L1 arm** — the real instance is at
[No-list — Q7 resolves here](#no-list--q7-resolves-here). The stub above is left exactly as
pre-registered so the shape it predicted can be compared against the shape that emerged;
they match.

---

## The L1 arm

**Level:** L1 — full control. Every seat occupied by the operator; every step interrogated.
**Date:** 2026-08-15. **Target:** `runs/ml/fraud/`. **Level fixed per run** (Q6 default,
not escalated — see the Q6 note below).

### What L1 could actually execute

The arm has a hard boundary that is a property of the target, not of the level, and it must
be stated before anything else so no reader takes L1's terminal state as a statement about
human involvement:

`runs/ml/fraud/src/run.py` **cannot run in this repository**, by design and on two
independent counts:

1. **No toolkit.** galactus declares no ML dependencies (`run.py:36-37`, README). The `ml`
   package lives in `ai-project-template` under
   `template/_scaffold/{{ py_project_root }}/{{ ml_source_root }}/` — a copier template
   path, not an importable tree. `ML_PACKAGE_ROOT` is unset (F8, the live specimen).
2. **No data.** `runs/ml/fraud/data/` does not exist; it is gitignored (`.gitignore:40`)
   because it holds real records from `lebanese-blonde`.

So the L1 arm exercised **everything the pipeline does around the model run** — the
verification chain, the plan's own Test Plan, the trail — and could not exercise the model
run itself. That is a scoping fact recorded here, not a failure of the arm and not a
finding against L1.

### Terminal state: (a) chain broke

Per the evidence rule, with evidence the agent did not author:

| Evidence | Value | Authored by |
|---|---|---|
| Process exit code, `uv run python runs/ml/fraud/src/run.py` | **1** | the interpreter |
| stderr first line | `could not import the ML toolkit (No module named 'ml').` | `run.py:69-76` — written before this arm |
| Transition ledger, furthest `Status:` | `EXECUTED` (`IN_PROGRESS → EXECUTED`, 2026-08-15T18:25:19Z) | `plan_status_validate` hook |
| Ledger depth | 38 lines | the hook |

**Classification: (a) chain broke** — the process exited non-zero and did not reach the
work it exists to do.

**But the break is the designed one.** `run.py:64-76` catches `ImportError` and raises
`SystemExit` with a written explanation naming the cause and the fix. Exit 1 with a sentence
is the guard firing correctly, not a chain failing silently. Recorded as (a) because the
evidence rule classifies on *terminal state*, and the state is a non-zero exit before
completion — **not** on whether the operator approves of the reason.

This is the arm sitting awkwardly against the pre-registration, and the awkwardness is the
observation: the evidence rule's four outcomes have **no cell for "stopped correctly at a
guard."** A designed refusal-to-start and a genuine break both land in (a) on identical
evidence — exit code plus ledger. That is the same structural defect the plan's Q5 withdrew
the superseded commitment #1 over: a rule that cannot separate two states it needs to
separate. Recorded as an Open Question below rather than patched here, because patching
the pre-registration after seeing one arm is precisely what pre-registration forbids.

Note the F9 kinship: this is a `loud-surface` failure — visible, exit-coded, self-describing.
It is the *good* kind, and the arm confirms F9's rating rationale holds in practice.

### Counted derivations, L1

**2 corrections of 9 derivations shown.** Both were to facts the plan asserted, caught by
interrogating rather than accepting them:

| # | Shown | Correction | Kind |
|---|---|---|---|
| 1 | Plan header: `Branch: GAL-23-hitl-gradient` | The branch **did not exist**; the session was on `main`, with the trail staged there. Created with `--no-track` per the operator's branch convention, carrying the staged file over | Precondition drift |
| 2 | Step 0: ledger holds "**21** real transitions" | Ledger holds **38 lines** at arm time. The plan's figure was true when written and is now stale; Step 0 says "re-run if the branch moves" | Stale count |

The other 7 held: `pocs` grep = 1 line, both `Deferred` checks = 0, severity count = 9 (≥ 4),
trail exists at the `docs/` path, full suite `533 passed`, fraud suite `35 passed, 3 skipped`.

**Do not over-read the 2.** Both corrections are bookkeeping — a branch that was not cut and
a count that drifted. **Neither is a judgment correction**, which is what B1 is actually
about: at L1 the operator interrogated 9 derivations and overturned *no reasoning*, only two
stale facts. One arm does not establish whether that is a well-drawn boundary or an agreeable
reviewer; the inherited caveat applies unchanged.

### Asked-tier, L1

Four roots were asked. Two changed a decision; two were ceremony, and both cost about a
sentence, so both are kept.

| Root | Changed a decision? | Detail |
|---|---|---|
| Can `run.py` execute here at all? | **Yes** | Determined the arm's entire scope. Without asking, the arm would have reported a terminal state for a chain it never entered |
| Which barrier fires first — toolkit or data? | **Yes** | The import guard (`run.py:60-76`) precedes `build_frame` (`run.py:255`), so **the toolkit barrier masks the data barrier**. An operator fixing only `ML_PACKAGE_ROOT` would hit the second barrier immediately after. Routed below |
| Do the four Findings rows still hold? | No — ceremony | All four re-read; all four stand as written. Kept: one sentence |
| Does §7's seat table say what the plan says it says? | No — ceremony | D1/D3/D9 verified at `orchestrator-design.md:369-379,403,1169`. Citation accurate. Kept: one sentence |

The two that changed a decision were both **"can this actually run?"** questions — the class
an unattended arm is least likely to volunteer, because the pipeline reports on what it did,
not on what it never reached. That is L1's specific contribution and the thing to watch when
L2 and L3 run.

### No-list — Q7 resolves here

**Q7 asked what a no-list looks like as an artifact.** It now has an instance rather than a
stub. The shape from the stub — *did not* / *because* / *would reconsider if* — **held
unchanged**; the third line did the work it was designed to do, and no fourth line was
wanted. Q7 is answered: **the stub's shape is the artifact's shape.**

> **Did not** fix `ML_PACKAGE_ROOT` (F8).
> **Because** it is the live specimen the gradient measures against; fixing it removes the
> subject. Named in the plan's Out of Scope.
> **Would reconsider if** a second unfixed `silent-verdict` specimen appears.

> **Did not** obtain `runs/ml/fraud/data/dataset.csv` to make the model run executable.
> **Because** it holds real records about identifiable people, is gitignored deliberately,
> and copying it in to complete an arm would trade a data-handling guarantee for a metric
> the arm does not need.
> **Would reconsider if** a synthetic frame with the same thinness (800 rows, 14 positives)
> were built — which would make the model run exercisable with no real records.

> **Did not** synthesize the L4 arm.
> **Because** L4 is gated on GAL-27's `Workflow` dispatcher, which has not landed. Writing
> what L4 "would have" produced turns the gradient's automated end from unmeasured into
> falsely measured.
> **Would reconsider if** GAL-27 lands and the dispatcher can run the arm for real.

> **Did not** record a graph verdict.
> **Because** §3d fixes the criterion at ≥ 5 real BUILD runs; this arm is one. Reading a
> verdict off one arm is exactly what the criterion exists to prevent.
> **Would reconsider if** the run count reaches 5 — at which point the verdict is read from
> `loop_backs_per_run`, not from any arm's narrative.

> **Did not** patch the evidence rule to add a "stopped correctly at a guard" outcome.
> **Because** the rule is pre-registration; amending it after seeing the first arm it
> constrains would destroy what makes it a commitment.
> **Would reconsider if** a second arm hits the same ambiguity — two instances make it a
> structural defect rather than one arm's bad luck.

**What the instance teaches that the stub could not:** every entry above is a *refusal to
manufacture evidence* — decline the data, decline L4, decline the verdict, decline the
patch. The no-list's real subject is the boundary between measured and asserted. The stub
could not show that, because a single worked example has no pattern to reveal.

### Q6 — level fixed, not escalated

Level was **fixed per run**, per Q6's recorded default. The arm did not escalate, and no
point in it wanted escalation: the barrier was structural, not a decision the operator could
have interrogated their way through. Q6 stays `Deferred(after the first two runs)` — one arm
cannot settle it, and this arm supplied no pressure either way.

---

## Divergence routing

Where two levels disagree, **exactly one of three is true**, and each routes somewhere
different. This is the feedback loop: a divergence that routes nowhere is not recorded as
a divergence.

| Divergence | Means | Routes to |
|---|---|---|
| Lower level produced a **worse artifact** | The template does not carry what the human supplied | **Template fix** — a GAL-27 checklist, or a skill body |
| Lower level **made a call the human would have made differently** | A seat was handed over that should not have been | **§7's seat table** — a finding against [`orchestrator-design.md`](../../../../.claude/docs/plans/2026-08-14-orchestrator-design.md) |
| Human **stated a preference no artifact records** | The preference is unencoded | **A preference record** — candidate for CLAUDE.md or a skill default |

### Recorded divergences

**None — and this is not a null result.** Divergence is defined *between levels*; one arm
exists, so the comparison the table describes cannot be performed at all. No routing may be
read off L1 alone, and B1/B2/B3 remain entirely untested.

One observation from L1 is **routable but is not a divergence**, and is recorded separately
so it is not miscounted as one:

| Observation | Route | Destination |
|---|---|---|
| The toolkit barrier (`run.py:60-76`) masks the data barrier (`run.py:255`). An operator who sets `ML_PACKAGE_ROOT` hits the missing-data exit immediately after, having been told about only one of two blockers | **Template fix** | `run.py`'s import guard — could name both preconditions in one message. Not fixed here: `run.py` is out of this plan's scope, and F8 must survive untouched |

Routed as a template fix rather than a seat-table finding because no seat was handed over —
at L1 the operator occupied every seat, and the masking is a property of the script's guard
ordering, not of who was sitting where.

---

## Open Questions

Each carries a concrete revisit trigger, per `/proto-scope`'s convention
(`proto-scope/SKILL.md:51-53`): a `Deferred` **without** a trigger counts as Open, which
is a blocker. That is the template's built-in falsifier.

| # | Question | State | Current default |
|---|---|---|---|
| Q6 | Per-run level, or mid-run escalation? | `Deferred(after the first two runs)` | Level is **fixed per run**. Escalation matches §5a-ter's escalation edge and is more useful, but a run that escalated sits at neither level cleanly, which costs the comparison its meaning |
| Q7 | What does a no-list look like as an artifact? | **RESOLVED (L1 arm, 2026-08-15)** | The stub's *did not* / *because* / *would reconsider if* shape **held unchanged**. Five real entries at [No-list](#no-list--q7-resolves-here); the instance's lesson is that the artifact's subject is the measured/asserted boundary |
| Q8 | Can the evidence rule distinguish a designed guard-stop from a genuine break? | `Deferred(if a second arm hits the same ambiguity)` — **raised by the L1 arm** | **No.** Both land in **(a)** on identical evidence (non-zero exit + ledger). Current default: classify as (a) and write the distinction in prose. Not patched — amending pre-registration after one arm forbidden |
| Q2-followup | Does `skipped` gate `beats_baseline`? Requires reading `ai-project-template`'s `run_classification` | `Deferred(when a work item takes it up)` | Fraud's verdict stays **UNVERIFIED** |
| ER-followup | Can (a) require replay rather than external signal? | `Deferred(when ai-project-template's experiments/ registry lands)` | External signal only |

---

## Known limitations

- **No skill reads this file at this path.** `DESIGN.md` under `docs/` matches the
  convention set by `runs/ml/lending/docs/` and `runs/ai/marketing-comms/docs/`, but
  `/proto-scope` resolves `--output` to repo-root or `.claude/docs/`, never a run
  directory (`proto-scope/SKILL.md:40`). The siting is justified by **convention-match
  alone**. The superseded plan's idempotency claim is **withdrawn, not relocated**.
- **Severity and level are judgments, not measurements.** The rationale is written out
  (see F9 above) so a reader can disagree without reverse-engineering.
- **The levels may not be cleanly separable in practice.** A human running L3 may
  interrogate reflexively, contaminating the arm. Q6 fixes level per run; the transition
  ledger records the path independently of the operator's self-report.
