# GAL-17 Customer segmentation — Trade Republic POC

Date: 2026-08-14
Status: COMPLETE
From: EXECUTED
Track: ml
Epistemic: NO_CONFLICT
Review: passed
Completed: 2026-08-14
Issue: #17

## Research

### Summary

The brief's Part 3 asks for customer clustering from named behavioural features, which is
unsupervised model fitting on a dataset — `Track: ml`, unambiguously. The raw sources
(`trades`, `prices`, `instruments`) are clean enough to build from directly, but **both
pre-computed assets in the directory are unusable as inputs**: `final_df.csv` covers
3,938 of 29,096 customers and contains 1,134 duplicate-`customer_id` rows with differing
values, and `group_label.csv` is positionally indexed with no customer key, so its labels
cannot be joined to anything. The feature matrix must be rebuilt from `trades.csv`.

The single most important finding is that **`cohort` is not an outcome** — it is exactly the
customer's first-trade month (perfect 6×6 diagonal, verified below). Any model that
"predicts" it is reading a timestamp back to itself.

### Scope

**Investigated:** all five CSVs, the challenge PDF, row/key alignment between the raw
tables and the two derived assets, the time axis, and the grouping structure that governs
the split.

**Out of scope:** Part 1 (SQL) and Part 2 (daily reporting metrics) of the brief — this
work item is Part 3 only. The Bonus (predicting 6th-month trades from the first 3) is a
supervised problem on a different frame; noted as follow-on, not built here.

### Findings

| # | Finding | Evidence | Confidence |
|---|---|---|---|
| F1 | **`cohort` is the first-trade month, not a label.** Crosstab of `cohort` against `month(min(execution_time))` is a perfect diagonal — cohort 1 ⇔ January (495), …, cohort 6 ⇔ June (803), zero off-diagonal. | `final_df.csv` joined to `trades.csv` | High |
| F2 | **`final_df.csv` is not a usable feature matrix.** 5,072 rows, 3,938 unique `customer_id`, 1,134 duplicated-ID rows that are *not* identical — so there is no safe dedup rule. Covers 13.5% of customers. | 375 cols × 5,072 rows | High |
| F3 | **`group_label.csv` cannot be joined.** 29,096 rows — matching the customer count — but indexed `0..29095` positionally with no `customer_id`. Customer IDs are *not* contiguous (min 1, max 30,000, 29,096 distinct), so positional alignment to a sorted ID list is an assumption the file gives no way to verify. | `group_label.csv` | High |
| F4 | **The raw trade data is clean.** 1,104,248 rows, 29,096 customers, 2020-01-02 → 2020-12-30. Exactly one malformed row (one NaN across `execution_size`/`execution_price`/`instrument_id`, one unparseable timestamp). BUY 809,897 / SELL 294,351. | `trades.csv` | High |
| F5 | **Trade counts are heavily right-skewed** — median 20, mean 38, p90 87, max 956. 712 customers (2.4%) have a single trade; 1,794 have fewer than 3. Skew this strong will dominate any distance metric unless the features are log-scaled. | `trades.csv` groupby | High |
| F6 | **The population is a H1-2020 signup cohort**, as the brief states: 28,182 of 29,096 customers (96.9%) first trade in Jan–Jun 2020; the Jul–Dec tail is small (76–349/month) and is *late first activity*, not a second intake. | first-trade month distribution | High |
| F7 | **Instrument catalog is nearly complete but not exactly.** Trades reference 626 distinct instruments; `instruments.csv` has 625. Instrument `900.0` appears in trades with no catalog row — sector/country/index joins must be outer-safe. | set difference | High |
| F8 | **Prices cover the full year for all 625 catalog instruments** (170,446 rows, 2020-01-01 → 2020-12-31), so end-of-day valuation for virtual P&L is computable without gap-filling across the panel. | `prices.csv` | High |
| F9 | **Instrument mix is derivative-heavy** — 500 DERIVATIVE, 100 STOCK, 25 ETF. Product-mix shares are therefore a meaningful segmentation axis rather than a near-constant. | `instruments.csv` | High |

### Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `trades.csv` | REUSE | — | The ground truth. All features derive from it (F4). |
| `prices.csv` | REUSE | — | Full-year EOD coverage for all catalog instruments; needed for virtual P&L (F8). |
| `instruments.csv` | REUSE | — | Sector/country/index/type joins; handle the one orphan ID (F7). |
| `final_df.csv` | SKIP | **Yes — as a feature *checklist*, not as data.** Its ~375 column names encode the previous attempt's feature vocabulary (monthly volume/size aggregates, distinct-instrument counts, realized vs virtual profit). Read the header to cross-check our feature list for omissions; never join the rows. | Duplicate IDs with conflicting values and 13.5% coverage make it unusable as input (F2). |
| `group_label.csv` | SKIP | **Yes — as a sanity baseline, not as truth.** Its 5-group size profile (10,484 / 7,537 / 4,837 / 4,330 / 1,908) is a prior expectation for cluster-balance: if our k=5 solution comes out wildly more uniform or more degenerate, that difference is worth explaining. Cannot be used as labels. | No join key; positional alignment unverifiable (F3). |
| `cohort` column | SKIP | **Yes — as a *validation* variable.** Cluster composition across signup months tests whether segments are behavioural or merely tenure artifacts. Must be excluded from the feature matrix. | It is the first-trade month restated (F1). |
| `LTV.ipynb` (`pocs/ml/`) | ADAPT | Sibling notebook in the same tree; check for reusable loading/valuation helpers before writing new ones. | Not yet read — flagged in Key Unknowns. |

### Assumptions

- **Assumption:** Clustering is the right frame; the brief asks to "segment customers into
  different groups" with no ground-truth labels. — **Evidence:** challenge PDF Part 3 —
  **If wrong:** the work is a supervised problem and the metric changes entirely —
  **Confidence:** High
- **Assumption:** A customer's full 2020 history is the unit of observation, so the frame is
  one row per customer. — **Evidence:** brief's per-customer feature list —
  **If wrong:** a time-windowed frame would need a group-aware split by customer —
  **Confidence:** High
- **Assumption:** Low-activity customers (<3 trades) belong in the segmentation rather than
  filtered out. — **Evidence:** they are 6.2% of the population and "dormant" is a real
  commercial segment — **If wrong:** they form a degenerate cluster that crowds out
  structure among active traders — **Confidence:** Medium
- **Assumption:** `execution_size × execution_price` is trade volume in account currency,
  with no FX conversion needed. — **Evidence:** the brief's `total` column is quantity ×
  price; single-currency dataset — **If wrong:** volume features mix currencies and every
  monetary feature is wrong — **Confidence:** Medium

### Disconfirming Evidence

- **Against F1 (cohort is first-trade month):** if the diagonal had been merely strong
  rather than perfect, `cohort` might have been an independent marketing-cohort assignment
  that correlates with signup timing. I ran the full crosstab rather than a correlation:
  every off-diagonal cell is exactly 0. It is a restatement, not a correlate.
- **Against F2 (final_df unusable):** the duplicates could have been benign exact repeats,
  which dedup would fix at no cost. Checked — `drop_duplicates()` on a duplicated ID's rows
  returns more than one row, so the duplicates disagree on feature values. There is no
  principled rule for choosing between them.
- **Against F3 (group_label unjoinable):** positional alignment to `sorted(customer_id)`
  would rescue the file if IDs were contiguous. They are not (min 1, max 30,000, 29,096
  distinct), so sorted-position alignment is an unverifiable guess.
- **Not looked at:** whether `final_df`'s duplicate rows correspond to a train/test split or
  a partial re-run of the prior pipeline. It would explain the artifact but would not make
  the file usable, so it does not change the verdict.

### Key Unknowns

1. **Baseline metric — named before computed (mandatory).** The comparison is
   **mean silhouette score on the standardized feature matrix**, against two baselines:
   (a) k-means at k=2, the trivial split, and (b) a random partition at the chosen k.
   A clustering that does not beat both has not been shown to find structure.
   Secondary: Davies–Bouldin (lower is better) and cluster-size balance. **Status: not yet
   computed.**
2. **Leakage check — red until proven (mandatory).** Unsupervised clustering has no
   train/test leak in the supervised sense, but it has three concrete analogues, each named
   with the column that would cause it:
   - **`cohort` / any first-trade-derived column in the feature matrix** — F1 makes this a
     direct restatement of signup timing; segments would encode tenure, not behaviour.
   - **Scaler fitted before any held-out split used for stability testing** — if cluster
     stability is assessed by re-fitting on subsamples, the `StandardScaler` must be fitted
     inside each subsample, not once on the full frame.
   - **Raw `total_trades` alongside its own monthly decomposition** — the sum and its twelve
     parts are the same information counted thirteen times, which silently weights activity
     volume above every other axis in Euclidean distance.
   **Status: red.** Reported red here, before any score exists.
3. **How many clusters** — not decidable from the data alone; needs elbow + silhouette
   across a k range, plus commercial interpretability. Deliberately left to the plan.
4. **`LTV.ipynb` contents** — not read; may contain reusable valuation logic (see Asset
   verdicts).
5. **Virtual P&L convention** — the brief defines it as open positions valued at the last
   EOD price. Whether "last" means the customer's last activity date or 2020-12-31 changes
   the number; 2020-12-31 is the reading this plan will take unless refine says otherwise.

### Recommendation

Rebuild the customer feature matrix from `trades.csv` joined to `instruments.csv` and
`prices.csv`, using `final_df.csv`'s column names only as a coverage checklist. Features
should span the four axes the brief names — activity (trades, volume, avg size), performance
(realized and virtual P&L), diversification (distinct instruments, sectors, product mix),
and timing (recency, inter-trade gaps) — with log-scaling for the heavy right skew in F5.
Exclude `cohort` and every first-trade-derived column from the matrix, then use them to
*validate* that the resulting segments are behavioural rather than tenure artifacts. Settle
`(family, output)` and the k range in the plan phase; report the silhouette against both
named baselines before interpreting any segment commercially.

**An implausibly clean separation is a finding, not a result** — if silhouette comes back
very high on the first pass, the first hypothesis is that a first-trade-derived column
survived into the matrix.

## Plan

Date: 2026-08-14
Based on: `## Research` above

### Goal

Produce a **reusable `ml`-track exemplar** — a segmentation of the 29,096 Trade Republic
customers whose value to this repo is that it demonstrates the track's discipline
(profile before framing, baseline named before computed, leakage shown red before it is
cleared) on a real frame, in code another POC can copy.

Confirmed with the operator, 2026-08-14. The commercial narrative for the board is a
by-product, not the goal: where the two pull apart, code clarity and the leakage
protocol win.

### Open Questions

| # | Question | Plan's default | Status |
|---|---|---|---|
| Q1 | What decision do the segments drive? | A reusable `ml`-track exemplar; commercial framing secondary | **Resolved 2026-08-14** — operator chose "reusable ml-track exemplar" |
| Q2 | Do low-activity customers (<3 trades, 6.2%) get filtered out? | No — segment all 29,096 and report the effect if they form a degenerate cluster | **Resolved 2026-08-14** — operator chose "segment all, report the effect" |
| Q3 | Does galactus take an sklearn dependency? | Yes — `scikit-learn` and `pandas` move into a `ml` dependency group. They are already resolved transitively (sklearn 1.9.0, pandas 3.0.5) but **undeclared**, so today's imports work by accident | **Resolved by this plan** — Step 1. Contrast with `pocs/ml/fraud`, which kept the toolkit external via `ML_PACKAGE_ROOT` because it consumed a *whole* external toolkit; this POC needs two standard libraries, and an undeclared import is the worse of the two evils |
| Q4 | Do the 68MB of CSVs get committed? | No — gitignore `pocs/ml/customer segmentation/csv/`, matching `pocs/ml/fraud/data/`. Keep the PDF (132KB, already tracked) | **Resolved by this plan** — Step 1 |
| Q5 | Virtual P&L valuation date | 2020-12-31 EOD for all open positions, so every customer is valued on the same date | **Open** — reviewer may prefer per-customer last-activity date; see Risk R3 |
| Q6 | How many clusters | Not fixed in advance. Step 5 sweeps k=2..10 and selects on silhouette + size balance + interpretability, reporting the whole sweep rather than the winner alone | **Open by design** |

### Approach

Build a per-customer feature matrix from `trades.csv` (joined to `instruments.csv` and
`prices.csv`), log-scale the heavy right skew, standardize, then k-means over a k sweep
with silhouette against two named baselines. The tradeoff: **k-means is chosen over
density methods (HDBSCAN) deliberately**, because the goal is an exemplar of the protocol
rather than the best-possible clustering — k-means makes the baseline comparison and the
scaling discipline legible, where HDBSCAN's variable cluster count would confound the
"did we beat a trivial split" question this plan exists to answer honestly. HDBSCAN is
named in Out of Scope as the obvious follow-on.

The module boundary follows `pocs/ml/fraud/`: `src/` holds importable functions with no
side effects at import time, `tests/` exercises them on **synthetic frames only** (no real
row enters a test file), and a single `run.py` is the only thing that touches the real CSVs.

### Out of Scope

- Part 1 (SQL) and Part 2 (daily reporting metrics) of the brief — Part 3 only.
- The Bonus (predict 6th-month trades from the first 3) — supervised, different frame.
- HDBSCAN / GMM / hierarchical clustering — named as follow-on, not built (see Approach).
- Any use of `final_df.csv` rows or `group_label.csv` labels as input (Research F2, F3).
- A board-ready slide deck. Step 7 emits a markdown report; formatting for a board is not
  this work item.
- Fixing `pocs/ai/marketing-comms/tests/conftest.py`, which fails to import on a clean
  main (`galactus.layout.contract` missing). Pre-existing, unrelated, verified by stashing.

### Steps

#### Step 1: Declare dependencies, register the test path, ignore the generated report

**Files**: `pyproject.toml` (lines 20–28 and 59–65), `.gitignore`
**What**: Three changes, two of them corrections from the refine gate (FA-004, FA-005):

1. Add an `ml` dependency group (`pandas>=3.0`, `scikit-learn>=1.9`) so the imports are
   declared rather than transitive.
2. **Add this POC's tests to `testpaths`.** `testpaths` is currently
   `["pocs/ai/marketing-comms/tests", "review/tests"]`, so a bare `uv run pytest` would
   collect *zero* tests from this POC — and its absence would be indistinguishable from
   its passing.
3. **Gitignore `pocs/ml/customer segmentation/docs/`,** not the CSVs. The CSVs are
   already covered by the repo-wide `*.csv` (`.gitignore:44`), so the originally-planned
   rule was a no-op whose Done-when was green before the step ran. The *actual* gap is
   the generated report: `docs/report.md` and `docs/segments.json` are aggregates over
   29,096 real customers and are **not** ignored by any existing rule. `pocs/ml/fraud/`
   gitignores its generated `report.html` for exactly this reason.

**Snippet**:
```toml
[dependency-groups]
dev = ["httpx>=0.27", ...]
ml = ["pandas>=3.0", "scikit-learn>=1.9"]

# testpaths — before
testpaths = ["pocs/ai/marketing-comms/tests", "review/tests"]
# after
testpaths = ["pocs/ai/marketing-comms/tests", "review/tests",
             "pocs/ml/customer segmentation/tests"]
```
```gitignore
# derived from real records is still real records — same rule as fraud's report.html
pocs/ml/customer segmentation/docs/
```
**Test**: `uv sync --group ml && uv run pytest --collect-only -q 2>&1 | tail -3`
**Done when**: `uv sync --group ml` resolves; **bare** `uv run pytest --collect-only`
reports a non-zero count from `pocs/ml/customer segmentation/tests` once Step 2 lands
(before Step 2 it correctly reports a collection error, not silence); and
`git check-ignore` returns a hit for `docs/report.md`.

#### Step 2: Loading and cleaning

**Files**: `pocs/ml/customer segmentation/src/load.py` (new), `src/__init__.py` (new),
`tests/conftest.py` (new — the `sys.path` shim, following `pocs/ml/fraud/tests/conftest.py:17`)
**What**: `load_trades()`, `load_instruments()`, `load_prices()`, plus
`parse_brace_array()` for the multi-valued catalog fields.

**Explicit `format=` on _every_ date parse, not just the trades one** (FA-003). The two
files use different and independently dangerous formats:

| File | Format | Hazard |
|---|---|---|
| `trades.csv` | `2020-01-02 20:00:00` → `%Y-%m-%d %H:%M:%S` | Inference silently yields `str` dtype; a later `.dt` access raises (hit during research) |
| `prices.csv` | `12/10/20` → **`%d/%m/%y`** | Ambiguous. **Measured: the first component reaches 31 and the second never exceeds 12, so these are day-first.** Inference that guessed month-first would scramble the panel by month with no error and no NaT — a wrong-but-plausible `virtual_pnl` for every open position |

Drop the single malformed row (counted, not swallowed). Left-join instruments so the
orphan `900.0` (F7) survives with null sector/country rather than vanishing.
**Snippet**:
```python
# before — silent dtype failure
t = pd.read_csv(path, parse_dates=["execution_time"])   # -> object dtype, no error

# after — explicit, and the failure is counted not swallowed
t["execution_time"] = pd.to_datetime(t["execution_time"], format="%Y-%m-%d %H:%M:%S",
                                     errors="coerce")
dropped = int(t["execution_time"].isna().sum())         # asserted == 1 in tests
```
**Test**: `uv run pytest "pocs/ml/customer segmentation/tests/test_load.py" -v`
**Done when**: loaders return the documented shapes; a synthetic frame with a bad
timestamp and an orphan instrument round-trips with the orphan retained and the bad row
counted; the parsed price panel has **366 distinct dates spanning 2020-01-01..2020-12-31
with zero NaT** (the assertion that would catch a format regression); and
`parse_brace_array('{Computer,"Elektronik & Haushalt"}')` returns two elements.

#### Step 3: Feature engineering

**Files**: `pocs/ml/customer segmentation/src/features.py` (new)
**What**: `build_customer_features(trades, instruments, prices) -> DataFrame` indexed by
`customer_id`, spanning the four axes the brief names:
- **Activity** — `n_trades`, `total_volume`, `mean_trade_size`, `active_months`
- **Performance** — `realized_pnl` (matched BUY→SELL, FIFO), `virtual_pnl` (open position
  at 2020-12-31 EOD price). **The oversell branch is specified, not left to the
  implementation**: a SELL exceeding accumulated BUY quantity (short, or a data artifact)
  matches what it can and records the unmatched remainder in `unmatched_sell_qty` rather
  than silently producing a negative position or dropping the trade. A test covers it,
  because "FIFO" alone hides a sign error
- **Diversification** — `n_instruments`, `n_sectors`, `n_countries`, and DERIVATIVE/ETF/
  STOCK volume shares.

  **The sector/country fields are brace-wrapped arrays with an empty sentinel, and a
  naive `nunique` collapses three different realities into two values** (FA-001,
  measured: `{""}` is 508/625 sectors = 81.3% and 534/625 countries = 85.4%; 13 rows are
  genuinely multi-valued). Without handling, a derivative-only customer gets
  `n_sectors == 1` for "unknown", identical to a genuine single-sector trader, while the
  orphan instrument yields `0` — so the diversification axis the brief explicitly names
  would carry near-zero variance and drop out of the distance metric silently.

  Therefore: parse with `parse_brace_array()` from Step 2, treat `{""}` as a **third
  state** (unknown — neither a value nor NaN), and emit `sector_coverage` /
  `country_coverage` (the fraction of a customer's volume in catalogued instruments)
  alongside the counts so "diversified" and "unknown" are separable downstream.
- **Timing** — `days_since_last_trade`, `mean_days_between_trades`, `tenure_days`

Every column is a `FEATURE_COLUMNS` constant; `cohort` and any first-trade-derived
column are excluded **by construction**, and a test asserts the exclusion (F1).
**Snippet**:
```python
FEATURE_COLUMNS = ("n_trades", "total_volume", ...)
FORBIDDEN = ("cohort", "first_trade_month", "first_trade_date")
# tenure_days is derived from the first trade *date* but is a duration, not a
# signup-month restatement; it is included and this comment is why.
```
**Test**: `uv run pytest "pocs/ml/customer segmentation/tests/test_features.py" -v`
**Done when**: features build for a synthetic frame with known P&L; `realized_pnl` matches
a hand-computed value; no `FORBIDDEN` name appears in `FEATURE_COLUMNS`; every customer in
the input appears in the output (no silent drops).

#### Step 4: Scaling and the leakage guard

**Files**: `pocs/ml/customer segmentation/src/prepare.py` (new)
**What**: `prepare_matrix(features) -> (ndarray, list[str])` — `log1p` the skewed
monetary/count axes (F5), then `StandardScaler`. The log-set is not "the four skewed
axes" hand-waved: it is an explicit `LOG_COLUMNS` tuple, and a test asserts every column
in it has skew > 1 on the real matrix and every column outside it does not.

`check_leakage(features)` returns PASS/FAIL per rule with the offending column:
- **(a)** no first-trade-derived column present (Research K2, F1)
- **(b)** scaler fitted inside any subsample used for stability, never once on the full frame
- **(c)** no sum-and-its-parts double count
- **(d) matrix health — the opposite direction** (FA-002). Every rule above detects too
  *much* information; none detects a **degenerate** matrix. Rule (d) fails on any
  zero-variance column, any column whose NaN fraction exceeds a stated threshold, or a
  row count that does not equal the customer count.

Rule (d) exists because of a specific escape hatch: if FA-001 or a NaN-producing groupby
silently guts a feature, rules (a)–(c) all PASS (they read column *names*), Step 6 sees no
FAIL, and the damage surfaces as a *low* silhouette — which Step 7 has pre-authorised to
report as the honest "structure is weak" verdict. Without (d), a broken feature build can
exit through the plan's own intellectual-honesty clause and nobody finds out.
**Snippet**:
```python
def check_leakage(df) -> list[Finding]:
    """Red until proven. Returns a finding per rule; empty list is not a pass,
    an all-PASS list is. Rules (a)-(c) catch too much information; rule (d)
    catches too little — a matrix can be clean and still carry no signal."""
```
**Test**: `uv run pytest "pocs/ml/customer segmentation/tests/test_prepare.py" -v`
**Done when**: a frame containing `cohort` FAILS (a) naming the column; a frame with both
`n_trades` and its 12 monthly parts FAILS (c); **a frame that is clean on (a)–(c) but has
an all-constant column and 40% NaN FAILS (d)** — the regression test for the escape hatch;
the real matrix PASSES all four.

#### Step 5: Cluster, with baselines named before scores

**Files**: `pocs/ml/customer segmentation/src/cluster.py` (new)
**What**: `sweep(matrix, k_range=range(2, 11))` fitting k-means (`n_init=10`,
`random_state=0`) and returning silhouette, Davies–Bouldin, inertia, and cluster sizes per
k. `baselines(matrix)` returns the two comparators fixed in Research: k=2 trivial split
and a random partition at the chosen k. Both computed and stored **before** any winner is
selected.
**Snippet**:
```python
# The baseline is computed in the same call that computes the score, so a
# result cannot be reported without its comparator.
Result = namedtuple("Result", "k silhouette davies_bouldin sizes baseline_random baseline_k2")
```
**Test**: `uv run pytest "pocs/ml/customer segmentation/tests/test_cluster.py" -v`
**Done when**: on a synthetic frame with three well-separated blobs the sweep peaks at
k=3 with silhouette > both baselines; sizes sum to n; the run is reproducible under a
fixed seed.

#### Step 6: The proving run

**Files**: `pocs/ml/customer segmentation/src/run.py` (new)
**What**: The only module that touches real CSVs. Loads → features → leakage check →
sweep → writes `docs/segments.json` + `docs/report.md`. **Refuses to report a winning k
if the leakage check has any FAIL** — exits 0 with the refusal recorded, following
`pocs/ml/fraud/src/run.py`'s "a refusing run is a successful run". Prints aggregates only,
never a customer row or ID.

**Stamp provenance into `segments.json`** (FA-006): a run id, the `FEATURE_COLUMNS` tuple,
input file sizes + hashes, and the four leakage verdicts. Both artifacts are written to
fixed paths and overwritten in place, so without a stamp there is no way to answer "was
this report produced before or after the sector fix?" — and the Goal makes this an
exemplar other POCs copy, so a superseded report must be identifiable as superseded rather
than merely overwritten.
**Test**: `uv run --group ml python "pocs/ml/customer segmentation/src/run.py"`
**Done when**: the run completes, `docs/report.md` names the baseline beside every score,
and the leakage section is printed **before** the silhouette table.

#### Step 7: Interpret and record

**Files**: `pocs/ml/customer segmentation/docs/report.md` (generated), plan doc `## Review`
**What**: Name each segment from its centroid profile, cross-tab segments against `cohort`
to test the F1 tenure hypothesis, and state the low-activity outcome Q2 asks about. Record
the honest verdict — including "the structure is weak" if silhouette says so.
**Test**: `uv run pytest "pocs/ml/customer segmentation/tests" -q && uv run ruff check .`
**Done when**: report states the chosen k with its justification, every segment has a
one-line commercial description, the cohort cross-tab is present, and an implausibly high
silhouette (>0.7) is flagged as a suspected leak rather than celebrated.

### Test Plan

| Level | What | Command |
|---|---|---|
| Unit | Loaders, features, scaling, leakage rules, sweep — synthetic frames only | `uv run pytest "pocs/ml/customer segmentation/tests" -q` |
| Regression | The repo's own tooling suite stays green (the corpus label added for this doc) | `uv run pytest review/ -q` |
| Lint | `uv run ruff check .` | |
| Integration | The proving run against the real 1.1M-row frame | `uv run --group ml python "pocs/ml/customer segmentation/src/run.py"` |

No real row enters a test file (`pocs/ml/fraud/tests/conftest.py` convention). The real
frame is exercised only by `run.py`, which is an integration concern.

### Risks & Rollback

| # | Risk | Mitigation |
|---|---|---|
| R1 | **A first-trade-derived column reaches the matrix**, making segments encode tenure (F1). The failure is silent and looks like a good result | Step 4's `check_leakage` rule (a) fails on the column by name; Step 7 cross-tabs against `cohort` as an independent check |
| R2 | **Low-activity customers form a degenerate cluster** that swamps structure (Q2 accepts this risk) | Report it rather than pre-empt it; Step 7 states the effect. If it dominates, the follow-on is a two-stage segmentation, noted not built |
| R3 | **Virtual P&L convention (Q5) changes every performance feature** | Valuation date is a single constant in `features.py`; switching it is a one-line change and a re-run |
| R4 | FIFO matching for realized P&L is subtle; a wrong implementation is plausible-looking | Step 3 tests against a hand-computed synthetic case with interleaved buys and sells |
| R5 | ~~1.1M rows × groupby may be slow enough to discourage iteration~~ **Retired 2026-08-14 by measurement**, not by argument: load + parse + a four-aggregate groupby over all 1,104,248 rows completes in **0.5s**. No parquet cache, no sampling. The risk was hedging against a number nobody had run | — |

**Rollback**: every step adds new files under `pocs/ml/customer segmentation/` except
Step 1, which touches `pyproject.toml` and `.gitignore`. Reverting is `git checkout` on
those two plus deleting the POC subdirectory — no existing module is modified.

## Refine

Date: 2026-08-14

### Trio

**PM**: The value holds and is now recorded rather than inferred — `### Goal` commits to a
reusable `ml`-track exemplar and Q1 carries the operator's explicit choice. Scope is
externally fixed by the brief's own feature list, so it is not negotiable mid-build.

**Designer**: Composes rather than fights. `src/` + `tests/` + a single real-data `run.py`
is `pocs/ml/fraud/`'s layout, and Step 6's refusal rule is that POC's "a refusing run is a
successful run" reused verbatim. One real departure: Step 1 declares an `ml` dependency
group where fraud kept its toolkit external via `ML_PACKAGE_ROOT`. Q3 argues the cases
differ — two standard libraries versus a whole external toolkit — which is sound, but it
is a departure and is recorded as one rather than buried.

**EM**: Steps 1–5 are comfortably one session. R5, the only unmeasured feasibility claim,
was measured during this gate rather than argued: 0.5s for the full 1.1M-row pass, so it
is retired. The residual engineering risk is R4 — FIFO realized-P&L matching is subtle and
a wrong implementation looks plausible; Step 3's hand-computed interleaved test is the
control on it.

**Disagreement**: none. All three lenses converge; EM's caveat is a sequencing note, not a
dissent, and the one thing it flagged is now measured.

### Definition of Ready

| # | Check | Verdict | Evidence |
|---|---|---|---|
| 1 | Problem stated | pass | Brief Part 3 + `### Goal`; externally specified, not "X should be better" |
| 2 | Scope bounded | pass | `### Out of Scope` — 6 explicit exclusions |
| 3 | Acceptance checkable | pass | Every step names a runnable command and a done-when; Step 5 is deterministic under `random_state=0` |
| 4 | Fits one session | pass | 7 small steps; no split needed |
| 5 | Dependencies named | pass | Q3 (sklearn/pandas), Q4 (data), plus the pre-existing `marketing-comms` conftest failure named out of scope |
| 6 | Verification named | pass | `### Test Plan` — unit, regression, lint, integration |
| 7 | Rollback exists | pass | Only 2 tracked files modified; rest are new files. Generated artifacts are gitignored |

**7 pass, 0 fail, 0 n/a.**

### Failure pass — `fog-advisor`

Dispatched (not skipped): the plan writes persistent state (`pyproject.toml`,
`.gitignore`, generated artifacts over real customer records), which is Stage 3's
trigger. `resolve-capability fog` exited 0 → `.claude/agents/fog-advisor.md`; `fog` was
confirmed active by `derive-phases`. The advisor received the plan only — not the trio
card, not the DoR table.

**Six findings, all six resolved in the plan above.** Every one was independently verified
against the data before being acted on; none was taken on the advisor's word.

| ID | Claim | Verified? | Resolution |
|---|---|---|---|
| FA-001 | `{""}` empty sentinel collapses `n_sectors`/`n_countries`; diversification axis silently drops out | **Confirmed** — 508/625 sectors (81.3%), 534/625 countries (85.4%) | Step 3: `parse_brace_array`, `{""}` as a third state, + coverage features |
| FA-002 | `check_leakage` is one-directional; a degenerate matrix passes all rules and exits via the "structure is weak" clause | **Confirmed by inspection** — all three rules read column names, none reads a value | Step 4: rule (d) matrix health, with the escape-hatch regression test |
| FA-003 | `prices.csv` dates are ambiguous and the explicit-format lesson was applied to only one of two files | **Confirmed, with a correction** — the advisor guessed month-first; measured, the first component reaches 31 and the second never exceeds 12, so the panel is **day-first (`%d/%m/%y`)**. The hazard is real and the fix is the same | Step 2: explicit format per file + a 366-date/zero-NaT assertion |
| FA-004 | The Step-1 gitignore rule was a no-op; the real gap is the uncommitted-but-unignored generated report | **Confirmed** — `git check-ignore` hits `.gitignore:44:*.csv` for the data; returns nothing for `docs/report.md` | Step 1 rewritten: ignore `docs/`, not the CSVs |
| FA-005 | New tests sit outside `testpaths`, so bare `pytest` collects zero and reads green | **Confirmed** — `testpaths = ["pocs/ai/marketing-comms/tests", "review/tests"]` | Step 1: add the POC to `testpaths`; Step 2: add `tests/conftest.py` |
| FA-006 | No retraction path for a published-then-falsified result; artifacts overwritten in place with no provenance | **Confirmed by inspection** — fixed paths, no run id | Step 6: stamp run id, `FEATURE_COLUMNS`, input hashes, leakage verdicts |

Two gaps the advisor flagged as unevaluable are also closed: the **FIFO oversell branch**
is now specified in Step 3 (match what exists, record `unmatched_sell_qty`), and the
**log-set** is now an explicit `LOG_COLUMNS` tuple with a skew assertion rather than "the
four skewed axes".

It also reported one pass clean — determinism — noting every stochastic call is seeded
(`random_state=0`, `n_init=10`) and the k sweep is exhaustive rather than searched. Recorded
because a pass that found nothing is evidence, not silence.

**Not closed, and deliberately:** Research K4 (`LTV.ipynb` unread) stands. It may carry a
valuation convention contradicting Q5's 2020-12-31 choice. R3 already makes that a
one-line change, so it is a live open question rather than a blocker.

Epistemic: NO_CONFLICT
Epistemic-by: fog-advisor
Epistemic-at: 2026-08-14
Epistemic-findings: 6

### Verdict

**READY.** All seven DoR checks pass, the trio does not disagree, and the failure pass
dispatched cleanly with all six findings resolved in the plan rather than deferred.

`NO_CONFLICT` here means the adversarial check found no *unresolved* contradiction — not
that the plan is correct. The six findings it did raise were substantive, and two were
rated fatal; they are closed because the plan changed, not because they were argued away.

## Execution

Date: 2026-08-14

All seven steps executed. **49 tests, all green; ruff clean; the proving run completed
with all four leakage rules PASS.**

### The result

| | |
|---|---|
| Customers segmented | 29,096 (all of them — Q2's "segment all") |
| Features | 16 across the brief's four axes |
| Chosen k | **4**, silhouette **0.2548** |
| Baselines | random partition **−0.0125**, trivial k=2 split **0.2320** — the winner beats both |
| Leakage | 4/4 PASS, printed before any score existed |

**The silhouette is modest and that is the honest answer.** 0.2548 is real but weak
separation: these are overlapping behavioural gradients, not four discrete customer types.
The plan pre-authorised reporting exactly this, and rule (d) is what makes the statement
credible — a degenerate matrix would also have produced a low score, and (d) is the check
that distinguishes "genuinely weak structure" from "the features are broken". It passed,
so the weakness is the data's, not the pipeline's.

Only k=3 and k=4 beat both baselines at all. k=4 wins on silhouette *and* has the best
Davies–Bouldin of the whole sweep (1.268), so the two metrics agree.

### The segments

| Seg | n | Share | Character | Median profile |
|---|---|---|---|---|
| 0 | 12,182 | 41.9% | **Active core** — the engaged majority | 48 trades, €17.7k volume, 14 instruments, 11 sectors, traded 9 days ago |
| 1 | 9,116 | 31.3% | **Dormant / low-activity** | 8 trades, €1.5k volume, 4 instruments, 63 days since last trade, zero realized P&L |
| 2 | 735 | 2.5% | **Derivative specialists** | 86% derivative volume, `sector_coverage` **0.13**, 1 sector, 113 days idle |
| 3 | 7,063 | 24.3% | **Buy-and-hold** | 15 trades, zero realized P&L but €180 virtual — they buy and do not sell |

**Q2 answered by measurement.** Low-activity customers did *not* swamp the structure. They
formed their own coherent 31.3% segment (seg 1) rather than a degenerate singleton, and
the active population still split three ways around them. Segmenting all 29,096 was the
right call and the concern the research raised did not materialise.

**Segment 2 is the FA-001 fix earning its keep.** Its defining feature is
`sector_coverage = 0.13` — these customers trade instruments the catalog has no sector
for. Under the naive `nunique` the plan originally specified, they would have scored
`n_sectors = 1`, identical to a genuine single-sector trader, and this segment would have
dissolved into the others. The advisor's fatal finding was correct and the fix is visible
in the output.

### The tenure test (Research F1)

Cross-tabbing segment against first-trade month, row-normalized:

| Seg | Jan | Feb | Mar | Apr | May | Jun |
|---|---|---|---|---|---|---|
| 0 | 0.191 | 0.177 | 0.199 | 0.170 | 0.140 | 0.117 |
| 1 | 0.078 | 0.097 | 0.151 | 0.167 | 0.186 | 0.250 |
| 2 | 0.079 | 0.162 | 0.301 | 0.135 | 0.139 | 0.131 |
| 3 | 0.158 | 0.179 | 0.163 | 0.172 | 0.169 | 0.139 |

**Every segment spans all six signup months; none concentrates in one.** Had `cohort`
leaked into the matrix, this table would be near-diagonal — the perfect diagonal F1 found
between `cohort` and first-trade month. It is not. The segments are behavioural.

The one real gradient is seg 1's tilt toward June (0.250 vs 0.078 in January), which is
not leakage but a mechanical artifact worth naming: a June joiner has had less time to
accumulate trades by year-end, so recent joiners are over-represented among the dormant.
`tenure_days` is doing legitimate work there.

### What was built

| File | Purpose |
|---|---|
| `src/load.py` | Loaders; `parse_brace_array`; explicit date format per file |
| `src/features.py` | 16 features; FIFO P&L with the oversell branch; sentinel-aware diversification |
| `src/prepare.py` | `LOG_COLUMNS` scaling; the four-rule `check_leakage` |
| `src/cluster.py` | k sweep; baselines computed in the same call as the score |
| `src/run.py` | The proving run; refuses on any FAIL; stamps provenance |
| `tests/` | 49 tests on synthetic frames only — no real row in any test file |

### Deviations from the plan

- **Step 3 gained `unmatched_sell_qty` as an internal quantity** rather than a feature
  column. It is computed and asserted in tests (the oversell branch) but excluded from
  `FEATURE_COLUMNS` — on the real frame it is near-zero for almost every customer, so as a
  feature it would have failed rule (d)'s variance check. It remains a correctness control.
- **`prepare_matrix` sign-preserves the log transform** (`sign(x) * log1p(|x|)`). Not
  specified in the plan; required because `realized_pnl` is legitimately negative and a
  bare `log1p` yields NaN. Covered by a test.
- **Step 7's report is generated by `run.py`** rather than hand-written, so it carries the
  provenance stamp FA-006 asked for.

Nothing else departed from the plan as refined.

### FA-005 is only half-closed, and the reason is not mine to fix

Step 1 registered `pocs/ml/customer segmentation/tests` in `testpaths`, which was the fix
FA-005 asked for. **It cannot be demonstrated by a bare `uv run pytest`**, because
`testpaths` also contains `pocs/ai/marketing-comms/tests`, whose `conftest.py:7` does
`from galactus.layout.contract import load_template` — and
`pocs/ai/marketing-comms/src/galactus/layout/` contains nothing but `__pycache__`. The
module's source is absent from the repo. Pytest aborts at collection before reaching any
other path, so *every* suite in this repo is invisible to the default invocation, not just
this one.

Verified pre-existing and not caused by this branch: `origin/main`'s conftest carries the
identical import, and the failure reproduces on a stashed (clean) tree.

What is proven instead: `uv run pytest "pocs/ml/customer segmentation/tests" "review/tests"`
collects and passes **202 tests**, so the registration itself is correct and the two suites
coexist. The remaining half of FA-005 — "the suite's absence would be visible under bare
pytest" — stays open until the marketing-comms import is repaired, which is its own work
item and is listed in Out of Scope.

## Review

Date: 2026-08-14

### Verification

| Check | Command | Result |
|---|---|---|
| POC unit tests | `pytest "pocs/ml/customer segmentation/tests" -q` | **49 passed** |
| POC + tooling suites | `pytest "pocs/ml/customer segmentation/tests" "review/tests" -q` | **202 passed** |
| Lint | `ruff check "pocs/ml/customer segmentation"` | **All checks passed** |
| Proving run | `uv run --group ml python "…/src/run.py"` | **exit 0**, 4/4 leakage PASS, k=4 |
| Bare `pytest` | `uv run pytest` | **blocked** by a pre-existing unrelated import error (above) |

### Plan fidelity

All seven steps executed as refined. Three deviations, all recorded above with reasons;
none changes an interface the plan specified. The two fatal advisor findings are both
verifiable in the output: rule (d) is exercised by a passing regression test, and segment 2
(`sector_coverage` 0.13) exists only because FA-001 was fixed.

### Honest limitations

1. **Silhouette 0.2548 is weak separation.** Four overlapping behavioural gradients, not
   four discrete types. Reported as such rather than dressed up; the segments are still
   commercially legible, but they are soft boundaries.
2. **`LTV.ipynb` was never read** (Research K4). If it carries a valuation convention that
   contradicts the 2020-12-31 choice, `virtual_pnl` shifts. One-line change, per R3.
3. **k-means only.** HDBSCAN/GMM were scoped out deliberately; a density method might find
   the derivative specialists more cleanly than a centroid method can.
4. **No stability testing across subsamples.** Rule (b) states the contract that would make
   it correct, but the run itself does not resample. That is the natural next increment.
5. **One run, one seed.** `random_state=0` throughout. Reproducible, but the sensitivity of
   k=4 to the seed is unmeasured.
