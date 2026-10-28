# GAL-4 Phase 4 — Two dry-run modes over the pipeline
Date: 2026-08-11
Status: SUPERSEDED
From: PLANNED
Superseded-by: #23 — "Dry-run the proto-* pipeline end to end — HITL and unattended".
  No successor plan doc yet; `/proto-research` is that issue's entry point.

<!-- 2026-08-15: superseded from PLANNED, never executed. Kept rather than deleted because
     the decision record below (D1-D8, F1-F5) is the reasoning the successor re-derives
     against, and four of those decisions resolved on evidence that has not itself expired.

     What expired is everything the steps below point *at*. The plan was written the day
     before the 2026-08-11 skill demotion and four days before the `pocs/` -> `runs/` move,
     and it did not survive either:

       - Step 2 has the operator run `/design-prototype`. That skill is archived at
         `.claude/skills/archived/design-prototype` — one directory below where the loader
         looks, so it is not invocable.
       - Step 5's deliverable is a second `### Observed` block appended to that same
         archived skill. It is 4a's entire output, and it would be written somewhere nothing
         reads. The refine comment on #4 flagged this as a 2026-08-17 retirement clock; the
         clock ran early.
       - Step 6 files into `~/.claude/skills/workflow-plan` and `workflow-review`. Both
         demoted to guacamayo on 2026-08-11; galactus's equivalents are `proto-plan` and
         `proto-review`.
       - Every path says `pocs/`.

     And the motivating evidence is consumed. 4b existed to find where independently-green
     components fail to compose, on the strength of two live instances. Both are closed:
     `runs/ml/lending/src/run.py:59-67` now raises a `SystemExit` naming the remediation
     instead of importing absent `ml.*` modules silently, and the half-completed `pocs/`
     directory move — the second instance, found unlooked-for during this plan's own research
     — was completed on 2026-08-15.

     That leaves the successor a subtler job than this plan had, and #23 states it rather than
     inheriting it: with both known breaks fixed, an unattended run may find nothing. That is
     a real outcome. But it has to be pre-registered as an expected-null, or a quiet run gets
     read as the pipeline being proven when it has only been untested. Lifting the eight steps
     forward would carry the bug-hunt framing along with the stale paths. -->

## Research

### Summary

Phase 4's two modes are not two features; they are **two instruments pointed at the same
pipeline, measuring different things** — 4a measures the *intake tier boundary* (which
decisions must be asked vs shown), 4b measures the *composition layer* (where independently
green components fail to compose). Both deliverables already have working precedents in the
repos, and neither is the code: 4a's decision trail has exactly one existing instance
(`design-prototype/SKILL.md:114-168`, the `### Observed — galactus, 2026-08-08` block), and
"filing a finding against a skill" has a real, machine-readable mechanism
(`review-findings.jsonl` + `tooling-ledger.md`) that nobody has yet used for a dry-run
finding. The load-bearing discovery is that **4b's motivating failure is not historical —
it is live and reproducible in galactus right now**: `ml-lending/ml/run.py:57-58` still
imports `ml.reporting.html` and `ml.workflows.classification`, and neither module exists in
this repo. A second instance of the same class was found unlooked-for: `pocs/` is a
half-completed directory move where data and docs relocated and source did not.

### Scope

**Investigated:** issue #4 Phase 4 and its Context/Sequencing; the executed ML dry run
(`pocs/ml/lending/WALKTHROUGH.md`) as the only existing evidence of what a dry run costs and
produces; the Phase 1 registry plan
(`ai-project-template/.claude/docs/plans/2026-08-11-gal-4-phase1-run-registry.md`) as the
declared dependency; the three implicated skills (`design-prototype`, `workflow-plan`,
`workflow-review`) for an existing finding-filing seam; the finding corpus and ledger
(`guacamayo/.claude/docs/review-findings.jsonl`, `guacamayo/.sounding/tooling-ledger.md`,
`workflow-retro/SKILL.md`); the asked-vs-derived intake boundary
(`design-prototype/SKILL.md:55-88`, `librarian/data/wiki/patterns/asked-vs-derived-scaffold-variables.md`,
`ai-project-template/copier.yaml`); and the current on-disk state of every candidate target
poc.

**Explicitly out of scope:** Phase 1's registry schema (planned separately, and this phase
consumes it rather than shaping it); Phase 2's `ml/fraud` build and Phase 3's `ai/evals`
extraction, except insofar as they determine Phase 4's target; W&B; any change to
`lebanese-blonde` or `parallax` (read-only); and step-level planning, which was deliberately
deferred at research time and **lifted on 2026-08-11 once the target poc existed** — see
`## Plan`, whose *Precondition clearance* table records what changed.

### Findings

**F1 — 4b's motivating failure is live in galactus today, not a historical anecdote.
(High — this is the load-bearing finding.)**

The issue describes `ml/workflows` as documented-but-absent in the past tense. It is still
absent *here*. `ml-lending/ml/run.py:54-67` imports four symbols from an `ml` package:

```python
from ml.evaluation.splitting import SplitPlan, assert_no_group_leakage, make_splitter
from ml.reporting.html import write_report
from ml.workflows.classification import run_classification
```

`ml-lending/ml/` contains exactly one file — `run.py` itself. The toolkit is external by
design (`run.py:24-32`): it resolves through `ML_PACKAGE_ROOT` into a rendered
`ai-project-template` project. The two modules the WALKTHROUGH says were written landed on
`ai-project-template` commit `0f8b2cf` (branch `AIT-67-ml-workflows-classification`,
unmerged) at
`template/_scaffold/{{ py_project_root }}/{{ ml_source_root }}/workflows/classification.py`
and `.../reporting/html.py`.

So the chain galactus documents is **still broken from galactus's own checkout**, and it
breaks at an environment seam (`ML_PACKAGE_ROOT` pointing at an unmerged branch of another
repo) rather than at a missing file. This matters for 4b's design: the automated run must
record the *resolution path* of its imports, not merely whether they succeeded. An
`ML_PACKAGE_ROOT` pointed at a stale render would import successfully and produce wrong
numbers — a silent break, which is strictly worse than the loud one.

**F2 — A second instance of the same failure class was found unlooked-for. (High)**

`pocs/` is untracked (`git status`: `?? pocs/`) and is a **half-completed directory move**:

| | `ml-lending/` (tracked) | `pocs/ml/lending/` (untracked) |
|---|---|---|
| source | `ml/run.py` | `src/` — contains only `__pycache__` |
| data | `data/.gitkeep` | `data/lending_club_2015Q4.csv` (the real extract) |
| docs | `docs/DESIGN.md`, `README.md` | `WALKTHROUGH.md` |

The data and the narrative moved; the code did not. Seven sibling directories under `pocs/`
are empty (`pocs/ml/{fraud,ltv,customer-segmentation,payment_classification}`,
`pocs/ai/{agentic-workflow,voice-assistant,chat-assistant-rag}`), matching the issue's
"seven of eight pocs are empty directories". `pocs/ai/marketing-comms/` mirrors the same
partial state — directory skeleton plus `__pycache__`, no `.py` sources.

This is the same class as F1 — **a structure that reads as complete to a documentation-level
inspection and is empty at the level that executes** — and it was found by asking where
Phase 4's target poc physically lives, not by any test. It is direct evidence for the
issue's claim that this class needs an automated run to surface it, and it belongs in the
"what else in the repos might belong to it" bucket the task asks about. **Confidence high on
the observation; medium on whether the move is deliberate in-flight work or abandoned** —
see Key Unknowns.

**F3 — The decision-trail artifact has exactly one existing instance, and it is a block
inside a skill file. (High)**

`design-prototype/SKILL.md:114-168` carries `### Observed — galactus, 2026-08-08`, written
after the ML6 take-home run. It is the only artifact in any repo that does what 4a's
deliverable is described as doing. Reading it as a *format specification* rather than as
prose, it has six recurring structural elements:

1. **A named, dated run header** scoped to the case (`— galactus, 2026-08-08`) with the
   run's shape stated (`~2,350 source lines / 2,810 test lines, uncapped across four
   sessions`).
2. **An explicit statement of what was a bet before the run** — "the rules above were
   written *before* the run, and two of them were bets." This is what makes the block
   evidence rather than rationalization.
3. **A counted derivation-correction score**: "**Derivation corrections: 0 of 5.**" with
   each derived variable named.
4. **A per-tier verdict on the asked side**: "two changed a decision and one was ceremony",
   with the ceremony item explicitly *kept* and the reason given.
5. **An explicit not-yet-tested marker**: "Contract stage under a time cap: **not yet
   tested**… the discipline's whole claim is that it survives when the clock bites, and
   that claim still has no evidence." A negative result recorded as a negative result.
6. **A rule-change decision, with the change withheld**: "**Do not shrink the block to a
   single sentence yet.** Zero corrections across one run is consistent with a well-drawn
   boundary and equally consistent with an agreeable reviewer; the count is the signal, and
   one sample does not establish it."

Element 6 is the mechanism that makes 4a *worth running at all*: the existing sample count is
one, and the skill explicitly refuses to act until there is a second, "differently-shaped
case". **4a's HITL run is that second sample.** That is a sharper statement of 4a's purpose
than the issue gives — the issue says the trail "records derivation corrections, which is the
measurement the intake tier boundary needs and currently has one sample of"; the skill says
what it will *do* with the second sample and under what condition.

Note what the block does **not** contain, against the issue's description: the issue calls the
no-list a first-class part of the artifact ("including the no-list"), and `SKILL.md:93-95`
asserts it is "a first-class artifact… the strongest evidence of judgment available in a
time-boxed exercise" — yet the `Observed` block records **no no-list at all**. The one
existing instance is missing the element the issue names first. Whether that is because the
uncapped run had nothing to decline, or because the format lost it, is unrecoverable now.

**F4 — "Filed against a skill" has a real mechanism, and it is three-target, not one.
(High)**

There is no single "file a finding" command, but there are three distinct, established write
targets with different durability and different owners. The issue's instruction — file
findings "against the specific skills they implicate… rather than summarized in prose" — is
satisfiable, and the choice among targets is itself a planning decision:

| Target | Path | Shape | Who writes | What it is for |
|---|---|---|---|---|
| **Skill-local observation block** | `~/.claude/skills/<skill>/SKILL.md` | `### Observed — <repo>, <date>` prose block (F3) | the run itself | Evidence that changes how the skill behaves, read every time the skill loads |
| **Findings corpus** | `guacamayo/.claude/docs/review-findings.jsonl` | one JSON object per finding | review driver (`guacamayo/review/`) | Machine-countable recurrence; feeds the promotion threshold |
| **Tooling ledger** | `guacamayo/.sounding/tooling-ledger.md` | one table row: Date, Change, Area, Metric, Status | `/workflow-retro` | A hypothesis with a falsifier and a due date |

The corpus row shape is fixed and observable (`review-findings.jsonl:1`):

```json
{"id": "SY-001", "source": "sanyi", "date": "2026-07-29", "repo": "librarian",
 "issue": "GUA-45", "file": "tools/cartographer/factstore.py", "lines": "114",
 "symbols": ["SUBAGENT_ATTRIBUTION_SINCE"], "category": "config",
 "merge_impact": "important", "evidence_state": "supported",
 "title": "...", "review_type": "workflow-review"}
```

Two constraints on that corpus are load-bearing for Phase 4 and easy to miss:

- **It is keyed to a `file` and `lines`.** Every existing row names a source location. A
  Phase 4 finding whose subject is *a skill's instructions* rather than a source file has no
  natural `file` value unless the skill file itself is used — which is coherent
  (`~/.claude/skills/workflow-plan/SKILL.md:31`) but is not a shape the corpus has seen.
- **galactus's copy is gitignored.** `.gitignore:31` excludes
  `.claude/docs/review-findings.jsonl` as "machine-local, regenerated per run", and the
  populated corpus lives in guacamayo. A finding written to galactus's local corpus is not
  durable.

The ledger, by contrast, requires something the corpus does not: a **metric with a
falsifier and a due date** (`tooling-ledger.md` header: `absence:`, `count-drop:`,
`presence:`, `ratio:`, `hook-blocks:`), plus a named promotion target
(`warn-hook | skill | rule | ledger-only`) with warn-hook as the **default** and `rule`
carrying "the burden of proof: say why the pattern is not mechanically checkable."

**The operational answer, therefore:** "filed against a skill" means the finding arrives at
a write target that the skill or its verifier *reads on its next run* — an `### Observed`
block for evidence that should change behaviour immediately, a ledger row for a claim that
needs a falsifier and a clock, and a corpus row when the finding is a code-located instance
of a countable pattern. What it excludes is a `## Findings` section in the Phase 4 plan doc
read by nobody. Note the ownership constraint: `/workflow-retro` is the only writer that
promotes to global memory, and retro's Step 1 explicitly says "Do NOT edit `.sounding/` —
flag only". Whether Phase 4 may write ledger rows directly or must route through retro is
unresolved (Key Unknowns).

**F5 — Nothing has ever been filed against `workflow-plan` or `workflow-review`; the
precedent is one-for-three. (High)**

Grepping all 24 global skills for the `Observed` block pattern returns exactly one hit
(`design-prototype/SKILL.md:114`). `workflow-plan/SKILL.md` and `workflow-review/SKILL.md`
have no equivalent section, and no ledger row names either skill as its promotion target for
a dry-run-sourced finding. So for two of the three skills the issue names, Phase 4 will be
**creating the seam, not using it.** That is a plan-shaped decision (where does the block go
in a skill that has no `Observed` section?) and a reason the phase is more than "run it and
write down what happened."

There is a relevant negative signal on the third: tooling-ledger row `2026-07-30` records
"R6 F6: design-* skills (sprint/initiative/milestones/prototype) — **0 invocations across
261 sessions / 3 retro windows**; decision: retire (a), consolidate (b), or document (c) —
pending Ramsey decision; due 2026-08-17." `design-prototype` is a live retirement candidate.
A Phase 4 run that files a substantive finding against it is also evidence in that open
decision — and if the skill is retired, findings filed into it evaporate. **Confidence high**
on the ledger row; **the interaction is a genuine planning input**, not a footnote.

**F6 — The asked/shown boundary is precisely specified, and its measurement is a count.
(High)**

Three sources agree, which lets the boundary be treated as fixed rather than re-derived:

- `design-prototype/SKILL.md:55-88` — the operative spec. **Ask three** (archetype +
  what you're building; who uses it; any decision whose silent default fails irreversibly).
  **Show five** (agent-shaped y/n, tools, memory, external systems, deployment target), as
  one sentence the user corrects in one word. Budget: 2 minutes total, "Do **not** run
  Copier; that was measured at ~12 min against ~2 min for this."
- `librarian/data/wiki/patterns/asked-vs-derived-scaffold-variables.md` — the source
  pattern, three tiers not two: Asked (6) / Derived (8) / **Inferred (rest, never mentioned
  unless raised)**. The governing rule: "**a default is safe to apply silently in proportion
  to how cheaply it can be reversed**" — blast radius, not importance. `human_approval` is
  the named never-derivable case ("independent of every other answer"); `deployment_target`
  is the named cheap-wrong-guess case ("one CD workflow + DESIGN.md row").
- `ai-project-template/copier.yaml` — the boundary as executed. 70 `when: false`
  declarations across ~68 distinct variables, against ~11 that actually prompt. The asked
  set is `project_name`, `project_description`, `project_type`, `primary_users`,
  `external_systems`, `human_approval`, plus a handful of feature toggles; everything from
  `py_project_root` and `ml_source_root` through `vector_backend`, `data_sensitivity`,
  `eval_root`, `python_version` and `aws_region` is `when: false` — resolved from defaults
  and never shown.

The distinction that matters for 4a: **`when: false` collapses "derived" and "inferred" into
one mechanism.** Copier cannot tell them apart — both are silently defaulted. The tier
boundary lives entirely in the *interview*, which chooses which of those ~68 to read back for
correction. That is why 4a's measurement is the **derivation-correction count** and not
anything copier records: a variable is correctly in the shown tier iff showing it produced no
correction, and correctly in the asked tier iff asking it changed a decision. The existing
sample is 0-of-5 corrections and 2-of-3 asked-questions-that-mattered (F3). One sample.

**F7 — The "chain breaks" signal is available, but only from Phase 1's registry plus an
absent third state. (Medium-High)**

Distinguishing a genuine break from an agent that is merely stuck requires separating three
outcomes, and the repos currently model two. The available signals, by origin:

| Signal | Source | Distinguishes |
|---|---|---|
| Phase-boundary artifact exists | plan doc `Status:` state machine (`galactus/CLAUDE.md`), hook-enforced over `RESEARCH → … → COMPLETE` | which phase the run reached — a break is a `Status:` that stops advancing |
| Import/composition failure | `run.py:59-67` raises `SystemExit` with a sentence, not a stack trace | F1's class — loud, attributable |
| Test/lint exit code | `make test_render`, `make lint` | component-level green, which is exactly what did *not* catch F1 |
| Run recorded at all | Phase 1 `record_run()` | whether the pipeline produced a comparable artifact or nothing |
| Frame/code identity | Phase 1 `DataIdentity` + `CodeState` (git SHA + dirty) | whether two runs are comparable, and *which input* differs |

The third state — **"the agent ran out of turns / budget / patience"** — has no signal in the
repos, and it is the one that masquerades. `~/.claude/rules/shell.md` ("Quota masquerade")
records the specific confusion: "Account usage exhaustion surfaces as `error_max_turns` or
silent empty results from the Agent SDK — indistinguishable from agent logic failures at the
API level… SDK-level `error_max_turns` in a low-turn session is a quota signal, not a turns
signal." An unattended 4b run that terminates without a verdict is therefore ambiguous
between *the chain broke here* and *the harness stopped here*, and **nothing currently
disambiguates them**. This is the sharpest unsolved design problem in 4b and the reason its
"deliverable is where the chain breaks" is not free.

The tractable resolution shape, from the same evidence: a break is only a *finding* when it
is **reproducible on a second run from a recorded state** — which is precisely what Phase 1
buys, and is why the dependency is real rather than nominal. A stuck agent does not reproduce
identically; a missing module does.

**F8 — WALKTHROUGH.md is the cost model, and it says a dry run is not an hour. (High)**

The one executed dry run gives real numbers for planning both modes. Its "Verdict on the
one-hour claim" is "**Not yet — but the blocker was structural, not conceptual**": the
composition layer had to be written before the run could proceed, logistic alone took 270s
per configuration, and a three-model comparison with calibration is ~36 fits. The mitigation
is stated — "cap folds and models, which the CLI already supports" — and the winning model
fits in 11.6s.

Two consequences. For **4b**, an unattended run against lending-scale data is a multi-hour
job dominated by a baseline nobody is evaluating, so the automated mode needs a capped
configuration or a smaller frame or it will measure fit time rather than chain integrity.
For **4a**, the watchability constraint is in direct tension with fit time — a demo cannot
contain a 270-second silent block — and `design-prototype/SKILL.md:90-92` already rules out
the obvious escape: "Serial by default. Parallel agents are faster and unwatchable; on a
recorded exercise the narration IS the deliverable."

**F9 — Phase 2's `ml/fraud` frame is a materially better 4a/4b target than lending, on cost
alone. (Medium-High)**

Issue #4 Phase 2 records the verified frame as **800 rows × 43 columns with 14 positives**,
against the brief's claimed 90,000. That is ~50× smaller than lending's 39,770 × 88. Every
cost problem in F8 is a row-count problem, so the thin frame makes both modes affordable —
and it independently exercises paths lending never touched (sigmoid calibration below 1000
validation rows; a 0.0175 PR-AUC floor; ~2.8 positives per fold). Phase 2's own
done-condition is *refusal or a defensible result, unmissably labelled* — a decision-shaped
outcome, which is exactly what 4a needs a human checkpoint over. It is also the harder test
for 4b: a pipeline that declines to report is a success that a naive automated runner will
score as a failure.

**F10 — The `--dry-run` adapter is a working precedent for unattended, zero-spend
execution. (High)**

`ai-marketing-comms/evals/run.py` ships `--dry-run` (`:491`, `:501-503`) backed by
`ScriptedEvalLLM` (`:150`), with difficulty driving behaviour "so the dry-run metrics have a
real spread" (`:262-270`). Its module docstring (`:14-19`) states the property: "runs the
whole harness against a scripted adapter: no network, no cost". Issue #4 Phase 3 names this
seam as "the part worth preserving exactly."

For Phase 4 this is a **naming collision worth catching early**: `--dry-run` here means
*substitute a scripted model for a real one*, while Phase 4's "dry run" means *drive the
whole research→review pipeline*. They are orthogonal — a Phase 4 automated run of an AI poc
would plausibly use `--dry-run` inside it — and conflating them in a plan would produce a
step that reads as satisfied when nothing was exercised.

### Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `design-prototype/SKILL.md:114-168` `### Observed — galactus, 2026-08-08` | **REUSE** | — | The only existing instance of 4a's deliverable; six structural elements extractable as a format (F3). Its own text asks for a second differently-shaped sample, which 4a is. Reuse as template *and* as the finding's destination. |
| `design-prototype/SKILL.md:55-88` stage-1 intake (ask 3 / show 5) | **REUSE** | — | The asked/shown boundary is already specified with budgets and a stated measurement (F6). 4a exercises it verbatim; changing it before measuring would destroy the comparison to the 0-of-5 baseline. |
| `librarian/.../asked-vs-derived-scaffold-variables.md` | **REUSE** | — | Source pattern behind the intake; supplies the *third* tier (Inferred) and the governing blast-radius rule the SKILL.md compresses away (F6). Read-only reference; librarian is not modified. |
| `ai-project-template/copier.yaml` | **ADAPT** | — | Ground truth for which variables are actually silently defaulted (70 `when: false`, F6). Phase 4 reads it to check the intake against the real variable space; it does not modify it. Adapt = derive a tier inventory from it, not edit it. |
| `guacamayo/.claude/docs/review-findings.jsonl` + `guacamayo/review/` driver | **ADAPT** | — | Real machine-readable finding corpus with recurrence counting (F4). Needs adaptation because every existing row is keyed to a source `file`/`lines`, and a finding against a *skill's instructions* has no such location. Also: galactus's own copy is gitignored (`.gitignore:31`), so writes must target guacamayo. |
| `guacamayo/.sounding/tooling-ledger.md` | **ADAPT** | — | The right home for findings that are claims-needing-falsifiers; row format (metric type + due date + promotion target) is fixed and usable as-is. Adaptation is one of ownership, not shape: `/workflow-retro` is the declared writer and its Step 1 says flag-don't-edit `.sounding/`. |
| `pocs/ml/lending/WALKTHROUGH.md` | **REUSE** | — | The only executed dry run; supplies the cost model (F8), the failure narrative 4b must reproduce (F1), and a demonstrated write-up shape. Reuse as the baseline both modes are compared against. |
| Phase 1 run registry (planned, `ai-project-template/.claude/docs/plans/2026-08-11-gal-4-phase1-run-registry.md`) | **REUSE** | — | Supplies the only credible "did this reproduce" signal, which is what separates a real break from a stuck agent (F7). Its `NotApplicable` sentinel and declared-`headline_metric` shape already cover an AI-side run with no seed. Consume; do not reshape. |
| `ai-marketing-comms/evals/run.py` `--dry-run` / `ScriptedEvalLLM` | **ADAPT** | — | Working zero-spend unattended execution (F10). Adapt = use as the inner substitution for an AI-poc target, with the vocabulary collision against Phase 4's "dry run" resolved explicitly. Do not modify: CLAUDE.md rules `ai-marketing-comms/` off-limits unless the task is about it. |
| `galactus/CLAUDE.md` `Status:` state machine + `plan_status_validate.sh` hook | **REUSE** | — | A hook-enforced, already-deployed phase-progress signal (F7). An unattended run's furthest-reached `Status:` is a free break-locator requiring no new instrumentation. |
| `workflow-review/SKILL.md` (+ `review/driver.py` gates) | **ADAPT** | — | It is the pipeline's last stage and one of the three named finding targets, but has no `Observed`-style intake for evidence about *itself* (F5). Adaptation is creating that seam. |
| `workflow-plan/SKILL.md` goal-elicitation (`:10-27`) | **ADAPT** | — | Its "confirm key decisions explicitly… do not proceed on silence" is structurally the same checkpoint 4a performs at each design decision — the shared mechanism between the copier interview and the plan phase. Adapt: 4a's trail should record plan-phase confirmations in the same ledger as intake confirmations. |
| `ml-lending/ml/run.py` | **ADAPT** | — | The live instance of the F1 break and the natural 4b subject. Adapt because its toolkit resolves through `ML_PACKAGE_ROOT` into an unmerged branch of another repo — the run must record import *resolution*, not just success. |
| `pocs/` untracked directory tree | **SKIP** | **The empty-directory inventory is separable and worth keeping**: seven named empty poc dirs are a machine-checkable "declared but absent" list, usable as a 4b probe target independent of whether the move completes. | As a Phase 4 target it is unusable — the move is half-done (data + docs relocated, source did not, F2), untracked, and its state is ambiguous. Building against it risks the exact stale-layout failure global session hygiene warns about. |
| `lebanese-blonde` | **SKIP** | **Its frame properties are already extracted into issue #4 Phase 2's table** (800 × 43, 14 positives) — the numbers survive without touching the repo. | READ-ONLY by explicit constraint; the WALKTHROUGH confirms it was "read as a reference and never executed against". Phase 2 gets its own copy of the frame; Phase 4 targets that copy. |
| W&B / MLflow | **SKIP** | **The run/params/metrics vocabulary**, already flagged as worth mirroring in the Phase 1 plan's own verdict table, so a later export stays mechanical. | Explicitly deferred by issue #4 to a follow-up that *reads* the Phase 1 registry. No account, no key, no network dep. |
| `/akira`, `/sanyi`, `/code-review` | **SKIP** | **`review-findings.jsonl` and the recurrence threshold they populate** — the corpus is reused (row above) even though the scanners themselves are out of scope. | Issue #4 names exactly three skills for findings (`design-prototype`, `workflow-plan`, `workflow-review`). Widening to the review ladder would make the phase unboundable. |
| `/workflow-refine` | **SKIP** | **Its DoR gate is a checkpoint 4a passes through**, so it should appear in the decision trail as a recorded stage even though no finding is filed against it. | Part of the pipeline both modes drive, but not one of the three named finding targets. Excluded from filing, not from execution. |

### Assumptions

- **Assumption:** The pipeline both modes drive is the five global `workflow-*` skills
  (research → plan → refine → execute → review), not a galactus-local variant —
  **Evidence:** `galactus/CLAUDE.md` "The pipeline" table names exactly those five with the
  plan doc as the bus; the `Status:` hook enforces their state machine —
  **If wrong:** the vendored `.claude/skills/` copies (CLAUDE.md "Vendoring exception") could
  drift from `~/.claude/`, and a finding filed upstream would not reach the skill the run
  actually used — **Confidence:** High on the skill set; **Medium** on which *copy* executes.
- **Assumption:** Findings filed into `~/.claude/skills/` are the durable target, and the
  galactus-vendored copies are downstream — **Evidence:** `galactus/CLAUDE.md` Vendoring
  exception: "**Canon remains `~/.claude/`;** the copies here are rendered payload. Fix
  generic skills upstream, then re-vendor" — **If wrong:** findings land in a rendered
  artifact and are lost at the next sync — **Confidence:** High.
- **Assumption:** 4a and 4b target the *same* poc, so their findings are comparable —
  **Evidence:** issue #4 says "both modes have run against a real poc" (singular) and the
  value of contrasting where the human sat depends on holding the target fixed —
  **If wrong:** the modes measure different pipelines and the comparison is void; the phase
  still produces two artifacts but not the contrast — **Confidence:** Medium.
- **Assumption:** A derivation-correction count from a *second* case is enough to move the
  intake tier boundary decision — **Evidence:** `design-prototype/SKILL.md:124-127` states
  the exact condition: "Record the count again next run and shrink only if it stays at zero
  on a second, differently-shaped case" — **If wrong:** two samples still under-determine it
  and the boundary stays open indefinitely — **Confidence:** High that it satisfies the
  skill's stated rule; **Low** that two samples are statistically adequate. The skill's rule
  is the standard being met, not statistics.
- **Assumption:** Phase 1's registry will have landed before Phase 4 runs —
  **Evidence:** issue #4 "Depends on: Phase 1 (so runs are recorded)"; the Phase 1 plan is
  written but `Status: PLANNED`, and itself waits on `AIT-67` — **If wrong:** 4b loses its
  reproduce-to-confirm signal (F7) and its breaks become unverifiable claims —
  **Confidence:** Medium — it is a two-deep dependency chain (AIT-67 → Phase 1 → Phase 4)
  with the first link unmerged.
- **Assumption:** An automated run may write to the repos it exercises —
  **Evidence:** global rules state Claude never pushes and only worktree agents commit;
  4b's own deliverable is "a real poc as the side effect", which requires writes —
  **If wrong:** 4b is a read-only rehearsal and cannot produce its stated side effect —
  **Confidence:** Low. This is the single most consequential unresolved item; see Key
  Unknowns.

### Disconfirming Evidence

**Against F1 (the composition gap is live, not historical):** Did the modules land in
galactus after the WALKTHROUGH was written, making this stale? Checked directly.
`find ml-lending -name "*.py" -path "*ml/*"` returns exactly one file, `run.py`. `git log`
on galactus shows the most recent ML commit is `6f78aeb feat(ml): training, evaluation,
reporting, persistence, drift (#62)`, which predates the WALKTHROUGH. The modules exist only
on `ai-project-template` commit `0f8b2cf`, on an unmerged branch. **Looked; the finding
strengthened** — and the *reason* it is not a defect in galactus (deliberate external
toolkit, `run.py:24-32`) is itself the interesting part: the gap is architectural, so 4b will
find it every time until the seam is instrumented.

**Against F2 (the `pocs/` move is an instance of the same class):** Is this simply
in-progress work that will complete tomorrow, making it noise rather than a finding? Partly
conceded. It is untracked and the working tree is on `GAL-3-review-leakage-unknown-verdict`
with an unrelated modified file, which is consistent with a deliberate in-flight
reorganisation. But the property that makes it an instance holds regardless of intent: the
*data* (a real gitignored extract) and the *narrative* moved while the source did not, so any
process reading `pocs/ml/lending/` as the poc finds a complete-looking directory with no
executable content. **Looked; found a real alternative explanation that bounds the finding
without refuting it** — carried into Key Unknowns as a question for the operator rather than
asserted as a defect.

**Against F3 (the `Observed` block is the decision-trail format):** Is there a better
existing artifact somewhere — an ADR template, a decision log, a `no-list` instance? Searched
all 24 global skills for `Observed`/decision-log structures (one hit), checked
`design-prototype`'s stated outputs (`SKILL.md:29-31`: "summarize findings as a comment in
ROADMAP.md or as an ADR" — no ROADMAP.md or ADR directory exists in galactus), and read the
tooling-ledger for a decision-trail row. Nothing else. **Looked; found the opposite of
contradicting evidence** — and found that the one instance is *missing the no-list* the issue
names first, which is a genuine gap in the precedent rather than a confirmation of it.

**Against F4 (findings can be "filed" mechanically):** Is the issue's "filed against the
specific skills" perhaps just rhetorical emphasis on specificity, satisfiable by a
well-organised prose section? The issue's own wording resists this — "rather than summarized
in prose" is an explicit exclusion of the prose option, and it names three skills rather than
a topic. Against that, honestly: **no existing finding in either the corpus or the ledger has
a skill's SKILL.md as its `file`**, so the mechanism is being *extended* by Phase 4, not
merely used. **Looked; the finding stands, but it is weaker than "the mechanism exists" —
it is "the mechanism exists and Phase 4 is its first use of this shape."**

**Against F7 (break-vs-stuck is undecidable without new signal):** Could an unattended run
simply be given a generous turn budget, making exhaustion rare enough to ignore? The quota
rule says no: exhaustion "surfaces as `error_max_turns` or silent empty results…
indistinguishable from agent logic failures at the API level", and explicitly warns that a
low-turn session showing `error_max_turns` is a quota signal. Budget size does not change
ambiguity, only its frequency — and a rare ambiguous result in a run whose *entire deliverable
is where it stopped* is worse than a common one, because it will not be suspected.
**Looked; the finding strengthened.**

**Against F9 (fraud is the better target):** Would lending be safer, since it is the frame
that has actually run end to end? Real tension. Lending's advantage is a known-good baseline
(the WALKTHROUGH's numbers), which makes a 4b break attributable to the pipeline rather than
the data. Its disadvantage is F8's cost: ~36 fits, 270s each for logistic. The honest reading
is that **lending is the better 4b control and fraud is the better 4a demo**, which conflicts
with the assumption that both modes share one target. **Looked; found a genuine conflict
between two of my own findings** — recorded in Key Unknowns rather than resolved, because
resolving it is a planning decision that needs the target to exist first.

### Key Unknowns

- ~~**Whether an automated 4b run may write to a repo, and where.**~~ **RESOLVED, in two
  parts.** *Where it runs* — worktree agent on a `GAL-` branch (operator, 2026-08-11; D2).
  *What it may write* — `pocs/`, excluding `pocs/ai/marketing-comms/` (operator,
  2026-08-14). See the D2 block in the refine pass for both, and note this was one
  unknown holding two questions; the 08-11 decision closed only the first.
- **Whether `pocs/` is in-flight or abandoned** (F2). Determines whether Phase 4's target
  path is `pocs/ml/fraud/` or a top-level sibling of `ml-lending/`, and whether the
  half-moved lending poc is a defect to file or a work-in-progress to leave alone.
- **Whether Phase 4 may write ledger rows directly, or must route through `/workflow-retro`**
  (F4). Retro's Step 1 says "Do NOT edit `.sounding/` — flag only", and retro is the only
  promoter to global memory. If Phase 4 may only flag, its findings sit unfiled until the
  next retro, which weakens "filed against the specific skills".
- **Which target poc, given F9's conflict.** Lending is the better control (known-good
  numbers, but expensive); fraud is the better demo (cheap, decision-shaped outcome, but
  unbuilt). Not resolvable until Phase 2 or 3 produces something.
- **What a no-list actually looks like as a recorded artifact.** The issue names it first;
  `design-prototype` calls it first-class; the one existing instance contains none (F3).
  There is no example anywhere in the repos.
- **Whether `design-prototype` will still exist.** Ledger row 2026-07-30 has it as a
  retirement candidate at 0 invocations across 261 sessions, due 2026-08-17 — before Phase 4
  plausibly runs (F5).
- **How a 4a "watchable" run is captured.** The mode is described as watchable and the
  `Observed` block says "the narration IS the deliverable", but nothing specifies whether the
  artifact is a transcript, a recording, or a written-after trail. The one existing instance
  is written-after.
- **Whether the vendored `galactus/.claude/skills/` copies or the global ones execute during
  a galactus-rooted run**, and therefore where a finding must land to reach the next run.

### Recommendation

Phase 4 should be understood as **two measurements, not two demos**, and its planning should
follow the measurement each mode makes rather than the pipeline both traverse. 4a's
measurement is already specified down to its acceptance rule — `design-prototype/SKILL.md`
asks for a derivation-correction count on a second, differently-shaped case and states what
it will do at zero — so 4a's plan is mostly a matter of choosing that case and fixing the
artifact format, for which the `### Observed` block supplies six structural elements and one
conspicuous omission (the no-list). 4b's measurement is harder and less specified: its
deliverable presupposes that "where the chain breaks" is observable, and the strongest
finding here is that it currently is not, because a stuck agent and a broken chain are
indistinguishable at the point of termination. The tractable disambiguator is reproduction
from a recorded state, which is exactly what Phase 1 provides and is why that dependency is
load-bearing rather than nominal. Meanwhile the failure class 4b exists to surface is
available for study today without waiting: the `ml.workflows` import gap is still live in
galactus, and a second instance turned up unlooked-for in the half-completed `pocs/` move —
two instances of *structure that reads complete and is empty where it executes*, both found
by asking where things physically are rather than by any test. The strongest argument for
running 4b at all is that this class has now been observed twice and caught by nothing. Step-
level planning should wait: the phase's done-condition names a real poc that does not exist
yet, and its two most consequential decisions — which target, and whether an unattended run
may write — are both undecidable until Phase 2 or 3 lands.

---

## Plan

**Deferral lifted 2026-08-11.** The section below was written as `## Plan — DEFERRED`
because Phase 4's target poc did not exist. It now does. All five preconditions in *What
must exist before step-level planning is possible* are met (see *Precondition clearance*),
and D2 — the largest fork — was answered by the operator. Steps are written against
`pocs/ml/fraud`, which is real and committed.

The original deferral rationale is preserved verbatim immediately below, because it records
*why* steps were withheld and what changed to permit them. Do not read it as current status.

> **Status: not step-planned, deliberately.** Issue #4 makes Phase 4's done-condition
> contingent on "both modes have run against a real poc", and names Phase 2 or Phase 3 as the
> source of that poc. Neither exists. A `### Steps` section written now would be steps against
> a hypothetical target, and the two decisions that most shape those steps (which poc; whether
> an automated run may write) are both properties of the target rather than of Phase 4. This
> section records the goal, the decisions a planner will need, the scope boundary, and the
> precise preconditions for step-level planning — and stops there.

### Precondition clearance — 2026-08-11

| # | Precondition | State | Evidence |
|---|---|---|---|
| 1 | Target poc runs end to end | **Met** | `pocs/ml/fraud/` on `GAL-4-fraud-poc-and-dry-runs` (`2b0f03f`). Done-condition met by *stated refusal*: `docs/summary.json` carries `operating_point_reported: false`, `min_positives_in_fold: 2`, all three models `threshold: None` |
| 2 | Phase 1 registry landed and callable | **Met** | `ai-project-template` `AIT-68-run-registry-and-evals` (`6702cde`) — `experiments/{record,provenance,fingerprint}.py`, 16 tests |
| 3 | D2 answered | **Met** | Operator, 2026-08-11: **worktree agent on a `GAL-` branch** |
| 4 | `pocs/` resolved | **Met** | Move completed and committed in the `main` merge (`776f1a1`); F2's half-move no longer holds — `ai-marketing-comms/` is an empty husk, all files tracked under `pocs/ai/marketing-comms/` |
| 5 | `design-prototype` survives | **Met** | Operator, 2026-08-11: "lets not retire 3 yet design-prototype" — option (c) on ledger row `2026-07-30`, ahead of its 08-17 due date |

**Two research findings are now stale and must not be planned against.** F2 (`pocs/` is a
half-completed untracked move) is resolved — the move landed. F9's cost conflict is resolved
by D1 toward `ml/fraud`. F1 remains live and is *deliberately preserved* as 4b's subject.

### Goal

Turn the prototyping pipeline into something that reports on itself: run
research → plan → refine → execute → review twice over one real poc, once with a human at
every design decision and once with none, and convert the difference into findings filed
where the implicated skills will read them on their next invocation. The decision the work
serves is **whether the intake tier boundary is drawn in the right place** (4a's
derivation-correction count is the second sample `design-prototype` explicitly asks for) and
**whether the composition-layer failure class is detectable by running rather than by
review** (4b). Neither mode's primary output is code.

### Refine pass — 2026-08-11

Phase 4 was refined together with Phases 1–3. **It does not become execute-ready, and
that is by design, not an omission:** Ramsey chose "research only, defer steps" at
planning, so there is no `### Steps` section to gate. The decisions below are resolved
where evidence or an operator decision allows; the rest are recorded as still-open with
their basis, because they depend on outputs that do not exist yet (see *What must exist
before step-level planning is possible*).

**Resolved at this pass:**

- **D1 — Target poc: `ml/fraud` (Phase 2's), for both modes.** Resolves F9's conflict
  toward the cheap, watchable target. Basis: 4a's deliverable is a *decision trail*, which
  requires watchability, and `design-prototype` forbids the parallel-agent escape (F8);
  lending's ~36 fits at 270s per logistic configuration is not watchable. Sharing one
  target across both modes keeps them comparable. Accepts the tradeoff that 4b loses
  lending's known-good numbers as a break control — mitigated by D6.
- **D4/D5 — Filing targets and write authority.** Phase 4 writes the skill-local
  `### Observed` block itself, and **flags** ledger rows for `/workflow-retro` rather than
  writing them. Basis: `/workflow-retro` Step 1 is explicit ("Do NOT edit `.sounding/` —
  flag only") and retro is the sole promoter to global memory. `review-findings.jsonl`
  rows are written directly, with the caveat that a finding about a *skill's instructions*
  has no natural `file`/`lines` anchor — Phase 4 is the corpus's first use of that shape.
- **D8 — Findings land in `~/.claude/skills/`, not the galactus-vendored copies.**
  Basis: galactus's own CLAUDE.md states it directly — "Canon remains `~/.claude/`; the
  copies here are rendered payload. Fix generic skills upstream, then re-vendor."
- **D6 — Break-vs-stuck discriminator: reproduction from a recorded state.** A break
  counts only when it reproduces from Phase 1's `RunRecord`. This is why the Phase 1
  dependency is load-bearing rather than nominal (F7). The concrete rule — attempt count,
  which recorded fields seed the retry, what is recorded when reproduction *itself* fails
  — is left to step planning, since it depends on the registry's landed shape.

**Still open — and correctly so:**

- **D2 — RESOLVED 2026-08-11 by operator decision: 4b dispatches a worktree agent on a
  `GAL-` branch.**
  <!-- 2026-08-14: D2 was already resolved on 2026-08-11 and is recorded here, at
       :6, :500, :520, and consumed by Step 3 at :743 — this note adds a distinct
       operator decision (2026-08-14) on D2's *second half*, not a re-resolution of
       the first. Key Unknowns asked two things: whether 4b may write, and under
       what containment. 2026-08-11 answered containment (the worktree). The write
       *target* was left open, and Out of Scope still narrows it. See the
       write-scope note immediately below. -->

  **Write scope — RESOLVED 2026-08-14 by operator decision: mode 4b MAY write to
  `pocs/`.** D2's 2026-08-11 answer settled *containment* (a worktree on a `GAL-`
  branch) but not *target*, and the two are separable: a worktree bounds where
  commits land, not which paths the agent may touch. This closes that half.
  Consequences for the steps, none of which reopen D2:
  - Step 3's agent may create and modify files under `pocs/` — its stated side
    effect, "a real poc", is now unambiguously permitted rather than inferred from
    the worktree grant.
  - The standing containment rules are unchanged and still bind: worktree agent,
    `GAL-` branch, commits provisional, dispatcher soft-resets, Claude never pushes.
  - **`pocs/ai/marketing-comms/` remains excluded.** Out of Scope bars modifying it
    beyond running it, and the repo rule treats it as the reference implementation.
    This resolution widens 4b to `pocs/`, not to that subtree — in practice
    `pocs/ml/fraud/`, the D1 target.
  - F1's `ML_PACKAGE_ROOT` gap stays out of scope regardless: 4b's job is to detect
    it, and fixing it destroys the phase's only live specimen. Containment is the worktree; the standing no-commit gate and the
  dispatcher soft-reset apply unchanged, so 4b needs no exception to any global rule — it
  uses the one exception that already exists. Consequences that shape the steps: 4b is an
  **orchestrated dispatch** (issue + branch + agent), not a single agent run; "where the
  chain broke" becomes readable from the branch's commit sequence, which is a durable
  artifact rather than a transcript; and the run genuinely writes, so `execute` is actually
  exercised and issue #4's "both modes have run against a real poc" is met on its own terms.
  Rejected alternatives: *diff-only* (a break in the commit/branch machinery becomes
  invisible) and *read-only* (leaves `execute` unexercised).
- **D3 — RESOLVED at planning: the decision trail is an `### Observed` block**, appended to
  `design-prototype/SKILL.md` in `~/.claude/skills/` (per D8), captured live during 4a and
  written immediately after. Basis: F3 establishes the format from its one instance, and
  element 6 is the mechanism that makes 4a worth running. Adds the **no-list** that F3 found
  missing — recorded even when empty, since "nothing was declined" is itself the datum whose
  absence made the first instance unrecoverable.
- **D7 — RESOLVED at planning: cap the configuration via `--n-splits`** (`run.py:233`), the
  lever F8 names as already supported. `ml/fraud` is 800 rows and its winning model fits in
  seconds, so no silent block approaches 4a's watchability threshold. `design-prototype`'s
  serial-by-default rule (F8) is honoured — no parallel agents in 4a.

**One clock worth noting:** `design-prototype` — the skill carrying the sole precedent for
4a's deliverable (F3) — has a tooling-ledger retirement row due **2026-08-17** at 0
invocations across 261 sessions. If it is retired before Phase 4 runs, findings filed into
it evaporate and D3/D8 both change. This is a dependency on a *date*, not on an artifact.

### Decisions a planner will need to make

1. **Target poc, and whether both modes share it.** F9 records a genuine conflict: lending is
   the better 4b control (known-good numbers from the WALKTHROUGH, so a break is attributable
   to the pipeline) but is expensive (~36 fits, 270s per logistic configuration); fraud is
   the better 4a demo (800 rows, decision-shaped refusal outcome, watchable) but does not
   exist yet. Sharing one target makes the modes comparable; splitting them makes each
   cheaper. This must be decided explicitly — it cannot be inherited.
2. **Whether 4b writes, and under what containment.** The mode's stated side effect is "a
   real poc", which is a code change; global rules require an issue and a branch, and permit
   commits only from worktree agents. Options range from a worktree agent on a `GAL-` branch
   through to a diff that is never committed. This decision determines whether 4b is one
   agent run or an orchestrated dispatch, and is the largest single fork in the phase.
3. **The decision-trail format, and where it lives.** F3 supplies six structural elements
   from the one existing instance plus the missing no-list. A planner must decide whether the
   trail is a new artifact type in `.claude/docs/`, an `### Observed` block appended to
   `design-prototype/SKILL.md`, or both — and whether it is captured live (watchable) or
   written after (as the precedent was).
4. **Which of the three filing targets each finding class goes to** (F4): skill-local
   `### Observed` block, `review-findings.jsonl` corpus row, or tooling-ledger row with a
   metric and due date. The corpus expects a `file`/`lines` location that a finding about a
   skill's *instructions* does not naturally have; the ledger expects a falsifier and a
   promotion target with warn-hook as default. A finding without a chosen target is the prose
   summary the issue rules out.
5. **Whether Phase 4 may write ledger rows directly or must flag for `/workflow-retro`.**
   Retro is the declared owner of `.sounding/` and the only promoter to global memory.
6. **The break-vs-stuck discriminator for 4b** (F7). The recommended shape — a break counts
   only when it reproduces from a recorded state — needs a concrete rule: how many
   reproduction attempts, from which recorded fields, and what is recorded when reproduction
   itself fails.
7. **How 4a's watchability is reconciled with fit time** (F8). `design-prototype` forbids the
   obvious escape (parallel agents are "faster and unwatchable"), so the remaining levers are
   a capped configuration, a smaller frame, or accepting silent blocks.
8. **Whether findings land in `~/.claude/skills/` or the galactus-vendored copies**, given
   that canon is global and the vendored copies are rendered payload.

### Scope boundary

**In scope when this is planned:** driving the five-skill pipeline twice over one target;
producing 4a's decision trail including the no-list; producing 4b's break report; filing
findings against `design-prototype`, `workflow-plan`, and `workflow-review`; consuming the
Phase 1 registry to make runs reproducible.

**Out of scope:** building the target poc itself (that is Phase 2 or 3); the Phase 1 registry
schema (planned separately — Phase 4 consumes it); W&B; any write to `lebanese-blonde` or
`parallax`; modifying `ai-marketing-comms/` beyond running it; widening the filing set beyond
the three named skills to the review ladder (`/akira`, `/sanyi`, `/code-review`); and
completing or reverting the `pocs/` directory move, which is the operator's call.

### What must exist before step-level planning is possible

1. **A target poc that runs end to end**, with a name and a path. Concretely: either Phase 2's
   `ml/fraud` — built against a poc-owned copy of the `lebanese-blonde` frame (800 × 43, 14
   positives), having met its own done-condition of a defensible result *or* a stated refusal
   — or Phase 3's extracted `ai/evals`, with a second AI poc running the harness without
   importing `galactus.*`. Until one of these has met its done-condition, Phase 4's steps have
   no subject.
2. **Phase 1's run registry, landed and callable**, so that 4b's "the chain broke here" is
   backed by a recorded state a second run can be attempted from (F7). Note this is two deep:
   Phase 1 itself waits on `ai-project-template` `AIT-67` (`0f8b2cf`, unmerged), which carries
   `ml/workflows/classification.py` and `ml/reporting/html.py`.
3. **A resolved answer to decision 2** (may 4b write, and where). It changes the step
   structure, not merely a step's content.
4. **A resolved state for `pocs/`** (F2) — completed, reverted, or explicitly frozen — so the
   plan's paths are stable. Global session hygiene is explicit that uncommitted structural
   moves cause agents to work against stale layouts.
5. **Confirmation that `design-prototype` survives its retirement decision** (ledger row due
   2026-08-17, currently 0 invocations across 261 sessions), since it is one of the three
   filing targets and findings filed into a retired skill evaporate.

When items 1–3 are true, this document is ready for `/workflow-plan` and the `### Steps`
section can be written against a target that exists.

**All five cleared 2026-08-11 — see *Precondition clearance* above. Steps follow.**

### Approach

Two runs over one target (`pocs/ml/fraud`), differing only in whether a human answers the
design questions. 4a is driven by the operator in a live session with `/design-prototype`,
capped for watchability, and its product is a **counted derivation-correction score** —
the second sample `design-prototype` explicitly refuses to act without. 4b is a worktree
agent dispatched with the same brief and no human, and its product is a **break report**
naming where the chain stopped and proving it reproduces. The key tradeoff: sharing one
target across both modes costs the known-good numbers lending would have provided as a
break control, bought back by D6's reproduction rule — a break counts only when it
reproduces from a recorded state, which distinguishes it from a stuck agent (F7).

Neither mode's primary output is code. The code 4b writes is the *medium* of the
measurement, not the deliverable.

### Out of Scope

- Building the target poc (done — Phase 2).
- The Phase 1 registry schema (done — Phase 3 consumes it; Phase 4 only reads records).
- Modifying `pocs/ai/marketing-comms/` beyond running it. (Still out of scope after the
  2026-08-14 write-scope resolution: 4b may write to `pocs/` — in practice `pocs/ml/fraud/` —
  but this subtree is the reference implementation and stays excluded.)
- Widening the filing set beyond `design-prototype`, `workflow-plan`, `workflow-review` to
  the review ladder (`/akira`, `/sanyi`, `/code-review`).
- W&B; any network dependency; any write to `lebanese-blonde` or `parallax`.
- Writing `.sounding/tooling-ledger.md` rows directly — Phase 4 **flags**, retro writes (D4/D5).
- Resolving F1's `ML_PACKAGE_ROOT` gap. 4b's job is to *detect* it, not fix it. Fixing it
  before 4b runs destroys the phase's only live specimen of its motivating failure class.

### Steps

#### Step 1: Freeze the 4a brief and pre-register the bets
**Files**: `.claude/docs/plans/2026-08-11-gal-4-phase4-dry-run-modes.md` (new `### 4a pre-registration` section)
**What**: Before either run, write down the brief both modes receive (identical wording) and
which parts of the asked/shown boundary are *bets*. F3 element 2 is what makes the
`### Observed` block evidence rather than rationalization — "the rules above were written
*before* the run, and two of them were bets." That property is only obtainable before the run;
it cannot be reconstructed after. Name the five shown variables and three asked questions from
`design-prototype/SKILL.md:55-88` and state, per item, the prediction (will it draw a
correction, y/n).
**Snippet**: before — no pre-registration exists. after —
```markdown
#### 4a pre-registration — 2026-08-11
Brief (verbatim, given to both modes): "..."
Shown (5), with prediction: agent-shaped=no-correction; tools=no-correction; ...
Asked (3), with prediction: archetype=will-change-a-decision; ...
Bets: (1) `human_approval` stays asked even for a refusing pipeline; (2) ...
```
**Test**: `grep -c "^Bets:" .claude/docs/plans/2026-08-11-gal-4-phase4-dry-run-modes.md` → `1`
**Done when**: the section exists, names all 8 boundary items with a per-item prediction, and
is written before Step 2 begins (verifiable by its position in the commit sequence).

#### Step 2: Run 4a — human-in-the-loop, watchable, capped
**Files**: none written during the run; `pocs/ml/fraud/` is the subject
**What**: Operator runs `/design-prototype` against the fraud poc in a live session, serially,
answering the three asked questions and correcting the five shown ones. Cap fit time via
`--n-splits 3` so no block exceeds the watchability threshold (D7). Record each correction as
it happens — the count is the measurement, and a correction noticed in retrospect is not
countable. Explicitly record the **no-list**: what was declined and why. If nothing was
declined, record that as an empty no-list rather than omitting it (F3's unrecoverable gap).
**Snippet**: run command for the capped configuration —
```bash
uv run python pocs/ml/fraud/src/run.py --n-splits 3 --report pocs/ml/fraud/docs/summary.json
```
**Test**: `uv run python pocs/ml/fraud/src/run.py --n-splits 3 --help` exits 0 (confirms the
cap lever exists at `run.py:233` before relying on it)
**Done when**: a derivation-correction count of the form `N of 5` exists, a
`M of 3` asked-questions-that-mattered count exists, and a no-list exists (possibly empty).

#### Step 3: Dispatch 4b — worktree agent, no human, `GAL-` branch
**Files**: new worktree off `GAL-4-fraud-poc-and-dry-runs`; agent commits on its own branch
**What**: Per D2. Dispatcher (not the agent) creates the branch
`git -C ~/workspace/galactus worktree add -b GAL-4-p4b-unattended <scratchpad>/gal-p4b` —
note `-b`, and note the worktree is created **in the target repo**, per the cross-repo
dispatch rule. Agent receives the Step 1 brief verbatim, with no human available for any
design decision, and drives research → plan → refine → execute → review. It must record the
**resolution path** of its imports, not merely whether they succeeded (F1: a stale
`ML_PACKAGE_ROOT` imports successfully and produces wrong numbers — a silent break, worse
than a loud one). Agent prompt includes: branch name, commit format `{type}({scope}): {desc} (#4)`,
`git fetch origin main && git rebase origin/main` before first commit, and "report and stop"
on rebase conflict.
**Snippet**: the discriminator the agent must apply at termination —
```
On terminating without a verdict, record which of three states applies:
  (a) chain broke   — reproduces from the recorded RunRecord (D6)
  (b) harness stopped — error_max_turns / empty result; see shell.md "Quota masquerade"
  (c) completed
Do not report (a) without attempting reproduction.
```
**Test**: `git -C ~/workspace/galactus log --oneline GAL-4-p4b-unattended` shows ≥1 commit
**Done when**: the agent has terminated, its branch exists with its commit sequence intact,
and its terminal state is classified (a), (b), or (c) with evidence.

#### Step 4: Apply the break-vs-stuck discriminator to 4b's outcome
**Files**: `.claude/docs/plans/2026-08-11-gal-4-phase4-dry-run-modes.md` (new `### 4b break report`)
**What**: D6's rule made concrete. If 4b terminated in state (a), attempt reproduction from
the Phase 1 `RunRecord`: **two attempts**, seeded from the record's `CodeState` (git SHA +
dirty flag) and `DataIdentity` (frame hash). A break that reproduces on both is a finding; one
that reproduces on neither is state (b) misclassified; one that reproduces on exactly one is
recorded as **indeterminate**, not rounded to either. If reproduction *itself* fails to run,
record that as its own outcome — it means the registry is not yet sufficient for 4b's purpose,
which is a finding about Phase 1, not about the pipeline.
**Snippet**:
```markdown
#### 4b break report
Terminal state: (a) chain broke
Break location: <phase>, <file:line or seam>
Reproduction: 2 of 2 attempts — reproduced
Seeded from: RunRecord <id> — code_sha <sha>, dirty false, frame_hash <hash>
```
**Test**: reproduction attempts are runnable from the recorded fields alone, with no
un-recorded state supplied by hand — if a human must supply anything, that is the finding.
**Done when**: 4b's terminal state has a reproduction verdict of reproduced / not-reproduced /
indeterminate / reproduction-unrunnable, each backed by the two attempts.

#### Step 5: File 4a's findings into `design-prototype`
**Files**: `~/.claude/skills/design-prototype/SKILL.md` (append after `:168`)
**What**: Write the `### Observed — galactus/ml-fraud, 2026-08-11` block, following F3's six
structural elements plus the no-list. Per D8 this goes to `~/.claude/skills/`, **not** the
galactus-vendored copy — canon is global, the vendored copies are rendered payload. Element 6
is the load-bearing one: with a second sample in hand, state whether the block's own retention
rule ("do not shrink to a single sentence yet") is now discharged or still holds, and give the
reason. Two samples that agree is a different claim from two that diverge — say which.
**Snippet**: before — `SKILL.md` ends at the 2026-08-08 block. after — a second dated block,
with the derivation-correction count, per-tier verdict, no-list, and an explicit rule-change
decision.
**Test**: `grep -c "^### Observed" ~/.claude/skills/design-prototype/SKILL.md` → `2`
**Done when**: the second block exists with all seven elements and names its sample number.

#### Step 6: File 4b's findings, creating the seam where none exists
**Files**: `~/.claude/skills/workflow-plan/SKILL.md`, `~/.claude/skills/workflow-review/SKILL.md`;
`guacamayo/.claude/docs/review-findings.jsonl`
**What**: F5 — neither skill has ever been filed against, so this **creates the seam rather
than using it**. Add an `### Observed` section to each skill that 4b's run implicates,
positioned where the skill's next invocation will read it. For findings that are countable
code-located instances, add a `review-findings.jsonl` row in guacamayo (galactus's copy is
gitignored at `.gitignore:31` and therefore not durable — F4). Where a finding's subject is a
*skill's instructions* rather than a source file, use the skill file itself as `file` and its
line as `lines`; this is the corpus's first row of that shape, so note it as such rather than
silently normalizing it.
**Snippet**:
```json
{"id": "P4-001", "source": "phase4-dry-run", "date": "2026-08-11", "repo": "galactus",
 "issue": "GAL-4", "file": "~/.claude/skills/workflow-plan/SKILL.md", "lines": "31",
 "category": "workflow", "merge_impact": "important", "evidence_state": "supported",
 "title": "...", "review_type": "phase4-automated"}
```
**Test**: `python -c "import json,sys; [json.loads(l) for l in open('.claude/docs/review-findings.jsonl')]"`
run in guacamayo exits 0 (every row parses)
**Done when**: each 4b finding has arrived at exactly one target, and no finding exists only
as prose in this plan doc — the outcome issue #4 explicitly rules out.

#### Step 7: Flag ledger rows for `/workflow-retro` — do not write them
**Files**: `.claude/docs/plans/2026-08-11-gal-4-phase4-dry-run-modes.md` (new `### Flagged for retro`)
**What**: Per D4/D5. Any Phase 4 finding that is a *hypothesis needing a falsifier and a
clock* belongs in `.sounding/tooling-ledger.md`, whose sole writer is `/workflow-retro`
(retro Step 1: "Do NOT edit `.sounding/` — flag only"). Write the proposed rows here, each
with the ledger's required shape — metric using one of `absence:` / `count-drop:` /
`presence:` / `ratio:` / `hook-blocks:`, a due date, and a promotion target
(`warn-hook | skill | rule | ledger-only`, warn-hook the default; `rule` carries the burden
of proof that the pattern is not mechanically checkable).
**Snippet**:
```markdown
#### Flagged for retro — proposed ledger rows (Phase 4 does NOT write these)
| Date | Change | Area | Metric | Promotion target | Due |
|---|---|---|---|---|---|
| 2026-08-11 | <finding> | workflow | `presence:...` | warn-hook | 2026-08-25 |
```
**Test**: `grep -c "sounding" .claude/docs/plans/2026-08-11-gal-4-phase4-dry-run-modes.md`
confirms no write path; `git -C ~/workspace/guacamayo status --short .sounding/` is clean
**Done when**: proposed rows exist in this doc, and `.sounding/tooling-ledger.md` is
unmodified by Phase 4.

#### Step 8: Compare the two modes and answer the phase's question
**Files**: `.claude/docs/plans/2026-08-11-gal-4-phase4-dry-run-modes.md` (new `### Verdict`)
**What**: The phase exists to answer two questions (`### Goal`): **is the intake tier boundary
drawn in the right place** (4a's correction count against the pre-registered bets from Step 1),
and **is the composition-layer failure class detectable by running rather than by review**
(4b — did an unattended run surface F1's class, which "has now been observed twice and caught
by nothing"). Answer both explicitly, including a negative answer. A negative result recorded
as a negative result is F3 element 5 and is a valid outcome of this phase.
**Snippet**:
```markdown
#### Verdict — 2026-08-11
Tier boundary: <correct / needs adjustment / still one sample> — N of 5 corrections,
  against pre-registered predictions: <hits>/<misses>
Failure class detectable by running: <yes / no / inconclusive> — basis: <4b terminal state>
```
**Test**: both questions have a stated answer with its basis named
**Done when**: the `### Verdict` section answers both, and each answer cites the run that
produced it.

### Test Plan

There is no unit-test surface here — Phase 4's outputs are measurements and documents.
Verification is therefore per-artifact:

| Check | Command | Expects |
|---|---|---|
| Target still runs | `uv run pytest pocs/ml/fraud/tests -q` | pass |
| Cap lever exists | `uv run python pocs/ml/fraud/src/run.py --help` | shows `--n-splits` |
| Registry callable | `uv run pytest tests/unit/experiments -q` (in ai-project-template) | 16 pass |
| Second Observed block | `grep -c "^### Observed" ~/.claude/skills/design-prototype/SKILL.md` | `2` |
| Corpus rows parse | `python -c "import json; [json.loads(l) for l in open('.claude/docs/review-findings.jsonl')]"` | exit 0 |
| Ledger untouched | `git -C ~/workspace/guacamayo status --short .sounding/` | empty |
| 4b branch intact | `git log --oneline GAL-4-p4b-unattended` | ≥1 commit |

**Pre-existing failure to not chase**: 8 tests in `review/tests/` fail on this branch,
verified pre-existing at base `776f1a1` (they reference `ai-marketing-comms/...` by hardcoded
path, broken by the authorized `pocs/` move). They are unrelated to Phase 4 and have their own
issue. Do not fix them inside this phase.

<!-- 2026-08-14: this note is now stale — the fixtures were repaired. They anchor on
     `pocs/ai/marketing-comms/src/model/gateway.py`, the post-move path, and
     `uv run pytest review/tests -q` is green at 88 passed. Left in place rather than
     deleted because it was accurate when written and explains why the suite was
     briefly untrustworthy. If a run here shows failures against
     `.../src/galactus/model/gateway.py` — note the extra `galactus/` segment, the
     pre-move path — that is stale `__pycache__`, not real drift. Clear it and re-run
     before chasing anything. -->


### Risks & Rollback

| Risk | Likelihood | Consequence | Mitigation |
|---|---|---|---|
| 4b terminates ambiguously (F7's third state) | **High** — this is the phase's known-hard problem | "Where the chain breaks" is unanswerable | D6's two-attempt reproduction rule (Step 4); `indeterminate` is an allowed verdict, so the phase does not need to force a false answer |
| Someone fixes `ML_PACKAGE_ROOT` before 4b runs | Medium | Destroys 4b's only live specimen | Named in Out of Scope; Step 3 runs before any F1 remediation |
| 4a's correction count is 0 again | Medium | Two samples, both zero — still no signal on the boundary | This is a *valid* outcome, not a failure. Step 8 records it as such; F3 element 6's retention rule then holds for a documented reason rather than an untested one |
| Worktree agent commits outside its branch | Low | Violates the no-commit gate | `risky_git_guard.sh` enforces; dispatcher soft-resets after (global CLAUDE.md step 4) |
| `design-prototype` retired before Step 5 lands | Low — operator deferred it | Findings evaporate | Ledger row `2026-07-30` is due 2026-08-17; run Step 5 before that date |

**Rollback**: every step's output is either a doc section or a commit on a dedicated branch.
Rollback is `git branch -D GAL-4-p4b-unattended` plus reverting the appended `### Observed`
blocks. No production code path is touched by Phase 4 itself.

### Open Questions

1. **Does 4b's brief tell the agent it is being measured?** Telling it risks performing for
   the measurement; not telling it risks an agent that gives up early where a human would
   push. The plan assumes **not told** — 4b measures the unattended baseline, and a primed
   agent is not that baseline. Flag if you disagree; it changes Step 3's prompt.
2. **If 4a and 4b reach different verdicts on the fraud poc's refusal** (F9: "a pipeline that
   declines to report is a success that a naive automated runner will score as a failure"),
   is that a 4b defect or a finding about the pipeline? The plan treats it as **a finding**,
   filed per Step 6 — it is precisely the composition-layer blindness the phase hunts.
3. **Issue #4 DoD** — Phase 4 is the last phase. Close #4 after the PR merges, not on
   Phase 4's completion, since Phases 1–3 land on separate branches in two repos.
