# ml-parity — LTV notebook angle
Date: 2026-08-15
Work item: [`../plans/2026-08-15-lending-parity.md`](../plans/2026-08-15-lending-parity.md) (synthesis in its Research addendum)
Bar: the five parity elements from `runs/ml/lending/docs/DESIGN-parity.md`

## 0. Provenance / repo integration

- **Tracked with outputs** (`git ls-files runs/ml/` → `runs/ml/LTV.ipynb`); working tree
  clean, so everything below is committed content.
- History: two commits only — `d46b61b rename runs` and `543e41f` (bulk import). No
  development history in this repo.
- Referenced nowhere: no `pyproject.toml`, `.gitignore`, nbstripout, or `.gitattributes`
  mention. Not in `testpaths`; no tests exist to add.
- Structurally the least-integrated ML asset: a bare notebook at `runs/ml/` top level
  with no directory, vs siblings' `src/` + `tests/` + `docs/`.

## 1. What it IS

Customer lifetime-value forecasting for a neobank. Markdown cell 0: forecast user value
28 days after KYC completion so marketing can set acquisition spend against LTV/CAC;
agreed horizon **2 years**; cohort definitions link to an **external Google Sheets URL**
(live third-party link, committed).

**Modeling shape**: a decomposed revenue/cost pair — two `HistGradientBoostingRegressor`
pipelines (cells 11, 13) targeting `two_y_revenue` / `two_y_cost`, profit derived
downstream. It fits models.

**Data path**: `pd.read_csv('Data/train.csv')` / `'Data/test.csv'` (cell 6) — **absent
from the repo** (no `Data/` anywhere; `*.csv` gitignored). Imports `utils.features`,
`utils.transform` — **no such package exists here**. Cells 79-81 reference
`connect_redshift`, S3 helpers, `/app/utils/CONFIG.ini`, a bucket and a Redshift IAM
ARN — another organization's infrastructure. **A fragment of a private employer repo**,
Python 3.7 vintage (repo requires ≥3.12), with two bare `pip install` cells violating the
uv-only rule. ~50 of 83 cells are empty; cell 76 is committed with a live `NameError`
traceback.

**Headline**: markdown cell 17 — ML weighted-percentage-error on cohort-summed profit
averages **23% vs 33%** for the cohort-mean model over four validation months. Per-user
metrics in cell 16: TEST R² 0.334 / MAE 39.50 vs baseline R² 0.1966 / MAE 44.41.

**The headline is not reproducible from the artifact.** Cells 23-26 are four copy-pasted
blocks each hardcoding a different `kyc_month` but printing an undefined loop variable
`month` (all four outputs claim `2019-02-01`) and merging `on=group` — also undefined.
They cannot execute in a fresh kernel; outputs are stale artifacts of a prior session.

## 2. Do committed outputs embed real data?

**Yes — aggregates and schema, no raw records.** All 11 output-bearing cells enumerated:

| Cell(s) | Content class |
|---|---|
| 2, 3 | pip logs — interpreter path + versions (environment fingerprint of employer machine) |
| 8, 15 | **88-column production DWH schema dump** (`user_id`, `kyc_first_completed`, `two_y_profit`, `amount_grocery_market`, …) — column names only, zero row values |
| 12 | sklearn warning implying heavy zero-mass in target distributions |
| 16 | **Aggregate model metrics over real records** — R²/MAE/MedAE/MSE; MAE ≈ 39-47 in currency units discloses real per-user 2-year profit magnitude |
| 23-26 + md 17 | **Aggregate weighted percentage errors** per validation month over cohort-summed real profit |
| 76 | traceback only |

No `head()` dumps, no printed rows, no identifiers, no plots (zero `display_data`
outputs; the barplots errored). **But not clean by the repo's own standard**: the
gitignore asserts three times that "aggregates derived from real records are still real
records" and ignores exactly this content class for lending, fraud, and segmentation.
LTV.ipynb ships it committed, plus a schema-disclosure class the other runs don't have.

## 3. Leakage-shaped risks in the code

- **(a) Target-derived sample weights** (cell 12): `KBinsDiscretizer` quantile-bins **the
  target itself** to build weights, plus hardcoded country/product bonuses
  (`ITA`, `BUSINESS_CARD`). Mitigating: the `sample_weight=` lines are commented out in
  the fitted models — but the code and a CSV export of the weights remain.
- **(b) No cross-validation anywhere**: `GridSearchCV`/`TimeSeriesSplit` imported, never
  used; single `.fit`; HGBR at bare defaults. Transform-in-pipeline is correct within
  that single fit.
- **(c) Temporal leakage — the big one**: a 2-year forward target, cohort-month
  evaluation, and a **random** `train_test_split` for test/validation; no temporal-cut
  assertion anywhere. Train/test temporal disjointness is plausible but **unverifiable
  from the notebook**.
- **(d) Cohort-aggregate features are a group-leakage vector**: `avg_revenues_2/3`,
  `std_revenues_2/3` etc. are means of the target quantity over neighbouring cohorts,
  constructed in `utils.transform` — which is not in the repo. If any row's aggregate
  includes its own month, that is direct target leakage. Unverifiable — and the
  unverifiability is itself the finding.
- **(e) The evaluation is disconnected from the training.** The scored columns
  (`profit_forecast`, `two_y_profit_mean`, …) are **pre-existing columns of `test.csv`**
  (visible in cell 8's dump); the predictions computed in cells 11/13 are never assigned
  into the frame (cell 14's assignment is commented out — and was wrong: cost predictions
  into the revenue column, with index misalignment). **The reported metrics score an
  upstream process's baked-in forecasts, not this notebook's models.**
- **(f)** The only prediction actually computed is in-sample (`predict(X_train)`), unused.
- **(g)** IsolationForest outlier removal is dead code — mask computed, never applied,
  positioned after modeling. A commented `joblib` load references a 2021 model artifact
  (corroborates vintage).
- **(h)** HGBR has no `random_state` — not reproducible even given the data.

## 4. Bar score and disposition

**0/5, with element 5 *violated* rather than unmet.** Conversion is blocked on missing
inputs, not code volume: the entire feature-engineering/data-quality layer lives in a
private repo; data absent with no schema contract beyond the 88 column names; Python
3.7→3.12 mechanical port touches every cell; the evaluation must be rewritten, not
ported (per (e) there is no correct eval to lift).

**RunRecord-worthy?** The *claim* (ML 23% vs 33% WPE — the mirror image of lending's
"nothing beats the baseline") is exactly the shape `runs/_index/` exists for. But it is
**currently unfalsifiable from this artifact**; recording it would record a number nobody
in this repo can check — the exact failure DESIGN-parity's naive-baseline paragraph
names. Treat as exploratory/historical.

**Recommended disposition**: not a parity candidate. Options: (a) strip outputs, keep as
a documented historical exhibit with an ignore/nbstripout rule; (b) mine it for the
feature taxonomy and drop it. Either way the immediate action is independent of parity:
cells 8/15/16/23-26 and markdown 17 carry committed real-data-derived content the repo's
own policy excludes for all three sibling runs.

## 5. Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| Domain framing (md cell 0) | ADAPT | — | Named consumer, decision, 2y horizon with rationale, cohort-level criterion — seed of a `docs/DESIGN.md`. Strip the external URL |
| Feature taxonomy (cell 5) | ADAPT | — | ~250 lines of hand-curated groupings + blacklist discipline; correctly excludes all `two_y_*` targets. Port as a config module — profile-doc-as-code, lending's own pattern |
| `utils.*` feature engineering | SKIP | Nothing — the code is not in this repo; only call signatures and the 88-column output contract survive. Cheapest recovery: rewrite from the column contract, or recover the private repo | Absent; also where the group-leakage question (3d) would be answered — its absence makes the leakage posture unknowable |
| Preprocessing ColumnTransformer (cell 12) | ADAPT | — | Structurally correct train-only fit; delete the target-derived weight block; clean the shadowed `_blacklist` |
| Model cells (11, 13) | REUSE (pattern only) | — | Revenue/cost decomposition with derived profit is sound; six lines — retype with seed, real predict wiring, folds |
| Evaluation (cell 16) | SKIP | Metric *selection* only (~10 lines): R²/MAE/MedAE/MSE side-by-side vs a named baseline | Scores pre-baked columns, not the fitted models (3e) |
| Cohort WPE eval (cells 23-26) | SKIP | Metric *definition* only (~15 lines): |actual-profit|-weighted percentage error on cohort sums, month as a loop parameter | Four broken copy-pastes; undefined `month`/`group`; wrong-month merges |
| Permutation importance (cell 76) | SKIP | Nothing — two-line idiom, cheaper fresh | Live `NameError`; writes CSVs to CWD; labels desynchronized post-one-hot |
| S3/Redshift ingestion (79-81) | SKIP | The data-quality *contract* only: `perform_data_quality_checks.run(df, min_date, max_date, expected_columns, ratio)` signature + `DWH_COLUMNS` sets describe exactly the deterministic guard the bar wants — reimplement locally | Another organization's infrastructure, all callables undefined here |
| Outlier removal (cell 82) | SKIP | Nothing — trivially retypable; feature list already captured in the taxonomy row | Dead code, mask never applied |
| Committed outputs (8/15/16/23-26, md 17) | SKIP | No — remove; restate the 23%-vs-33% numbers in a docs note *with* the unverified caveat | Real-data aggregates + employer DWH schema; the exact class the repo ignores elsewhere; no nbstripout to have caught it |
