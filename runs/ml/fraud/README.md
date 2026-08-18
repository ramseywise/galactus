# ml/fraud — a refusal, not a metric

The third case study in this repo, and a different shape than the other two. Where
[`ai-marketing-comms/`](../../ai/marketing-comms) is **generation under a contract** and
[`ml-lending/`](../lending) is **prediction under uncertainty**, this poc is about the
uncertainty *estimate itself* — specifically, what a toolkit should do when the data
cannot support one.

> **A confident-looking number produced over three positives is not a result. It is a
> failure the toolkit should refuse to hide.**

## The frame

`lebanese-blonde/src/data/dataset.csv`, copied read-only (`cp`, never `mv`) into
`data/dataset.csv` (gitignored — see [Data handling](#data-handling)):

| property | value |
|---|---|
| rows | 800 |
| columns | 43 (42 after dropping `uuid`, see below) |
| target | `default` |
| positives | 14 (1.75% prevalence) |
| `uuid` | 800/800 distinct — dropped, not encoded (see `src/run.py`) |
| `age` | raw, 18–74, median 46, 36 missing — kept raw, recorded as a fairness note |

At `n_splits=5`, `StratifiedKFold` puts **2–3 positives per test fold**. That is the
thinness this poc exists to catch.

## The finding this poc demonstrates

Run the existing ML toolkit (`ai-project-template`, branch `AIT-67-ml-workflows-classification`,
pinned at `0f8b2cf`) against this frame exactly as shipped, with no guard: all three
registry models (logistic, random forest, lightgbm) complete **without a single warning**,
report a PR-AUC within 0.003 of the 0.0175 prevalence floor, and each still produces a
cost-minimising threshold with **precision 0.000, recall 0.000, zero true positives** —
printed with three-decimal precision and a `savings_vs_default` figure, as if it were a
decision. That captured run is [`docs/before-guard.json`](docs/before-guard.json) — saved
before any guard exists, so the "before" state can't be accused of being a strawman.

**A refusing run is a successful run.** The guard this poc adds does not make the toolkit
raise on a thin frame — a refusal is not an error, it's a verdict. When the positive count
per fold is insufficient, the run still exits 0, still produces a report, and the report
says so: a `refusal` block in both the JSON summary and the HTML, in place of (not instead
of) a threshold nobody should act on.

## Layout

```
runs/ml/fraud/
├── README.md              This document
├── docs/
│   ├── before-guard.json  Captured "before" run — no guard, no warning, a hollow threshold
│   └── report.html        Generated report (gitignored — derived from real data)
├── data/                  Gitignored. Real records never enter this repo.
├── src/
│   ├── run.py             Frame loading + the wired run (constants = recorded decisions)
│   ├── sufficiency.py      The refusal guard — pure, never raises, never does I/O
│   └── report.py           Poc-local report wrapper: refusal banner + prevalence floor
└── tests/                  Unit tests for the sufficiency guard
```

## Abort vs. refuse — the taxonomy

The parity bar admits two guard outcomes, and they route differently:

| Outcome | Exit code | When | Example |
|---|---|---|---|
| **Abort** | non-zero | The matrix is contaminated — a leak makes every score meaningless | Leakage guard FAIL: an identifier column was encoded against the target |
| **Refuse** | 0 | The matrix is clean but the evidence is insufficient — the run completed and declined to claim what the evidence cannot support | Sufficiency guard: 2–3 positives per fold, threshold arithmetic is not evidence |

This poc demonstrates the **refuse** path. The sufficiency guard (`src/sufficiency.py`)
never raises, never fits a model, and never does I/O — it returns a verdict. A refusing
run is a successful run that writes its own limitation into the record.

See also: [`runs/ml/lending/docs/DESIGN-parity.md`](../lending/docs/DESIGN-parity.md)
Key Decision 6, which states the abort half of this taxonomy.

## Data handling

The data is a sample of real transaction-level records. It does not get committed, and it
does not get pasted into a model context. `data/` is gitignored explicitly (not just via
the repo's `*.csv` glob); worked examples in tests use synthetic fixtures. Aggregates
only — no artifact this poc produces (JSON, HTML, or log output) contains a row, an index,
or an identifier value.

The source repo (`~/workspace/lebanese-blonde`) is read-only from this poc's perspective:
data left it via `cp`, nothing was ever written back.

## Dependency

The ML toolkit lives in `ai-project-template`, not in this repo — galactus declares no ML
dependencies by design. `src/run.py` imports it via an `ML_PACKAGE_ROOT` environment
variable, following the pattern established in [`ml-lending/src/run.py`](../lending/src/run.py).
Pinned at commit `0f8b2cf` on branch `AIT-67-ml-workflows-classification` (unmerged as of
this writing — see that repo's history for status).
