# WALKTHROUGH — ml/fraud: a refusal, not a metric

## The question

Issue #4's done-condition: run the existing ML toolkit against a real, thin, imbalanced
frame, and make sure the run either produces a defensible result *or* refuses with a
stated reason — with the report making which one happened unmissable.

Concretely: `lebanese-blonde`'s fraud sample is 800 rows with 14 positives (1.75%
prevalence). At 5-fold stratified cross-validation that's 2–3 positives per test fold.
Does the toolkit (`ai-project-template`, `AIT-67-ml-workflows-classification`, pinned
`0f8b2cf`) know it doesn't have enough evidence to choose an operating point — or does it
just answer anyway?

## Result

The run **declined to report an operating point**, and that is the pass condition.

| Stage | Status | Evidence |
|---|---|---|
| Data cleaning | Works | 800 x 43 -> 800 x 42; `uuid` dropped before inference |
| Model selection | Works | registry served logistic / random_forest / lightgbm; catboost skipped (recorded, not silent) |
| Training | Works | sigmoid calibration throughout — Brier and ECE improved on every model |
| Sufficiency | **Refused** | thinnest test fold: 2 positives; 14 across the frame; floor is 10 |

## Walkthrough

### 1. The frame, measured against the brief

| property | value |
|---|---|
| rows | 800 |
| columns | 43 (42 after dropping `uuid`) |
| target | `default` |
| positives | 14 (1.75% prevalence) |
| `uuid` | 800/800 distinct values — dropped as a feature, not target-encoded |
| `age` | raw, 18–74, median 46, 36 missing — kept raw, recorded as a fairness note |
| stratified 5-fold | 2–3 positives per test fold (measured, not assumed) |

This is a frame where the arithmetic works and the evidence doesn't. Every model can be
fit, every fold can be scored, and the resulting numbers are still not a basis for a
decision — that gap is what the rest of this walkthrough is about.

### 2. The unguarded run — before-guard.json

Before any guard existed, the toolkit was run against this frame exactly as shipped:

| model | PR-AUC | threshold | precision | recall | true_positives |
|---|---|---|---|---|---|
| logistic | 0.0200 | 0.0562 | 0.000 | 0.000 | 0 |
| random_forest | 0.0189 | 0.0619 | 0.000 | 0.000 | 0 |
| lightgbm | 0.0175 | 0.0735 | 0.000 | 0.000 | 0 |

No warning. No refusal field. A `savings_vs_default` figure, printed to four decimal
places, computed over a threshold that flags one row and catches nothing. This is
[`docs/before-guard.json`](docs/before-guard.json), captured before the guard existed, so
the "before" state can't be accused of being a strawman built to make the "after" look
better.

### 3. The guarded run — the central exhibit

Same frame, same models, same seed. The only change: `assess_sufficiency` runs before
`run_classification`, counts positives in the thinnest test fold (2, against a floor of
10), and the run passes `cost_fp=None, cost_fn=None` instead of stipulated costs when the
verdict says the fold can't support a threshold.

| model | PR-AUC | ROC-AUC | Brier | threshold |
|---|---|---|---|---|
| logistic | 0.0200 | 0.4911 | 0.0172 | `null` |
| random_forest | 0.0189 | 0.5398 | 0.0172 | `null` |
| lightgbm | 0.0175 | 0.4356 | 0.0172 | `null` |

The discrimination metrics (PR-AUC, ROC-AUC, Brier) are **byte-identical** to the
unguarded run — they're computed over every scored row regardless of fold thinness, so
withholding the threshold doesn't cost the run anything it could otherwise report
honestly. What's gone is the threshold block: no `value`, no `precision`, no `recall`, no
`true_positives`, no `savings_vs_default`. In its place, `summary.json` carries:

```json
"refusal": {
  "operating_point_reported": false,
  "reason": "the thinnest test fold holds only 2 positive case(s), below the
    10-positive floor (14 positives across the frame, 1.75% prevalence). A
    threshold chosen and scored over that few events is arithmetic, not
    evidence — no operating point is reported.",
  "min_positives_in_fold": 2,
  "n_positives": 14
}
```

Exit code: `0`. This is the composition insight the guard turned on: `run_classification`
already reports no threshold when `cost_fp`/`cost_fn` are `None` — nothing about the
toolkit needed to change. The guard's entire job is deciding whether to ask the question.

The generated `docs/report.html` (gitignored — it embeds distributional detail derived
from real records, so it isn't committed, but it's regenerable by re-running `src/run.py`)
carries the same verdict in the reader-facing surface: a refusal banner in the toolkit's
own `.verdict.null` style appears immediately before the model comparison table — before
any metric a reader might otherwise mistake for a green light.

### 4. Calibration worked here — a branch lending never reached

Sigmoid calibration ran on all three models and **improved** Brier and ECE in every case
(e.g. logistic: Brier 0.0673 → 0.0172, ECE 0.0819 → 0.0013). `ml-lending`'s poc never
exercised this path — this is the first real-data run in this repo where calibration had
a chance to help, and it did. Worth stating plainly because the poc's headline is a
refusal: calibration succeeding is a second, independent finding riding along in the same
run, not the same failure mode as the threshold refusal.

### 5. The floor: 0.0175 vs lending's 0.2056

PR-AUC's no-skill baseline is the positive-class prevalence, not 0.5. On this frame that
floor is **0.0175** — nearly twelve times lower than `ml-lending`'s 0.2056. A PR-AUC of
0.0200 here is 1.1x chance; the same number on the lending frame would be roughly 0.1x
chance and obviously bad. The same metric means something different depending on how
imbalanced the frame is, and a report that prints "PR-AUC: 0.0200" with no floor stated
lets a reader import the wrong intuition. The guarded report states the floor in the
run-facts block and relabels the PR-AUC column header itself (`PR-AUC (floor 0.0175)`) so
the number can't be read in isolation.

### 6. The `age` fairness note

`age` is used raw as a numeric feature (18–74, median 46, 36 missing), reproducing the
reference implementation rather than deriving or binning it. `age` is a protected
characteristic. This run records its use rather than endorsing it — the note travels into
both `summary.json`'s `fairness_notes` and the report's own "Fairness notes" section,
following the precedent already set for `zip_code` in the lending run script.

### 7. The `uuid` near-miss — a toolkit-gap recurrence

`uuid` has 800/800 distinct values on an 800-row frame — every row has its own value.
Feeding that into any encoder that looks at the target (target/mean encoding, in
particular) would leak: with only 14 positives, a per-row identifier would let the
encoding memorize which specific rows are positive. `uuid` is dropped before the frame
ever reaches the toolkit (`IDENTIFIER_COLUMNS`), the same treatment `ml-lending` gives
`zip_code`-shaped high-cardinality identifiers. This is a recurrence of the same toolkit
gap found in the lending poc: the toolkit itself has no automatic identifier-column
detection, so this guard lives in the poc's run script, not upstream.

## Verdict

The run declined to report an operating point, and the report makes that unmissable
without opening the JSON — the guard did not change what the toolkit can compute, only
whether it was asked to.
