# GAL-23 — Dry-run the proto-* pipeline end to end (HITL and unattended)
Date: 2026-08-15
Status: SUPERSEDED
From: PLANNED
Superseded-by: `.claude/docs/plans/2026-08-15-gal-23-hitl-gradient.md`
Track: agent

> **Superseded 2026-08-15, after a NOT-READY gate.** Two framings in this doc were wrong:
> it modelled human involvement as a binary (Mode A / Mode B) when every run has a human,
> and it described BUILD as a sequential chain when the pipeline is orchestrated from
> scope (`2026-08-14-orchestrator-design.md` §3f). The successor replaces both with a
> four-level HITL gradient.
>
> **What survives, and is cited rather than restated:** the `## Research` section below,
> in particular findings F1–F9 and the asset verdicts. **What does not:** the Mode A/Mode B
> structure, Step 3 (the repair landed in `fecd27b` before this doc could run), the
> run-root siting of `DESIGN.md`, pre-commitment #1 (unfalsifiable), and the claim that
> skill-invocation suppression is a loader defect (it is deliberate; GAL-27 D2 keeps it).

Supersedes-research-of: `.claude/docs/plans/2026-08-11-gal-4-phase4-dry-run-modes.md`
(`Status: SUPERSEDED`). That doc's D1–D8 decisions are re-derived here against live paths
rather than inherited; where a decision survives unchanged it is cited, not restated.

## Research

### Summary

The pipeline this issue proposes to dry-run is **not the pipeline the superseded plan
measured**, and the difference is load-bearing: `workflow-*` became `proto-*`, `pocs/`
became `runs/`, and 4a's filing target was archived one directory below where the loader
looks. Re-deriving those, the sharpest finding is that **Mode A's filing target should be
the plan doc's own decision record via `/proto-scope`'s Open Questions and
`Deferred(<trigger>)` vocabulary — not an `### Observed` block in a skill body**, because
every `### Observed` precedent in this repo now sits in `.claude/skills/archived/` and is
unreachable to the loader. The issue's own framing — evidence-gathering with an
expected-null — is correct and should be pre-registered, but it is **not** the whole
picture: this research found two live composition-layer specimens without running the
pipeline at all, which means Mode B's expected-null is narrower than the issue assumes.

### Scope

**Investigated:** issue #23 and its superseded predecessor (`2026-08-11-gal-4-phase4`,
976 lines, read to line 771 plus targeted greps); the live `proto-*` skill set
(`.claude/skills/`, 14 non-review skills); `proto-research/SKILL.md` and
`proto-scope/SKILL.md` in full; the archived skill tree; the D1 target's current state
(`runs/ml/fraud/`, incl. `docs/summary.json` parsed field-by-field); the F1 specimen
(`runs/ml/lending/src/run.py:50-67`); hook registration in `.claude/settings.json` against
the `~/workspace/.claude → ~/.claude` symlink; and vendored-vs-global hook parity by `cmp`.

**Explicitly out of scope:** running either mode (this phase produces the frame for them,
not the runs); building or modifying `runs/ml/fraud/` beyond reading it; `runs/ai/marketing-comms/`
beyond reading; guacamayo's `review-findings.jsonl` and `.sounding/tooling-ledger.md` as
write targets — both are cross-repo and the filing question is re-opened below on
loader-reachability grounds, which changes the answer; and resolving the `ML_PACKAGE_ROOT`
gap, which is Mode B's specimen and must survive.

### Findings

**F1 — Every `### Observed` precedent in galactus is loader-unreachable. This invalidates
the superseded plan's D3 and D8, not merely their paths. (High — load-bearing.)**

`grep -rln "### Observed" .claude/skills/` returns exactly one file:
`.claude/skills/archived/design-prototype/SKILL.md`. CLAUDE.md states the consequence
directly — archived skills "are one directory below where the loader looks, so they are
not invocable." The superseded plan's D3 resolved the decision trail to *"an `### Observed`
block appended to `design-prototype/SKILL.md`"* and D8 sent it to `~/.claude/skills/`;
both targets are now either archived (galactus) or demoted to guacamayo (global). Issue #23
already flags the path problem. What it does not say is that **the format's only instance
went with it** — so Mode A is not re-pointing an existing mechanism at a new address, it is
choosing a format with no live precedent in this repo.

**F2 — `/proto-scope` already carries the decision-record vocabulary Mode A needs, and it
is loader-visible. (High.)**

`proto-scope/SKILL.md:48-58` defines exactly the primitives Mode A's artifact requires:

- "**'I don't know' is a first-class answer**" — park, don't force a guess;
- Open Questions entries carry "a concrete revisit trigger";
- Key Decisions are marked `Deferred(<trigger>)` **with the current default choice
  recorded**, and — the operative rule — "A Deferred with a real trigger blocks nothing…
  a Deferred without one counts as Open (a blocker)."

That last clause is a *falsifiable* record shape: a decision is well-formed iff it names
its trigger. It is the same measurement the intake tier boundary needs (was this decision
correctly deferred, or should it have been asked?), expressed in a vocabulary the live
pipeline already writes and reads. This matches the operator's stated structure — scope
carries the decision tree; unresolved design questions flow to research and plan; refine
gates before execute.

**F3 — The D1 target survived the rename and still refuses, but its schema is not what the
superseded plan recorded. (High.)**

`runs/ml/fraud/docs/summary.json` exists and carries a genuine refusal — but the two fields
the superseded plan's precondition table cites as top-level (`operating_point_reported`,
`min_positives_in_fold`) are **nested one level down** under a `refusal` object:

```json
"refusal": {"operating_point_reported": false, "min_positives_in_fold": 2, "n_positives": 14,
            "reason": "the thinnest test fold holds only 2 positive case(s), below the
                       10-positive floor … A threshold chosen and scored over that few
                       events is arithmetic, not evidence — no operating point is reported."}
```

Also live: `beats_baseline: false`, `headline_metric: "average_precision"`. The refusal is
intact and well-shaped — this is a *good* target, and the decision-shaped outcome the
superseded plan wanted it for is real. But **any step written against the flat field names
would silently read `ABSENT` and evaluate falsy**, which reads identically to "no refusal
was made." That is the repo's own signature failure class (structure that reads complete
and is empty where it executes), sitting in the acceptance check of the plan meant to
detect it.

**F4 — A second live composition specimen: `catboost` is silently dropped from the fraud
run. (Medium-High.)**

`summary.json` carries `"skipped": {"catboost": "only one of the parameters random_seed,
random_state should be initialized."}`. A model in the comparison set failed to fit for a
mundane API-conflict reason and the run continued, recording the skip in a field nothing
gates on. `beats_baseline: false` is therefore a verdict rendered over an incomplete model
set. This is not the `ML_PACKAGE_ROOT` class — nothing failed to import — but it is the
same *shape*: a green-looking terminal state with a component quietly absent.

**Consequence for the issue's expected-null framing.** Issue #23 argues both known breaks
are closed, so an unattended run may find nothing, and pre-registers that null. F4 (and F3)
were found by reading artifacts, not by running anything — so the honest pre-registration
is narrower: **the null applies to the two *named* breaks, not to the failure class.** The
class has now been observed twice more, by inspection, since the issue was written.

**F5 — `Status:` transitions are hook-enforced on this session, and the vendored hooks are
in parity. (High.)**

`.claude/settings.json` registers `plan_status_validate.sh` (PostToolUse) and
`plan_transition_validate.sh` (PreToolUse) via `$CLAUDE_PROJECT_DIR`. `cmp` confirms both
are byte-identical to `~/.claude/hooks/`. So the state machine
(`RESEARCH → RESEARCHED → PLANNED → REFINED → READY → IN_PROGRESS → EXECUTED → COMPLETE`)
is a **real, free break-locator** for both modes: the furthest `Status:` a run reaches is
recorded without new instrumentation. The superseded plan's F7 called this out; it still
holds, and it is now verified rather than assumed.

`lib.sh` differs between the two trees — but that is an artifact of *this branch*, not a
defect (see Assumptions).

**F6 — Break-vs-stuck remains undecidable at the point of termination, and no new signal
has appeared. (High.)**

Issue #23 requires every run to classify as (a) chain broke / (b) harness stopped /
(c) completed, and forbids reporting (a) without reproduction. `~/.claude/rules/shell.md`
("Quota masquerade") is unchanged: exhaustion "surfaces as `error_max_turns` or silent
empty results… indistinguishable from agent logic failures at the API level." Nothing in
the repo disambiguates them. The superseded plan's D6 answer — a break counts only when it
reproduces from a recorded state — survives as the only tractable shape, **but its
precondition has weakened**: CLAUDE.md now states `runs/_index/` "is reserved for run
records… Nothing writes here yet," and that a run's result "currently lives as a
`summary.json` under its own `docs/`, which is why the lending baseline could be overturned
but not reproduced." The registry Phase 1 was to supply is declared but unpopulated in
galactus.

**F7 — Mode B's containment rules are unchanged and need no exception. (High.)**

Global CLAUDE.md's dispatcher rules cover Mode B exactly: worktree agent, `{PREFIX}-{NUM}-slug`
branch created `--no-track`, agent rebases before first commit, commits are provisional, the
dispatcher soft-resets to staged, Ramsey pushes. The cross-repo dispatch rule applies with
force here — the worktree must be created in the target repo. The superseded D2 resolution
(worktree on a `GAL-` branch; may write to what is now `runs/`, excluding
`runs/ai/marketing-comms/`) transfers intact under the rename.

### Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `.claude/skills/proto-scope/SKILL.md` Open Questions + `Deferred(<trigger>)` | **REUSE** | — | Live, loader-visible, and already the right vocabulary for Mode A's decision record (F2). The trigger-or-blocker rule gives the artifact a falsifier for free. |
| `.claude/docs/plans/` + `Status:` state machine + both hooks | **REUSE** | — | Verified byte-identical and registered (F5). Free break-locator for both modes; no new instrumentation. |
| `runs/ml/fraud/` (+ `docs/summary.json`) | **REUSE** | — | D1's target survived the rename; refusal is real and decision-shaped (F3). Read-only here. Steps must key on the **nested** `refusal.*` fields. |
| `runs/ml/lending/src/run.py:50-67` | **REUSE** | — | Mode B's live specimen. The loud `SystemExit` is the *fixed* half; the unfixed half is that a stale `ML_PACKAGE_ROOT` imports cleanly and yields wrong numbers. Preserve — do not fix (issue #23). |
| `2026-08-11-gal-4-phase4-dry-run-modes.md` D1–D8 | **ADAPT** | — | The reasoning survives; the paths and two decisions (D3, D8) do not (F1). Adapt = re-derive each against live targets, cite where unchanged. |
| `.claude/skills/archived/design-prototype/SKILL.md:114-168` | **ADAPT** | **The six structural elements of the `### Observed` format — extractable as a format spec without reviving the skill.** Element 2 (pre-registered bets) and element 5 (negative result recorded as such) are what make the artifact evidence rather than rationalization. | Unreachable to the loader (F1), so it cannot be a filing *target*. It remains the only worked example of the artifact's *shape*. |
| guacamayo `review-findings.jsonl` / `.sounding/tooling-ledger.md` | **SKIP** | **The ledger's row discipline — a metric with a falsifier and a due date — is portable to a plan-doc decision record at zero cost**, and is what `Deferred(<trigger>)` already approximates. | Cross-repo write targets for a galactus-local measurement; the corpus keys rows to `file`/`lines` a skill-instruction finding lacks; galactus's own copy is gitignored. Filing there routes findings away from the pipeline that must read them. |
| `runs/_index/` | **SKIP** | **The declared intent — one record per training execution — is the reproduction anchor F6 needs**, and stating that it is unpopulated is itself the finding. | Reserved but empty; CLAUDE.md says nothing writes here yet. Cannot be consumed by this phase. |
| `runs/ai/marketing-comms/` | **SKIP** | **Its `--dry-run` / scripted-adapter pattern is a working zero-spend precedent** worth citing if Mode B ever targets an AI run. | Reference implementation, 277 tests; out of scope beyond running. Also a live vocabulary collision: its `--dry-run` means *scripted model*, not *drive the pipeline*. |

### Assumptions

- **Assumption:** `.claude/hooks/lib.sh` differing from `~/.claude/hooks/lib.sh` is a
  branch artifact, not repo drift — **Evidence:** `git show GAL-20-hook-observer-parity:.claude/hooks/lib.sh`
  is byte-identical to the global copy; this branch forked from `origin/main` before GAL-20
  landed — **If wrong:** CLAUDE.md's "byte-identical as of 2026-08-15" claim is false on main
  and the parity check belongs in this phase's scope — **Confidence:** High.
- **Assumption:** Mode A's decision record belongs in the plan doc under `/proto-scope`'s
  vocabulary rather than in a skill body — **Evidence:** F1 (no reachable `### Observed`),
  F2 (live vocabulary with a built-in falsifier), and the operator's stated structure —
  **If wrong:** the record is not read by the skill whose boundary it measures, weakening
  "filed where the implicated skill reads it" — **Confidence:** Medium-High.
- **Assumption:** Both modes share `runs/ml/fraud/` as target — **Evidence:** superseded D1;
  F3 confirms it survived the rename with its refusal intact — **If wrong:** the two modes
  measure different pipelines and the HITL/unattended contrast is void — **Confidence:** High.
- **Assumption:** A galactus-rooted session loads galactus's vendored `.claude/skills/`
  — **Evidence:** F5 confirms `$CLAUDE_PROJECT_DIR` hook resolution works this way for hooks
  — **If wrong:** findings filed in galactus never reach the executing skill —
  **Confidence:** Low-Medium. **This session is direct evidence against it:** rooted at
  `~/workspace`, `Skill(galactus:proto-research)` returned *Unknown skill* and the SKILL.md
  had to be executed by hand. Session root, not repo, determines skill visibility.
- **Assumption:** `average_precision` with `beats_baseline: false` means the fraud run
  completed its comparison honestly — **Evidence:** the refusal object is well-formed and
  reasoned — **If wrong:** F4's silent catboost skip means the baseline verdict was rendered
  over a partial model set — **Confidence:** Low. F4 is the reason this is Low, and it is a
  Key Unknown rather than a finding about the metric.

### Disconfirming Evidence

**Against F1 (no reachable `### Observed` target):** Could a live `proto-*` skill carry one
that the grep missed under a different heading? Grepped all of `.claude/skills/` for
`### Observed` — one hit, archived. Also read `proto-research/SKILL.md` and
`proto-scope/SKILL.md` in full for any equivalent intake section; neither has one.
**Looked; finding strengthened** — and it surfaced F2, a *better* target than the one being
replaced, so the invalidation is not merely a loss.

**Against F2 (`/proto-scope` is the right home):** Is this over-reading a scoping skill?
Honest tension. `/proto-scope` is a FRAME-band skill that emits `DESIGN.md`, while Mode A's
trail spans the whole BUILD band — so the vocabulary fits but the *ownership* is a stretch:
scope would be lending its notation to a record it does not write. Against that, CLAUDE.md
is explicit that "FRAME is a band, not a sequence" and that the plan doc is "the bus between
phases," which is where a cross-phase record belongs. **Looked; found a real boundary
question that bounds the finding** — carried to Key Unknowns as *which* artifact holds the
trail, with the vocabulary settled either way.

**Against F3 (schema mismatch matters):** Is this pedantry — would a planner just read the
JSON? The superseded plan's own precondition table (line 548) asserts the flat names as
evidence that the done-condition was met, so the mismatch already propagated into a document
that gated a phase. A check keyed on `summary.get("operating_point_reported")` returns
`None` and reads as "no refusal reported," inverting the finding. **Looked; finding
strengthened** — it is an instance of the class, inside the plan meant to detect the class.

**Against F4 (catboost skip is a finding):** Is this just a known upstream API conflict,
correctly handled by skipping? Partly conceded — the skip is *recorded*, not swallowed, and
recording it is better than silence. But `beats_baseline` is computed over the survivors
with no gate on `skipped` being non-empty, so the recorded fact does not reach the verdict.
**Looked; found a real mitigation that bounds the finding without refuting it** — it is
evidence about *verdict computation*, not about catboost.

**Against F6 (break-vs-stuck still undecidable):** Has the `runs/_index/` registry landed
since the superseded plan, closing this? Checked CLAUDE.md directly: `runs/_index/` is
"reserved… Nothing writes here yet," and the lending baseline "could be overturned but not
reproduced." **Looked; the finding strengthened** — the dependency is not merely unmet, it
is documented as unmet in the repo's own table of contents.

### Key Unknowns

- **Which artifact holds Mode A's decision trail** — the plan doc's own section, a
  `DESIGN.md` under `runs/ml/fraud/`, or `.claude/docs/decisions/`. F2 settles the
  *vocabulary* (`Deferred(<trigger>)` + Open Questions) but not the *location*; the
  disconfirming pass found a genuine band-ownership question. This is the first thing
  `/proto-plan` must decide.
- **Whether F4's catboost skip gates `beats_baseline`.** Determines whether the fraud run's
  headline verdict is sound, and therefore whether it is a usable control for Mode B.
  Cheap to check — read the verdict computation in `runs/ml/fraud/src/`.
- **What Mode B reproduces from, given `runs/_index/` is empty (F6).** Without a run record,
  the (a)-vs-(b) discrimination issue #23 mandates has no anchor. Options: populate a minimal
  record as part of this work, reproduce from `summary.json` + git SHA, or accept that Mode B
  can report (b) and (c) but never (a).
- **Whether a galactus-rooted session sees the vendored skills.** This session (rooted at
  `~/workspace`) did not. If Mode A must run from inside the repo for `/proto-*` to resolve,
  that is a precondition on the run, not a detail.
- **What a no-list looks like as a recorded artifact.** Issue #23 names it first ("the
  decision trail *including the no-list*"); the superseded research found the one existing
  instance contained none. Still no example anywhere in the repo.
- **Whether the expected-null should be re-registered given F3/F4.** Two more specimens were
  found by inspection since the issue was written. The pre-registration should probably read
  "null for the two named breaks; open for the class."

### Recommendation

Plan this as **framing two runs, not performing them**, and treat the issue's expected-null
as the thing most in need of sharpening rather than the thing most settled. The single
highest-value planning decision is where Mode A's decision trail lives, because F1 removed
the inherited answer and F2 supplies a better vocabulary than the one that was lost — the
`Deferred(<trigger>)`-or-blocker rule turns the intake-boundary measurement into something
with a built-in falsifier, which is exactly what the counted derivation-correction score was
reaching for. Mode B should be planned around what it can honestly conclude: with
`runs/_index/` unpopulated, the reproduction anchor that separates *chain broke* from
*harness stopped* does not exist, so either this phase supplies a minimal one or Mode B must
pre-commit to never reporting state (a) — and saying which, in advance, is worth more than
the run. The strongest argument for running at all is that the failure class the phase exists
to surface produced two fresh specimens during this research alone, both found by reading
artifacts rather than executing anything: a schema mismatch sitting inside the superseded
plan's own acceptance check, and a model silently absent from a comparison whose verdict was
reported anyway. The class is not closed; only its two named instances are.

---

## Plan
Date: 2026-08-15
Based on: `## Research` above, plus four live checks run during planning (see Step 0 note).

### Goal

Produce the pre-registered frame — targets, pre-commitments, and a severity-carrying
decision-record shape — that makes the two dry-run modes interpretable when they are later
run, and repair the one stale-path defect found while framing. This phase runs neither mode.

The frame serves **two** decisions, and the record shape must make both readable from the
same artifact: (1) *can `proto-*` be trusted unattended, or do HITL checkpoints stay
mandatory?* — a verdict; and (2) *which part of the pipeline gets hardening effort next?* —
a ranking. A record carrying only occurrence answers the first and is silent on the second,
which is why severity is a required field rather than a nicety.

### Open Questions

Resolved during planning (2026-08-15), each with the evidence that settled it:

- **Q1 — Where does Mode A's decision trail live?** → **`runs/ml/fraud/DESIGN.md`**
  (operator decision, 2026-08-15). Colocates the record with the run it measures. Chosen
  over the plan doc's own section; the cost is that the record splits from the plan that
  gates it (carried to Risks R2). Supported by `proto-scope/SKILL.md:57-59` — the skill is
  **idempotent over `DESIGN.md`**, so a later `/proto-scope` run ratifies the trail rather
  than overwriting it. F2's vocabulary (`Deferred(<trigger>)` + Open Questions) is adopted
  regardless of location, as the research recommended.

- **Q2 — Does F4's catboost skip gate `beats_baseline`?** → **Unresolvable inside galactus.**
  Traced during planning: `beats_baseline` is *not* computed in this repo. `run.py:170`
  reads `result.beats_baseline`, where `result` comes from `run_classification`, imported
  from the external `ml` package via `ML_PACKAGE_ROOT` path injection
  (`runs/ml/fraud/src/run.py:55-71`). The verdict computation lives in `ai-project-template`.
  The research called this "cheap to check"; that was wrong, and the correction matters —
  fraud's headline verdict is recorded **UNVERIFIED**, not sound and not wrong.

- **Q3 — What does Mode B reproduce from, given `runs/_index/` is empty?** → **Nothing; so
  Mode B pre-commits to never reporting state (a).** `runs/_index/` is reserved and
  unpopulated, and CLAUDE.md states galactus **does not define the record shape** — the
  registry is `ai-project-template`'s `experiments/` module. Populating one here would have
  galactus invent a shape it is not allowed to own. The `summary.json` + git-SHA fallback
  was rejected: `ML_PACKAGE_ROOT` is unpinned, so the same SHA can import a different
  toolkit and yield different numbers — an anchor that does not anchor.

- **Q4 — How is the expected-null stated?** → **Null for the two *named* breaks; open for
  the *class*.** Exactly the research's recommendation, now with more support than it had.

- **Q5 — Does a galactus-rooted session see the vendored skills?** → **Still open, and
  re-confirmed as a live defect during planning.** This session (rooted at `~/workspace`)
  could not resolve `Skill(galactus:proto-plan)` — *Unknown skill* — despite
  `.claude/skills/proto-plan/SKILL.md` existing on disk; the SKILL.md was executed by hand,
  exactly as `/proto-research` was. Notably the loader registered **21 of 29** skills from
  the same directory (all `review-*`, `proto-scope`, `proto-review`, the CROSS family) while
  omitting the six BUILD-band `proto-*` skills. `Deferred(before Mode A runs)` — default:
  **both modes run from a session rooted at `~/workspace/galactus`.** This is a precondition
  on the runs, not a detail; Step 1 records it as such.

Deliberately left open (not blockers):

- **Q6 — What does a no-list look like as a recorded artifact?** No instance exists anywhere
  in the repo; the archived format names it first and contained none. `Deferred(first Mode A
  run)` — default: Step 1's template reserves the section with a worked stub, and the first
  run populates it. A trigger exists, so this blocks nothing.

### Approach

Write the frame as two artifacts and one repair. The frame is a **record template plus a set
of pre-commitments** — statements registered *before* any run about what each mode may and
may not conclude — so that a later run cannot retroactively upgrade a suspicion into a
verdict the evidence does not carry. The template is derived from the archived
`design-prototype` `### Observed` block, which the research identified as the only worked
example of the artifact's shape; its two load-bearing elements are pre-registered bets and
negative results recorded as such (`"Contract stage under a time cap: not yet tested"` is a
first-class entry there, not an omission). To that inherited shape this plan adds one field
the original lacked — **severity** — because the goal serves a hardening ranking as well as
a trust verdict, and the archived format carries occurrence only.

The tradeoff: colocating the trail in `runs/ml/fraud/DESIGN.md` puts it next to the run it
measures but splits it from the plan doc that gates it, so the plan doc keeps a pointer and
the `DESIGN.md` keeps the content. Accepted per Q1.

### Out of Scope

- **Running either mode.** This phase produces the frame; the runs are a later phase.
- **Resolving `ML_PACKAGE_ROOT`** (research F-series; Mode B's live specimen — must survive).
- **Fixing the catboost skip**, or reading `ai-project-template` to settle Q2. The
  unresolvability *is* the recorded finding.
- **Populating `runs/_index/`** — galactus does not own the record shape (Q3).
- **Any change to `runs/ai/marketing-comms/`** (reference implementation, 277 tests).
- **Reviving `archived/design-prototype/`.** Its format is extracted as a spec; the skill
  stays archived.
- **Fixing Q5's skill-loader gap.** Recorded as a precondition and a finding; diagnosing the
  loader is its own work item.
- **Adjacent cleanup in `runs/ml/fraud/src/run.py`** beyond the two default-path lines.

### Steps

#### Step 0: Preconditions (already satisfied — recorded for the executing session)

**Files**: none (verification only)
**What**: Four checks were run during planning and are recorded here so execute does not
repeat them. Re-run only if the branch has moved.
- Baseline: `530 passed, 3 skipped` on a clean tree, branch `GAL-23-proto-pipeline-dry-run`.
- `runs/ml/fraud/tests` **is** in `pyproject.toml` `testpaths` (38 tests collected) — so the
  Step 3 repair has a live test surface and is not silently uncollected.
- `grep -rn "pocs"` repo-wide over `*.py` returns **exactly two lines**, both in
  `runs/ml/fraud/src/run.py:50-51`. The repair is contained.
- `Path("runs/ml/fraud/src/run.py").resolve().parents[4]` == repo root — the `parents[4]`
  arithmetic is **correct**; only the `"pocs"` path segment is stale.

**Done when**: read. No action.

---

#### Step 1: Create `runs/ml/fraud/DESIGN.md` with the decision-record template

**Files**: `runs/ml/fraud/DESIGN.md` (new file — the first `DESIGN.md` in any run directory)

**What**: Establish the trail's home and its shape. This is a *template with pre-registered
content*, not an empty scaffold: the pre-commitments (Step 2) and the four already-observed
specimens (Step 4) are written into it now, before any run, which is what makes them
pre-registrations rather than post-hoc narration.

Structure it on the six elements extracted from
`.claude/skills/archived/design-prototype/SKILL.md:183-238`, adding **severity**:

1. **Header** — what was run, when, at what scale, and the explicit note that the rules
   being measured were written *before* the run.
2. **Pre-registered bets** — what was predicted, recorded before evidence.
3. **Counted derivations** — the tier-boundary measurement (`N of M` corrected), with the
   archived block's own warning against over-reading a single sample carried forward.
4. **Asked-tier assessment** — which asked questions changed a decision, which were ceremony.
5. **Negative results, recorded as such** — the element that makes this evidence rather than
   rationalization. `"not yet tested"` is a valid, first-class entry.
6. **No-list** — what was declined and why (Q6: stub now, populated by the first run).
7. **Severity** *(new — not in the archived format)* — each finding rated
   `silent-verdict` > `silent-component` > `loud-surface`, so the hardening ranking is
   readable from the same artifact as the trust verdict.

Use `/proto-scope`'s vocabulary for anything unresolved: Open Questions carry a **concrete
revisit trigger**, Key Decisions are `Deferred(<trigger>)` **with the current default
recorded**. Per `proto-scope/SKILL.md:51-53`, a `Deferred` with a real trigger blocks
nothing; **a `Deferred` without one counts as Open — a blocker.** That rule is the
template's built-in falsifier: an entry is well-formed iff it names its trigger.

**Snippet** (shape, not content):

```markdown
# runs/ml/fraud — DESIGN

## Decision Trail — Mode A (HITL), <date>
<header: scale, sessions, and "rules below were written before the run">

### Pre-registered bets
- Bet 1: <claim> — falsified by: <what would disprove it>

### Derivation corrections: N of M
<count, plus the do-not-over-read caveat>

### Asked tier
- <question> → changed a decision | ceremony

### Negative results
- <thing>: not yet tested. <why that matters>

### No-list
- Declined: <what> — because <why>

### Findings
| # | Finding | Severity | Evidence |
|---|---|---|---|
| F3 | refusal.* nested, not flat | silent-verdict | summary.json |

## Key Decisions
- D1: <choice> — Deferred(<concrete trigger>)   ← trigger required, else blocker

## Open Questions
- Q1: <question> — revisit trigger: <concrete event>
```

**Test**: `test -f runs/ml/fraud/DESIGN.md && grep -c "Deferred(" runs/ml/fraud/DESIGN.md`
— and manually verify every `Deferred(` has a non-empty trigger inside the parens.
**Done when**: the file exists; all seven elements are present; every `Deferred(` names a
concrete trigger; the severity column is populated for all four Step 4 specimens.

---

#### Step 2: Write the pre-commitments into `DESIGN.md`

**Files**: `runs/ml/fraud/DESIGN.md` (section added by Step 1)

**What**: Register what each mode may and may not conclude, *before* either runs. Four
commitments, stated so a later run cannot quietly exceed them:

1. **Mode B reports (b) *harness stopped* or (c) *completed* only.** State (a) *chain broke*
   is **unavailable** — no reproduction anchor exists (`runs/_index/` empty; `ML_PACKAGE_ROOT`
   unpinned). A suspected break is recorded as an *observation with severity*, never as a
   verdict. Rationale recorded inline so the constraint is not mistaken for an oversight.
2. **Expected-null is scoped**: null for the two *named* breaks (both closed); **open for the
   failure class**, which has four specimens (Step 4) — none of which required running
   anything.
3. **Fraud's `beats_baseline: false` is UNVERIFIED** — computed cross-repo (Q2). It may not
   be cited as a sound control for Mode B without reading `ai-project-template`.
4. **Both modes run from a session rooted at `~/workspace/galactus`** — precondition, not
   detail (Q5). If a mode is run from `~/workspace`, the BUILD-band `proto-*` skills do not
   resolve and the run measures the loader, not the pipeline.

**Test**: `grep -n "may not\|unavailable\|UNVERIFIED" runs/ml/fraud/DESIGN.md`
**Done when**: all four are written as explicit prohibitions with rationale, each falsifiable
by a later run that violates it.

---

#### Step 3: Repair the stale `pocs/` default paths

**Files**: `runs/ml/fraud/src/run.py` (lines 50-51)

**What**: The only code change in this phase. Both argparse defaults point at the pre-rename
`pocs/` tree, which no longer exists — and neither does `runs/ml/fraud/data/`. `parents[4]`
is correct (Step 0); only the path segment is wrong.

Scope is **these two lines only** — no adjacent cleanup. Per the strict gates, a code change
needs a GitHub issue; this rides GAL-23 (see R4).

**Snippet**:
```python
# before
DEFAULT_DATA = REPO_ROOT / "pocs" / "ml" / "fraud" / "data" / "dataset.csv"
DEFAULT_REPORT = REPO_ROOT / "pocs" / "ml" / "fraud" / "docs" / "report.html"

# after
DEFAULT_DATA = REPO_ROOT / "runs" / "ml" / "fraud" / "data" / "dataset.csv"
DEFAULT_REPORT = REPO_ROOT / "runs" / "ml" / "fraud" / "docs" / "report.html"
```

Note `runs/ml/fraud/data/` still does not exist — the repair makes the default *correct*,
not *satisfiable*. Do not create the data directory; the dataset is not in the repo. Record
that gap in `DESIGN.md` as a finding rather than papering over it.

**Test**: `uv run pytest "runs/ml/fraud/tests" -q` (expect 38 passed) and
`grep -rn "pocs" runs/ --include="*.py"` (expect no output)
**Done when**: both greps are clean, fraud's 38 tests pass, and full-suite baseline still
reads `530 passed, 3 skipped`.

---

#### Step 4: Record the four observed specimens with severity

**Files**: `runs/ml/fraud/DESIGN.md` (Findings table)

**What**: Populate the Findings table with the specimens found **by inspection alone** —
zero required executing the pipeline. This is the evidence that the failure class is open,
and it is what Step 2's commitment #2 rests on.

| # | Finding | Severity | Source |
|---|---|---|---|
| F3 | `refusal.*` fields nested, not flat — a check keyed on the flat names reads `None` and inverts the finding | **silent-verdict** | research F3; propagated into the superseded plan's own acceptance check |
| F4 | `catboost` silently dropped; `beats_baseline` computed over survivors with no gate on `skipped` | **silent-verdict** (unverified — Q2) | research F4 |
| F8 | `ML_PACKAGE_ROOT` stale-but-importable → clean import, wrong numbers | **silent-verdict** | research F-series; **preserve, do not fix** |
| F9 | `pocs/` default paths stale after rename | **loud-surface** | found during planning; repaired in Step 3 |

**Severity rationale** — F9 is deliberately rated *below* F3/F4. It fails loudly at file-open
rather than producing a confident wrong number, so counting it alongside the silent-verdict
specimens would inflate the class. The distinction is the point of the severity field: four
specimens, but **three** of the dangerous kind.

**Test**: `grep -c "silent-verdict\|loud-surface" runs/ml/fraud/DESIGN.md` (expect ≥4)
**Done when**: all four rows present with severity and source; the F9-vs-F3/F4 rationale is
written, not implied.

---

#### Step 5: Point the plan doc at the trail

**Files**: this plan doc (a `## Decision Trail` pointer section)

**What**: Q1 put the content in `runs/ml/fraud/DESIGN.md`; this closes the split by leaving a
pointer where a reader of the plan will look. **A pointer, not a copy** — two copies drift,
and the drift would be invisible.

**Snippet**:
```markdown
## Decision Trail
Lives in `runs/ml/fraud/DESIGN.md` (Q1, 2026-08-15) — colocated with the run it measures.
Pre-commitments: Mode B reports (b)/(c) only; null scoped to the two named breaks.
This section is a pointer. Do not copy content here.
```

**Test**: `grep -n "runs/ml/fraud/DESIGN.md" .claude/docs/plans/2026-08-15-gal-23-proto-pipeline-dry-run.md`
**Done when**: the pointer resolves to an existing file and no finding text is duplicated
between the two documents.

### Test Plan

| Check | Command | Expect |
|---|---|---|
| Full baseline holds | `uv run pytest --tb=no -q` | `530 passed, 3 skipped` |
| Fraud suite | `uv run pytest "runs/ml/fraud/tests" -q` | 38 passed |
| No stale paths | `grep -rn "pocs" runs/ --include="*.py"` | no output |
| Trail exists | `test -f runs/ml/fraud/DESIGN.md` | exit 0 |
| Every Deferred has a trigger | `grep -n "Deferred(" runs/ml/fraud/DESIGN.md` | no empty parens |
| Severity populated | `grep -c "silent-verdict\|loud-surface" runs/ml/fraud/DESIGN.md` | ≥ 4 |

The `Deferred(` check is the one that matters most: it is the template's own falsifier
(`proto-scope/SKILL.md:51-53`), and a trail full of triggerless defers is a blocker wearing
the costume of a decision record.

### Risks & Rollback

- **R1 — The frame is written but never exercised.** This phase deliberately runs neither
  mode, so every pre-commitment is untested. *Mitigation:* Step 2's commitments are written
  as falsifiable prohibitions, so the first run either honors or violates them visibly.
  *Rollback:* the artifacts are additive — `git checkout runs/ml/fraud/`.

- **R2 — Trail/plan split (accepted cost of Q1).** The record lives in `DESIGN.md` while the
  plan that gates it lives here; they can drift. *Mitigation:* Step 5 is a pointer, not a
  copy — there is one source of truth by construction.

- **R3 — `DESIGN.md` is the first in any run directory.** No precedent means no convention
  to match, and a later `/proto-scope` run will treat it as its own file. *Mitigation:*
  `proto-scope/SKILL.md:57-59` — the skill is idempotent over `DESIGN.md` and ratifies rather
  than overwrites. This is a genuine reason the choice is safe, verified rather than assumed.

- **R4 — Step 3 crosses the framing-only scope boundary** and, per the strict gates, code
  changes need an issue. *Mitigation:* it rides GAL-23, is capped at two lines, and is
  covered by 38 existing tests. Flagging explicitly because the research scoped this phase to
  framing and the operator extended it deliberately — that extension should be visible to
  refine, not buried. *Rollback:* `git checkout runs/ml/fraud/src/run.py`.

- **R5 — Q5's loader gap could void a mode's run.** If Mode A is run from `~/workspace`, the
  BUILD-band `proto-*` skills silently fail to resolve and the run measures the loader
  instead of the pipeline — a failure that looks like a pipeline break. *Mitigation:*
  Step 2 commitment #4 makes the session root a precondition. This is itself an instance of
  the class the phase exists to study, which is why it is registered rather than just fixed.

- **R6 — Severity is a judgment, not a measurement.** The `silent-verdict` /
  `loud-surface` split is defensible but not derived from a rule. *Mitigation:* Step 4
  requires the rationale be written out, so a reader can disagree with the rating without
  having to reverse-engineer it.

### Open Questions

Carried forward for `/proto-refine` — none block execute:

- **Q5 (loader visibility)** — `Deferred(before Mode A runs)`, default: run from
  `~/workspace/galactus`. Refine should decide whether diagnosing the loader gap is its own
  issue; it now has two confirmed instances (`/proto-research`, `/proto-plan`) and a
  suggestive pattern — the loader registered 21 of 29 skills while omitting exactly the six
  BUILD-band `proto-*` ones.
- **Q6 (no-list shape)** — `Deferred(first Mode A run)`, default: stub reserved in Step 1.
- **Q2 follow-up** — whether a separate work item should read `ai-project-template`'s
  `run_classification` to settle whether `skipped` gates `beats_baseline`. Out of scope here;
  fraud's verdict stays UNVERIFIED until someone does.

---

**Next step**: `/proto-refine gal-23-proto-pipeline-dry-run`
