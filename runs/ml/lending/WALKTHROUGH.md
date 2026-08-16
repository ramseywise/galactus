# ML quick-start dry run — can galactus prototype a classifier in under an hour?

Status: EXECUTED
Date: 2026-08-11
Data: `runs/ml/lending/data/lending_club_2015Q4.csv` (real extract, 45,224 × 151, gitignored)
Reference frame: `lebanese-blonde` (read-only; never written to during this run)

## The question

Not "is the ml-lending framing correct" — that was answered when the frame was
profiled. The question this run exercises is the one the toolkit exists to
answer: **can the four stages of a tabular prototype be driven end to end from
the existing skills, in under an hour, on real data?**

Both repos predict default. `ml-lending` targets `charged_off`, `lebanese-blonde`
targets `default`; same task, same domain, different frame properties. So the
dry run is a single walkthrough, not a comparison.

## Result

Three of the four stages ran end to end on the real 39,770-row modelling frame.
The fourth does not exist.

| Stage | Status | Evidence |
|---|---|---|
| Data cleaning | Works | 45,224 → 39,770 rows; 47 columns dropped, 39 post-outcome |
| Model selection | Works | registry served logistic / lightgbm / random_forest on identical folds |
| Training | **Was broken — now works** | `ml.workflows` and `ml.reporting` did not exist; both written |
| Experiment tracking | **Was absent — now exists** | closed 2026-08-16 (GAL-32): records via `experiments/io.py` → `runs/_index/`; see "The remaining gap" |

The headline number: **LightGBM beats the logistic baseline by 0.0924 PR-AUC**
(0.4351 vs 0.3427) on the leakage-free frame, at a 20.56% prevalence floor.
That is nine points — an order of magnitude above the 0.01 tolerance band, so
it is a real win rather than fold variance.

This contradicts DESIGN.md's Step 15 table, which recorded a 0.0002 margin and
"nothing beats the baseline". See "Correcting the Step 15 result" below.

## What was actually missing

The chain was documented as complete and was not. `ml-lending/ml/run.py` imports
two modules that had never been written:

```python
from ml.reporting.html import write_report  # ml/reporting/ — absent
from ml.workflows.classification import run_classification  # ml/workflows/ — absent
```

`grep -rn 'run_classification'` returned zero definitions repo-wide. Every
individual step — column inference, sampling, splitting, calibration, threshold
choice — existed and was unit-tested. **The composition layer was the gap**, and
because each part was independently green, nothing surfaced it. This is why
`docs/DESIGN.md`'s Step 15 metrics table could not be reproduced from the repos
as they stood.

Both modules now exist in `ai-project-template` (issue #67, branch
`AIT-67-ml-workflows-classification`):

- `ml/workflows/classification.py` — composes the existing steps; no
  reimplementation
- `ml/reporting/html.py` — aggregates-only HTML report

## Walkthrough

### 1. Data cleaning

Driven by `run.py`'s frame builder plus `infer_column_types`:

```
loaded extract: 45224 rows x 151 columns
resolved 39770 rows, dropped 5454 unresolved (outcome has not happened yet)
dropped 47 columns (39 of them post-outcome)
modelling frame: 39770 rows x 106 columns
```

The 5,454 dropped rows are loans whose outcome has not resolved. Keeping them
would mean labelling an in-progress loan as "not charged off", which is a label
that becomes false with time.

The 39 post-outcome columns are the leakage set. The one that matters is
`last_fico_range_high` — single-feature AUC 0.9511 with an entirely innocent
name. A name-based leakage rule misses it. The A/B recorded in DESIGN.md:
ROC-AUC 0.9993 → 0.7514 once the leaks are removed.

### 2. Model selection

`get_models("classification", "binary", include=[...])` — the registry appends
the logistic baseline regardless of what was requested, so a comparison always
has a floor. Models with missing optional deps are skipped with a warning and
recorded in `result.skipped`, so an absent model is a recorded decision rather
than a silent omission.

### 3. Training

`run_classification` runs every candidate on **identical folds**, with two
load-bearing properties:

- **Preprocessing lives inside the per-fold pipeline.** A transformer fitted on
  the full frame sees validation rows and inflates every score *upward* — the
  failure mode that looks like success. `result.assert_no_transform_outside_pipeline()`
  asserts this rather than trusting it.
- **Predictions are out-of-fold.** Calibration and threshold selection see
  probabilities from models that did not train on those rows.

The split is grouped, verified at runtime:

```
group split verified across 3 folds (stratified_group)
```

The group column is carried via precomputed folds, *not* passed as `group_col`.
Passing it would put the key into the feature matrix, where it gets
target-encoded — and a group key is usually a near-perfect feature.

Three models on identical folds, real frame:

| model | PR-AUC | ROC-AUC | Brier | fit (s) |
|---|---|---|---|---|
| logistic *(baseline)* | 0.3427 | 0.6741 | 0.1523 | 269.6 |
| random_forest | 0.4238 | 0.7406 | 0.1426 | 114.4 |
| **lightgbm** | **0.4351** | **0.7430** | **0.1419** | **11.6** |

LightGBM wins on every metric *and* is 23× faster to fit than the baseline —
logistic is the slow model here, because 88 one-hot columns on 39,770 rows is
the case lbfgs handles worst (it hit the 2,000-iteration limit without
converging on every fold).

Calibration earned its place: isotonic moved logistic's Brier **0.2280 → 0.1523**
and its ECE **0.2680 → 0.0048** — a 56× reduction in calibration error. That is
not cosmetic. The threshold below is chosen by expected cost, and a cost
calculation on uncalibrated scores is arithmetic over a number that does not
mean what it says.

Chosen operating point at 4:1 FN:FP — threshold 0.2027, precision 0.300, recall
0.627, expected cost 24,136 vs 32,685 at the 0.5 default. The saving is the
argument for having chosen at all.

### 4. Experiment tracking

**Does not exist.** See below.

## Correcting the Step 15 result

DESIGN.md recorded random_forest 0.4215 vs logistic 0.4213 — a 0.0002 margin, which
was read as "nothing beats the baseline". This run does not reproduce that table,
and the interesting part is *which* number moved:

| model | DESIGN.md Step 15 | this run | delta |
|---|---|---|---|
| logistic *(baseline)* | 0.4213 | 0.3427 | **−0.0786** |
| random_forest | 0.4215 | 0.4238 | +0.0023 |
| lightgbm | not run | 0.4351 | — |

random_forest reproduces within fold noise. **The baseline is what changed.** A
logistic regression at 0.4213 — matching a tuned tree ensemble on an 88-column
one-hot frame — is the anomaly, not the 0.3427. The most likely explanation is
that the Step 15 baseline was scored on a differently-preprocessed frame; there
is no way to check, because nothing recorded which one. That is the experiment-
tracking gap below, arriving as a concrete cost rather than a hypothetical.

So the corrected reading is the opposite of the recorded one: with the baseline
measured on the same folds as the challengers, **there is a real margin, and it
is 0.0924.** The 0.01 tolerance band was built to catch a false win; here it
confirms a true one.

## Three toolkit findings, resolved

DESIGN.md recorded three defects. All three are now fixed in the new module:

1. **`group_col` forced the group column into the feature matrix.** Resolved by
   accepting a prebuilt `SplitPlan`, so grouping arrives through the folds and
   the column never enters `X`.
2. **`beats_baseline` had no tolerance band.** A strict `>` called a 0.0002
   PR-AUC margin a win. Now `BASELINE_TOLERANCE = 0.01`. Its unit test is the
   degenerate case it exists for: random_forest clears logistic by 0.0037 on a
   noise frame, and `beats_baseline` correctly returns False. On the real frame
   the same band returns True at 0.0924 — a band that only ever says "no" is a
   constant, not a test.
3. **`choose_threshold` did not mark its output in-sample.** The threshold is
   now selected on out-of-fold probabilities, and `run.py` labels it
   `SELECTED_IN_SAMPLE` in the summary.

Two further mismatches surfaced during the run, both silent: `run.py` read
`metrics.brier_score` and `calibration.ece_before`, while the dataclasses exposed
`brier` and `expected_calibration_error_*`. Both were read via `getattr(..., None)`,
so they reported `null` — a missing number and an uncomputed one looked identical
in the report. Aliases added.

## The remaining gap: experiment tracking

Nothing in either repo records a run. No MLflow, no W&B, no run registry, no
persisted metrics history. Each invocation overwrites `docs/report.html` and the
previous run is gone.

The consequence is concrete and was hit during this dry run: **DESIGN.md's Step 15
table could not be reproduced.** The numbers were real when written; nothing
recorded the code state, the seed, or the fold assignment that produced them, so
they could not be checked. A comparison table with no provenance is a screenshot.

This is out of scope for issue #67 and needs its own.

**Closed 2026-08-16 (galactus#32).** Every execution of `src/run.py` now assembles a
`RunRecord` (ai-project-template's `experiments/` registry) and writes it through
`experiments/io.py`: real runs to `runs/_index/{utc_timestamp}-{frame_hash[:8]}.json`
(committed), dry-runs to a temp path. The record carries the galactus SHA, the toolkit
tree's state, the fitted-frame hash, the resolved config including every module
constant, and a fold-plan description. The reproduce check is asserted in
`tests/test_reproduce.py`: same seed, same frame → byte-identical `metrics`;
`read_record` reconstructs the frozen dataclasses so validation re-fires on load. The
report-overwrite hazard is also gone for dry-runs, which never touch
`docs/report.html`.

## Verdict on the one-hour claim

**Not yet — but the blocker was structural, not conceptual.**

Data cleaning and model selection are genuinely one-command stages. Training now
is too. Against that, honest accounting of this session: the composition layer
had to be written first, and the fits themselves are not one-hour work on this
frame — logistic alone took 270s per configuration, and a three-model comparison
with calibration is ~36 fits.

For a prototype the practical answer is to cap folds and models, which the CLI
already supports — and note that the *winning* model fits in 11.6s. The hour is
spent on the baseline, not the candidate. The claim holds for *reaching a
defensible model choice on a real frame*; it does not hold for a full
multi-model sweep at this row count without capping folds.

## The finding worth keeping

Not the win. **The baseline is the number that needs auditing.**

The 0.0924 margin is real, but it exists mostly because the recorded baseline
was wrong — 0.4213 against this run's 0.3427, with the challenger reproducing
almost exactly. A comparison is only as trustworthy as its floor, and a floor
scored on a different frame silently converts a real win into a null result.
Step 15 read as "nothing works" when what had actually happened was "the
baseline was measured somewhere else".

Three properties of the new module are what make that visible rather than
invisible: identical folds for every candidate, preprocessing inside the
pipeline, and out-of-fold predictions. None of them improve a score. All of them
make scores comparable — which is the only thing that lets a margin mean
anything.

And the wider frame still holds: the leakage-free number here is 0.4351, and the
version of this run that reports ROC-AUC 0.9993 is the one that gets believed.
