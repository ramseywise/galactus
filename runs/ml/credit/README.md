# credit — tabular ML prototype

Reference POC for the **ML branch** of `/prototype-genesis`, the way
`runs/ai/marketing-comms/` is the reference for the AI branch.

Binary classification: predict credit default from aggregated account history.

## Data

`data/credit_default.csv` is **gitignored** (`.gitignore` — `*.csv`), so a fresh clone
will not have it. Restore it with:

```bash
cp ~/workspace/lebanese-blonde/src/data/dataset.csv \
   runs/ml/credit/data/credit_default.csv
```

Semicolon-delimited. 800 rows × 43 columns, target `default`.

| Property | Value | Consequence |
|---|---|---|
| positives | **14 of 800 (1.75%)** | Severe imbalance — PR-AUC, not ROC-AUC |
| positives per 5-fold | **~2.8** | Metrics are extremely noisy; report spread, not just mean |
| columns with nulls | **41 of 43** | Missingness is near-universal and needs a pattern check, not a blanket fill |
| leakage candidates | `has_paid`, `recovery_debt` | Post-outcome? Resolve before including |

**Read the positives-per-fold number before trusting any metric.** With ~3 positives per
fold, fold-to-fold variance dwarfs any plausible model difference. This sample demonstrates
the mechanics honestly; it does not produce a trustworthy model. The full extract (the
original README cites 90k customers, 1.4% default) is what a real run needs.

## Layout

```
notebooks/01-eda.ipynb   EDA narrative — thin cells that call eda.py and show
                         the output inline; bivariate-first, templated from the
                         operator's own 2020 lebanese-blonde exploration notebook
notebooks/eda.py         the EDA functions themselves — load / analyze / plot
src/run.py               run script (gate 3 output)
data/                    gitignored
```

**The notebook holds narrative, not logic.** A markdown cell says what a step is for,
a code cell makes one call into `src/eda.py`, and the output renders under it. The
analysis lives in the module where it is diffable, importable, and testable — a
notebook that carries its own logic can only be reviewed by re-running it.

`notebooks/eda.py:column_plan` wraps `ml.transform.columns.infer_column_types` rather than
re-deriving dtypes, so the notebook's view of the columns and `run.py`'s view come
from one implementation and cannot drift apart.

```bash
cd runs/ml/credit/notebooks && uv run jupyter lab   # then open 01-eda.ipynb
```

Shipped with outputs stripped. Re-running it top to bottom is the check that it still
works against the current frame.

Its **last cell is the handoff**: `CATEGORICAL` / `NUMERIC` / `ORDINAL` / `EXCLUDED`, with
a reconciliation check (`eda.reconcile`) that names any column you did not decide about.
41 unaccounted on a fresh run is correct — that is the gate, not a bug.

## Pipeline

The modelling code is **not written here** — it comes from `ml/` at the repo root (33
modules, vendored from `ai-project-template`, 158 tests passing). It already handles
per-fold fitting, out-of-fold prediction, calibration, threshold choice, and asserts the
no-transform-leakage claim.

```bash
uv run python -c "
from ml.selection.registry import get_specs
for s in get_specs('classification', 'binary'):
    print(f'{s.name:14} baseline={s.is_baseline} available={s.available}')
"
```

`catboost` and `lightgbm` are registered but not installed — the comparison runs one model
shorter with a logged warning. `uv add --group ml catboost lightgbm` to enable them.

## Prior art

`~/workspace/lebanese-blonde` is the end-to-end precedent: EDA + model-development
notebooks, Flask endpoint, Docker, Elastic Beanstalk. The 2020 notebooks are in HEAD, with
a richer set in commit `4391492` (including separate LabelEncoding / OrdinalEncoding
annexes). Its EDA structure is what `01-eda.ipynb` is templated from — three API changes were
ported forward into `src/eda.py` (`np.object`/`np.bool`, `sns.distplot`, a single-column
`get_dummies` that silently mangled its assignment).
