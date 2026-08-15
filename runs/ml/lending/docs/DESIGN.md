# ml-lending — data profile and leakage findings

Status: PROFILED — no modelling decisions taken beyond the baseline config below.
Date: 2026-08-11
Plan: [`2026-08-10-ml-capability-parity.md`](../../.claude/docs/plans/2026-08-10-ml-capability-parity.md) Phase D, Step 14
Framing: [`pocs/ml/lending/README.md`](../README.md)

---

## What this document is, and what it is not

This is the output of running `/ml-transform` profiling and leakage analysis against a
real frame, before any modelling. It records what the data says.

**It is not about the client.** The frame profiled here is a public US peer-lending
dataset standing in for collections data that has not arrived. Every number below is a
property of *that* dataset. Nothing here promotes an **Assumed** label in
[`pocs/ml/lending/README.md`](../README.md) to **Given** — a Lending Club extract cannot confirm
anything about a client's business, and the six domain unknowns are untouched by it.

The proxy exercises the *toolkit*. It does not answer the *domain*.

### Label convention

[`pocs/ml/lending/README.md`](../README.md) labels domain statements **Given** (client-stated) or
**Assumed** (our inference). This document needs a third, because the proxy introduces
facts that are neither:

| Label | Meaning |
|---|---|
| **Given** | Stated by the client. **Nothing in this document carries this label.** |
| **Assumed** | Our inference about the client domain, pending confirmation. |
| **Observed** | Measured in the proxy frame. True of Lending Club, says nothing about the client. |
| **Planted** | Introduced by us to exercise a code path. Fabricated, and marked as such. |

---

## The frame

**Observed.** Source: [`codesignal/lending-club-loan-accepted`](https://huggingface.co/datasets/codesignal/lending-club-loan-accepted)
on HuggingFace, CC0-1.0. Local path `pocs/ml/lending/data/lending_club_2015Q4.csv` — **gitignored,
never committed**.

| Property | Value |
|---|---|
| Rows × columns | 45,224 × 151 |
| Rows after resolving the label | 39,770 |
| Rows dropped as unresolved | 5,454 |
| Duplicate rows | 0 |
| Columns entirely null | 15 |
| Near-constant columns (≥99% top value) | 17 |

### Provenance caveat — the filename lies

The file is named `accepted_2007_to_2018Q4.csv` upstream and the dataset card carries no
description. It is **not** the 2.26M-row full extract that name implies: it is a
45,224-row sample spanning **November–December 2015 only**. The schema is complete (all
151 columns, every leakage column intact), but the time range is two months.

This was discovered by profiling, not from the card, and it is the reason the temporal
findings below are parked rather than answered.

### Why the Zenodo mirror was rejected

The obvious no-account alternative — [Zenodo 11295916](https://zenodo.org/records/11295916),
CC BY 4.0, 1.35M rows — was checked and rejected. It is a **granting-model** extract: 15
columns of application-time features. Every post-outcome column has been curated out,
which is precisely the property that makes it useless here. Recorded so the next person
does not re-derive it.

---

## The label

**Observed / our construction.** Lending Club has no collections label. The target is
constructed from `loan_status`:

| `loan_status` | Rows | Target |
|---|---|---|
| Fully Paid | 31,593 | 0 |
| Charged Off | 8,176 | 1 |
| Default | 1 | 1 |
| Current | 5,090 | *excluded — unresolved* |
| Late (31–120 days) | 233 | *excluded — unresolved* |
| In Grace Period | 94 | *excluded — unresolved* |
| Late (16–30 days) | 37 | *excluded — unresolved* |

**Positive class = charge-off. Minority share 20.56%** (8,177 / 39,770).

Two consequences, both stated rather than assumed:

- **The 5,454 unresolved rows are excluded, and that is itself a modelling choice.** Loans
  still `Current` at extract time have no outcome. Dropping them is standard and it is
  also a mild survivorship filter — the excluded set is not a random sample of the
  portfolio. Recorded here so it is visible rather than buried in a `dropna`.
- **This is an origination-time default label, not a collections-propensity label.** The
  client target as framed ([`README.md`](../README.md)) is *"at collection intake, will this
  account pay?"* — a population where everyone has already defaulted. The proxy's
  population is all borrowers. **The shapes are analogous, not the same**, and no
  threshold or feature finding here transfers to the client without re-derivation.

### Balance

Minority share **20.56%** sits just above the skill's 20% line, so the recommendation is
`class_weight` rather than SMOTE — the cheapest option, no synthetic rows, no fold-order
hazard. It is close enough to the boundary to be worth re-checking on real data.

**Assumed, unchanged:** the client's own balance is unknown and expected to be worse. A
collections population is a defaulted population; the minority class there may be the
*payers*, inverting the polarity of this finding.

---

## Leakage — the headline finding

This is what the proxy was chosen for, and it delivered.

### The evidence

A single-feature association scan over all 151 columns (AUC of each column alone against
the label), plus a null-asymmetry check for columns populated only in one class:

| Column | Single-feature AUC | Null share | Post-outcome name? |
|---|---|---|---|
| `debt_settlement_flag_date` | **0.9649** | 96.6% | yes |
| `last_fico_range_high` | **0.9511** | 0.0% | **no** |
| `last_fico_range_low` | **0.9511** | 0.0% | **no** |
| `settlement_date` | 0.9442 | 96.6% | yes |
| `total_rec_prncp` | 0.8625 | 0.0% | yes |
| `settlement_amount` | 0.8449 | 96.6% | yes |
| `recoveries` | 0.8399 | 0.0% | yes |
| `collection_recovery_fee` | 0.8397 | 0.0% | yes |
| `settlement_status` | 0.8080 | 96.6% | yes |
| `last_pymnt_amnt` | 0.7685 | 0.0% | yes |

Two structural missingness blocks corroborate the name evidence — 13 `hardship_*` columns
all missing at **exactly 99.39%**, and 6 `settlement_*` columns all at **exactly 96.56%**.
Identical rates across a block mean one fact, not thirteen: these fields exist only for
the accounts that entered hardship or settlement, which happens *after* the outcome.

The vendor's own data dictionary confirms the mechanism rather than leaving it inferred —
`debt_settlement_flag` is documented as *"Flags whether or not the borrower, **who has
charged-off**, is working with a debt-settlement company."* The definition contains the
label.

### The confirmation

Two `HistGradientBoostingClassifier` fits on an identical grouped split, differing only in
which columns were available:

| Configuration | Features | ROC-AUC | PR-AUC |
|---|---|---|---|
| All features, leaks included | 130 | **0.9993** | **0.9989** |
| 39 leakage columns excluded | 91 | **0.7514** | **0.4500** |
| *(prevalence floor for PR-AUC)* | — | — | 0.2056 |

The 91 is a **diagnostic** count, not the modelling count. This A/B is a standalone probe
that label-encodes every column and keeps the all-null and constant ones; the Step 15 run
reports **88**, because `infer_column_types` drops 16 columns as unused (14 all-null
`sec_app_*`/`revol_bal_joint`, plus constant `policy_code`, `verification_status_joint`,
`disbursement_method`) and the two group-source columns are removed. Different frames,
both correct — noted because the two numbers otherwise look like a contradiction.

**0.9993 is the failure mode this case study exists to demonstrate.**
[`README.md`](../README.md) predicted it in advance: *"Any AUC above ~0.95 on a first pass
is treated as a leakage alarm, not a success."* The dataset produces that alarm
organically — no leak was planted to get it.

### The finding the name heuristic missed

`last_fico_range_high` / `last_fico_range_low` score **0.9511** with **no post-outcome
name pattern and zero nulls**. They are the borrower's FICO band at the *most recent
credit pull* — which for a charged-off loan happens after the default has already damaged
the score. A regex over column names does not catch this. A correlation scan does.

This is the argument for `review-leakage` being a reporter rather than a lint rule,
restated as evidence: **the most dangerous leak in this frame is the one that looks
innocent.** Two of the three detection signals had to agree to find it.

### The exclusion list

39 columns, excluded as post-outcome:

`recoveries`, `collection_recovery_fee`, `total_rec_prncp`, `total_rec_int`,
`total_rec_late_fee`, `total_pymnt`, `total_pymnt_inv`, `out_prncp`, `out_prncp_inv`,
`last_pymnt_d`, `last_pymnt_amnt`, `next_pymnt_d`, `last_credit_pull_d`,
`last_fico_range_high`, `last_fico_range_low`, `debt_settlement_flag`,
`debt_settlement_flag_date`, `settlement_status`, `settlement_date`, `settlement_amount`,
`settlement_percentage`, `settlement_term`, `funded_amnt_inv`, `pymnt_plan`,
`deferral_term`, `payment_plan_start_date`, `orig_projected_additional_accrued_interest`,
and all 12 remaining `hardship_*` columns.

`funded_amnt_inv` is a judgement call worth naming: it is set at origination, not after
the outcome, but it tracks investor fill and correlates with loan quality in a way that
would not be available for a *new* application. Excluded as conservative; flag if the
honest baseline needs the signal back.

---

## Column treatments

Per `/ml-transform` Step 2. Every column appears in one of these groups — the profile
covers all 151, including the ones whose treatment is `drop`.

### Drop — no signal

| Group | Columns | Reason |
|---|---|---|
| All-null | 15 columns incl. `member_id`, all 13 `sec_app_*` | 100% null in this extract; `member_id` is nulled in every public LC file |
| Identifiers | `id`, `url` | >99% distinct — row identifiers; scaled as numerics if left in |
| Free text | `desc`, `title` | Out of scope: no text features this phase (plan Out of Scope) |

### High cardinality

| Column | Distinct | Share | Treatment |
|---|---|---|---|
| `emp_title` | 17,538 | 44.1% | **target-encode in-fold, no collapse** — see below |
| `zip_code` | 852 | 2.1% | collapse rare (<1%) → target-encode in-fold |
| `earliest_cr_line` | 594 | 1.5% | parse to date → months-since; not a category |

**`emp_title` is the degenerate-floor case the skill warns about.** Top value is 2.06% of
non-null rows; with 17,538 distinct values over 39,770 rows, a literal 1% floor would
collapse essentially the entire column into one `other` bucket — deleting the feature
while appearing to treat it. No head, no collapse: target-encode directly, **fitted inside
the CV fold**, and say so. 6.29% null is itself a state (self-employed, retired,
unemployed), so it gets an indicator rather than a fill.

### Low cardinality — one-hot

`term`, `grade`, `sub_grade` (35), `emp_length`, `home_ownership`, `verification_status`,
`purpose` (12), `addr_state` (49), `initial_list_status`, `application_type`,
`disbursement_method`.

`addr_state` at 49 distinct sits under the 50 threshold and one-hots cleanly. **Flagged
for fairness, not for encoding**: geography is the classic protected-characteristic proxy
([`README.md`](../README.md) names postcode explicitly). `zip_code` compounds this. Both
are kept for now and the position is recorded as unresolved below — not silently accepted.

### Numeric — scaler by skew

| Column | Skew | IQR outliers | Treatment |
|---|---|---|---|
| `annual_inc` | **51.96** | 4.4% | log1p, then robust scaler — extreme right tail |
| `dti` | **23.57** | 0.06% | robust scaler — tail is a few extreme values, not a shape |
| `delinq_2yrs` | 4.97 | — | count column; leave unscaled or robust |
| `fico_range_low` | 1.36 | 3.1% | standard scaler |
| `open_acc` | 1.29 | 2.7% | standard scaler |
| `int_rate` | 0.71 | 1.8% | standard scaler |
| `loan_amnt` | 0.71 | 0.0% | standard scaler |
| `revol_util` | 0.02 | 0.01% | standard scaler — symmetric |

Skew and outliers are treated as **separate problems** per the skill: the treatment above
is scaling, not removal. Nothing is deleted for being inconveniently shaped.

### Near-constant — 17 columns

`policy_code`, `acc_now_delinq`, `num_tl_30dpd`, `num_tl_120dpd_2m`, `delinq_amnt`,
`chargeoff_within_12_mths` and 11 others carry ≥99% one value. Recommend drop: they are
noise with a name. **Nine of the 17 overlap the leakage exclusion list** (`out_prncp`,
`hardship_*`, `pymnt_plan`, `next_pymnt_d`) — they are near-constant *because* the
post-outcome event is rare, which is the same finding twice.

### Missingness

| Block | Columns | Rate | Reading |
|---|---|---|---|
| `hardship_*` | 13 | 99.39% | **not missingness — post-outcome**; excluded as leakage |
| `settlement_*` | 6 | 96.56% | **not missingness — post-outcome**; excluded as leakage |
| `open_acc_6m`, `open_il_*`, `total_bal_il` … | 12 | 52.36% | **structural** — identical rate across 12 columns means one cause (a reporting-era change), not twelve. Indicator + impute. |
| `annual_inc_joint`, `dti_joint`, `verification_status_joint` | 3 | 99.55% | structural — joint applications are rare. Indicator + impute. |
| `emp_title` | 1 | 6.29% | NMAR — absence is a state. Indicator + constant fill. |
| `dti`, `last_credit_pull_d` | 2 | 0.01% | negligible; impute. |

The 52.36% block is the most consequential: **imputing those 12 columns to a median would
invent data for half the portfolio.** Indicator plus impute, never impute alone.

---

## Group structure — Planted, and weak

**This is the one problem the proxy does not supply organically**, and the decision taken
was to derive a proxy key rather than fabricate an ID.

`member_id` is 100% null in every public Lending Club file, so there is no borrower
identity. The derived key is `emp_title | zip_code | annual_inc`:

| Property | Value |
|---|---|
| Distinct groups | 39,561 |
| Groups with >1 row | 202 |
| Rows in a multi-row group | 411 (**1.03%**) |
| Largest group | 3 rows |

**Honest reading: this barely exercises `GroupKFold`.** At 1.03% of rows in multi-row
groups and a maximum group size of 3, a grouped split is almost identical to a random one.
The key is also **inferred, not observed** — two different people sharing an employer,
ZIP-prefix and income collide, and the same person changing job is missed.

It is used in the confirmation run above so the grouped code path is exercised end to end,
and its weakness is recorded rather than presented as coverage. **Group leakage is
effectively unexercised on this proxy.** See open items.

---

## What the data settled, and what it did not

Against the six unknowns in [`README.md`](../README.md#open-questions--resolve-before-modelling):

| # | Unknown | Status |
|---|---|---|
| 1 | Label definition and horizon | **Not settled for the client.** The proxy has its own label (charge-off vs fully-paid, loan-lifetime horizon, no 30/60/90 choice available). The client's horizon remains open. |
| 2 | The decision the score feeds | **Not settled — client question.** No dataset can answer it. |
| 3 | Cost asymmetry | **Not settled — client question.** Step 15 *stipulates* a cost matrix to make `choose_threshold` runnable; stipulated, not discovered. |
| 4 | Propensity vs uplift | **Not settled, and the proxy cannot settle it.** Lending Club has no collection-action log, so the "we chased them, they paid" confound is absent by construction. This is the unknown the proxy is *least* able to speak to. |
| 5 | Time structure | **Partially observed, mostly parked.** The frame has `issue_d` but spans two months. See below. |
| 6 | Regulatory posture | **Not settled — client question.** |

**Zero promotions from Assumed to Given.** Expected, and stated in the plan's Step 14
Done-when as the thing to check: the criterion says to promote *"where the data or client
confirms them,"* and here neither did.

---

## Open items, with triggers

Each names what would close it, so silence reads as deliberate.

| # | Item | Trigger to resolve |
|---|---|---|
| 1 | **Temporal leakage unexercised.** Two months of `issue_d` (Nov 2015: 2,302 rows; Dec 2015: 37,468) gives `TimeSeriesSplit` nothing meaningful to split on. No cohort effects, no regime change, no seasonality. | Real client data with cohort dates, **or** the full 2.26M-row LC extract (needs a Kaggle account). |
| 2 | **Group leakage effectively unexercised.** 1.03% of rows in multi-row groups, max group size 3. The code path runs; the invariant is not stressed. | Real client data with genuine debtor IDs across accounts. |
| 3 | **Uplift vs propensity untestable on the proxy.** No treatment log exists in Lending Club. | Client data containing collection-action history — the moment it arrives, this becomes the highest-priority question. |
| 4 | **Fairness position not taken.** `addr_state` and `zip_code` are retained as features and are textbook protected-characteristic proxies. [`README.md`](../README.md) requires *"an explicit position, not silence"* — this document records the exposure but does not resolve it. | Operator decision, before any model informs a real decision. Not deferrable to deployment. |
| 5 | **Cost matrix is stipulated.** Step 15's threshold uses invented costs. Every threshold number downstream inherits that. | Client cost inputs (unknown #3). |
| 6 | **`funded_amnt_inv` exclusion is a judgement call.** Origination-time, but investor-fill correlated. | Re-include and measure if the honest baseline underperforms; the delta is the answer. |
| 7 | **Unresolved-row exclusion is a survivorship filter.** 5,454 `Current` loans dropped. | Accept as standard, or model with censoring, if the proxy is ever load-bearing for a claim. |

---

## Config for Step 15

Emitted for `run_classification`. Not applied here — this document profiles; it does not
transform.

```
family:          classification
output:          binary
target:          charged_off  (1 = Charged Off/Default, 0 = Fully Paid)
rows:            39,770
sampling:        class_weight        # 20.56% minority — above the 20% line
group_col:       group_key           # derived; weak (see Group structure)
time_col:        None                # two months only — declaring it would be theatre
calibrate:       True                # the binding constraint per README
primary_metric:  PR-AUC              # ROC-AUC misleads under imbalance
seed:            42
excluded:        39 leakage columns + 15 all-null + 2 identifiers + 2 free-text
```

`time_col` is deliberately `None`. `make_splitter` refuses to return a random splitter
when a time column is declared — declaring `issue_d` over a two-month window would trip
that guard for a structure the data does not have. Recorded as open item 1 instead.

---

## Step 15 result

Run: [`pocs/ml/lending/src/run.py`](../src/run.py). 39,770 rows, **88 features**, 5-fold
`StratifiedGroupKFold`, `class_weight`, isotonic calibration. No models skipped.

| Model | PR-AUC | ROC-AUC | Brier before → after |
|---|---|---|---|
| random_forest | **0.4215** | 0.7335 | 0.14359 → 0.14292 |
| logistic *(baseline)* | 0.4213 | **0.7379** | 0.14347 → 0.14333 |
| lightgbm | 0.4165 | 0.7323 | 0.14435 → 0.14336 |
| catboost | 0.4114 | 0.7304 | 0.14548 → 0.14319 |

### The honest finding: nothing beats the baseline

`beats_baseline` returns `True`, and it should not be believed. The margin is **0.0002
PR-AUC** — random forest 0.42151 vs logistic 0.42128, a 0.05% relative difference on a
single 5-fold estimate with no repeats and no confidence interval. Logistic regression
also has the **best ROC-AUC of the four**, so the two headline metrics disagree about the
winner. Three gradient-boosted ensembles landed on top of a linear model.

The plan's Done-when for Step 15 admits exactly this outcome — *"a calibrated model beats
the logistic baseline on PR-AUC **or** the honest finding is recorded that it does not."*
This is the second branch. **Read as: no candidate model beat the baseline.** Shipping
random forest on a 0.0002 margin would be reading noise as signal, and `RunResult.
beats_baseline` is a strict `>` with no tolerance band — a toolkit finding in its own
right (see below).

Every model sits at PR-AUC ~0.42 against a prevalence floor of **0.2056** — roughly double
the base rate. That is a real but modest signal, and it is the credible band for this
problem once the leaks are gone. The contrast with **0.9989 PR-AUC** on the leaked frame
is the entire point of the exercise.

Calibration improved Brier for all four, most for catboost (0.14548 → 0.14319) and least
for logistic (0.14347 → 0.14333) — the expected ordering, since a well-specified linear
model is close to calibrated already.

### Threshold — reported, not recommended

At the stipulated 4:1 cost matrix the chosen thresholds cluster around 0.19–0.23, well
below the 0.5 convention, which is the correct direction when false negatives cost more.
**These numbers are load-bearing on two assumptions and should not be quoted:** the cost
matrix is invented (open item 5), and the threshold is selected in-sample — swept over the
same out-of-fold probabilities its precision/recall are then measured on, so those figures
are optimistic. Flagged as `SELECTED_IN_SAMPLE` in the run output. The PR-AUC and ROC-AUC
above are unaffected; they are genuinely out-of-fold.

### Toolkit findings from the proving run

Phase D's job was to exercise Phases A–C and report gaps against the toolkit rather than
patch around them locally. Three:

1. **`group_col` forces the group column into the feature matrix.** `SplitPlan.split`
   resolves groups with `x[self.group_col]`, but `x` inside `run_classification` is the
   *feature* frame — so the column must be a feature for the split to work, and
   `infer_column_types` then buckets it by cardinality. At 39,561 distinct values it lands
   in `high_cardinality` and is **target-encoded**: near-unique borrower identity encoded
   against the label. The toolkit creates a leak while honouring its own grouping
   contract. Worked around here by pre-computing folds and passing `splitter=`; the fix
   belongs in the toolkit, which should exclude `group_col` from `plan.features`.
2. **`beats_baseline` has no tolerance band.** A strict `>` reports a 0.0002 margin as a
   win. A near-tie is the single most common real outcome of a model comparison and the
   property is currently unable to say so — the docstring already argues that a tie is a
   result, so the code should agree with it.
3. **`choose_threshold` does not mark its output as in-sample.** The docstring is candid
   that the grid is every observed probability, but `ThresholdResult` carries `precision`
   and `recall` with no indication they were measured at a point fitted on those same
   rows. A caller has to know to add the caveat.

Findings 1 and 3 were surfaced by dispatching `review-leakage` against `run.py` — the
reporter caught the in-sample threshold independently, which is the dimension doing the
job it was built for.
