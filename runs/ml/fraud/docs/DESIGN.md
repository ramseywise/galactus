# ml-fraud — the HITL gradient decision trail

Scale: four runs of the same target at four levels of human involvement (L1–L4).
Date: 2026-08-15
Plan: [`2026-08-15-gal-23-hitl-gradient.md`](../../../../.claude/docs/plans/2026-08-15-gal-23-hitl-gradient.md)
Issue: #23

**These rules were written before the run.** The level contract, the evidence rule, the
severity ladder, and the divergence routes below are pre-registration, not description.
A run that violates them does so visibly.

**Three arms have since been run: L1, L2, and L3, all on 2026-08-15.** Everything above
[The L1 arm](#the-l1-arm) is the pre-registration as written before them; the arm sections
and the per-level rows in Counted derivations / Asked-tier are the record. The
pre-registration has not been edited to fit any arm — where an arm sat awkwardly against
it (see all three terminal-state entries, and B2's vacuous firing at L3), the awkwardness
is recorded rather than smoothed.

**The post-L3 Q8/Q9/Q10 batch has since landed** — see
[Post-L3 amendments](#post-l3-amendments--the-q8q9q10-batch). It amends the instrument
for L4 onward; the pre-registration text above the arms stands as written, with pointer
notes marking what v2 supersedes.

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

**Amended post-L3 (Q10):** the falsifiers above carry no vacuity clause, and B2's fired
at L3 on a match the guard guaranteed. The table is left as written — B2's vacuous firing
was recorded under it — and a [vacuity clause](#vacuity-clause-q10) now binds firings
prospectively.

---

## The levels

Taken from the plan's level contract; L3's seat set cites `orchestrator-design.md` §7
rather than restating it, so a change to §7 propagates here.

| Level | Human occupies | Status |
|---|---|---|
| **L1 — full control** | Every seat; every step interrogated | **run 2026-08-15** — see [The L1 arm](#the-l1-arm) |
| **L2 — ask all** | Every question raised, no volunteered interrogation | **run 2026-08-15** — see [The L2 arm](#the-l2-arm) |
| **L3 — ask vital** | §7's permanent set only — D1, D3, D9-decision | **run 2026-08-15** — see [The L3 arm](#the-l3-arm) |
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

**Amended post-L3 (Q8 + Q9):** the table above is v1 — the instrument all three arms were
measured under, left as written, including the relative ledger path that is F10's whole
subject. The binding rule for L4 and after is
[Evidence rule v2](#evidence-rule-v2-q8--q9).

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
| F10 | Evidence rule / Step 0 / Test Plan name the ledger by a **relative** path; it resolves by session rooting (`~/workspace` → global 1-line file, `~/workspace/galactus` → repo-local 39-line file). Two arms rooted differently cite different files under one name and read as continuous | `silent-verdict` | **L2** | [The L2 arm](#f10--the-ledger-path-is-session-rooted); first of this class found by *running*, not by inspection |

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
| L2 | **2** | **of 8** | Both to plan-asserted facts again; **neither a judgment correction**. See [Counted derivations, L2](#counted-derivations-l2) |
| L3 | **0** new (2 re-observations) | **of 8** | Both of L2's corrections re-observed unchanged — the plan is deliberately unpatched mid-gradient. Zero new corrections; zero judgment corrections. See [Counted derivations, L3](#counted-derivations-l3) |
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
| L2 | **2** | **2** | **0** — see [Asked-tier, L2](#asked-tier-l2) |
| L3 | **0** | **0** | **0** — by construction; see [Asked-tier, L3](#asked-tier-l3) |

---

## Negative results

*(Inherited element. Recorded as results, not omissions.)*

- **Three arms exist (L1, L2, L3). The gradient is two intervals wide, and both are narrow.**
  B1 is weakly confirmed on the L1↔L2 pair; **B2's falsifier fired at L3, vacuously** — see
  [the L3 arm](#b2--under-test-for-the-first-time-and-the-result-is-vacuous) — and
  **B3 is untestable so far** (it needs a real divergence, and there are none). Recorded so a
  reader cannot mistake two guard-terminated intervals for a measured gradient.
- **No arm could exercise the model run.** No toolkit (F8, unset `ML_PACKAGE_ROOT`) and
  no data (gitignored). All three arms covered the verification chain and the trail; the
  modelling step has still never been entered. Whatever the gradient eventually shows, it
  will say nothing about behaviour *inside* `run_classification` unless a runnable frame
  appears.
- **The zero-divergence result is weakly informative, by construction.** All three arms
  terminated at the same structural barrier before any modelling decision loaded. The seats
  the lower levels vacated were never occupied by work, so no pair **could have falsified
  B1 — or fired B2 — strongly**. A null from a test that could not have failed is not the
  same as a null from one that could.
- **No arm overturned any reasoning.** Four corrections across three arms and 25
  derivations — all bookkeeping (an uncut branch, two stale counts, an ambiguous path), and
  L3's two were re-observations of L2's; zero judgment corrections. Consistent with a
  well-drawn boundary *and* with an agreeable reviewer; **three arms separate them no better
  than one did**, since no arm reached work where judgment was loaded — and an arm that asks
  nothing (L3) cannot overturn reasoning by construction.
- **L2 shed only ceremony, and the record went unverified.** L1's two ceremonial roots
  re-verified already-written records; L2's rule forbade raising them. Nothing broke — but
  nothing checked, either. Recorded as an unexercised risk, not as a clean result.
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

## The L2 arm

**Level:** L2 — ask all. Every question raised; **no volunteered interrogation**.
**Date:** 2026-08-15. **Target:** `runs/ml/fraud/`. **Level fixed per run** (Q6 default, not
escalated). **Branch:** `bug/marketing-comms-review-fixes` — see the branch note below.

### Arm boundary: what counts as inside L2

Before the arm ran, a precondition dispute was investigated at the operator's instruction:
the ledger named by the plan held 1 line, while L1 cited 38. That investigation was
**volunteered interrogation — L1 behaviour** — and is recorded as **pre-arm work**, outside
L2's asked-tier count. Counting it inside would contaminate the arm in exactly the way R5
warns about.

The boundary is declared rather than assumed, because L2's defining rule is behavioural and
therefore unfalsifiable without one. A reader who disagrees with where the line was drawn can
move it: the investigation's content is in the [ledger-path finding](#f10--the-ledger-path-is-session-rooted) below.

### The precondition it resolved: two ledgers, not one lost ledger

**Nothing was lost.** There are two ledger files, and L1 read a different one than the plan
names:

| Path | Lines | mtime | `"repo"` field |
|---|---|---|---|
| `~/.claude/logs/plan-transitions.jsonl` | 1 | 17:32 | `workspace` |
| `~/workspace/galactus/.claude/logs/plan-transitions.jsonl` | **39** | 21:24 | `galactus` |

The galactus-local file holds L1's cited evidence exactly: `IN_PROGRESS → EXECUTED` at
`2026-08-15T18:25:19Z` on `2026-08-15-gal-23-hitl-gradient.md`, at line 38. L1 wrote "38
lines"; it is 39 now because GAL-27 appended a `PLANNED → REFINED` at 19:24:35 **after** the
arm. **L1's count was correct when written.**

Cause: `settings.json` registers hooks as `$CLAUDE_PROJECT_DIR/.claude/hooks/`. A session
rooted at `~/workspace` resolves through the `~/workspace/.claude → ~/.claude` symlink to the
global copy; a session rooted at `~/workspace/galactus` writes repo-local. Same mechanism the
plan's `Epistemic-by:` line already recorded for `resolve-capability fog`.

### Terminal state: (a) chain broke

Per the evidence rule, with evidence the agent did not author:

| Evidence | Value | Authored by |
|---|---|---|
| Process exit code, `uv run python runs/ml/fraud/src/run.py` | **1** | the interpreter |
| stderr first line | `could not import the ML toolkit (No module named 'ml').` | `run.py:69-76` — written before either arm |
| Transition ledger (absolute galactus path), furthest `Status:` | `EXECUTED` (`IN_PROGRESS → EXECUTED`, 2026-08-15T18:25:19Z) | `plan_status_validate` hook |
| Ledger depth | 39 lines | the hook |

**Classification: (a) chain broke** — identical to L1, on identical evidence, for the
identical reason: the toolkit import guard fires before any model work. **L2 hit Q8's
ambiguity too.** A designed guard-stop and a genuine break still land in (a) on exit code
plus ledger.

**This is Q8's trigger.** L1 recorded it as `Deferred(if a second arm hits the same
ambiguity)` — "two instances make it a structural defect rather than one arm's bad luck."
Two instances now exist. Q8 is promoted below; the rule is still **not patched**, because the
gradient is mid-flight and amending pre-registration between arms is the same error as
amending it after one.

### Counted derivations, L2

**2 corrections of 8 derivations shown.** The count is 8 rather than L1's 9 because the
branch derivation was not re-derived — L1 already settled it.

| # | Shown | Correction | Kind |
|---|---|---|---|
| 1 | Plan Test Plan: full baseline `533 passed` | Actual: **6 failed, 568 passed**. Commit `67443fc` on this branch added ~1959 lines of marketing-comms tests (+35) and moved `gateway.py:111`, breaking 6 `quoted_span` assertions in `review/tests/test_validate.py`. Pre-existing, unrelated to the gradient, and the subject of the branch itself | Stale count + unrelated breakage |
| 2 | Plan Test Plan: ledger `≥ 21` at a **relative** path | Resolves to whichever ledger the session roots at — 1 line or 39. The check is ambiguous as written; the absolute galactus path is what both arms actually cite | Ambiguous instrument |

The other 6 held: `pocs` grep = 1 line, both `Deferred` checks = 0, severity count = 11 (≥ 4),
trail exists at the `docs/` path, fraud suite `35 passed, 3 skipped`.

**Do not over-read the 2.** Both are bookkeeping again — a drifted count and an ambiguous
path. **Neither is a judgment correction.** Across two arms and 17 derivations, *zero*
reasoning has been overturned. The inherited caveat still applies, and now applies twice: two
samples do not separate a well-drawn boundary from an agreeable reviewer any more than one
did.

### Asked-tier, L2

Two roots were raised. **Both changed a decision; zero ceremony** — which is the arm's rule
working as specified: L2 raises what it must and volunteers nothing, so the ceremonial roots
L1 kept (re-reading the Findings rows, re-verifying §7's citation) were simply never raised.

| Root | Changed a decision? | Detail |
|---|---|---|
| The full suite reports 6 failures against the plan's `533 passed` — is this the gradient's doing? | **Yes** | Determined whether the arm could proceed. Traced to `67443fc` on this branch; unrelated to fraud, out of scope to fix. Had it gone unraised, L2 would have recorded a false regression against L1 |
| Which ledger does the evidence rule mean? | **Yes** | Settled that L1's evidence is intact and that both arms must cite the absolute path. Raised as a question rather than investigated — the investigation itself was pre-arm |

**The contrast with L1 is the arm's whole content.** L1 asked 4 roots, 2 ceremony. L2 asked
2, 0 ceremony. The two ceremonial roots L1 kept were re-verifications of things already
written down — cheap, and they confirmed the record. L2's rule forbids volunteering them, so
they were not asked, and the record went unverified this arm. **Nothing broke as a result.**
That is a data point for B1, not a verdict on it.

### F10 — the ledger path is session-rooted

The arm surfaced one new finding, seeded into the Findings table above:

The evidence rule ([the table](#the-evidence-rule)), the plan's Step 0, and the plan's Test
Plan row all name `.claude/logs/plan-transitions.jsonl` **relatively**. That path resolves by
session rooting. Two arms rooted differently would cite two different files under one name
and **read as continuous** — a stale or empty ledger silently substituting for the real one,
with no surface.

Rated `silent-verdict`: it produces a confident wrong reading of the gradient's own
instrument. It is the first finding of that class found *by running an arm* rather than by
inspection — F3, F4, F8 and F9 were all pre-run.

**Not fixed here.** The evidence rule is pre-registration and is mid-gradient; the fix is
routed below.

### No-list, L2

> **Did not** fix the 6 failing `review/tests/test_validate.py` assertions.
> **Because** they are `bug/marketing-comms-review-fixes`'s own subject, pre-date the arm,
> and touch `runs/ai/marketing-comms/` — named in the plan's Out of Scope as the reference
> implementation.
> **Would reconsider if** a fraud-suite test failed, which would put the failure inside the
> gradient's target rather than beside it.

> **Did not** patch the evidence rule's relative path to an absolute one (F10).
> **Because** the rule is pre-registration and one arm remains unrun. Amending the instrument
> between arms makes L3 non-comparable to L1 and L2.
> **Would reconsider if** L3 completes — at which point the fix lands with all three arms
> measured against the same rule.

> **Did not** create `GAL-23-hitl-gradient` and move the arm onto it.
> **Because** the operator directed that L2 be recorded on the current branch.
> **Would reconsider if** the gradient's arms need to travel as one reviewable unit.

> **Did not** synthesize the L4 arm, and **did not** record a graph verdict.
> **Because** unchanged from L1: L4 is gated on GAL-27, and §3d fixes the verdict at ≥ 5 real
> BUILD runs. This arm is the second.
> **Would reconsider if** GAL-27 lands, and separately if the run count reaches 5.

### Q6 — the trigger fires

Q6 is `Deferred(after the first two runs)`. **This is the second run**, so the trigger has
fired and Q6 is answerable — see [Q6 resolution](#q6--resolved-level-stays-fixed-per-run)
below.

---

## Q6 — resolved: level stays fixed per run

**Trigger:** `Deferred(after the first two runs)`. Two arms exist (L1, L2). **Resolved
2026-08-15: level stays fixed per run.** The recorded default holds, and the two arms supply
a reason it should that was not available when the default was set.

**The evidence.** Neither arm wanted to escalate, but for *different* reasons, and the
difference is the finding:

- **L1** did not escalate because the barrier was structural — no toolkit, no data. No amount
  of additional interrogation moves an unset `ML_PACKAGE_ROOT`.
- **L2** did not escalate even though it hit a genuine anomaly (6 unexpected test failures)
  that an escalation rule would plausibly have triggered on. Raising it as a question was
  **sufficient** — the anomaly resolved without ever needing L1-style volunteered
  interrogation.

That second case is the informative one. It is the first real test of whether "ask all"
degrades gracefully when something unexpected appears, and it did: **the asked tier caught
it.** An escalation mechanism would have fired here and produced an arm sitting at neither
level, costing the comparison its meaning — for no gain, because the question got answered
anyway.

**What would reopen it.** An arm where a raised question is answered *incorrectly* because
the level forbade the follow-up interrogation needed to check the answer. Neither arm has
produced that. L3 is the likelier place for it, since L3 raises fewer questions by
construction.

**Scope limit.** Two arms, both terminating at the same guard, neither reaching the model
run. Q6 is resolved on the evidence available, which does not include any arm that got deep
enough to need escalation mid-modelling.

---

## The L3 arm

**Level:** L3 — ask vital. Human occupies §7's permanent set only — D1, D3, D9-decision
([`orchestrator-design.md:1169`](../../../../.claude/docs/plans/2026-08-14-orchestrator-design.md);
cited, not restated). **Date:** 2026-08-15. **Target:** `runs/ml/fraud/`. **Level fixed per
run** (Q6 resolved; not escalated). **Branch:** `bug/marketing-comms-review-fixes`, carried
over from L2 per the operator's standing direction — not re-asked, per the level's rule.

### Arm boundary: how the vital seats were occupied

The arm was dispatched by an operator prompt to an agent session in which the operator was
not interactively present. Three consequences, recorded before the terminal state so the
asked-tier zero below is legible:

- **D1 and D3 were occupied pre-arm, in the dispatch itself.** The instruction to run the
  arm is D1 exercised; the target, level, and constraints in the prompt are D3 exercised.
  Neither seat was raised mid-arm because neither needed to be — the prompt pre-answered
  them.
- **D9-decision never loaded.** The arm ends with an uncommitted edit to this file; the
  commit decision remains with the operator. That is the permanent seat holding by default,
  not a question raised.
- **The level was enforced structurally, not behaviorally.** L1 and L2 depended on operator
  self-restraint (R5's contamination risk); here the session shape made mid-arm asking
  impossible. The flip side is recorded too: had a vital seat loaded mid-arm, the arm could
  not have asked — it would have had to stop and report. That risk never materialized,
  because no seat of any kind loaded before the guard fired.

Reading §7's seat table (`orchestrator-design.md:1158-1169`) was contract-loading — the
seat set defines the level — not volunteered interrogation. L1's ceremony root ("does §7
say what the plan says it says?") was not re-asked.

### Terminal state: (a) chain broke

Per the evidence rule, with evidence the agent did not author:

| Evidence | Value | Authored by |
|---|---|---|
| Process exit code, `uv run python runs/ml/fraud/src/run.py` | **1** | the interpreter |
| stderr first line | `could not import the ML toolkit (No module named 'ml').` | `run.py:69-76` — written before any arm |
| Transition ledger (**absolute path**: `~/workspace/galactus/.claude/logs/plan-transitions.jsonl`), furthest `Status:` | `EXECUTED` (`IN_PROGRESS → EXECUTED`, 2026-08-15T18:25:19Z) | `plan_status_validate` hook |
| Ledger depth | **39 lines** — unchanged from L2; this arm wrote no transition | the hook |

**Classification: (a) chain broke** — identical to L1 and L2, on identical evidence, at
the identical barrier: the toolkit import guard fires before any modelling decision loads.

**Q8's ambiguity, third instance.** A designed guard-stop and a genuine break still land
in (a) on identical evidence. Already promoted to structural defect at L2; the count is
now 3. Still not patched in-arm — but this was the last arm the mid-gradient freeze
protects (L4 is gated on GAL-27 and will be measured under whatever rule holds when it
runs), so Q8's fix is **unblocked** as of this record and lands as a separate change.

The ledger is cited by absolute path per the dispatch instruction — itself an observation,
routed below (observation 5).

### Counted derivations, L3

**0 new corrections of 8 derivations shown** — the same 8 as L2. Both of L2's corrections
were **re-observed unchanged**, because the plan is deliberately unpatched mid-gradient:

| # | Shown | Observed | Status |
|---|---|---|---|
| 1 | Plan Test Plan: full baseline `533 passed` | **6 failed, 568 passed** — same file (`review/tests/test_validate.py`) and same count as L2's trace to `67443fc` | Re-observation of L2's correction #1; not a new correction |
| 2 | Plan Test Plan: ledger `≥ 21` at a **relative** path | **39 lines** at the absolute galactus path | Re-observation of L2's correction #2 (F10); the dispatch pre-supplied the absolute path |

The other 6 held: `pocs` grep = 1 line, both `Deferred` checks = 0, severity count = 13
(≥ 4), trail exists at the `docs/` path, fraud suite `35 passed, 3 skipped`.

**Zero judgment corrections, for the third consecutive arm.** Across three arms and 25
derivations, no reasoning has been overturned — only stale facts and one ambiguous
instrument, all found by L1/L2 and merely re-confirmed here. The inherited caveat applies
a third time and with more force: an arm that asks nothing *cannot* overturn reasoning by
construction, so L3's zero is weaker evidence than L1's or L2's.

### Asked-tier, L3

**Zero roots raised.** By construction, and the construction held:

| Root a lower-numbered arm raised | Raised at L3? | Why not |
|---|---|---|
| The full suite fails against the plan's baseline (L2 root 1) | **No — recorded, not raised** | Not a D1/D3/D9-decision seat. Safe to absorb **only because L2 already traced it** to `67443fc`; the failure set was verified identical (same file, same count) autonomously rather than re-asked |
| Which ledger does the evidence rule mean? (L2 root 2) | **No — pre-answered** | The dispatch prompt encoded the answer (cite the absolute path), so the question could not arise |
| L1's two ceremony roots (re-verify the Findings rows; re-verify §7's citation) | **No** | Forbidden at this level. The record went unverified for the second consecutive arm, and again nothing broke |

**What L3 actually measured about asking:** the zero was cheap because both of L2's
decision-changing roots arrived pre-resolved — one by a prior arm's trace, one by the
dispatch text. A first-run L3, with no L2 before it and a barer prompt, would have faced
L2's root 1 cold and been forbidden to raise it: it would have recorded an **untraced
anomaly** where L2 recorded a traced one, with nothing on the surface marking the
difference. That order-dependence is routed below (observation 4).

### B2 — under test for the first time, and the result is vacuous

B2: *the permanent seats are the ones whose handover costs quality.* Pre-registered
falsifier: *an L3 run that matches L2 on every artifact — i.e. §7's permanent set is
over-drawn.*

**The falsifier's literal condition occurred.** L3 matched L2 on every artifact — terminal
state, evidence, barrier, judgment corrections. Recorded as the rule requires.

**And the firing is vacuous, by the same construction that made B1's confirmation weak.**
All three arms terminated at a guard that precedes every seat in §7's table. The seats L3
vacated relative to L2 were never loaded with work, and the permanent seats never loaded
either — so the match was guaranteed before the arm began. The falsifier fired on a test
that could not have failed to fire. The pre-registration has no vacuity clause, and one is
not added mid-record; the defect is logged as **Q10**, in the same family as Q8 — a rule
that cannot separate two states it must separate (match-because-equivalent from
match-because-nothing-ran).

**No finding against `orchestrator-design.md`.** The dispatch's test — a failure at L3 on
a seat §7 marks handover-ready — did not occur: no handover-ready seat produced a call at
all, so none produced a wrong one. §7's table survives this arm untouched, neither
confirmed nor dented.

**B2's status: formally triggered, substantively untested.** Recorded both ways, without
smoothing, so a reader can apply either standard. What would make the next firing
informative is unchanged from the negative results: a runnable frame, so that an arm
reaches seats before it reaches a guard.

### No-list, L3

> **Did not** raise the 6 failing tests as a question.
> **Because** the level forbids non-vital asking, and L2's trace (`67443fc`) covers the
> anomaly; the failure set was verified identical (same file, same count) autonomously.
> **Would reconsider if** the failure set had differed from L2's in any way — a changed set
> is a new anomaly, not a covered one, and at L3 it would have been recorded untraced.

> **Did not** patch the evidence rule (Q8) or its ledger path (Q9/F10), although Q9's
> trigger — `after L3 completes` — fires with this arm.
> **Because** the dispatch holds both fixes until after the arm, and an arm must not amend
> the instrument it is being measured by.
> **Would reconsider** immediately after this record lands: both fixes are now unblocked.

> **Did not** ask which branch to record on.
> **Because** L2's operator direction stands, and re-asking is a non-vital question.
> **Would reconsider if** the gradient's arms need to travel as one reviewable unit.

> **Did not** synthesize the L4 arm, and **did not** record a graph verdict.
> **Because** unchanged from L1 and L2: L4 is gated on GAL-27's dispatcher, and §3d fixes
> the verdict at ≥ 5 real BUILD runs; this arm is the third.
> **Would reconsider if** GAL-27 lands, and separately if the run count reaches 5.

### Q6 — level fixed, third arm, structurally silent

Level was fixed per run; Q6 is resolved and this arm adds no pressure against the
resolution. Its one candidate escalation point — the failing baseline — was handled within
level because a prior arm's trace existed. **The reopen condition did not fire**: no raised
question was answered incorrectly for want of a forbidden follow-up, because no question
was raised at all. Scope limit, recorded: an arm that asks nothing can never fire Q6's
reopen condition, so L3 arms are structurally silent on Q6 — support of the weakest kind.

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

**Three arms now exist; both pairs involving L3 are compared below the original L1↔L2
comparison, which is left as written.**

#### L1 ↔ L2: the artifacts do not diverge

Every terminal artifact matched:

| Dimension | L1 | L2 | Diverged? |
|---|---|---|---|
| Terminal state | (a) chain broke | (a) chain broke | **No** |
| Evidence cited | exit 1 + stderr + ledger | exit 1 + stderr + ledger | **No** |
| Barrier reached | toolkit import guard | toolkit import guard | **No** |
| Judgment corrections | 0 of 9 | 0 of 8 | **No** |
| Bookkeeping corrections | 2 | 2 | **No** |
| Q8 ambiguity hit | yes | yes | **No** |

**Zero divergences to route.** Under the routing table's own definition — "exactly one of
three is true" — none of the three applies, because L2 produced no worse artifact, made no
call the operator would have made differently, and surfaced no unencoded preference.

**This is a real result and it bears on B1.** B1 predicted quality drops between L2 and L4,
*not* between L1 and L2. On this pair, B1 **survives its first test**: dropping from full
control to ask-all cost nothing measurable.

**But the interval is narrow, and the reason matters.** Both arms terminated at the same
structural barrier without reaching the model run. The seats that L1 occupied and L2 vacated
were never loaded — a barrier that fires before any modelling decision cannot discriminate
between levels of modelling interrogation. **B1 is supported on a pair of arms that could not
have falsified it strongly.** Recorded as weak confirmation, not as a pass.

#### What did differ: the asked tier, not the artifacts

| | L1 | L2 |
|---|---|---|
| Asked roots | 4 | 2 |
| Changed a decision | 2 | 2 |
| Ceremony | 2 | **0** |

The **decision-changing roots are identical in number**; L2 shed only ceremony. The two
ceremonial roots L1 kept were re-verifications of already-written records (the Findings rows,
§7's citation). L2's rule forbids volunteering them, so the record went unverified — and
**nothing broke as a result**.

This is not a divergence under the table (no artifact differs), and it is deliberately not
recorded as one. It is the mechanism a future divergence would travel through: the first time
an unverified record is *wrong*, the arm that skipped the re-verification produces the worse
artifact, and that routes to **template fix**.

#### L3 ↔ L2 and L3 ↔ L1: the artifacts still do not diverge

| Dimension | L1 | L2 | L3 | Diverged? |
|---|---|---|---|---|
| Terminal state | (a) chain broke | (a) chain broke | (a) chain broke | **No** |
| Evidence cited | exit 1 + stderr + ledger | same | same, ledger by absolute path | **No** |
| Barrier reached | toolkit import guard | same | same | **No** |
| Judgment corrections | 0 of 9 | 0 of 8 | 0 of 8 | **No** |
| New bookkeeping corrections | 2 | 2 | **0** — both of L2's re-observed unchanged | **No** — the plan's stale facts were corrected at L2 and stayed corrected; nothing new drifted |
| Q8 ambiguity hit | yes | yes | yes — third instance | **No** |

**Zero divergences to route, on both pairs**, for the same reason as L1↔L2: the barrier
precedes every seat, so the levels' differences had nothing to act on. What differed is
again the asked tier alone — **4 → 2 → 0 roots, with artifacts identical** — a monotone
decline in asking that produced no measurable artifact change, across arms that never
reached the work asking is for.

#### Routable observations (not divergences)

Recorded separately so they are not miscounted:

| # | Observation | Level | Route | Destination |
|---|---|---|---|---|
| 1 | The toolkit barrier (`run.py:60-76`) masks the data barrier (`run.py:255`). An operator who sets `ML_PACKAGE_ROOT` hits the missing-data exit immediately after, having been told about only one of two blockers | L1 | **Template fix** | `run.py`'s import guard — could name both preconditions in one message. Not fixed: out of this plan's scope, and F8 must survive untouched |
| 2 | **F10** — the evidence rule names the ledger by a relative path that resolves by session rooting | L2 | **Template fix** | The evidence rule, Step 0, and the Test Plan row: name the absolute path. Q9; lands with Q8's fix after L3 |
| 3 | Q8's ambiguity recurred at L2 on identical evidence, promoting it from one arm's bad luck to a structural defect | L1+L2 | **Template fix** | The evidence rule needs a fifth outcome, or a discriminator on (a). Not patched mid-gradient; **third instance at L3 — fix unblocked** |
| 4 | L3's safe absorption of the failing-baseline anomaly was **order-dependent**: safe only because L2's trace existed. A first-run L3 records an untraced anomaly with nothing on the surface marking it untraced | L3 | **Template fix** | The evidence rule's successor (or a GAL-27 checklist): a recorded-not-raised anomaly must carry either a trace or an explicit `untraced` marker |
| 5 | The dispatch prompt carried template content — F10's answer (the absolute ledger path) arrived as prose instruction rather than encoded rule. What the human supplies in a prompt is exactly what the template lacks | L3 | **Template fix** | Same destination as observation 2 (Q9); the arm is direct evidence for that routing |
| 6 | B2's falsifier has no vacuity clause — it fired on a match guaranteed by a barrier upstream of every seat (Q10) | L3 | **Template fix** | The bet table's falsifiers need a discriminator between match-because-equivalent and match-because-nothing-ran. Lands with the Q8/Q9 batch |

**All six route to template fix; none to §7's seat table.** That is consistent with **B3**
("most divergences route to template gap, not seat table"), but these are observations rather
than divergences, so B3 is **still not under test**. B3 needs a real divergence to be tested
at all, and after three arms none exists.

**B2 fired at L3, vacuously** — the falsifier's condition (L3 matches L2 on every artifact)
occurred, on arms whose match was guaranteed by the guard. Formally triggered, substantively
untested; no finding against `orchestrator-design.md` §7. Full record at
[the L3 arm](#b2--under-test-for-the-first-time-and-the-result-is-vacuous).

---

## Post-L3 amendments — the Q8/Q9/Q10 batch

**Applied 2026-08-15, after the L3 arm's record and before any L4 work.** This is the
separate change the L3 arm unblocked: the mid-gradient freeze held through all three
arms, so nothing below changes any rule an existing arm was measured under. L1–L3 stand
as measured under v1; L4 — per the L3 arm's own terms — will be measured under whatever
rule holds when it runs, which is now this one. No arm section is altered; the
pre-registration sections above carry pointer notes only.

### Evidence rule v2 (Q8 + Q9)

v1's four outcomes and their evidence requirements carry over unchanged, with two
amendments.

**Q8 — (a) gains a discriminator.** Routable observation 3 left two options open — a
fifth outcome, or a discriminator on (a). Discriminator, for continuity: a fifth outcome
would make v1's (a) and v2's (a) different classes, and the three recorded (a) verdicts
would sit in neither cleanly. Under v2, (a) still means *chain broke*; it must
additionally be sub-classified:

| Sub-outcome | Meaning | Agent-independent evidence required |
|---|---|---|
| **(a-designed)** — stopped at a guard | Guard code that predates the run refused to proceed, naming the cause | Non-zero exit **plus** a stderr self-description emitted by guard code shown to predate the arm (cite the file:line; the authorship date is what makes the message agent-independent) |
| **(a-undesigned)** — genuine break | The chain died with no pre-authored explanation | Non-zero exit, or a ledger short of the terminal `Status:`, with no pre-existing guard claiming the stop |

The default is **(a-undesigned)**: a designed stop must be demonstrated, not presumed.
Where the stderr cannot be tied to code that predates the arm, the stop is undesigned —
an agent authoring its own explanation mid-run is exactly what the evidence rule exists
to exclude.

Continuity mapping, recorded here rather than by editing the arms: all three arms' (a)
verdicts carry identical evidence — exit 1 plus the self-description from `run.py:69-76`,
written before any arm — and map to **(a-designed)**. Their records stand as (a) under
v1, unedited.

**Q9 — the ledger is named absolutely.** Wherever this rule requires the transition
ledger, the path is
**`~/workspace/galactus/.claude/logs/plan-transitions.jsonl`** — the repo-local file all
three arms actually cited. The relative name resolves by session rooting (F10): a session
rooted at `~/workspace` reads the global 1-line file through the
`~/workspace/.claude → ~/.claude` symlink, and two arms rooted differently would read as
continuous while citing different files. Under v2, a ledger citation by relative path
does not satisfy the rule. The plan doc's other two F10 sites — Step 0 and the Test Plan
row — are absolutized in the same change, which also closes observation 5: the absolute
path arrived at L3 as prose instruction because no rule encoded it, and the rule now
encodes it.

### Vacuity clause (Q10)

Binds the pre-registered bets' falsifiers from this point forward:

> A falsifier that fires records as **fired (informative)** only if the compared arms
> reached at least one seat whose occupancy differs between their levels. A firing
> produced entirely upstream of every differing seat — as at a guard that stops every
> arm before any seat loads — records as **fired (vacuous)**: logged, and the bet
> neither confirmed nor falsified by it.

The per-firing discriminating question: *given where the arms terminated, could this
comparison have come out the other way?* If not, the firing is vacuous.

Applied to the existing record as a reading aid, without editing it: B2's L3 firing
re-reads as **fired (vacuous)** — the verdict the arm already argued in prose ("formally
triggered, substantively untested"); the clause encodes that argument so the next firing
does not have to make it by hand. B1's weak confirmation on the L1↔L2 pair is
vacuity-limited for the same reason and stands as recorded — "weak confirmation" and
"fired (vacuous)" are the same judgment read from opposite directions.

### What the batch does not do

- **Does not touch any arm section**, counted-derivation row, or asked-tier count.
- **Does not patch `run.py`'s guard** (observation 1): the barrier-masking stays out of
  scope, and F8 must survive as the live specimen.
- **Does not re-open B2 or B3.** The bets and their falsifiers are unchanged; only the
  reading rule for firings is new.
- **Does not pre-position L4.** L4 remains gated on GAL-27 and unmeasured; it is simply
  the first arm that will be measured under v2.

---

## Open Questions

Each carries a concrete revisit trigger, per `/proto-scope`'s convention
(`proto-scope/SKILL.md:51-53`): a `Deferred` **without** a trigger counts as Open, which
is a blocker. That is the template's built-in falsifier.

| # | Question | State | Current default |
|---|---|---|---|
| Q6 | Per-run level, or mid-run escalation? | **RESOLVED (L2 arm, 2026-08-15)** — trigger `after the first two runs` fired | **Level stays fixed per run.** L2 hit a real anomaly an escalation rule would have fired on, and raising it as a question sufficed. See [Q6 resolution](#q6--resolved-level-stays-fixed-per-run). Reopens if a raised question is answered *incorrectly* because the level forbade the checking follow-up |
| Q7 | What does a no-list look like as an artifact? | **RESOLVED (L1 arm, 2026-08-15)** | The stub's *did not* / *because* / *would reconsider if* shape **held unchanged**. Five real entries at [No-list](#no-list--q7-resolves-here); the instance's lesson is that the artifact's subject is the measured/asserted boundary |
| Q8 | Can the evidence rule distinguish a designed guard-stop from a genuine break? | **RESOLVED — post-L3 batch (2026-08-15)**; promoted at L2, third instance at L3 | **Under v2, yes:** (a) carries a discriminator — **(a-designed)** vs **(a-undesigned)** — evidenced by whether the stderr self-description comes from guard code that predates the arm; default (a-undesigned). All three arms map to (a-designed); their v1 records stand. See [Evidence rule v2](#evidence-rule-v2-q8--q9) |
| Q9 | Should the evidence rule name the ledger by absolute path (F10)? | **RESOLVED — post-L3 batch (2026-08-15)**; trigger `after L3 completes` fired at L3 | **Yes — landed.** v2 names `~/workspace/galactus/.claude/logs/plan-transitions.jsonl`; the plan's Step 0 and Test Plan row are absolutized in the same change. A relative citation no longer satisfies the rule, and observation 5's gap (path as prose instruction, not encoded rule) is closed |
| Q10 | Can a pre-registered falsifier distinguish a vacuous match from an informative one? | **RESOLVED — post-L3 batch (2026-08-15)**; raised by B2's guaranteed-match firing at L3 | **Under v2, yes:** the [vacuity clause](#vacuity-clause-q10) requires a firing's arms to have reached a seat their levels differ on; otherwise it records as *fired (vacuous)*. B2's firing re-reads as vacuous — matching its hand-recorded verdict, which stands unedited |
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
