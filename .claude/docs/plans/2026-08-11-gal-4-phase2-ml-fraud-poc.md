# GAL-4 Phase 2 — `ml/fraud` poc on lebanese-blonde (thin-frame honesty)
Date: 2026-08-11
Status: COMPLETE
From: EXECUTED
Review: passed
Completed: 2026-08-15

## Research

### Summary

The frame is exactly as issue #4 asserts — **800 rows × 43 columns, 14 positives, 1.75%
prevalence** — verified by direct read-only inspection, not taken on trust. Running the
existing toolkit against it end to end (done during this research, on a scratchpad copy)
produces the failure the phase exists to catch: **all three models complete without a
single warning, every PR-AUC lands within 0.003 of the 0.0175 prevalence floor, ROC-AUC
is ~0.49 (a coin flip), and each model still reports a cost-minimising threshold whose
precision is 0.000, recall 0.000, and true-positive count 0.** The toolkit has no
thin-frame guard anywhere; the refusal the issue wants does not exist and must be built.

The second finding is that the reporting layer already *has* the number it needs and
throws it away: `classification_metrics` computes `prevalence`
(`evaluation/metrics.py:146`) and `pr_curve` carries `baseline=prevalence`
(`metrics.py:193`), but `reporting/html.py` renders neither — a reader sees `PR-AUC
0.0200` in a column with no floor and no way to know that 0.0175 is chance.

### Scope

**Investigated:** the on-disk lebanese-blonde frame (shape, target, prevalence, dtypes,
missingness, cardinality, `age` treatment); the ML toolkit in `ai-project-template`
(`workflows/classification.py`, `evaluation/{calibration,splitting,threshold,metrics}.py`,
`transform/columns.py`, `sampling/resample.py`, `selection/registry.py`,
`reporting/html.py`); the lending poc as the model for a poc run
(`pocs/ml/lending/WALKTHROUGH.md`, `ml-lending/ml/run.py`); the Phase 1 registry plan;
git/commit state of AIT-67.

**Empirically executed (read-only, scratchpad copy of the toolkit):** column inference,
fold construction, calibration-method selection, and three full `run_classification`
invocations on the real frame. The numbers in Findings are measured, not projected.

**Out of scope for this research:** the upstream 90k-row Klarna dataset (not on disk and
not obtainable here); any modelling improvement; the AI side (#4 Phase 3); W&B.

### Findings

#### F1 — Frame properties: the issue is right, the brief was wrong (Confidence: High)

Measured directly from `~/workspace/lebanese-blonde/src/data/dataset.csv` (`;`-delimited,
read-only, never written):

| property | brief said | issue said | **measured** |
|---|---|---|---|
| rows | 90,000 | 800 | **800** |
| positives | 1.4% | 14 (1.75%) | **14 (0.0175)** |
| columns | — | 43 | **43** |

Additional measured facts the issue does not state, all load-bearing for the plan:

- `sha256(dataset.csv)` = `ef4c290e21f37c4bb6aacd9462c1f024aec61b6bcf752b9f76090a6cf355342a`,
  201,777 bytes, 801 lines (800 + header). This is the identity the poc copy must match.
- Target `default` has **zero missing values** — `{0: 786, 1: 14}`. No unresolved-row
  filter is needed (unlike lending's 5,454-row survivorship drop).
- `uuid` is 800/800 distinct.
- 41 of 43 columns have some missingness; the worst is 6.5%
  (`account_days_in_rem_12_24m`). No column is all-missing or constant, so
  `infer_column_types` drops nothing as `unused`.
- `age`: min 18, max 74, median 46, **36 missing**.

**Verdict: the issue's numbers are correct and the phase scope stands.** No contradiction
to report.

#### F2 — There is no thin-frame guard anywhere in the toolkit (Confidence: High)

`run_classification` (`workflows/classification.py:247-384`) validates exactly three
things: that the target is a column (`:275`), that some feature survives inference
(`:280`), and that some fold produced predictions (`:326`). **Nothing anywhere inspects
the positive count.** `choose_threshold` (`evaluation/threshold.py:86`) rejects
non-positive costs and empty inputs, and nothing else. `make_splitter`
(`evaluation/splitting.py:145`) refuses temporal/group contradictions but says nothing
about class counts.

The toolkit's refusal vocabulary is real but aimed elsewhere — `TemporalLeakageError`,
`GroupLeakageError`, `SamplingLeakageError`, `TransformLeakageError`. Every one guards
*leakage*. **None guards insufficiency.** That is the gap this phase fills, and the
existing errors are the template to copy: raise with a sentence explaining the
consequence, not a warning nobody reads (`splitting.py:14-19` states this principle
explicitly).

#### F3 — Measured: the toolkit reports a confident-looking number over 3 positives (Confidence: High)

Executed during research against the real frame (uuid dropped, 5 folds, calibrate=True,
cost_fp=1.0, cost_fn=10.0, seed=42), all three registry classifiers:

| model | PR-AUC | ROC-AUC | calibration | threshold | precision | recall | TP | FP | n_flagged |
|---|---|---|---|---|---|---|---|---|---|
| logistic *(baseline)* | 0.0200 | 0.4911 | sigmoid | 0.0562 | 0.000 | 0.000 | 0 | 1 | 1 |
| random_forest | 0.0189 | 0.5398 | sigmoid | 0.0619 | 0.000 | 0.000 | 0 | 1 | 1 |
| lightgbm | 0.0175 | 0.4356 | sigmoid | 0.0735 | 0.000 | 0.000 | 0 | 1 | 1 |

`skipped` was empty. `beats_baseline` returned `False`. **No warning was emitted by any
layer.** Total wall time ~12 seconds.

Read this table the way a reader without the floor would: "PR-AUC 0.0200, and the
baseline wins." Read it with the floor: **every model is at or below chance** (floor
0.0175; lightgbm is *exactly* the floor; ROC-AUC ~0.49 for the winner is worse than a
coin). The threshold rows are the sharpest evidence — a cost-minimising operating point
that flags exactly one row, catches zero of the 14 positives, and is nonetheless reported
with three-decimal precision and a `savings_vs_default` figure.

This is precisely the issue's "a number produced over 3 positives without a warning is a
failed phase." **The current toolkit fails it.**

#### F4 — Fold arithmetic: 2–3 positives per test fold, measured (Confidence: High)

`make_splitter(n_splits=5, random_state=42)` → `StratifiedKFold`, kind `stratified`.
Measured per-fold positives:

| fold | train n | train pos | test n | test pos |
|---|---|---|---|---|
| 0 | 640 | 12 | 160 | **2** |
| 1 | 640 | 11 | 160 | **3** |
| 2 | 640 | 11 | 160 | **3** |
| 3 | 640 | 11 | 160 | **3** |
| 4 | 640 | 11 | 160 | **3** |

The issue's "~2.8 per fold" is exact. `StratifiedKFold` emits no warning at this count
(sklearn only warns when a class has fewer members than `n_splits`; 14 ≥ 5, so it stays
silent). A test fold with 2 positives supports exactly three distinct recall values
(0, 0.5, 1.0) — the metric is quantised far coarser than the four decimal places the
report prints.

There is a **second, worse layer**: calibration cross-validates *within* the training
rows at `cv=3` (`classification.py:221`), so the inner calibration folds see ~11
positives split three ways — **~3.7 positives each**. The threshold is chosen downstream
of that.

#### F5 — Sigmoid calibration is confirmed reached, on both call sites (Confidence: High)

`recommend_method` (`evaluation/calibration.py:80-82`) returns sigmoid below
`DEFAULT_ISOTONIC_MIN_SAMPLES = 1000`. Measured on this frame:

- Per-fold path (`classification.py:219`, `recommend_method(len(y_train))`) →
  `recommend_method(640)` → **sigmoid**.
- Report path (`classification.py:344`, `recommend_method(int(scored.sum()))`) →
  `recommend_method(800)` → **sigmoid**.

Both call sites agree here, which matters: they can disagree (per-fold uses train rows,
report uses scored rows), and a frame between 640 and 1000 scored rows would label an
isotonic report over sigmoid fits. Not a problem on this frame; worth recording.

Confirmed in the F3 run — all three models report `cal=sigmoid`. **This is the
calibration branch lending never touched** (lending had 39,770 rows → isotonic
throughout), so Phase 2 exercises it for the first time. Notably it did not fail or
degrade: the fold-level `try/except` (`classification.py:224`) never fired, and Brier
moved 0.0673 → 0.0172 for logistic. Sigmoid's two parameters are doing what the docstring
claims — being safe on a small set. **The calibration path is fine; the threshold built
on top of it is not.**

#### F6 — The prevalence floor is computed and then discarded by the report (Confidence: High)

`classification_metrics` already stores `prevalence` (`metrics.py:146`), `ClassificationMetrics`
declares the field (`metrics.py:75`), and `pr_curve` sets `baseline=float(np.mean(binary_true))`
with the docstring "prevalence as the no-skill baseline" (`metrics.py:182-193`).
`CurvePoints.baseline` is documented as "The no-skill reference: prevalence for a PR
curve, 0.5 for ROC" (`metrics.py:55-56`).

`reporting/html.py` renders **none of it**. `_model_table` (`html.py:56-84`) emits a
PR-AUC column with no floor annotation; `_run_facts` (`html.py:183-211`) shows `class
balance` but never labels it as the PR-AUC floor; `_verdict` (`html.py:87-118`) compares
best-vs-baseline margin and never compares either to chance. Grepping `html.py` for
`prevalence` and `floor` returns zero matches outside the word "baseline" used in the
*model*-baseline sense — a genuinely confusing collision, since "baseline" in this report
means "the logistic model" and "baseline" in `metrics.py` means "chance".

**This is issue point 3, and it is a display fix, not a computation fix.** The floor is
already in the object graph. Lending never surfaced this because at a 0.2056 floor a
0.4351 PR-AUC reads as obviously good; at a 0.0175 floor, 0.0200 reads as a small number
that could be anything.

#### F7 — `age` is used raw, confirmed at source (Confidence: High)

`~/workspace/lebanese-blonde/src/features.py:28` lists `"age"` inside `numeric_features`,
with no binning, no ratio, no derivation. It flows straight into the model as an integer
year count. Range 18–74, median 46, 36 missing (which `TabularPreprocessor` will impute —
so an imputed age is indistinguishable from a real one downstream).

Age is a protected characteristic in most credit and fraud jurisdictions. The lending poc
has direct precedent for how to handle this: `ml-lending/ml/run.py:154` drops `zip_code`
as "a protected-characteristic proxy (DESIGN.md open item 4)" — a *recorded* decision
with a pointer to where the argument lives. **Phase 2 should record, not silently
reproduce and not silently drop.** The issue is explicit: "worth recording as a
fairness/derivation note, not silently reproducing."

#### F8 — AIT-67 is committed and pushed, but not merged (Confidence: High)

The task brief said `workflows/classification.py` and `reporting/html.py` are
**uncommitted**. That is now stale. Verified in `~/workspace/ai-project-template`:

- `git status --porcelain` → **clean**.
- Current branch `AIT-67-ml-workflows-classification`, HEAD `0f8b2cf`
  ("feat: implement classification workflow and reporting structure", 823 insertions
  across 7 files including `tests/unit/ml/test_workflows.py`).
- `git branch -r --contains 0f8b2cf` → `origin/AIT-67-ml-workflows-classification` only.
- `origin/main` is at `1865f81` and does **not** contain the modules.

So the dependency is real but weaker than stated: the code exists, is committed, is
pushed, and is importable from that branch — it is simply not on `main`. Phase 2 can be
planned and executed against the branch. **Flagged as blocked-by #67 for merge purposes
only**, not for execution. The Phase 1 plan's Open Question 6 records the same dependency
with the older (uncommitted) reading; it can be relaxed the same way.

#### F9 — `uuid` would be target-encoded — a per-row key against 14 labels (Confidence: High)

Measured `infer_column_types(df, target="default")` on the raw frame:

```
numeric            37
categorical        ('merchant_category', 'merchant_group', 'name_in_email', 'has_paid')
high_cardinality   ('uuid',)
boolean            ()
unused             ()
n_features         42
```

`uuid` has 800 distinct values over 800 rows, exceeds `DEFAULT_HIGH_CARD_THRESHOLD = 50`
(`transform/columns.py:19`), lands in `high_cardinality`, and `TabularPreprocessor`
target-encodes that bucket (`classification.py:307` folds `high_cardinality` into
`categorical` for the preprocessor). **A row-unique key target-encoded against 14
positives is a near-perfect memorisation feature.**

This is the identical class of defect the lending poc documented and routed around
(`ml-lending/ml/run.py:266-283`, the "TOOLKIT GAP" docstring — the group key at 39,561
distinct values landing in `high_cardinality` and being target-encoded). Lending solved
it by keeping the column out of the frame. Phase 2 must do the same for `uuid`, and the
recurrence is itself a finding: **the toolkit has now created this exact hazard on two of
two real frames.**

Note `has_paid` lands in `categorical`, not `boolean` — under this pandas version the
column reads as `str` ("True"/"False"), so `is_bool_dtype` is False. Harmless (it
one-hots to two columns) but worth not being surprised by.

#### F10 — Phase 1's registry can record this run, and Phase 2 must not wait for it (Confidence: High)

The Phase 1 plan (`ai-project-template/.claude/docs/plans/2026-08-11-gal-4-phase1-run-registry.md`)
defines `RunRecord` with `metrics: dict[str, float]` + a required `headline_metric: str`
(Step 1, lines 328-344), explicitly so no PR-AUC assumption is baked in. A refusal run
fits that shape: the metrics map carries `prevalence` and `n_positives`, and
`NotApplicable(reason=...)` (Step 1) is the exact mechanism for "no threshold was chosen
because the frame was too thin" — a *recorded* inapplicability rather than a null.

That is a good fit and a real convergence. But Phase 1 targets `ai-project-template` and
is itself unexecuted. **Phase 2 must emit a self-contained JSON summary of its own**
(lending's `--summary-json` precedent, `ml-lending/ml/run.py:391`), shaped so a later
adapter can lift it into a `RunRecord` without re-running. Depending on Phase 1's module
would block Phase 2 on an unwritten module in a different repo.

#### F11 — The one-hour claim is not what this phase tests (Confidence: High)

Measured: the full three-model run completes in **~12 seconds** (3.3s + 3.4s + 4.8s), vs
lending's ~270s for logistic alone. The WALKTHROUGH's headline caveat — "the fits
themselves are not one-hour work on this frame" — evaporates at 800 rows.

So Phase 2 inherits none of the speed question and all of the honesty question. That is a
clean separation and worth stating in the poc's write-up: **the constraint on a thin
frame is never compute, it is evidence.**

### Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `ml/workflows/classification.py` (AIT-67) | **REUSE** | n/a — reused whole | Composes the chain correctly; runs clean on this frame in 12s (F3). Needs a guard *added*, not a rewrite. The guard belongs at the poc/run layer first (see Approach), so the module is reused unmodified in the primary path. |
| `ml/evaluation/calibration.py` | **REUSE** | n/a — reused whole | `recommend_method` correctly selects sigmoid at both call sites (F5) and sigmoid measurably improved Brier 0.0673→0.0172. The untested path works; Phase 2's job is to *witness* it, not fix it. |
| `ml/evaluation/threshold.py` | **REUSE** | n/a — reused whole | `choose_threshold` is a correct pure function. Its output is meaningless here, but that is an input-sufficiency problem, not a defect in the minimiser. Guard upstream of the call, never inside it. |
| `ml/evaluation/splitting.py` | **REUSE** | n/a — reused whole | `StratifiedKFold` via `make_splitter` is the right splitter; no group or time structure exists in this frame. Its refusal *style* (`splitting.py:14-19`) is the model to copy for the new insufficiency error. |
| `ml/evaluation/metrics.py` | **REUSE** | n/a — reused whole | Already computes `prevalence` and PR-curve `baseline` (F6). The floor is present; only the report discards it. No change needed here. |
| `ml/reporting/html.py` (AIT-67) | **ADAPT** | The whole aggregates-only discipline and the `_verdict` null-result block are kept verbatim; only two additions | Renders PR-AUC with no floor and no refusal surface (F6). Needs a floor annotation and a refusal banner. Touching AIT-67's file is a cross-repo change — the plan defers it to a poc-local report wrapper first (Step 6) and files the template change as a follow-up, so Phase 2 is not blocked on #67 review. |
| `ml/transform/columns.py` | **ADAPT** | Bucketing logic is correct and reused as-is; only the *caller* changes | `uuid` → `high_cardinality` → target-encoded (F9). Same defect class lending hit. Fixed at the poc's frame builder by dropping identifiers before inference — the cheap, local, already-precedented fix. A toolkit-level identifier heuristic is a separate issue, not this phase. |
| `ml/selection/registry.py` | **REUSE** | n/a — reused whole | Served all three classifiers; `skipped` empty. catboost is absent from the probe env and would be recorded as skipped, which is the designed behaviour. |
| `ml/sampling/resample.py` | **REUSE** | n/a — reused whole | `class_weight` is the right strategy at 1.75%; SMOTE variants over 14 positives would synthesise minority rows from 14 real ones, which is fabrication at this count. Plan pins `class_weight` and says why. |
| `ml-lending/ml/run.py` | **ADAPT** | Its structure is the template: module docstring stating WHAT THIS RUN IS + DATA HANDLING, constants-as-recorded-decisions, `build_frame`, `summarise`, `--summary-json`, aggregates-only discipline | Welded to Lending Club specifics (leakage lists, `loan_status`, group key). The *shape* transfers wholesale; the content does not. Copy the skeleton, replace the decisions. |
| `pocs/ml/lending/WALKTHROUGH.md` | **ADAPT** | Section skeleton (The question / Result table / Walkthrough per stage / findings / Verdict) transfers exactly | It is the model for what evidence a poc run must produce, per the task brief. Phase 2's write-up mirrors it with an inverted headline: lending's was "a real win", Phase 2's is "a justified refusal". |
| `lebanese-blonde` repo | **REUSE (read-only)** | `src/features.py` is read as the derivation reference (F7) and never imported | READ-ONLY constraint is absolute. Frame is copied out; nothing is written back. Its `features.py` supplies the `age`-raw fact and the ordinal-vs-numeric column intent. |
| `lebanese-blonde/src/models.py`, `app.py`, `synthetic.py` | **SKIP** | **`synthetic.py` is salvageable** — it holds column-wise synthetic generators (incl. an `age` branch at `synthetic.py:35`) that could seed a fixture frame for the refusal unit test without copying real rows. The plan takes this: Step 2's test fixture is synthetic, not a slice of the real frame. `models.py`/`app.py` are genuinely not salvageable — Streamlit/serving concerns with no bearing on a batch honesty run. | Out of scope: Phase 2 is a batch run, not a served app. |
| Phase 1 registry (`runs/`) | **SKIP** *(this phase)* | **Salvageable now: the record *shape*.** Phase 2's `--summary-json` is deliberately keyed to be liftable into `RunRecord` — flat `metrics` dict + explicit `headline_metric` + a reason string wherever Phase 1 would put `NotApplicable`. So the schema is adopted without the dependency. | Unexecuted, and in a different repo (F10). Importing it would block Phase 2 on Phase 1. |
| `ml/model_comparison/compare.py` (`TabularPreprocessor`) | **REUSE** | n/a — reused whole | Fitted inside the per-fold pipeline, which is the property `assert_no_transform_outside_pipeline` protects. Its target-encoding of `high_cardinality` is what makes F9 dangerous, but the fix is caller-side. |
| `ml/feature_engineering/`, `clustering/`, `regression/`, `timeseries/`, `stats_testing/` | **SKIP** | **Nothing salvageable for this phase**, checked: `feature_engineering/mining.py` is the nearest candidate, but adding engineered features over 14 positives increases the ways to overfit without adding evidence — the opposite of what the phase argues. Deliberately unused. | Wrong family (unsupervised/regression/temporal) or actively counterproductive at this positive count. |

### Assumptions

- **Assumption:** The refusal threshold should be expressed in *positives per test fold*,
  not total positives or prevalence — **Evidence:** F4 measures 2–3 per fold; the issue
  frames it as "over ~2.8 positives per fold"; prevalence alone is scale-free and would
  clear a 100k-row frame at the same 1.75% — **If wrong:** the guard fires on the wrong
  frames (either too eager on large imbalanced frames or silent on small balanced ones) —
  **Confidence:** High
- **Assumption:** A refusal must block the *threshold and operating point* specifically,
  while still reporting discrimination metrics with their floor — **Evidence:** F3 shows
  PR-AUC/ROC-AUC are computed over all 800 scored rows and are informative (they say
  "chance"), whereas precision/recall at the chosen threshold are computed over ~1 flagged
  row and say nothing — **If wrong:** either the run reports nothing (unhelpful) or
  reports everything (the failed phase) — **Confidence:** High
- **Assumption:** The poc copy of the frame is committed-safe because `*.csv` is
  gitignored repo-wide (`.gitignore:40`) — **Evidence:** verified; lending's data dir is
  additionally listed explicitly — **If wrong:** real records enter git history —
  **Confidence:** High. Plan adds an explicit path entry anyway rather than relying on
  the glob.
- **Assumption:** Phase 2 may execute against AIT-67's branch without waiting for merge —
  **Evidence:** F8, the modules are committed and pushed at `0f8b2cf` — **If wrong:** the
  poc's imports break when #67 is rebased or reworked in review — **Confidence:** Medium.
  Mitigated by pinning the SHA in the poc's run docstring.
- **Assumption:** `uuid` must be dropped before inference — **Evidence:** F9, measured —
  **If wrong:** every metric in the run is inflated by memorisation and the whole phase
  reports the opposite conclusion — **Confidence:** High

### Disconfirming Evidence

- **"Maybe the toolkit does warn and I missed it."** Looked: grepped every module for
  `warn`, `raise`, `MIN_`, and threshold constants; read `run_classification` end to end;
  and *ran it* with `warnings.catch_warnings(record=True)` plus logging at WARNING. The
  F3 run emitted nothing. `skipped` was empty. **Confirmed absent, not merely unfound.**
- **"Maybe sigmoid calibration fails on 14 positives, and *that* is the finding."**
  Tested: it does not. The per-fold `try/except` (`classification.py:224`) never fired and
  Brier improved 4× for logistic. The honest finding is the less dramatic one — **sigmoid
  is fine and the threshold is not** — and reporting a calibration failure would have been
  wrong.
- **"Maybe a model genuinely beats the floor and the refusal is premature."** Tested all
  three registry classifiers. Best PR-AUC 0.0200 vs floor 0.0175; ROC-AUC 0.4911 for that
  same model, i.e. *below* chance discrimination. `beats_baseline` returned False. There is
  no signal being suppressed by the refusal.
- **"Maybe 5 folds is the problem and fewer folds would give enough positives per fold."**
  Considered: 3 folds gives ~4.7 positives per test fold, 2 gives 7. But fewer folds does
  not create evidence — it re-partitions the same 14 events, and a threshold chosen on 7
  positives is still a threshold chosen on 7 events. Recorded as a rejected mitigation in
  the plan rather than an option, and the guard is deliberately expressed per-fold so that
  lowering `n_splits` to dodge it is visible.
- **"Maybe the issue's numbers came from a different file."** Checked the whole
  `src/data/` directory — `dataset.csv` is the only file present. Hash and line count
  recorded in F1 so any future divergence is detectable.

### Key Unknowns

1. **Where the 90k/1.4% brief numbers came from.** The issue says "the upstream Klarna
   dataset"; that file is not in the checkout and cannot be verified here. Unresolvable
   locally; does not affect the plan, since the plan is scoped to what is on disk.
2. **The right universal value for the minimum-positives-per-fold constant.** 5 and 10 are
   both defensible rules of thumb (the epidemiological "events per variable ≥ 10" heuristic
   argues for far more given 41 features). The plan picks a default and flags it for
   sign-off rather than asserting a literature value it cannot cite from here.
3. **Whether the guard ultimately belongs in the toolkit or the poc.** The plan puts it in
   the poc first (executable now, no cross-repo blocker) and files the promotion as a
   follow-up. Which repo *ends up* owning it is a decision for refine.
4. **What `time_hours` means.** It is numeric (0–24-ish by inspection) and looks like a
   time-of-day-of-application feature rather than a row ordering, so no temporal split is
   indicated. Not verified against upstream documentation; recorded so nobody later
   assumes it ordered the rows.

### Recommendation

The frame is confirmed and the phase's premise holds exactly. The evidence that matters is
already in hand: **the toolkit today produces a fully-formed, warning-free, three-decimal
threshold report over 2–3 positives per fold, in which every model sits at chance.** That
measured run is the artifact the phase should be built around — it is the "before", and it
should be preserved verbatim in the write-up rather than discarded once the guard exists,
because a guard whose necessity is asserted is much weaker than one whose necessity was
photographed.

The work therefore splits cleanly: (a) build the frame copy and derivation with the `uuid`
hazard and the `age` note handled as *recorded decisions* in the lending style; (b) add an
insufficiency check that refuses the operating point while still reporting
discrimination-with-floor; (c) make the refusal and the floor unmissable in the output;
(d) write it up. The refusal is the deliverable, not the fallback — which means it needs
its own tests, its own report surface, and its own success criteria, and the plan below
treats it that way.

---

## Plan
Date: 2026-08-11
Based on: `## Research` above

### Goal

Produce a recorded `ml/fraud` poc run on the 800-row lebanese-blonde frame that **refuses
to report an operating point** over ~2.8 positives per fold and states why, while still
reporting discrimination metrics against their 0.0175 prevalence floor — so that
galactus has a worked example of a prototype whose honest output is a declined answer.

> **Goal was inferred, not elicited.** The `/workflow-plan` goal-elicitation interview was
> skipped (this session cannot ask questions). The goal above is read from issue #4's
> Phase 2 done-condition. Every decision that the interview would have confirmed is in
> **Open Questions** below, marked UNCONFIRMED with the plan's assumed default.
> **All UNCONFIRMED items need sign-off at `/workflow-refine` before execute.**

### Open Questions

**All ten resolved 2026-08-11 at `/workflow-refine`.** Items 1, 3 and 5 were confirmed by
Ramsey directly; the rest were resolved on recorded evidence and are marked with their
basis. No item remains UNCONFIRMED.

1. **RESOLVED (Ramsey, 2026-08-11) — Refusal criterion: minimum positives in any test
   fold < 10.** Confirmed over the 5 and events-per-variable alternatives. This frame
   measures 2–3 per fold, so it refuses **decisively rather than marginally** — the margin
   was the deciding factor: at 5 a slightly richer frame would pass while still being too
   thin to trust, and an events-per-variable rule (~410 positives for 41 features) would
   refuse frames a reviewer would consider legitimately reportable.

2. **RESOLVED (evidence) — Refuse the threshold / operating point only.** Still report
   PR-AUC, ROC-AUC, Brier and calibration, each labelled with its floor. Basis: the
   discrimination metrics are computed over all 800 scored rows and correctly report
   "chance", whereas precision/recall derive from ~1 flagged row (Assumption 2). Refusing
   the whole run would suppress numbers that are *correct* and are the evidence for the
   refusal itself.

3. **RESOLVED (Ramsey, 2026-08-11) — A recorded verdict, not a raised exception.** The run
   completes, exit code 0, and emits a `refusal` block in both the JSON summary and the
   HTML. Confirmed over `FrameTooThinError`. Rationale as planned: the phase's deliverable
   *is* the artifact, and an exception produces none. The toolkit's existing errors
   (`TemporalLeakageError` et al.) raise because they guard leakage, where no output is the
   correct output; insufficiency differs — the frame profile is worth reporting.
   **This decision defines the CI/automation contract: a refusing run is a successful run.**

4. **RESOLVED (evidence) — The guard lives in the poc** (`pocs/ml/fraud/src/run.py`), not
   in `ai-project-template`. Basis: executable immediately with no cross-repo blocker, and
   Phase 4b is what will tell us whether the automated chain wants it in the toolkit —
   promoting before that evidence exists would be guessing. Follow-up issue proposes
   promotion to `ml/evaluation/sufficiency.py`.

5. **RESOLVED (Ramsey, 2026-08-11) — Keep `age` raw and record it as a fairness note** in
   the run docstring, the JSON summary, and the report. Confirmed over dropping or binning.
   Follows the `zip_code` precedent at `ml-lending/ml/run.py:154`. The reasoning that
   carried: a silent drop is as unrecorded as a silent inclusion, and dropping would also
   diverge from the reference implementation, weakening the poc as a reproduction control.

6. **RESOLVED (evidence) — Drop `uuid` before inference**, recorded as an explicit
   `IDENTIFIER_COLUMNS` constant in the lending style. Basis: F9 measured `uuid` at 800/800
   distinct, target-encoded against 14 positives — it is a pure identifier and its
   inclusion is a leakage path, not a modelling choice.

7. **RESOLVED (evidence) — Preserve the unguarded "before" run.** Step 1 re-runs it
   deliberately as a captured artifact before the guard exists. Basis: the F3 table is the
   phase's evidence that the failure condition occurs *today*; without the captured
   artifact the guard has nothing to demonstrate against. Costs ~12s.

8. **RESOLVED (evidence) — Poc-local report wrapper** that calls
   `ml.reporting.html.write_report` and injects the floor + refusal, leaving AIT-67's file
   untouched. Basis: editing `template/.../reporting/html.py` on the #67 branch would
   couple Phase 2 to an unmerged branch in another repo and put Phase 2's scope inside
   #67's review. Follow-up issue proposes folding it into the template once #67 merges.

9. **RESOLVED (evidence) — Standalone JSON summary, no import of Phase 1 code.** Shaped
   for later lift into Phase 1's `RunRecord` (flat `metrics` dict + explicit
   `headline_metric` + reason strings where Phase 1 uses `NotApplicable`). Basis: F10, and
   the same direction rule Phase 1 sets — consumers serialize *into* the record shape;
   the registry never imports them and they never import it.

10. **RESOLVED (Ramsey, 2026-08-11) — One issue and one branch per repo, not per phase.**
    Phase 2 executes on the galactus branch shared with Phase 4 (`GAL-4-dry-run-coverage`),
    under a single galactus issue tracking both. Ramsey commits after runs; review happens
    after each phase completes. Note: a single branch across *all four* phases is not
    possible — Phases 1 and 3 change `ai-project-template` and Phases 2 and 4 change
    `galactus`, and a branch exists within one repo.

### Approach

Build `pocs/ml/fraud/` as a sibling of `pocs/ml/lending/`, reusing the lending run
script's *shape* (constants-as-recorded-decisions, `build_frame`, `summarise`,
`--summary-json`, aggregates-only) with fraud-specific content. Compose the AIT-67 toolkit
unchanged for everything it already does correctly — splitting, calibration, metrics,
model registry, the classification workflow — and add exactly one new concept: a
**sufficiency check** that runs *between* the workflow returning `RunResult` and the
report being written, deciding whether an operating point may be reported at all. The
run is executed twice: once with the guard bypassed (capturing the unguarded output as
evidence, per Open Question 7) and once with it active, and the WALKTHROUGH shows both.

**Key tradeoff:** the guard lives in the poc rather than the toolkit, so it is not yet
reusable by the next thin frame. That is deliberate — it makes Phase 2 executable today
against a branch-only #67, and it lets Phase 4b's automated run be the thing that argues
for promotion, rather than promoting on a sample of one.

### Out of Scope

- **Any modelling improvement.** No feature engineering, no tuning, no resampling
  experiments, no extra models. The frame has 14 positives; a better score would be
  suspicious, not welcome.
- **Fixing `infer_column_types` to auto-detect identifiers.** F9 is handled caller-side.
  A toolkit-level heuristic is a separate issue (filed, not implemented here).
- **Editing AIT-67's `reporting/html.py` or `workflows/classification.py`.** Deferred to
  follow-ups (Open Questions 4 and 8) so Phase 2 does not depend on #67 review.
- **Implementing or importing Phase 1's `runs/` registry** (F10).
- **The upstream 90k-row Klarna dataset.** Not on disk (Key Unknown 1).
- **Phases 3 and 4** of issue #4.
- **Any write to `lebanese-blonde`.** Read-only, absolute.
- **W&B / MLflow.**
- **Lowering `n_splits` to manufacture more positives per fold.** Explicitly rejected in
  Disconfirming Evidence — recorded as a non-option, not an unexplored one.

### Steps

Seven steps, one review boundary after Step 4 (guard complete and unit-tested before it
is wired into the run).

---

#### Step 1: Poc skeleton, frame copy, and the captured "before" run

**Files**: new `pocs/ml/fraud/data/dataset.csv` (copied, gitignored), new
`pocs/ml/fraud/README.md`, new `pocs/ml/fraud/docs/before-guard.json`,
edit `.gitignore` (after line 40)

**What**: Create the poc directory in the shape of `pocs/ml/lending/`. Copy the frame
**out of** lebanese-blonde with `cp` (never `mv`, never any write to the source), verify
the copy's sha256 matches `ef4c290e...342a` from F1. Add an explicit gitignore entry for
`pocs/ml/fraud/data/` rather than relying on the `*.csv` glob. Then run the *current*
unguarded toolkit against the frame exactly as F3 did and save the output as
`before-guard.json` — this is the evidence artifact (Open Question 7), captured before any
guard exists so it cannot be accused of being a strawman.

**Snippet**:
```
# .gitignore — after the ml-lending/data block
# Phase 2 poc frame: a copy of lebanese-blonde's sample. Real records; never committed.
pocs/ml/fraud/data/
```
```bash
cp "/Users/wiseer/workspace/lebanese-blonde/src/data/dataset.csv" \
   pocs/ml/fraud/data/dataset.csv
shasum -a 256 pocs/ml/fraud/data/dataset.csv   # must print ef4c290e...342a
```

**Test**:
```bash
cd /Users/wiseer/workspace/galactus && \
  shasum -a 256 pocs/ml/fraud/data/dataset.csv && \
  git check-ignore -v pocs/ml/fraud/data/dataset.csv && \
  git -C /Users/wiseer/workspace/lebanese-blonde status --porcelain
```

**Done when**: the copy's sha256 equals `ef4c290e21f37c4bb6aacd9462c1f024aec61b6bcf752b9f76090a6cf355342a`;
`git check-ignore` confirms the data path is ignored; `git status` in lebanese-blonde is
**empty** (proving read-only was honoured); and `before-guard.json` contains the three
models at PR-AUC ≈ 0.0200 / 0.0189 / 0.0175 with `precision: 0.0` and
`true_positives: 0`, and contains **no** warning or refusal field.

---

#### Step 2: Frame derivation — `build_frame` with recorded decisions

**Files**: new `pocs/ml/fraud/src/run.py` (module docstring + constants + `build_frame`,
~lines 1-140)

**What**: Port the lending run script's structure (`ml-lending/ml/run.py:1-229`). Module
docstring states WHAT THIS RUN IS / DATA HANDLING / RUNNING IT, and pins the AIT-67 SHA
`0f8b2cf` (F8, Assumption 4). Constants encode the recorded decisions: `TARGET = "default"`,
`IDENTIFIER_COLUMNS = ["uuid"]` with the F9 rationale in its comment, `SEED = 42`,
`COST_FP`/`COST_FN` marked STIPULATED (no cost matrix is discoverable for this frame), and
an `AGE_FAIRNESS_NOTE` string constant carrying the F7 note. `build_frame` loads with
`sep=";"`, drops identifiers, and logs aggregates only — never a row, index, or value.
**No unresolved-row filter** (F1: the target has zero missing).

**Snippet**:
```python
# after
#: Row identifiers. `uuid` is 800/800 distinct, so `infer_column_types` buckets it as
#: high-cardinality and TabularPreprocessor TARGET-ENCODES it — a per-row key encoded
#: against 14 positives, i.e. near-perfect memorisation. Same defect class the lending
#: poc routed around (ml-lending/ml/run.py:266-283). Dropped before inference.
IDENTIFIER_COLUMNS = ["uuid"]

#: RECORDED, NOT CORRECTED. The reference implementation uses `age` raw (18-74, median 46,
#: 36 missing) as a numeric feature — lebanese-blonde/src/features.py:28. Age is a
#: protected characteristic in most credit/fraud jurisdictions. Kept raw here to reproduce
#: the reference, and surfaced in the summary and report so it is a recorded decision
#: rather than a silent one. Precedent: ml-lending/ml/run.py:154 (zip_code).
AGE_FAIRNESS_NOTE = (
    "`age` is used raw as a numeric feature (18-74, median 46, 36 missing), reproducing "
    "the reference implementation. Age is a protected characteristic; this run records "
    "its use rather than endorsing it. Not derived, not binned, not dropped."
)
```

**Test**:
```bash
cd /Users/wiseer/workspace/galactus && ML_PACKAGE_ROOT=<ait-ml-parent> \
  uv run python -c "import sys; sys.path.insert(0,'pocs/ml/fraud/src'); \
  from run import build_frame; from pathlib import Path; \
  d=build_frame(Path('pocs/ml/fraud/data/dataset.csv')); \
  print(d.shape, 'uuid' in d.columns, int(d['default'].sum()))"
```

**Done when**: `build_frame` returns **800 × 42** (43 minus `uuid`), `'uuid' in df.columns`
is `False`, the positive count is **14**, and the logged output contains no row values.

---

#### Step 3: The sufficiency check — refusal as a first-class result

**Files**: new `pocs/ml/fraud/src/sufficiency.py`

**What**: A pure, dependency-light module holding the phase's one new concept. Define
`MIN_POSITIVES_PER_FOLD = 10` (Open Question 1) and a frozen `SufficiencyVerdict`
dataclass carrying `sufficient: bool`, `reason: str`, `min_positives_in_fold: int`,
`n_positives: int`, `prevalence: float`, `threshold_reportable: bool`. `assess_sufficiency(y,
split_plan, *, min_per_fold=...)` counts positives in every test fold and returns the
verdict. **Pure — no I/O, no fitting, no raising** (Open Question 3: a verdict, not an
exception). The docstring states the argument in the style of `splitting.py:14-19`: why a
warning is insufficient and why the threshold specifically is what gets withheld.

**Snippet**:
```python
# after
MIN_POSITIVES_PER_FOLD = 10
"""Below this many positives in the thinnest test fold, no operating point is reported.

A threshold is chosen by minimising expected cost over observed probabilities, and its
precision/recall are then read off the same rows. With 2-3 positives per fold that
arithmetic still returns a number to four decimal places — it is simply a number about
three events. Measured on this frame the toolkit returned threshold 0.0562, precision
0.000, recall 0.000, true_positives 0, and reported it with no warning at all. The
discrimination metrics survive (they are computed over every scored row); the operating
point does not.
"""

@dataclass(frozen=True)
class SufficiencyVerdict:
    sufficient: bool
    reason: str
    n_positives: int
    min_positives_in_fold: int
    prevalence: float

    @property
    def threshold_reportable(self) -> bool:
        return self.sufficient
```

**Test**: `uv run pytest pocs/ml/fraud/tests/test_sufficiency.py -v`

**Done when**: `assess_sufficiency` on the real frame's fold plan returns
`sufficient=False` with `min_positives_in_fold == 2` and a non-empty `reason`; on a
synthetic frame with 200 positives over 5 folds it returns `sufficient=True`; the function
never raises and never writes.

---

#### Step 4: Tests — the refusal is a success path with its own assertions

**Files**: new `pocs/ml/fraud/tests/test_sufficiency.py`, new
`pocs/ml/fraud/tests/conftest.py`

**What**: Unit tests treating refusal as the primary behaviour, not an error case.
Fixtures are **synthetic** (seeded generator in the spirit of
`lebanese-blonde/src/synthetic.py`, per the Asset verdicts salvage note) so no real row
enters a test file. Cases: (a) thin frame → `sufficient=False`, reason mentions the fold
count; (b) healthy frame → `sufficient=True`; (c) boundary at exactly
`MIN_POSITIVES_PER_FOLD` → sufficient (inclusive); (d) one fold thin and four healthy →
refuses on the **minimum**, not the mean — the case that catches an averaging bug; (e)
zero positives → refuses without a ZeroDivisionError; (f) refusal never raises.

**Snippet**:
```python
# after
def test_refuses_on_the_thinnest_fold_not_the_average(healthy_and_one_thin_plan):
    """Four folds at 40 positives and one at 2 averages to 32 — comfortably above the
    line, and completely wrong. The guard reads the minimum for exactly this reason."""
    verdict = assess_sufficiency(y, plan, min_per_fold=10)
    assert verdict.sufficient is False
    assert verdict.min_positives_in_fold == 2
```

**Test**: `uv run pytest pocs/ml/fraud/tests/ -v`

**Done when**: all six cases pass; no test file reads `pocs/ml/fraud/data/`; coverage of
`sufficiency.py` is 100% (it is a small pure module, so this is a reachable bar).

> **REVIEW BOUNDARY** — guard is complete, pure, and tested before any wiring.

---

#### Step 5: Wire the guard into the run and emit the summary

**Files**: `pocs/ml/fraud/src/run.py` (add `summarise` + `main`, ~lines 140-300)

**What**: `main` builds the frame, builds the split plan via `make_splitter(n_splits=5,
random_state=SEED)`, calls `assess_sufficiency` **before** `run_classification`, and passes
`cost_fp`/`cost_fn` **only when the verdict is sufficient** — so on a refusal the toolkit
is never asked to choose a threshold, and `ModelRun.threshold` is `None` by the module's own
contract (`classification.py:348-356`, "Without them no threshold is reported"). This is
the key composition insight: **the existing API already supports refusal; nothing needs
patching, the caller just has to decline to ask.** `result.assert_no_transform_outside_pipeline()`
is still called. `summarise` emits a flat `metrics` dict + `headline_metric: "average_precision"`
+ a `refusal` block + `prevalence_floor` + the `age` note, shaped for Phase 1 lift (F10,
Open Question 9).

**Snippet**:
```python
# after
verdict = assess_sufficiency(y, split_plan)
result = run_classification(
    frame, target=TARGET, output="binary", models=args.models,
    sampling="class_weight", splitter=split_plan, calibrate=True,
    # Costs are withheld on an insufficient frame. run_classification reports no
    # threshold without them — so the refusal is expressed by not asking the
    # question, rather than by discarding an answer after the fact.
    cost_fp=COST_FP if verdict.threshold_reportable else None,
    cost_fn=COST_FN if verdict.threshold_reportable else None,
    seed=SEED,
)
summary["refusal"] = {
    "operating_point_reported": verdict.threshold_reportable,
    "reason": verdict.reason,
    "min_positives_in_fold": verdict.min_positives_in_fold,
    "n_positives": verdict.n_positives,
}
summary["prevalence_floor"] = verdict.prevalence
summary["headline_metric"] = "average_precision"
summary["fairness_notes"] = [AGE_FAIRNESS_NOTE]
```

**Test**:
```bash
cd /Users/wiseer/workspace/galactus && ML_PACKAGE_ROOT=<ait-ml-parent> \
  uv run python pocs/ml/fraud/src/run.py \
  --summary-json pocs/ml/fraud/docs/summary.json --report pocs/ml/fraud/docs/report.html
```

**Done when**: the run exits 0; `summary.json` has `refusal.operating_point_reported ==
false` with a reason naming the 2-positive fold; **every** model entry has `threshold: null`
(vs `before-guard.json`, where all three carry a full threshold block);
`prevalence_floor == 0.0175`; `fairness_notes` is non-empty; and the JSON contains no row,
index, or `uuid` value.

---

#### Step 6: Report surface — the floor and the refusal are unmissable

**Files**: new `pocs/ml/fraud/src/report.py`

**What**: A poc-local wrapper (Open Question 8) that calls
`ml.reporting.html.write_report` and then injects two blocks that AIT-67's report cannot
produce (F6): a **refusal banner** at the top, using the existing `.verdict.null` style so
it reads as the report's loudest element; and a **floor annotation** on the model table —
each PR-AUC shown as a multiple of the 0.0175 prevalence floor, with the floor stated in
the run-facts block and the "PR-AUC" header relabelled to say what chance is. Aggregates
only, inherited from `html.py:5-10`. Also renders the `age` fairness note.

**Snippet**:
```python
# after
FLOOR_NOTE = (
    "PR-AUC's no-skill floor is the positive-class prevalence, here <strong>0.0175</strong> "
    "— not 0.5. A PR-AUC of 0.02 on this frame is 1.1x chance, not 'poor but working'. "
    "(For contrast, the lending poc's floor was 0.2056.)"
)
REFUSAL_BANNER = (
    "<div class='verdict null'><strong>No operating point is reported.</strong> "
    "The thinnest test fold holds {min_pos} positive cases ({n_pos} across the frame, "
    "{prevalence:.2%}). A cost-minimising threshold over that many events is arithmetic, "
    "not evidence. Discrimination metrics below are reported with their floor; "
    "precision, recall, and expected cost are withheld.</div>"
)
```

**Test**:
```bash
cd /Users/wiseer/workspace/galactus && \
  grep -c "No operating point is reported" pocs/ml/fraud/docs/report.html && \
  grep -c "0.0175" pocs/ml/fraud/docs/report.html && \
  grep -ci "uuid" pocs/ml/fraud/docs/report.html
```

**Done when**: the refusal banner appears **before** the model comparison table; the floor
0.0175 appears in both the run-facts block and the PR-AUC column header/annotation; the
operating-point section states withholding rather than showing an empty table; `grep -i
uuid` returns 0; and a reader shown only the report can answer "was a threshold reported,
and why not" without opening the JSON.

---

#### Step 7: WALKTHROUGH — the poc's evidence document

**Files**: new `pocs/ml/fraud/WALKTHROUGH.md`

**What**: Mirror `pocs/ml/lending/WALKTHROUGH.md`'s structure (The question / Result table
/ Walkthrough per stage / findings / Verdict) with the inverted headline. Must carry: the
measured frame properties vs the brief (F1 table); the **before/after pair** — the F3
unguarded table beside the guarded output, which is the phase's central exhibit; the
sigmoid-calibration finding (F5, including that sigmoid *worked*); the floor comparison
(0.0175 vs lending's 0.2056); the `age` fairness note; the `uuid` near-miss (F9) as a
recurrence of the lending toolkit gap; and a "Verdict" section stating that the run
declined and that declining was the correct outcome. Aggregates only.

**Snippet**:
```markdown
## Result

The run **declined to report an operating point**, and that is the pass condition.

| Stage | Status | Evidence |
|---|---|---|
| Data cleaning | Works | 800 x 43 -> 800 x 42; `uuid` dropped before inference |
| Model selection | Works | registry served logistic / random_forest / lightgbm |
| Training | Works | sigmoid calibration throughout — the branch lending never reached |
| Sufficiency | **Refused** | thinnest test fold: 2 positives; 14 across the frame |
```

**Test**: `ls -l pocs/ml/fraud/WALKTHROUGH.md && grep -c "0.0175" pocs/ml/fraud/WALKTHROUGH.md`

**Done when**: the document contains both the unguarded and guarded result tables; states
the 0.0175 floor and the lending 0.2056 contrast; contains the `age` note and the `uuid`
finding; contains no row, index, or identifier value; and its Verdict section answers issue
#4's done-condition — "the run either produces a defensible result *or* refuses with a
stated reason, and the report makes which one happened unmissable" — in one sentence.

---

### Test Plan

| Level | Command | Asserts |
|---|---|---|
| Unit | `uv run pytest pocs/ml/fraud/tests/ -v` | Six sufficiency cases (Step 4), incl. min-not-mean and the zero-positive edge |
| Integration | `uv run python pocs/ml/fraud/src/run.py --summary-json ...` | Run exits 0, refuses, every `threshold` is null (Step 5) |
| Regression (negative) | Compare `summary.json` against `docs/before-guard.json` | The before file has three full threshold blocks; the after file has none. **The diff is the phase's proof.** |
| Contract | `grep -i uuid` over report + summary; `grep` for row values | Aggregates-only holds |
| Read-only | `git -C ~/workspace/lebanese-blonde status --porcelain` | Empty at every step |
| Lint | `uv run ruff check pocs/ml/fraud/` | Clean |

**Sufficiency of the guard itself** is tested by the healthy-frame case: a guard that only
ever refuses is a constant, not a check — the same argument AIT-67 makes for
`BASELINE_TOLERANCE` (`classification.py:53-60`), whose test asserts both directions.

### Risks & Rollback

| Risk | Likelihood | Mitigation |
|---|---|---|
| **AIT-67 changes under review**, breaking imports | Medium | The run docstring pins `0f8b2cf` (F8). If #67 is reworked, re-pin and re-run — ~12s (F11), so a re-run is cheap. |
| **The guard is written in the poc and never promoted**, so the next thin frame repeats the failure | Medium | Explicit follow-up issue filed in Step 7's write-up; Phase 4b is designed to surface exactly this class of gap. Open Question 4 flags it for sign-off. |
| **Refusal-as-verdict (exit 0) is misread by automation** as a pass | Medium | Open Question 3 flags it. The JSON's `refusal.operating_point_reported: false` is machine-readable; a CI consumer checks that field, not the exit code. |
| `MIN_POSITIVES_PER_FOLD` **is bikeshed** and blocks the phase | Low | Any value ≥ 4 refuses this frame decisively (measured min = 2), so the phase's conclusion is robust to the exact constant. Say so at refine. |
| **Copying the frame leaks real records into git** | Low | Explicit `.gitignore` path (Step 1) *plus* the existing `*.csv` glob, verified with `git check-ignore`. |
| **A write reaches lebanese-blonde** | Low | `cp` only; `git status --porcelain` on the source repo is a done-when condition in Step 1 and a Test Plan row. |

**Rollback**: the whole phase is additive under `pocs/ml/fraud/` plus one `.gitignore`
line. `rm -rf pocs/ml/fraud/` and revert the gitignore hunk. No toolkit file is modified,
so nothing to unwind in `ai-project-template`.

## Review

`/proto-review`, 2026-08-15. **Retrospective** — the work shipped on 2026-08-11 across six
commits (`77e49c5..f520f7e`) and is already merged to `main`. This is the review that should
have run before the first of those commits and did not.

### 1. Overall understanding

The phase's pass condition is a refusal, and the refusal is real. On a frame of 800 × 43 with
14 positives (1.75% prevalence, min 2 positives in the thinnest fold), the run declines to
report an operating point and says why. The before/after artifacts
(`docs/before-guard.json` → three full threshold blocks; `docs/summary.json` → none) are the
proof, and they hold up.

### 2. Review contract

| Field | Value |
|---|---|
| Diff | `77e49c5^..f520f7e` — 13 files, +1093/−0, entirely additive |
| Profile | general; `is_ml_code=true`, `is_agent_code=false`, no `SANYI.md` |
| Dimensions active | 8 of 11, per `review.cli detect-signals` |
| Lint | `ruff check pocs/ml/fraud/` — clean |
| Tests | `pytest pocs/ml/fraud/tests -q` — 6 passed |

### 3. Plan fidelity

All eight steps match. The `## Result` table is accurate against the artifacts on disk: the
guard refuses, sigmoid calibration ran (the branch lending never reached), `uuid` is dropped
before inference, and `assert_no_transform_outside_pipeline()` is asserted rather than
trusted. No stubs, no `NotImplementedError`, no TODO on a critical path.

### 4. What looks strong

- **The refusal is structural, not cosmetic.** `run.py:273-274` withholds `cost_fp`/`cost_fn`
  when the frame is insufficient, so `run_classification` has nothing to optimise a threshold
  against. The refusal is expressed by not asking the question rather than by discarding an
  answer after the fact — which means there is no code path that computes a threshold and
  then suppresses it.
- **Min, not mean.** `sufficiency.py:92` uses `min(fold_counts)`, and
  `test_refuses_on_the_thinnest_fold_not_the_average` builds a frame with four healthy folds
  and one thin one specifically so a mean-based implementation would fail.
- **The guard is a check, not a constant** — the healthy-frame case asserts it passes.
- **Leakage clean.** Nothing is fitted outside the CV pipeline; calibration is in-fold;
  rebalancing is `class_weight` rather than pre-split resampling.
- **Aggregates-only holds.** No row, index, identifier, or `uuid` value survives into any
  committed artifact.

### 5. Blocking findings

None.

### 6. Important findings

**TE-001 — `report.py` has zero unit test coverage** (`src/report.py:38-128`).
**RESOLVED 2026-08-15.** The five functions that inject the refusal banner, the
prevalence-floor note, and the fairness notes into the HTML were untested. They work by
string/regex injection against anchors like `<h2>Model comparison</h2>`; if an anchor
moves, the injection silently no-ops and the reader gets an unannotated report. This is
the surface the whole phase's "unmissable" claim rests on.

Writing the tests escalated the finding from *untested* to *a live defect*. Pinning the
anchors against a genuine `write_report` document (`pocs/ml/lending/docs/report.html` —
the only committed toolkit output in the repo) showed **three of the five injections had
never matched anything**:

| Injection | Against real markup |
|---|---|
| refusal banner | rendered |
| PR-AUC column header floor | rendered |
| floor fact row (`<dl class="meta">`) | **silent no-op** |
| floor note paragraph | **silent no-op** |
| fairness notes section | **silent no-op** |

No exception was raised in any of the three cases. Step 7's done-condition — the 0.2056
lending contrast and the `age` fairness note being *on the page* — was verified against
`WALKTHROUGH.md` by grep, not against the HTML, so the gap survived the phase.

Fixed in three parts: the three anchors corrected against real markup; `_replace_once` /
`_sub_once` added so a non-matching anchor raises `ReportAnchorError` instead of returning
the document unchanged; and `tests/test_report.py` (17 tests) pinning every anchor against
`upstream_report`, including a parametrised drift case per anchor. Inventing the fixture
HTML would have reproduced the original defect — a fixture that agrees with the
implementation cannot catch an implementation that disagrees with reality.

**TE-002 — orchestration in `run.py` is not regression-protected** (`src/run.py:229-291`).
**RESOLVED 2026-08-15.** `main()` and `summarise()` carry the `threshold_reportable`
gating and the JSON contract. The Test Plan covered them only as manual shell commands, so
a regression in the gate would not have failed any test run.

`tests/test_summary.py::TestSummariseFunction` now calls `summarise()` directly with
`SimpleNamespace` fakes, asserting both directions — a refusal nulls every threshold, and
a sufficient verdict reports every threshold. The second is the load-bearing one: without
it, `summarise` could null thresholds unconditionally and every refusal test would still
pass. These are gated behind `@requires_toolkit` and **skip in this checkout**, because
`run.py` imports the ML toolkit at module scope and `ml/` holds no source here (the
`ML_PACKAGE_ROOT` gap Phase 4b keeps as its live specimen). The skip reason says so.

### 7. Questions and hypotheses

Both important findings shared one root: the tested unit was the *decision*
(`sufficiency.py`, 6 cases, well covered) while the untested units were the *expression*
of that decision (`report.py`) and its *wiring* (`run.py`). The answer turned out not to
be a judgement call — the untested expression was already broken, in the direction the
poc exists to refuse: an artefact that looks complete with the caveat quietly missing.

### 8. Suggestions and nits

**TE-003 (suggestion)** — the regression proof is a manual diff. **RESOLVED 2026-08-15.**
`docs/before-guard.json` was a captured artifact, not an assertion; nothing in code
checked that every `threshold` in `summary.json` is null.
`tests/test_summary.py::TestCommittedArtifacts` (11 tests, no toolkit needed) now asserts
it, along with the negative control — that the *unguarded* run did report three threshold
dicts, and that those suppressed thresholds described zero true positives. Without the
control, the guarded run's silence could mean the toolkit never reports thresholds at all,
and the guard would be unfalsifiable.

**SF-001 (nit)** — `--summary-json` is written without path validation (`run.py:287-288`).
Reported by the safety dimension as `important` for path traversal; **downgraded to nit by
the orchestrator**, with reason: the only actor who can supply that argument is the operator
invoking the script, who already has shell write access to the same paths. No privilege
boundary is crossed. It would become real if this path were ever exposed through an API or a
CI parameter.

### 9. Testing and evaluation assessment

**Reassessed 2026-08-15 after TE-001/002/003 were fixed.** 35 passing, 3 skipped.

`sufficiency.py` remains well covered — six cases including min-not-mean and the
zero-positive edge, both directions asserted. `report.py` now has 17 tests pinned against
a real toolkit document, `test_summary.py` adds 11 unconditional assertions over the two
committed artefacts plus 3 toolkit-gated ones over `summarise()` itself.

The regression and contract Test Plan levels are now automated: "the diff is the phase's
proof" is an assertion rather than an instruction, and the two committed JSONs are checked
for identifiers and row data on every run. Integration and read-only remain documented
shell commands — they cannot be automated in this checkout, because the toolkit has no
source here.

The one branch no committed artefact exercises — a frame the guard *passes*, where
thresholds must appear — is covered only by the skipped tests. That is honest rather than
green: the assertion exists and will run wherever `ML_PACKAGE_ROOT` is set.

### 10. Definition of done

| Item | Status | Note |
|---|---|---|
| Tests | met | 35 passed, 3 skipped. Guard, `report.py`, and the summary contract all covered (TE-001/002/003 resolved 2026-08-15); the 3 skips are toolkit-gated and say so |
| Lint | met | `ruff check` clean |
| Docs | met | README + WALKTHROUGH match the artifacts; numbers reconcile with `summary.json` |
| Config | met | `MIN_POSITIVES_PER_FOLD` is a named module constant, and the plan argues the conclusion is robust to its exact value |
| Errors | met | No swallowed exception; the guard's own failure paths raise rather than fall through to a number |
| Reversibility | met | Additive under `pocs/ml/fraud/` plus one `.gitignore` line |
| Plan steps accounted for | met | All eight |
| Acceptance criteria (issue #4) | met | "Defensible result *or* refusal with a stated reason, unmissable in the report" — refusal, stated, unmissable |

### 11. Dimension dispatch

| Dimension | Status | Findings |
|---|---|---|
| intent | completed | 0 |
| correctness | completed | 0 |
| silent_failure | completed | 0 |
| testing | completed | 3 (all resolved 2026-08-15) |
| safety | completed | 1 |
| architecture | completed | 0 |
| performance | completed | 0 |
| leakage | completed | 0 |
| runtime | skipped | no agent-framework import or agent path in the changed files |
| safeguards | skipped | no agent-framework import or agent path in the changed files |
| contracts | skipped | no `SANYI.md` in the repo |
| plan-fidelity | ran | 0 |
| lint/tests | ran | pass |

No corrective round. No injection hits. No validation failures.

### 12. Merge verdict

**comment at first pass; recomputed to approve 2026-08-15** after TE-001, TE-002, and
TE-003 were fixed on `GAL-4-phase2-closeout`. Both verdicts came from
`review.verdict.compute_verdict`, not from a judgement here — the ladder's rung 3 fires on
any `important` finding, and with the two testing gaps closed the remaining set is one
`nit` (SF-001), which falls through to rung 4.

The first pass claimed the code was sound and only the tests were missing. Writing the
tests showed that was wrong about `report.py`: three of five injections had never matched
the toolkit's markup, so the phase's "unmissable" surface was, in three of five places,
missing. The `comment` verdict was correct for a reason the review did not state.

<!-- 2026-08-15: the state line is advanced in a separate pass from this section, using
     GALACTUS_BACKFILL=1. The doc sat at REFINED while the work was already merged, so the
     four edges to COMPLETE are reconciliation, not traversal — all four land in the same
     minute for work done 2026-08-11, and that ledger is the sole input to the loop-back
     rate D10 turns on. The marker is what lets the doc be honest and the measurement stay
     honest at the same time; review/transitions.py excludes marked edges from every count
     and reports them under `backfill`. -->

### Follow-up

The architecture dimension returned clean but confirmed the plan's own Open Question 4: the
guard lives in `pocs/ml/fraud/src/sufficiency.py` while the defect it fixes is toolkit-level,
and `pocs/ml/lending` still runs the same toolkit unguarded. Promotion is out of scope for
this phase by design and needs its own issue.
