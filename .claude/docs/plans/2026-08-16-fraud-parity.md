# ml-fraud parity — dry-run harness + record for a refusal
Date: 2026-08-16
Status: SUPERSEDED
From: REFINED
Superseded-by: [`2026-08-18-ml-parity-consolidated.md`](2026-08-18-ml-parity-consolidated.md)
Track: ml

> **Superseded for execution 2026-08-18 — do not execute these steps.** Consolidated with
> segmentation into one pass so the shared `RunRecord`/`runs/_index/` seam is built once.
> **This doc remains the research and rationale record** — its resolved Open Questions are
> carried forward by reference, not re-litigated.
>
> Two corrections the consolidated plan applies:
> - **Step 5 is no longer blocked.** `runs/_index/` exists and is tracked; `experiments/`
>   is importable natively in galactus (no `ML_PACKAGE_ROOT`, no rendered tree).
> - **Open Question 6 is stale.** Lending's Step 7 *did* land —
>   `runs/ml/lending/src/run_record.py` and `tests/test_reproduce.py` both exist.
>
> **Premise warning:** this plan is built around fraud's headline being *a refusal*, and
> hard-codes that frame's measured values (PR-AUC 0.0200, `min_positives_in_fold: 2`,
> `threshold: null`). The 2026-08-18 sourcing decision would make the guard **pass**,
> leaving no refusal to record. The frame swap is unresolved — see
> [`2026-08-18-ml-frame-sourcing.md`](2026-08-18-ml-frame-sourcing.md). The consolidated
> plan therefore executes fraud's *harness* work only, which is frame-independent.
Epistemic: NO_CONFLICT
Epistemic-by: fog
Epistemic-at: 2026-08-18
Epistemic-findings: 6

Scout: [`../research/2026-08-15_ml-parity_fraud.md`](../research/2026-08-15_ml-parity_fraud.md)
Parent synthesis: [`2026-08-15-lending-parity.md`](2026-08-15-lending-parity.md) § Research addendum
Bar: the five parity elements from [`runs/ml/lending/docs/DESIGN-parity.md`](../../../runs/ml/lending/docs/DESIGN-parity.md)
GitHub issue: [galactus#34](https://github.com/ramseywise/galactus/issues/34) — branch `GAL-34-fraud-parity`.

## Research

### Summary

`runs/ml/fraud/` scores **3 of 5** against the bar — the closest of any run — and is
missing only the dry-run and the record. Tests, guards, and data handling are all met, and
the guard implementation is the strongest in the repo. The two gaps are asymmetric: the
dry-run is straightforward wiring against fixtures that already exist, while the record
raises a question no other run raises, because **fraud's headline is a refusal, not a
metric**. Registering PR-AUC 0.0200 against a prevalence floor of 0.0175 would register a
number the run's own source explicitly disclaims.

This item is **partially blocked**: the record step depends on
[AIT#83](https://github.com/ramseywise/ai-project-template/issues/83) (`experiments/io.py`
serializer) and on the `runs/_index/` layout that the lending plan drives out. Per the
2026-08-16 scoping decision, the plan is written in full with the record step marked
blocked — mirroring how lending's own Step 7 handles the same dependency. Steps before it
land value independently.

### Scope

Investigated: fraud's five bar elements against source; its toolkit dependency and pin; the
`report.html` fixture coupling; the guard's refuse-vs-abort semantics. Out of scope per the
addendum: the repo-hygiene sweep (separate item), other runs, any modelling change.

### Findings

**F1 — Tests are MET; a DESIGN-parity premise is stale. (High)** `runs/ml/fraud/tests` **is**
in `testpaths` (`pyproject.toml:96`, added 2026-08-15, after the design was drafted).
Verified green: `uv run pytest runs/ml/fraud/tests -q` → **35 passed, 3 skipped**, 38
collected. Coverage by file:

- `tests/test_sufficiency.py` (6) — the guard, including the boundary case (`:29`), the
  averaging-bug catch (four folds at 40 plus one at 2, `:38-45`),
  zero-positives-no-ZeroDivision (`:47`), and a never-raises sweep (`:54`).
- `tests/test_report.py` (17) — HTML injection anchors pinned against **real** toolkit
  markup, plus `TestAnchorDriftIsLoud` proving a silent skip would have passed the old suite.
- `tests/test_summary.py` (15) — `TestCommittedArtifacts` (12, always run) asserts the
  phase's proof against both committed JSONs, including `test_artefacts_carry_no_identifier`
  and `test_artefacts_carry_no_row_data`. `TestSummariseFunction` (3) is the only skipped
  group, skipped because `run.py` imports `ml.*` at module scope and the toolkit is absent
  (`tests/test_summary.py:36-46`).

**The 3 skips are the honest signature of the missing dry-run**: the only tests that need
the harness are the only tests that cannot run. Closing F2 should un-skip them.

> **CORRECTION 2026-08-18 (refine).** The clause above — and `TestSummariseFunction`'s
> skip being caused by `run.py`'s module-scope imports — is **wrong**. The toolkit is
> present: `ml/` is tracked at the galactus repo root (36 files) and
> `import ml.workflows.classification` succeeds with `ML_PACKAGE_ROOT` unset. The 3 tests
> skip because pytest does not put cwd on `sys.path` and `pythonpath`
> (`pyproject.toml:117`) lists only marketing-comms paths. Adding `"."` to `pythonpath`
> alone yields **38 passed, 0 skipped** with no source edit — measured. The skip-reason
> string at `test_summary.py:46-49` asserts `ml/` "holds only stale `__pycache__`", which
> is false and is what propagated the error into this plan. See the revised Step 3.

**F2 — The dry-run is missing entirely. (High)** `grep -rn "dry.run\|dry_run" runs/ml/`
returns zero hits under `runs/ml/fraud/`. `src/run.py:236-256` (`main()`) offers `--data`,
`--report`, `--n-splits`, `--models`, `--summary-json` — no `--dry-run`. `build_frame`
hard-exits without the real CSV (`src/run.py:150-155`), and `runs/ml/fraud/data/` **does
not exist in this checkout**, so the run currently cannot execute here at all.

Partial credit: the *unit* layer already has synthetic fixtures with no real data
(`tests/conftest.py:1-8`, six seeded generators at `:82-150`), and `conftest.py:35` uses
deterministic placement rather than a shuffle precisely for reproducibility. What is absent
is the *harness path* — nothing exercises `build_frame → assess_sufficiency →
run_classification → summarise → write_fraud_report` end to end.

**F3 — Guards are MET, and stronger than lending's. (High)**
`runs/ml/fraud/src/sufficiency.py` is a pure, non-raising, non-I/O verdict function
(`:60-72`: *"never raises, never fits a model, and never touches the filesystem: the same
`(y, split_plan)` pair returns the same verdict forever, which is what makes a refusal
reproducible"*).

- `MIN_POSITIVES_PER_FOLD = 10` at `src/sufficiency.py:26`, with measured justification
  inline (`:28-36`).
- Reads the **minimum** fold, not the mean (`src/sufficiency.py:88-96`).
- Wired at `src/run.py:266-272`; the refusal is expressed by **withholding costs** rather
  than discarding an answer (`src/run.py:280-284`: *"the refusal is expressed by not asking
  the question"*).
- Leakage guard proper: `result.assert_no_transform_outside_pipeline()` (`src/run.py:288`).
- Identifier-leakage guard as a recorded decision: `IDENTIFIER_COLUMNS = ["uuid"]`
  (`src/run.py:103`), target-encoding hazard documented at `:98-102`.
- Report-drift guard: `ReportAnchorError` (`src/report.py:63-77`) raises rather than
  skipping — a silently-missing caveat is *"the same failure this poc exists to refuse, one
  layer up."*

**F4 — The guard semantics conflict with the bar's letter, and the conflict is now
resolved. (High)** Lending's Key Decision 6 (`DESIGN-parity.md:119`) says guards **abort**.
Fraud's sufficiency guard deliberately does not — `src/sufficiency.py:18-20`: *"A run that
refuses is not a run that failed."* Exit 0 is intentional (`README.md:40-45`), and the
loudness lives in the payload, asserted by `test_summary.py`.

Per the 2026-08-16 operator decision (addendum X2, recommendation 5): **the bar admits two
failure modes** — abort for leakage-class violations, refuse-and-exit-0 for
sufficiency/structure verdicts. Fraud's stance is ratified, not a gap. The plan must decide
where that taxonomy is written down so it is inherited rather than re-argued (addendum
skill-gate item 2 proposes `/proto-harden`'s ML checklist variant).

**F5 — The record is missing, and may be inapplicable. (High)** Zero hits for `RunRecord`,
`experiments`, `_index`, `frame_hash`, or git-SHA capture under `runs/ml/fraud/`.
`runs/_index/` does not exist repo-wide — nothing writes it anywhere yet.

Partial credit: `summarise()` was explicitly shaped for a later registry lift
(`src/run.py:172-178`: *"Shaped for a later Phase 1 registry lift (plan F10): a flat
`metrics`-shaped model list, a `headline_metric` naming which one is load-bearing, and a
`refusal` block"*). `headline_metric: "average_precision"` is present in
`docs/summary.json`. **The payload half exists; the provenance half (git SHA, frame hash,
resolved config) and the persistence half do not.**

The open question is not mechanical. `DESIGN-parity.md:110` (Key Decision 1) already named
fraud as the road not taken — "no trained-model metric worth registering." The scout and
the addendum (X3) both conclude element 4 is *arguably inapplicable* here: the run's
load-bearing output is a verdict about the evidence
(`refusal.operating_point_reported: false`), which is already deterministic, pure, and
unit-tested. Numbers from `docs/summary.json`: logistic PR-AUC 0.0200, random_forest
0.0189, lightgbm 0.0175 against `prevalence_floor` 0.0175; `beats_baseline: false`; all
three `threshold: null`; `refusal.min_positives_in_fold: 2`. `src/run.py:14-17` says
plainly: *"No number this produces is a statement about the client's actual fraud rate."*

**"What does a record of a refusal carry?" is an ai-project-template question**, filed
alongside the serializer. Galactus never defines the record shape.

**F6 — Data handling is MET; fraud is the only run whose gitignore survived the rename.
(High)** Verified with `git check-ignore -v`: `runs/ml/fraud/data/dataset.csv` ignored via
`.gitignore:40`; `runs/ml/fraud/docs/report.html` ignored via `.gitignore:43`.
Aggregates-only is **tested**, not merely asserted — `test_artefacts_carry_no_identifier`
and `test_artefacts_carry_no_row_data`, parametrized over both committed JSONs.

**F7 — The before/after evidence pair is the run's real asset. (Medium)**
`docs/before-guard.json` was deliberately saved before the guard existed so the finding
cannot be called a strawman (`README.md:37-38`). Unguarded, the toolkit produces three
models that complete **with no warning**, report PR-AUC within 0.003 of the prevalence
floor, and each still emit a cost-minimising threshold with **precision 0.000, recall
0.000, zero true positives**. Whatever the record decision, this pair is what makes the
refusal checkable, and `test_summary.py` already asserts against both.

**F8 — The `report.html` fixture coupling is dissolved, not pending. (High)** The scout
flagged a sequencing hazard: fraud's 17 report tests pin anchors against lending's committed
`report.html` (`tests/conftest.py:22-25`), so untracking it would break them. Lending's
Open Question 2 **resolved to ratify** — `report.html` stays tracked, the three documents
claiming otherwise were corrected (lending Step 1, landed 2026-08-16). Verified:
`.gitignore:36-38` now carries the ratification comment naming
`runs/ml/fraud/tests/conftest.py` as the reason. Fraud's fixture keeps its ground truth;
addendum X1 does not apply to this item.

**F9 — The toolkit pin is better than lending's and still unenforced. (Medium)**
`ML_PACKAGE_ROOT`, same mechanism as lending (`src/run.py:59-61`). Imports:
`ml.evaluation.splitting.make_splitter`, `ml.workflows.classification.run_classification`
(`:64-66`), deferred `ml.reporting.html.write_report` (`report.py:160`). Pinned to
`ai-project-template` branch `AIT-67-ml-workflows-classification`, commit `0f8b2cf`
(`src/run.py:29-30`, `README.md:77-79`; branch unmerged). Lending names no commit at all —
but a prose pin in a docstring is not enforced by anything in either run.

### Asset verdicts (from the scout)

| Asset | Verdict | Reason |
|---|---|---|
| `src/sufficiency.py` | REUSE | Pure, deterministic, min-fold, no toolkit dep, no I/O, never raises; directly liftable |
| `src/report.py` | ADAPT | Sound drift detection; anchor coupling now ratified rather than needing decoupling (F8) |
| `src/run.py` | ADAPT | Needs `--dry-run`, an argv seam, + record assembly. (Scout claimed the module-scope `ml.*` import forces the 3 skips — **false**, see the F1 correction; the imports stay put.) |
| `tests/test_sufficiency.py` | REUSE | 6 tests, no toolkit dep, boundary/averaging/zero/never-raises |
| `tests/conftest.py` | REUSE | Six seeded generators — the ready dry-run substrate |
| `tests/test_summary.py` | REUSE | Asserts the finding and aggregates-only mechanically; skips un-skip once dry-run lands |
| `tests/test_report.py` | REUSE | 17 good tests; fixture ground truth ratified (F8) |
| `README.md`, `WALKTHROUGH.md` | REUSE | Accurate at current paths; README states finding + pin |
| `docs/summary.json` + `before-guard.json` | REUSE | The before/after evidence pair, test-asserted |
| `docs/DESIGN.md` | SKIP for parity | 922-line data profile, not a system design; same `PROFILE.md` vs `DESIGN.md` name collision lending flagged |

### Open questions for `/proto-plan`

1. **Is element 4 applicable at all?** Options: (a) record the refusal with a shape that
   makes it explicit (`headline_metric` + `refusal` block, no operating point), pending the
   AIT answer; (b) declare it inapplicable, document why in the run's README, and count
   fraud at 4/4-applicable; (c) defer entirely until AIT answers. This is the decision the
   whole item turns on.
2. **Does the dry-run write a record?** Lending's default (Key Decision 5) is that dry-run
   records go to a temp path, never `runs/_index/`. Inherit or diverge?
3. **Where does the abort-vs-refuse taxonomy get written?** Addendum skill-gate item 2
   proposes `/proto-harden`'s ML variant, which would make it a standing gate rather than
   per-run prose. In scope here or a separate tooling item?
4. **Does the dry-run need `runs/ml/fraud/data/` restored?** It does not exist locally. A
   dry-run that never reads the real CSV is the point — but the run's non-dry path is
   currently unrunnable in this checkout, which affects what "verified" means for any step.
5. **Toolkit-test posture** — inherit lending's plan default (toolkit-free unit tests always
   run; toolkit-importing tests `pytest.skip` with a reason naming `ML_PACKAGE_ROOT`)?
   Fraud already follows this pattern, so it is likely a confirm rather than a decision.

### Dependencies

- **AIT#83** (`experiments/io.py` serializer) — blocks the record step only.
- **`runs/_index/` layout** — driven out by the lending plan; nothing writes it yet.
- **"What does a record of a refusal carry?"** — an AIT shape question, unfiled as of
  2026-08-16. The addendum recommends filing it alongside the serializer.
- Steps for the dry-run, un-skipping the 3 tests, and the taxonomy write-down are
  **unblocked**.
## Plan
Date: 2026-08-18
Based on: `## Research` above, plus direct inspection of `runs/ml/fraud/src/run.py`,
`tests/conftest.py`, `tests/test_summary.py`, and the merged AIT `experiments/` module
(`record.py`, `io.py`, `provenance.py`, `fingerprint.py`).

### Goal
Give `runs/ml/fraud/` a dry-run harness that exercises the full pipeline on synthetic
fixtures with no real CSV, so the refusal becomes reproducible by anyone who clones the
repo — and specify the record step against the now-merged registry so it lands the moment
`runs/_index/` exists.

### Open Questions

1. **Is element 4 (the record) applicable to a refusal?** — **RESOLVED 2026-08-18:
   applicable, option (a).** Research framed this as open pending an AIT answer; the merged
   schema answers it. `RunRecord` (record.py:128-147) takes a flat `metrics` map plus a
   declared `headline_metric`, and requires only that the headline names a key that is
   present. **Fraud's `average_precision` IS computed (0.0200) and IS present** — what the
   run refuses is the *operating point*, not the metric. So the record is ordinary: real
   metrics, `headline_metric: "average_precision"`, and the refusal carried in
   `execution.resolved_config` as the withheld-costs fact (`cost_fp`/`cost_fn` = None
   because `threshold_reportable` was False). **`NotApplicable` is NOT used** — it marks
   "this field has no meaning for this run kind", and every field here has meaning.
   Fraud counts 5/5, not 4/4-applicable.

2. **Does the dry-run write a record?** — **RESOLVED 2026-08-18: inherit lending Key
   Decision 5.** Dry-run records go to a caller-supplied temp path, never `runs/_index/`.
   Enforced by an assertion in Step 5, not by convention.

3. **Where does the abort-vs-refuse taxonomy get written?** — **RESOLVED 2026-08-18: in
   scope here, as run-local prose (Step 6),** not as a `/proto-harden` gate. Making it a
   standing skill gate is a separate tooling item; writing it down where the only two
   runs that instantiate it live is what stops it being re-argued. Step 6 puts the
   taxonomy in `runs/ml/fraud/README.md` and cross-links lending's `DESIGN-parity.md`
   Key Decision 6, which currently states only the abort half.

4. **Does the dry-run need `runs/ml/fraud/data/` restored?** — **RESOLVED 2026-08-18: no,
   and that is the point.** `--dry-run` builds its frame from a seeded generator and never
   touches `DEFAULT_DATA`. Step 1 asserts the dry-run path does not call `build_frame`.
   The real-CSV path stays unrunnable in this checkout; that is a data-availability fact,
   not a plan gap, and Step 6 states it.

5. **Toolkit-test posture** — **RE-OPENED AND RESOLVED 2026-08-18. The earlier
   "CONFIRMED" rested on a false premise.** It assumed the toolkit is absent from this
   checkout and that skipping is the healthy steady state. Neither holds: `ml/` is a
   **tracked package at the repo root** (36 files under `git ls-files ml/`) and imports
   cleanly with `ML_PACKAGE_ROOT` unset. The gate is a `sys.path` artefact of how pytest
   is invoked, not a statement about what is installed.

   Corrected posture: toolkit-free tests always run; toolkit-importing tests run **too**,
   because the repo root goes on `pythonpath` (Step 3). `ML_PACKAGE_ROOT` remains the
   escape hatch for pointing at a *different* toolkit tree, not the normal path. **0
   skipped is the expected state after Step 3**, so a skip is now a signal rather than the
   baseline — which is why Step 3 also narrows the gate's exception class.

6. **NEW — lending's Step 7 is marked `✓ DONE` but did not land.** Verified 2026-08-18:
   `runs/_index/` does not exist and is untracked; `runs/ml/lending/src/run.py` contains no
   `write_record` call; `runs/ml/lending/tests/test_reproduce.py` does not exist;
   `grep -rn "write_record\|dry_run" runs/ml/lending/src/` returns nothing. The
   `experiments/io.py` serializer AIT#83 delivers exists upstream, so the step was
   *unblocked* — but unblocked was recorded as done. **Assumed default: fraud's Step 7 is
   BLOCKED on `runs/_index/` regardless of lending's status line, and execute must not
   read that `✓ DONE` as a precondition met.** The lending doc's status line needs
   correcting; that is lending's issue, not this one — flagged, not fixed here.

### Approach
**Land Step 3 first** — revised 2026-08-18. Step 3 is now a two-line `pythonpath` and
skip-string fix, independent of everything else, and it is what makes the toolkit
importable so Steps 1, 2 and 4 can be *verified as they land* rather than written blind
against a gate that skips. The original ordering put it third on a premise that turned out
false (it was believed to depend on Step 1's edits to `run.py`; it does not touch `run.py`
at all).

Then the dry-run (Steps 1–2), which makes the refusal reproducible without the real frame —
the whole value of the item, and entirely unblocked. Wire the record's *assembly* next
(Step 4) as a pure function that returns a `RunRecord`, separated from its *persistence*
(Step 5): assembly is testable today against the merged AIT schema, persistence is not,
because `runs/_index/` does not exist. The tradeoff is one extra seam — `build_record()`
returning an object nobody writes yet — accepted because it converts the blocker from
"the record step cannot start" into "one call site is pending a directory".

### Out of Scope
- Restoring `runs/ml/fraud/data/` or running the real-CSV path.
- Any modelling change — no new model, no re-tuning, no change to `MIN_POSITIVES_PER_FOLD`.
- Patching the toolkit. Findings go upstream to `ai-project-template` as issues.
- Fixing lending's false `✓ DONE` on its Step 7, or creating `runs/_index/` itself
  (that is lending's Step 7 to land — see Open Question 6).
- Making the abort-vs-refuse taxonomy a `/proto-harden` gate. Prose only, this run.
- Touching `docs/summary.json` or `docs/before-guard.json` — the committed evidence pair
  is ground truth for 12 existing tests and must not be regenerated.
- `docs/DESIGN.md` (the 922-line data profile) — SKIP per the scout's asset verdicts.

### Steps

#### Step 1: `--dry-run` flag, an argv seam, and a synthetic frame builder
**Files**: `runs/ml/fraud/src/run.py` (lines 121-150 `build_frame`, 234-256 `main`)
**What**: Add `build_synthetic_frame(n_rows, n_positives, seed)` beside `build_frame`,
returning a DataFrame with the same column contract the real frame has (`default` target,
a `uuid` identifier column so the drop path is genuinely exercised, plus numeric and
categorical features). Add `--dry-run` to the parser. In `main()`, branch the frame source
only — every downstream call (`assess_sufficiency`, `run_classification`, `summarise`,
`write_fraud_report`) stays on one path, so the dry-run exercises the real pipeline rather
than a parallel one.

**Two shapes, not one.** The default mirrors the measured frame — 800 rows, 14 positives —
so the dry-run refuses exactly as the real run does. But that shape *always* refuses, so
`main()` passes `cost_fp=None, cost_fn=None` (`run.py:278-279`) and the entire
threshold-formatting branch (`run.py:207-219`) stays dark forever. Expose `--n-rows` and
`--n-positives` so a sufficient shape is reachable too. Verified 2026-08-18: 800/14 →
`min_positives_in_fold=2, threshold_reportable=False`; **1000/200 → `min_fold=40,
threshold_reportable=True`**. Step 2 asserts both.

**The argv seam belongs here, not in Step 2.** `main()` currently takes no arguments and
reads `sys.argv` via `argparse` (`run.py:234`), and there is no `main_with` anywhere in
`runs/ml/` — so a test cannot drive the dry-run without mutating global state. Add
`argv=None` and pass it through to `parse_args`, so Step 2's tests target a real API.
**Snippet**:
```python
# before
def main() -> int:
    ...
    args = parser.parse_args()
    df = build_frame(args.data)

# after — argv seam, then branch the frame source only
def main(argv: list[str] | None = None) -> int:
    ...
    args = parser.parse_args(argv)
    df = (
        build_synthetic_frame(n_rows=args.n_rows, n_positives=args.n_positives, seed=SEED)
        if args.dry_run
        else build_frame(args.data)
    )
```
`build_synthetic_frame` must emit `uuid` as one distinct value per row — dropping it is the
identifier-leakage guard, and a fixture without it would let that guard pass vacuously.
`if __name__ == "__main__": raise SystemExit(main())` keeps working unchanged, since `argv`
defaults to `None` and `parse_args(None)` reads `sys.argv`.
**Test**: `uv run python runs/ml/fraud/src/run.py --dry-run --summary-json /tmp/fraud-dry.json`
(no `ML_PACKAGE_ROOT` needed — the tracked root `ml/` package satisfies the import once
Step 3 lands; before that, invoke from the repo root)
**Done when**: the command exits 0 with no `runs/ml/fraud/data/` present, and
`/tmp/fraud-dry.json` carries `refusal.operating_point_reported: false` with
`min_positives_in_fold` at 2. With `--n-rows 1000 --n-positives 200`, the same command
exits 0 and every model carries a **non-null** `threshold` block.

#### Step 2: dry-run integration test, and the no-real-data assertion
**Files**: new `runs/ml/fraud/tests/test_dry_run.py`
**What**: A toolkit-gated test class (reuse `requires_toolkit` from
`tests/test_summary.py:43-49`, with the corrected reason string from Step 3) covering: the
dry-run produces a summary with the same key set as the committed `docs/summary.json`; two
dry-runs at the same seed produce byte-identical `models` blocks; the refusing shape
(800/14) reports no threshold on any model; **the sufficient shape (1000/200) reports a
non-null threshold on every model** — this is what makes the harness a pipeline test rather
than a single-path replay; and — the load-bearing one — `build_frame` is never called on
the dry-run path, asserted by monkeypatching it to raise.
**Snippet**:
```python
def test_dry_run_never_reads_the_real_csv(monkeypatch):
    monkeypatch.setattr(run, "build_frame", _raises("dry-run touched the real frame"))
    assert run.main(["--dry-run"]) == 0          # argv seam from Step 1, not `main_with`
```
**The RED is mandatory, not optional.** Every test in this file is toolkit-gated, so a test
written against a nonexistent API does not fail — it *skips*, and a skipped file is
byte-identical in output to a correctly-skipped one. Before this step counts as done,
invert the monkeypatch (let `build_frame` run) and watch
`test_dry_run_never_reads_the_real_csv` go **RED**, then restore it. A gated assertion that
has never been observed failing is asserting nothing.
**Test**: `uv run pytest runs/ml/fraud/tests/test_dry_run.py -v`
**Done when**: green from the repo root (Step 3's `pythonpath` makes the tracked `ml/`
importable, so these tests **run** rather than skip — 0 skips, not 4); the no-real-CSV test
has been demonstrated RED once and restored; and `uv run pytest runs/ml/fraud/tests -q`
never reports a silent 0-collected.

#### Step 3: un-skip `TestSummariseFunction` by putting the repo root on `pythonpath`
**Files**: `pyproject.toml` (line 117, `pythonpath`), `runs/ml/fraud/tests/test_summary.py`
(lines 43-49, the `requires_toolkit` skip reason)
**What**: **Cause corrected 2026-08-18 — the original premise was false.** This step
previously asserted the 3 skips exist "only because `run.py` imports `make_splitter` and
`run_classification` at module scope," and prescribed moving those imports into `main()`.
That diagnosis was wrong, and acting on it would have edited `run.py`'s error-handling
structure without un-skipping anything.

The real cause: **`ml/` is a tracked package at the galactus repo root** — 36 files under
`git ls-files ml/`, including `ml/evaluation/splitting.py` and
`ml/workflows/classification.py`. It imports cleanly with `ML_PACKAGE_ROOT` **unset**
(`uv run python -c "import ml.workflows.classification"` → OK). The tests skip because
pytest does not put the invocation cwd on `sys.path`, and `pythonpath`
(`pyproject.toml:117`) lists only the marketing-comms paths. So `_toolkit_available()`
returns False under pytest while the same import succeeds under `python -c`.

Fix: add `"."` to `pythonpath`. **Do not touch `run.py`** — its module-scope imports and
the `try/except ImportError → SystemExit` wrapper are correct as they stand, and that
message is a deliberate UX affordance.

Then fix the skip reason string, which is the proximate cause of the misdiagnosis: it
asserts *"the ML toolkit has no source in this checkout (ml/ holds only stale
`__pycache__`)"*, which is false and is what this plan believed. Replace it with a reason
naming the actual condition (toolkit not importable — set `ML_PACKAGE_ROOT` or ensure the
repo root is on `pythonpath`).

While in that function, **narrow the exception class**. `_toolkit_available()` currently
catches bare `Exception` (`test_summary.py:38-40`), so a syntax error or a bad transitive
import inside the toolkit returns False and reports as a skip rather than a failure —
"broken" and "absent" become indistinguishable. Catch `ImportError` (which covers
`ModuleNotFoundError`) and let every other class propagate.
**Snippet**:
```toml
# before
pythonpath = ["runs/ai/marketing-comms/src", "runs/ai/marketing-comms"]

# after — the repo root carries the tracked `ml/` package
pythonpath = ["runs/ai/marketing-comms/src", "runs/ai/marketing-comms", "."]
```
**Test**: `uv run pytest runs/ml/fraud/tests -q` with `ML_PACKAGE_ROOT` **unset**
**Done when**: **38 passed, 0 skipped** — verified 2026-08-18 by applying this exact
`pythonpath` change alone, with no source edit, then reverting. `TestSummariseFunction`'s
3 tests pass rather than skip, and the skip-reason string no longer claims `ml/` has no
source. Note this also un-skips the toolkit-gated tests generally, which changes Step 2's
expected counts — see the Test Plan.

#### Step 4: `build_record()` — assembly, not persistence
**Files**: new `runs/ml/fraud/src/record.py`; `runs/ml/fraud/src/run.py` (`main()`)
**What**: A pure function `build_record(df, result, verdict, *, seed, n_splits) -> RunRecord`
assembling the four AIT groups. Metrics come from the model list as a flat map; the
headline is `average_precision`, which **is present** — see Open Question 1. The refusal is
recorded in `execution.resolved_config` as the withheld-costs fact, which is the honest
machine-readable form of "no operating point was chosen":
**Snippet**:
```python
return RunRecord(
    code=capture_code_state(RUN_ROOT),               # provenance.py — EXPLICIT repo, never cwd
    data=fingerprint_frame(df),                      # fingerprint.py — frame AS FITTED, post-uuid-drop
    execution=ExecutionConfig(
        seed=seed,
        resolved_config={
            "n_splits": n_splits, "target": TARGET, "sampling": "class_weight",
            "cost_fp": COST_FP if verdict.threshold_reportable else None,
            "cost_fn": COST_FN if verdict.threshold_reportable else None,
            "min_positives_per_fold": MIN_POSITIVES_PER_FOLD,
            "operating_point_reported": verdict.threshold_reportable,
        },
        folds=f"StratifiedKFold(n_splits={n_splits}, seed={seed})",   # a PLAN description, never indices
    ),
    metrics=metrics,                                 # built defensively — see below
    headline_metric="average_precision",
    run_kind="classification",
)
```
**Four traps to hold.** `fingerprint_frame` must receive the frame **after** the `uuid` drop
(record.py:61-71 — the hash covers the frame as fitted); and `resolved_config` must be
JSON-serializable, because `io.write_record` raises rather than coercing with `default=str`
(io.py:86-93). `folds` is a plan string, never per-row indices — indices would be one
identifier per row, which the aggregates-only constraint forbids.

Third: **`capture_code_state()` defaults to `Path.cwd()`** (provenance.py:83), so a bare
call records the provenance of whatever tree the invoker happened to stand in — a foreign
SHA from another checkout, or `NotApplicable` from `/tmp`. Provenance is the record's whole
purpose, and getting it wrong does not raise. Pass `RUN_ROOT` explicitly.

Fourth: **do not use direct attribute access for metrics.** Every existing call site reads
these defensively (`getattr(model.metrics, "average_precision", None)`, `run.py:193`)
because the attribute is not guaranteed. `RunRecord.__post_init__` checks only that the
headline *key is present* (record.py:141-147) — a `None` **value** validates clean and
round-trips through `io.py`, producing a record whose headline metric is null. Build the map
with `getattr` and reject `None` at assembly:
```python
metrics = {}
for m in result.models:
    value = getattr(m.metrics, "average_precision", None)
    if value is None:
        raise ValueError(f"{m.name} carries no average_precision — an unrankable record")
    metrics[m.name] = float(value)
```
**Test**: `uv run pytest runs/ml/fraud/tests/test_record.py -v`
**Done when**: `build_record` returns a valid `RunRecord` from a `SimpleNamespace` fake
(no toolkit needed, so these tests always run), `RunRecord.__post_init__` accepts it, and
a test asserts the record carries no `uuid` and no list longer than the model count. Two
further assertions, because the fake is authored by the same step as the function and
cannot catch either hazard on its own: a model whose `average_precision` is missing raises
rather than producing a null-headline record, and `code.git_sha` matches
`git -C <galactus> rev-parse HEAD` rather than the cwd's. Once Step 1 lands, exercise
`build_record` against a **real** `result` from the dry-run, not only the fake.
**Note**: importing `experiments.*` needs the AIT tree on `sys.path` — same
`ML_PACKAGE_ROOT` mechanism, or a second env var if the two trees differ. Decide at
execute; if it needs a second var, name it and document it rather than overloading
`ML_PACKAGE_ROOT` silently.

#### Step 5: persistence to `runs/_index/` — **BLOCKED on `runs/_index/`**
**Files**: `runs/ml/fraud/src/run.py` (the `io.write_record` call site); new
`runs/ml/fraud/tests/test_reproduce.py`
**What**: **BLOCKED — verified 2026-08-18.** `runs/_index/` does not exist and is
untracked; lending's Step 7, which creates it and its README, is marked `✓ DONE` but did
not land (Open Question 6). The AIT serializer half is *not* the blocker — `io.write_record`
is merged and its signature is known. **Do not create `runs/_index/` from this item**: the
directory carries a README defining the record grain repo-wide, and defining that from the
fraud run would set a cross-run contract from inside one run.
When unblocked: real runs write `runs/_index/{utc_timestamp}-{frame_hash[:8]}.json`;
`--dry-run` writes the same format to a caller-supplied temp path and **asserts the target
is not under `runs/_index/`** (Open Question 2). Reproduce check: two dry-runs at one seed
→ identical `metrics`; `io.read_record(io.write_record(r)) == r` round-trips and re-fires
validation.
**Test**: `ML_PACKAGE_ROOT=<tree> uv run pytest runs/ml/fraud/tests/test_reproduce.py -v`
**Done when**: **not startable this session.** If execute reaches this step and
`runs/_index/` still does not exist: land Steps 1–4 and 6, report the block, do **not**
write a local serializer and do **not** create the directory. Steps 1–4 and 6 are the
deliverable; this step is specified so it is a wiring task when the directory arrives.

#### Step 6: docs — the abort-vs-refuse taxonomy and the dry-run story
**Files**: `runs/ml/fraud/README.md`, `runs/ml/fraud/WALKTHROUGH.md`
**What**: Write down the taxonomy the bar now admits (Open Question 3), so it is inherited
rather than re-argued: **abort** for leakage-class violations — the caller's arguments
contradict the data's shape, continuing produces a number that does not mean what it
claims, and the toolkit raises (`TemporalLeakageError`, `GroupLeakageError`,
`TransformLeakageError`, plus `assert_no_transform_outside_pipeline`); **refuse-and-exit-0**
for sufficiency and structure verdicts — the request is answerable arithmetically but the
answer would not generalise, so the run completes, reports, and withholds the claim.
State the test: *does continuing produce a wrong number, or a right number about too little
evidence?* Wrong number aborts; too little evidence refuses. Then document the dry-run
invocation and its precondition (rendered AIT tree + `ML_PACKAGE_ROOT`), state plainly that
the real-CSV path is unrunnable in this checkout because `data/` is gitignored, and note
that the record step is pending `runs/_index/`.
**Snippet**: cross-link lending's `DESIGN-parity.md` Key Decision 6, which states only the
abort half — a reader who finds that line alone concludes fraud's guard violates the bar,
which is exactly the re-argument this step exists to stop.
**Test**: `grep -rn "dry-run" runs/ml/fraud/README.md && uv run pytest runs/ml/fraud/tests -q`
**Done when**: README states both failure modes with the discriminating test; no stale
claim about the record existing; the suite is still green.

### Test Plan

Counts corrected 2026-08-18. The old table assumed the toolkit was absent and that skips
were the healthy steady state; both are false. With `ml/` tracked at the repo root and
Step 3's `pythonpath` in place, **0 skipped is the expected state** and any skip is a
signal worth reading.

| Layer | Command | Expectation |
|---|---|---|
| Baseline (measured 2026-08-18) | `uv run pytest runs/ml/fraud/tests -q` | 35 passed, 3 skipped |
| After Step 3 (measured 2026-08-18, `pythonpath` alone) | `uv run pytest runs/ml/fraud/tests -q` | **38 passed, 0 skipped** |
| After Steps 1-3 | `uv run pytest runs/ml/fraud/tests -q` | 38 + the new `test_dry_run.py` tests, 0 skipped |
| After Step 4 | `uv run pytest runs/ml/fraud/tests -q` | above + `test_record.py`, 0 skipped |
| Negative control (Step 2) | invert the `build_frame` monkeypatch | `test_dry_run_never_reads_the_real_csv` goes **RED** |
| Determinism | dry-run twice at `SEED` | `models` blocks byte-identical |
| Both verdicts | dry-run at 800/14 and at 1000/200 | refusal has no threshold; sufficient shape has one on every model |
| Aggregates-only | existing `test_artefacts_carry_no_*` | still green; extended to the record in Step 4 |

A skip count above 0 after Step 3 means the gate is masking a real toolkit failure rather
than reporting absence — see Risks. The suite must never report 0 collected either;
`runs/ml/fraud/tests` is already in `testpaths` (`pyproject.toml:100`), and new test files
land in that directory rather than a new one.

### Risks & Rollback

**Commit granularity: one commit per step.** Steps 1 and 3 no longer touch the same file
(Step 3 is now `pyproject.toml` + the skip string), but Step 1 and Step 4 both edit
`run.py`, so the per-step rollbacks below are only available if each step lands as its own
commit. Landing the plan as one commit collapses every rollback into "revert everything."

| Step | Touches | Rollback |
|---|---|---|
| 1 | `run.py` (new function, argv seam, frame branch) | Revert the step's commit. The argv seam is additive (`argv=None` default), so `__main__` behaviour is unchanged and nothing else depends on it. |
| 2 | new `tests/test_dry_run.py` | Delete the file. No other file imports it. |
| 3 | `pyproject.toml` (one list), `test_summary.py` (one string) | Revert two lines. Verified reversible 2026-08-18 — applied, ran, restored to a clean 35/3 baseline. |
| 4 | new `src/record.py`, `run.py` call site | Delete the module; revert the call site hunk. Steps 1–3 and 6 do not depend on it. |
| 6 | `README.md`, `WALKTHROUGH.md` | Docs only — revert the commit. |

- **The synthetic fixture could drift from the real frame's contract**, making the dry-run
  green while the real path breaks. **This risk cannot be closed in this checkout**:
  `runs/ml/fraud/data/` does not exist, so the one path that would falsify the fixture's
  column contract is the one path nothing here can run. Mitigated as far as possible by
  keeping one downstream path (Step 1) and by emitting `uuid` so the drop is genuinely
  exercised — but the dry-run is a harness test, not a claim about the client's data, and
  Step 6 says so.
- **Step 4 assembles against an upstream schema that is merged but unexercised by galactus.**
  If `experiments/` changes shape, `build_record` breaks at import. Contained to one new
  module; Steps 1–3 and 6 are independent of it. Signatures verified 2026-08-18 against the
  merged module: `RunRecord`'s six fields, `capture_code_state`, `fingerprint_frame`,
  `write_record`, `read_record` all match this plan's usage.
- **`_toolkit_available()` swallows every exception** (`test_summary.py:38-40`,
  `except Exception: return False`), so a genuine toolkit breakage — a syntax error, a bad
  transitive import, a renamed symbol — reports as a *skip*, not a failure. The Test Plan's
  counts cannot distinguish "correctly skipped" from "silently broken." Narrow the gate to
  `ImportError`/`ModuleNotFoundError` in Step 3 and let other exception classes propagate.
  This matters more after Step 3, not less: once `pythonpath` makes the toolkit importable,
  a skip is no longer the expected state, so anything still skipping is a signal.
- **Lending's false `✓ DONE`** could lead execute to assume `runs/_index/` exists and
  create it ad hoc, setting a repo-wide contract from inside one run. Step 5 forbids this
  explicitly.
