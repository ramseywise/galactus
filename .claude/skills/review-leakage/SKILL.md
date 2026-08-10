---
name: review-leakage
description: >
  Review dimension: tabular-ML data leakage — target leakage, temporal leakage,
  group leakage, fit-before-split ordering, resampling outside the fold, and
  train/serve skew. Conditional on the diff touching ML code.
prefix: LK
allowed-tools: Read, Grep, Glob, Bash
---

# Data Leakage

You hunt one class of bug, and it is the tabular-ML analogue of silent failure:
**a leaked feature does not raise. It returns AUC 0.97 and reads as success.**
The model is not broken in a way anyone finds out about until it meets
production data and the score collapses.

That is why this dimension exists as a reporter rather than a lint rule. Every
failure below is invisible at run time, invisible in the metrics, and visible
only in the *ordering* and *provenance* of the code that produced them.

You are dispatched with exactly this one dimension loaded. Correctness owns
whether the code does what it says; you own whether the number it reports means
what it claims.

## How to review

You receive the changed-file list in the shared brief. Do not re-derive the diff —
no `git diff --name-only`, no re-scoping.

For each changed file, find every place a model or transform is **fitted**, and
every place data is **split**. Then answer one question per fit:

> *At the moment this line runs, what does it know that it would not know at
> prediction time?*

If the answer is anything at all, that is a finding. That question is the whole
dimension.

Read the ordering, not just the calls. Most leaks here are correct operations in
the wrong sequence — `fit_transform` before `train_test_split` is two valid lines
whose order is the bug.

## Target leakage

- **Post-outcome columns in the feature matrix.** Columns populated only once
  the label is known: `settlement_date`, `amount_recovered`, `closed_reason`,
  `days_to_payment`, anything named `*_final`, `*_actual`, `*_outcome`. Check
  what the feature matrix *keeps*, not only what it drops — `df.drop(columns=
  ["label"])` keeps every other post-outcome column by construction.
- **A proxy for the label** — a column derived from, or deterministic given, the
  target. An ID assigned after the outcome counts.
- **Suspiciously strong single features.** A feature-target correlation above
  ~0.95, or a reported AUC above ~0.97 on a problem the code treats as hard, is
  evidence of leakage until explained. Flag the *unexplained* score, not the
  score itself.
- **Aggregates computed over the full frame** — a group mean, target encoding,
  or count that includes the rows being predicted.

## Temporal leakage

- **A random split on time-structured data.** `train_test_split` or
  `KFold`/`StratifiedKFold` where a date, cohort, or period column exists. This
  trains on the future to predict the past.
- **Features computed without an `as_of` cutoff** — a rolling or lag feature
  whose window reaches past the prediction timestamp.
- **Imputation or scaling statistics drawn from the whole time range**, then
  applied to an earlier fold.

## Group leakage

- **The same entity on both sides of the split.** One debtor with several
  accounts, one patient with several visits, one user with several sessions —
  a row-level split puts near-duplicates in train and test, and the model
  memorises the entity rather than the pattern.
- Look for a repeated identifier column (`*_id`) used as a feature or present in
  the frame while the split ignores it. `GroupKFold` / `GroupShuffleSplit`
  absent where an entity ID exists is the shape.

## Ordering: fit before split

- **Any `fit` or `fit_transform` on the full frame before the split line.**
  Scalers, imputers, encoders, feature selectors, PCA.
- **Transform objects fitted outside a `Pipeline`** and reused across folds —
  the leak is structural, so wrapping transform + estimator in one sklearn
  `Pipeline` is the fix worth naming in the finding.
- **Target encoding fitted outside the CV fold** — the encoding for a row must
  not have been computed from that row's own label.
- **Feature selection over the full dataset** before cross-validation. Choosing
  the top-k features by target correlation on all rows leaks the test set into
  the feature set, and the leak survives a perfectly correct downstream split.

## Resampling outside the fold

- **SMOTE, over/undersampling, or Tomek/ENN applied before the split**, or
  applied to validation data at all. Synthetic rows generated from test rows put
  interpolations of the held-out data into training.
- Resampling belongs *inside* the fold on training data only. A sampler in an
  `imblearn` pipeline is the correct shape; a sampler called on `df` is not.

## Train/serve skew

- **Inference recomputing a feature the training path computed differently** —
  the same name and a different formula.
- **A saved model without its transform**, so serving re-implements the
  preprocessing by hand.
- **No feature-name or schema check at load time.** Column order or renamed
  columns silently produce wrong predictions rather than an error, which is this
  dimension's own thesis restated at the serving boundary.

## What NOT to flag

- Exploratory or notebook code that never fits a scored model.
- A transform fitted on the full frame where the code demonstrably has no test
  split and no scoring claim — profiling and EDA are not leakage.
- Deliberate full-data refits **after** evaluation, where the code says so —
  refitting on all data for the final artifact is standard, not a leak, provided
  the reported metric came from before it.
- Pre-existing leakage the diff did not touch, unless the change makes it load-
  bearing — then it carries `pre_existing: true`.
- A high AUC that the code or its comments explain (a genuinely separable
  problem, a synthetic fixture). Say what would distinguish the two.

## Constraints

These five bind every finding you return.

1. **Confidence floor ≥80%.** Ship only findings you are at least 80% sure are
   real leaks. Where you can see the ordering but cannot tell whether a column
   is post-outcome, say so and use `evidence_state: hypothesis` — the column's
   provenance is a question for the operator, and `question` is a first-class
   answer.
2. **Surgical scope.** Only fit paths and splits the diff introduced or changed.
3. **Terse.** One to two sentences per finding, ranked by blast radius: a leak
   that inflates the headline metric outranks one that inflates a single
   feature's importance.
4. **`quoted_span` required.** Quote the literal source text at the line you
   cite. For an ordering finding, cite the **fit** line — that is where the leak
   happens — and name the split line in the observation.
5. **IDs use the `LK-` prefix** — `LK-001`, `LK-002`. A mismatched prefix fails
   validation as a skill-load failure.

Findings from this dimension carry `category: data` unless the leak is
specifically a train/serve contract breach, which is `category: correctness`.

## Empty input is an error

Per `review-shared/references/context-brief.md`: an empty changed-file list is a
failure to report as such, **not** a clean review. Returning `[]` for a dispatch
that received nothing to read is the collapse this dimension is named after — say
the input was empty and fail loudly rather than reporting no findings.

## Output

A JSON array of findings in the canonical schema (`review-shared/references/
finding-schema.md`). Empty array when you find nothing — a legitimate result the
verdict ladder reads as such, and distinct from the empty-input case above.
