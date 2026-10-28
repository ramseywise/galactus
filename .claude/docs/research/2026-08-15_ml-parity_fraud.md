# ml-parity — fraud angle
Date: 2026-08-15
Work item: [`../plans/2026-08-15-lending-parity.md`](../plans/2026-08-15-lending-parity.md) (synthesis in its Research addendum)
Bar: the five parity elements from `runs/ml/lending/docs/DESIGN-parity.md`

One correction to a premise in the dispatch: `runs/ml/fraud/tests` **is** already in
`testpaths` (added 2026-08-15), and 35 tests pass.

## 1. What the run IS

**Not a trained-model metric comparison. It is a data-sufficiency verdict — a refusal.**
The README states this in its title: `runs/ml/fraud/README.md:1` — "ml/fraud — a refusal,
not a metric".

The headline finding (`runs/ml/fraud/README.md:7-8`): *"A confident-looking number
produced over three positives is not a result. It is a failure the toolkit should refuse
to hide."*

Mechanically (`runs/ml/fraud/README.md:29-38`): running the toolkit unguarded against the
frame (800 rows, 14 positives, 1.75% prevalence) produces three models that complete
**with no warning**, report PR-AUC within 0.003 of the prevalence floor, and each still
emit a cost-minimising threshold with **precision 0.000, recall 0.000, zero true
positives**. The "before" state is captured at `runs/ml/fraud/docs/before-guard.json` —
deliberately saved before the guard existed so it cannot be called a strawman
(`runs/ml/fraud/README.md:37-38`).

The finding's numbers, from `runs/ml/fraud/docs/summary.json`: logistic PR-AUC 0.0200,
random_forest 0.0189, lightgbm 0.0175 against a `prevalence_floor` of 0.0175;
`beats_baseline: false`; all three `threshold: null`; `refusal.min_positives_in_fold: 2`.

**Is it worth registering as a RunRecord?** Largely no, and the repo already decided
this. `runs/ml/lending/docs/DESIGN-parity.md:110` (Key Decision 1) explicitly names fraud
as the road not taken: "Over fraud / customer-segmentation (both already have tests but
no trained-model metric worth registering) ... Gave up: fraud/segmentation stay below the
full bar for now."

The reason is structural, not incidental: the fraud run's load-bearing output is a
*verdict about the evidence* (`refusal.operating_point_reported: false`), and that
verdict is already deterministic, pure, and unit-tested. The metrics it does produce are
explicitly disclaimed as meaningless — `runs/ml/fraud/src/run.py:14-17`: *"No number this
produces is a statement about the client's actual fraud rate."* Registering PR-AUC
0.0200-vs-floor-0.0175 as a reproducible headline would register a number the run itself
says not to read.

## 2. State vs each of the 5 bar elements

### (1) Tests — MET (premise correction)

`runs/ml/fraud/tests` **is** in `testpaths`, at `pyproject.toml:96`. Added 2026-08-15;
the surrounding comment (`pyproject.toml:88-92`) records exactly the failure mode: "An
omission does not fail — it collects zero tests from that poc, which is indistinguishable
from that poc passing. `runs/ml/fraud/tests` was missing until 2026-08-15, so its 35
tests had never run under a bare `uv run pytest`."

Verified green: `uv run pytest runs/ml/fraud/tests -q` → **35 passed, 3 skipped in
0.06s**, 38 collected.

Coverage, by file:
- `runs/ml/fraud/tests/test_sufficiency.py` (6 tests) — the guard. Includes the boundary
  case (`:29`), the averaging-bug catch (four folds at 40 + one at 2, `:38-45`),
  zero-positives-no-ZeroDivision (`:47`), and a never-raises sweep (`:54`).
- `runs/ml/fraud/tests/test_report.py` (17 tests) — HTML injection anchors pinned against
  **real** toolkit markup, plus `TestAnchorDriftIsLoud` proving a silent skip would have
  passed the old suite.
- `runs/ml/fraud/tests/test_summary.py` (15 tests) — `TestCommittedArtifacts` (12, always
  run) asserts the phase's proof against both committed JSONs, including aggregates-only
  checks (`test_artefacts_carry_no_identifier`, `test_artefacts_carry_no_row_data`).
  `TestSummariseFunction` (3) is the **only skipped group** — skipped because `run.py`
  imports `ml.*` at module scope and the toolkit is absent
  (`runs/ml/fraud/tests/test_summary.py:36-46`).

The 3 skips are the honest signature of the missing dry-run: the only tests that need the
harness are the only tests that cannot run.

### (2) Dry-run — MISSING ENTIRELY

`grep -rn "dry.run\|dry_run" runs/ml/` returns zero hits in `runs/ml/fraud/`.
`runs/ml/fraud/src/run.py:236-256` (`main()`) has `--data`, `--report`, `--n-splits`,
`--models`, `--summary-json` — no `--dry-run`. `build_frame` hard-exits without the real
CSV (`runs/ml/fraud/src/run.py:150-155`).

Partial credit: the *unit* layer already has synthetic fixtures with no real data
(`runs/ml/fraud/tests/conftest.py:1-8`, six seeded generators at `:82-150`), and
`conftest.py:35` uses a deterministic placement rather than a shuffle precisely for
reproducibility. What's absent is the *harness path* — nothing exercises
`build_frame → assess_sufficiency → run_classification → summarise → write_fraud_report`
end to end.

### (3) Deterministic in-run guards — MET, stronger than lending's

`runs/ml/fraud/src/sufficiency.py` is a pure, non-raising, non-I/O verdict function
(`:60-72` docstring: *"never raises, never fits a model, and never touches the
filesystem: the same `(y, split_plan)` pair returns the same verdict forever, which is
what makes a refusal reproducible"*).

- Threshold: `MIN_POSITIVES_PER_FOLD = 10` at `runs/ml/fraud/src/sufficiency.py:26`, with
  measured justification inline (`:28-36`).
- Reads the **minimum** fold, not the mean (`runs/ml/fraud/src/sufficiency.py:88-96`).
- Wired into the run at `runs/ml/fraud/src/run.py:266-272`; the refusal is expressed by
  **withholding costs** rather than discarding an answer
  (`runs/ml/fraud/src/run.py:280-284`): *"the refusal is expressed by not asking the
  question."*
- Leakage guard proper: `result.assert_no_transform_outside_pipeline()` at
  `runs/ml/fraud/src/run.py:288`.
- Identifier-leakage guard as a recorded decision: `IDENTIFIER_COLUMNS = ["uuid"]` at
  `runs/ml/fraud/src/run.py:103`, target-encoding hazard documented at `:98-102`.
- Report-drift guard: `ReportAnchorError` (`runs/ml/fraud/src/report.py:63-77`) raises
  rather than skipping — a silently-missing caveat is *"the same failure this poc exists
  to refuse, one layer up."*

Caveat vs the bar's wording: lending's Decision 6 (`DESIGN-parity.md:119`) says guards
**abort**. Fraud's sufficiency guard deliberately does *not* abort —
`runs/ml/fraud/src/sufficiency.py:18-20`: *"A run that refuses is not a run that
failed."* Exit 0 is intentional (`runs/ml/fraud/README.md:40-45`). A defensible
divergence, not a gap, but different semantics from the bar's letter. The loudness lives
in the payload, which `test_summary.py` asserts.

### (4) Run record — MISSING ENTIRELY

Zero hits for `RunRecord`, `experiments`, `_index`, `frame_hash`, or git-SHA capture
under `runs/ml/fraud/`. `runs/_index/` does not exist on disk.

Partial credit: `summarise()` was explicitly shaped for a later registry lift —
`runs/ml/fraud/src/run.py:172-178`: *"Shaped for a later Phase 1 registry lift (plan
F10): a flat `metrics`-shaped model list, a `headline_metric` naming which one is
load-bearing, and a `refusal` block."* `headline_metric: "average_precision"` is present
in `docs/summary.json`. The payload half exists; the provenance half (git SHA, frame
hash, resolved config) and the persistence half do not.

### (5) Data handling — MET at current paths (only run whose gitignore survived the rename)

Verified with `git check-ignore -v`:

| Path | Result |
|---|---|
| `runs/ml/fraud/data/dataset.csv` | ignored — `.gitignore:40` |
| `runs/ml/fraud/docs/report.html` | ignored — `.gitignore:43` |
| `runs/ml/lending/data` | **NOT IGNORED** |
| `runs/ml/lending/docs/report.html` | **NOT IGNORED** — tracked and committed |

Note `runs/ml/fraud/data/` does not currently exist locally, so the run cannot execute in
this checkout without re-copying the frame.

Aggregates-only is **tested**, not just asserted: `test_artefacts_carry_no_identifier`
and `test_artefacts_carry_no_row_data`, parametrized over both committed JSONs.

## 3. Toolkit dependency

`ML_PACKAGE_ROOT`, same mechanism as lending (`runs/ml/fraud/src/run.py:59-61`).
Imports: `ml.evaluation.splitting.make_splitter`,
`ml.workflows.classification.run_classification` (`:64-66`), deferred
`ml.reporting.html.write_report` (`report.py:160`).

**Pin: `ai-project-template`, branch `AIT-67-ml-workflows-classification`, commit
`0f8b2cf`** — `runs/ml/fraud/src/run.py:29-30` and `README.md:77-79` (branch unmerged).
Better pinned than lending (which names no commit) — but a prose pin in a docstring is
not enforced.

## 4. Gap-to-bar

| Bar element | Status |
|---|---|
| 1. Tests in testpaths passing | **MET** |
| 2. `--dry-run` full harness path | MISSING |
| 3. Deterministic guards | **MET** (refuse-not-abort semantics) |
| 4. RunRecord → `runs/_index/` | MISSING (arguably inapplicable — headline is a refusal) |
| 5. Data handling | **MET** |

**Net: 3 of 5.** Easier than lending: tests done, guard exists with fixture twins, data
handling correct, toolkit pinned in prose, `summarise()` pre-shaped, modules separated.
Harder: the headline is not a metric (element 4 may be inapplicable); inherits the
serializer block; `data/` absent locally; **the report layer's anchors are pinned against
lending's committed `report.html`** (`conftest.py:22-25`) — fixing lending's gitignore
would turn 17 tests into failures. Sequencing hazard.

## 5. Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `src/sufficiency.py` | REUSE | — | Pure, deterministic, min-fold, no toolkit dep, no I/O, never raises; directly liftable |
| `src/report.py` | ADAPT | — | Sound drift detection; anchors need decoupling from lending's report.html |
| `src/run.py` | ADAPT | — | Needs `--dry-run` + record assembly; module-scope `ml.*` import forces the 3 skips |
| `tests/test_sufficiency.py` | REUSE | — | 6 tests, no toolkit dep, boundary/averaging/zero/never-raises |
| `tests/conftest.py` | REUSE | — | Six seeded generators; `upstream_report` fixture is the one ADAPT part |
| `tests/test_summary.py` | REUSE | — | Asserts the finding and aggregates-only mechanically; skips un-skip once dry-run lands |
| `tests/test_report.py` | ADAPT | — | 17 good tests pinned to a file that should be untracked; retarget to a dry-run-generated report |
| `README.md` | REUSE | — | Accurate at current paths, states finding + pin |
| `docs/summary.json` + `before-guard.json` | REUSE | — | The before/after evidence pair, test-asserted |
| `WALKTHROUGH.md` | REUSE | — | Current-path clean |
| `docs/DESIGN.md` | SKIP (for parity) | Yes — keep as data profile; lift only the frame-shape table into any parity design doc | 922-line Step-14-style profile, not a system design; same name collision lending flagged |
| `src/__init__.py` | SKIP | Yes — zero-cost to keep | Empty file |
