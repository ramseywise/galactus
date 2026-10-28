# ml-parity — customer segmentation angle
Date: 2026-08-15
Work item: [`../plans/2026-08-15-lending-parity.md`](../plans/2026-08-15-lending-parity.md) (synthesis in its Research addendum)
Bar: the five parity elements from `runs/ml/lending/docs/DESIGN-parity.md`

## 1. What the run IS

Part 3 of the Trade Republic recruiting challenge — k-means segmentation of 29,096
customers over 16 behavioural features, valued at 2020-12-31
(`runs/ml/customer segmentation/src/run.py:5-8`, `docs/report.md:3`). Headline: **k=4 at
silhouette 0.2548, Davies–Bouldin 1.268**, beating a random-partition baseline (-0.0125)
and the k=2 baseline (0.2320). Full k=2..10 sweep reported (`src/run.py:96-101`); only
k=3 and k=4 beat both baselines. The artifact's own honest reading: silhouette ~0.25 is
weak separation, and the code has a "weak structure" refusal clause
(`src/run.py:107-108`, `src/cluster.py:99-101`).

**RunRecord-worthy?** This is the case `DESIGN-parity.md:114` (Key Decision 1) already
adjudicated against: "no trained-model metric worth registering." The substantive reason:
`RunRecord` is shaped around a supervised comparison — headline metric, seed, fold plan.
A clustering run has **no held-out metric and no fold plan**. A segmentation record would
be cheap and honest (git SHA, frame hash over three input CSVs, resolved config, the
sweep + chosen_k + cluster sizes — KMeans is seeded, `src/cluster.py:21,69,75`, and
`test_reproducible_under_fixed_seed` at `tests/test_cluster.py:40` already asserts
reproducibility) but would carry an internal-validity index, not a claim a second party
can refute the way "nothing beats the logistic baseline" can.

**`segments.json` is already a proto-record** (`src/run.py:110-134`): run_id, valuation
date, feature columns, per-input sha256(16) + byte counts, all four leakage verdicts,
refusal flag, n_customers, full sweep, chosen_k. Missing only git SHA,
resolved-config-as-such, and a canonical shape/location.

**The PDF.** `Trade Republic_Data Science Challenge.pdf` (132 KB) is Trade Republic's
**recruiting take-home brief**, verbatim ("RECRUITING / DATA SCIENCE CHALLENGE"; Part 1
SQL, Part 2 trading activity, Part 3 clustering — the part this run implements; "submit
your solution … via email"). It **is tracked and not gitignored** (`git ls-files`
confirms; `git check-ignore` → NOT IGNORED, while `csv/*.csv` hits `.gitignore:48` and
`docs/` hits `.gitignore:47`). A data-handling concern of a different class than the
CSVs: a third party's proprietary assessment instrument in a repo external readers are
meant to see. The run's DATA HANDLING docstring (`src/run.py:14-18`) discusses only
`csv/` and `docs/` — the PDF is unaddressed. The challenge framing is already restated in
`src/run.py:5-8`.

## 2. State vs the 5 bar elements

| Bar element | State | Evidence |
|---|---|---|
| (1) Tests in `testpaths`, pass | **MET** | `pyproject.toml:97`; `uv run --group ml pytest ... -q` → **49 passed in 1.69s** |
| (2) `--dry-run` | MISSING | zero `dry_run`/`argparse` hits; `main()` (`src/run.py:60`) takes no args, reads CSVs unconditionally (`:67-69`) |
| (3) Guards | **MET in substance, partial on "loudly"** | `check_leakage` runs *before any score exists* (`src/run.py:80-85`), four rules (`src/prepare.py:55-121`); implausibility alarm at silhouette >0.70 (`src/cluster.py:25,44-45`). Caveats: **exits 0 and refuses to name a winner** rather than aborting (`src/run.py:12,92-93,119`) — deliberate, inherited from fraud, differs from lending's Decision 6; rule (b) is a **constant `True`** (`src/prepare.py:79-85`) — asserts a contract, doesn't verify it |
| (4) Record in `runs/_index/` | MISSING | no `RunRecord`/`experiments.` refs; `runs/_index/` doesn't exist; artifacts overwrite fixed paths `docs/segments.json` / `docs/report.md` (`src/run.py:134,215`), docstring concedes the overwrite problem (`:20-24`); no git SHA |
| (5) Data handling | **MET for CSVs/docs; GAP: the PDF** | `csv/*.csv` ignored via `.gitignore:48`; `docs/` via the explicit rule at `:47` ("aggregates derived from real records are still real records"); `git ls-files` shows only `src/*.py`, `tests/*.py`, and the PDF tracked; report emits medians + cluster sizes, never a `customer_id` (`src/run.py:186-205`) |

`csv/` contents (all ignored, all local): `trades.csv` 58.3 MB, `final_df.csv` 9.6 MB,
`prices.csv` 3.3 MB, `group_label.csv` 222 KB, `instruments.csv` 27 KB. Only three are
read by the run — `final_df.csv` and `group_label.csv` are orphaned intermediates from
Jan 2022.

Test coverage is substantive: brace-array parsing incl. the `{""}` empty sentinel and the
day-first/month-first date hazard (`tests/test_load.py:10-68`); FIFO buy/sell matching
incl. oversell branches and hand-computed P&L (`tests/test_features.py:15-109`);
one class per leakage rule with failing + clean twins and the "empty list is not a pass"
contract (`tests/test_prepare.py:24-105`); sweep-peaks-at-true-k, noise-doesn't-beat-
baselines, implausibility-fires, seed reproducibility (`tests/test_cluster.py:24-81`).
No real row in any fixture (`tests/conftest.py:1-9`).

## 3. Dependency posture

**Galactus's own venv — no `ML_PACKAGE_ROOT`, no `ml.*` imports at all.**
`pyproject.toml:35-40` states it and contrasts with fraud. Confirmed in source
(`src/run.py:38`, `src/cluster.py:15-16`, `src/prepare.py:24`; zero `os.environ` hits).
Invocation: `uv run --group ml python "runs/ml/customer segmentation/src/run.py"`.

Consequence: the What-Breaks-First toolkit-pinning risk **does not apply** — versions are
in `uv.lock`. But importing `experiments.RunRecord` would introduce the
`ML_PACKAGE_ROOT` mechanism to this run for the first time — net-new coupling, the
opposite of lending's situation.

## 4. Gap-to-bar

**Met 2/5** (tests; data handling modulo PDF). **Partial 1/5** (guards — refuse-not-abort,
rule (b) hardcoded). **Missing 2/5** (dry-run; record).

Easier than lending: already modular (5 modules, 8–219 lines each, no 400-line `main()`
refactor needed); guards done with twins; the dry-run's synthetic fixtures already exist
in `tests/conftest.py:22-90` — dry-run is largely wiring (argparse + data-source param +
temp-path record), plausibly the smallest of the five gaps; no toolkit-pinning risk;
fast and seeded so the reproduce check is nearly free; `segments.json` is ~80% of a
record payload.

Harder than lending: **the record has weaker justification** — fitting a clustering
sweep into a supervised-shaped `RunRecord` risks the dishonest-`NotApplicable` failure,
and extending the shape is ai-project-template's call (galactus never defines the shape).
Cross-repo dependency on top of the serializer question. The refuse-vs-abort semantic
conflict is a decision, not a task. The PDF needs a human call. Whichever run lands first
pays for the `_index` layout decision.

## 5. Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `src/prepare.py` (4 rules + `prepare_matrix`) | REUSE | — | Element 3 satisfied and tested both directions; rule (d) matrix-health (`:102-119`) catches a gutted feature build escaping through the weak-structure clause; `Finding` dataclass + "empty list is not a pass" (`:45-61`) portable. Fix: rule (b) constant `True` (`:79-85`) |
| `src/cluster.py` | REUSE | — | Baseline computed in the *same call* as the score — no code path yields a score without its comparator (`:1-8,73-87`); seeded (`:20-21`) |
| `src/features.py` | REUSE | — | FIFO P&L well-factored; `FORBIDDEN_COLUMNS` (`:61`) feeds guard rule (a); tested to the oversell branch |
| `src/load.py` | REUSE | — | Date-format hazard note (`:8-15`) + regression test — measured hazard, not defensive style |
| `src/run.py` | ADAPT | — | Sound structure + provenance payload (`:110-133`); locus of both missing elements: no argparse/dry-run, no git SHA, no `_index` write, overwritten fixed outputs |
| `tests/` (49) | REUSE | — | conftest generators are the ready dry-run substrate |
| `docs/report.md` + `docs/segments.json` | ADAPT | — | Correctly ignored, aggregates-only; ~80% of a record; overwritten in place with no SHA — a record precursor, not a record |
| Trade Republic PDF | SKIP | Yes — keep locally, add ignore rule, `git rm --cached`, preserve a 3–5-line prose summary in a run README (currently absent) | Third party's live recruiting assessment, verbatim and tracked, in a repo meant for external readers; contributes nothing to the bar |

Also flagged: `csv/final_df.csv` (9.6 MB) and `csv/group_label.csv` are orphaned — no
module reads them; `.DS_Store` at run root (ignored).
