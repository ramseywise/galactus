# ml-lending parity — reproducible lending harness
Date: 2026-08-15
Status: EXECUTED
Review: pending
Outstanding: Steps 7–8 uncommitted on `GAL-32-lending-parity` (Steps 1–6 committed by Ramsey as 4a40304/6e617e2/b744b46); AIT#83 branch not yet merged upstream — records depend on `experiments/io.py` from `AIT-83-experiments-io`. Review 2026-08-16: verdict `comment`, 11 important findings (see `## Review`).
From: IN_PROGRESS
Track: ml
Epistemic: UNTESTED
Epistemic-by: skipped — branch-only changes with named rollback (no persistent-state or external effect); dry-run is seed-deterministic with a byte-identical reproduce check, so no new probabilistic step feeds downstream; no blocking DoR failure
Epistemic-at: 2026-08-15
Epistemic-findings: 0

Design: [`runs/ml/lending/docs/DESIGN-parity.md`](../../../runs/ml/lending/docs/DESIGN-parity.md)
Frozen config: [`runs/ml/lending/docs/DESIGN.md`](../../../runs/ml/lending/docs/DESIGN.md) § Config for Step 15
GitHub issue: [galactus#32](https://github.com/ramseywise/galactus/issues/32) — branch `GAL-32-lending-parity`.

## Research

### Summary

The parity design is buildable as scoped: the experiments registry is exactly the three
dataclass modules the design assumes (no writer, no loader — verified), the sibling-import
claim holds, and every dry-run pattern it cites has a live precedent in-repo. The one open
decision — serializer placement — resolves decisively toward `experiments/io.py` in
ai-project-template on evidence the design did not have: the template already owns a
versioned-JSON-with-validating-loader idiom (`ml/persistence.py`), and galactus#5 (W&B
reads the local run registry) is a *queued second consumer*, making the format-fork cost of
a galactus-side writer concrete rather than hypothetical. One finding contradicts the
design: `report.html` is not gitignored — it is tracked on `main` and load-bearing (the
fraud run's tests use it as their ground-truth fixture), while three documents claim
otherwise.

### Scope

Investigated: the experiments registry (`record.py`, `provenance.py`, `fingerprint.py` +
tests) in ai-project-template; `run.py`'s current structure and import mechanism; galactus
test/dependency posture for an in-suite dry-run; gitignore/data-handling state after the
`ml-lending/` → `runs/ml/lending/` rename; issue state in both repos; dry-run and
fixture-twin precedents. Out of scope (per DESIGN-parity): the three toolkit findings'
fixes, any modelling change, other `runs/ml/` runs, the six client unknowns.

### Findings

**F1 — The registry has no serializer, and the template already knows how it writes one.
(High)** `experiments/` is `record.py` (147L), `provenance.py` (109L), `fingerprint.py`
(85L), empty `__init__.py`; no json/dump/load code anywhere in the module or its 16 tests
(verified by grep). But the template's own IO idiom already exists:
`{{ ml_source_root }}/persistence.py` writes a JSON metadata sidecar with a
`SCHEMA_VERSION` and a loader that **raises** on mismatch (`SchemaMismatchError`). An
`experiments/io.py` with the same shape — versioned JSON, tagged `NotApplicable`
round-trip, validate-on-read — is squarely in the template's established vocabulary, not a
new invention.

**F2 — Validation-on-load comes free if the loader reconstructs the dataclasses. (High)**
`ExecutionConfig.__post_init__` rejects bare-`None` seed/folds and
`RunRecord.__post_init__` enforces `headline_metric ∈ metrics`
(`experiments/record.py`). A loader that rebuilds the frozen dataclasses (rather than
returning a dict) re-triggers those checks on every read — which is precisely the
"loader-side validation exercised in tests" row of DESIGN-parity's Evaluation table. The
only serializer-specific work is the `NotApplicable` tagged representation and restoring
`DataIdentity.columns` to a tuple.

**F3 — A second consumer of the record format is already queued. (High)** galactus#5,
open since 2026-08-11: "W&B experiment tracking — reads the local run registry." Key
Decision 3's stated cost of a galactus-side writer ("the format forks the moment a second
consumer appears") is not hypothetical — the second consumer is in the backlog of the same
repo.

**F4 — `report.html` is tracked, load-bearing, and three documents say it is gitignored.
(High)** `git ls-files` shows `runs/ml/lending/docs/report.html` on `main` (32K,
committed in a253d94, path-renamed in d46b61b). The gitignore rule that was meant to
cover it still reads `ml-lending/docs/report.html` (line 37) — anchored patterns stopped
matching at the 2026-08-15 rename. It cannot simply be `git rm --cached`'d:
`runs/ml/fraud/tests/conftest.py:19-24` uses it as "the only real
`ml.reporting.html.write_report` output committed anywhere in this repo" — the
ground-truth fixture for fraud's report-injection tests. Meanwhile `run.py:21-23`,
DESIGN-parity's Out list ("report.html stays as-is, still gitignored"), and the gitignore
comment ("Derived from real data is still real data") all assert it is ignored. The repo
is private (verified via `gh repo view`), which mitigates but does not resolve.

**F5 — The stale gitignore block is wider than the report. (Medium)** Lines 34-35
(`ml-lending/data/`, `!ml-lending/data/.gitkeep`) are dead after the rename. The real CSV
is currently protected only by the catch-all `*.csv` (line 48, verified with
`git check-ignore -v`); any **non-CSV** file dropped into `runs/ml/lending/data/` would be
tracked. The fraud run got updated rules at the new path; lending did not.

**F6 — The sibling-import claim verifies. (High)** `experiments/` sits directly under
`{{ py_project_root }}` and `{{ ml_source_root }}` renders to `ml` under the same root
(`__init__.py` at its top level), so one `ML_PACKAGE_ROOT` makes both importable, as
DESIGN-parity's System Context asserts. No second env var needed.

**F7 — The What-Breaks-First mitigation is already implementable with existing registry
API. (High)** `capture_code_state(repo: Path | None)` takes an explicit repo argument and
returns `NotApplicable(reason)` when the path is not a git repo — so calling it a second
time pointed at the `ML_PACKAGE_ROOT` tree captures the toolkit's own SHA with zero new
registry code. Precedent for wanting this: the fraud run pins its toolkit by branch +
commit in prose (`runs/ml/fraud/src/run.py` docstring, "pinned at commit `0f8b2cf`") —
the record can carry what fraud had to write by hand.

**F8 — Dependency posture: the dry-run can fit in-venv; the toolkit cannot. (High)**
galactus's `ml` dependency group carries pandas, scikit-learn, catboost (no lightgbm —
verified by import). So a "tiny fast model set" dry-run fits the venv, but
`run_classification`, `make_splitter`, `write_report`, and `experiments.*` all arrive via
`ML_PACKAGE_ROOT` — a clean checkout of galactus alone cannot run the dry-run or any test
that imports toolkit code. The fraud precedent handles this by keeping unit tests
toolkit-free (synthetic fixtures, `runs/ml/fraud/tests/conftest.py`); nothing in-repo yet
demonstrates a toolkit-importing test. The POC demo target's "clean checkout" therefore
implicitly includes a rendered template tree + env — a precondition the plan must state
rather than inherit silently.

**F9 — No AIT issues exist for any of this. (High)** ai-project-template's open-issue
list is empty: the three Step 15 toolkit findings (DESIGN-parity Open Question 4) and the
serializer work item are all unfiled.

**F10 — `run.py` refactor surfaces are clean. (Medium)** The 437-line script already
separates label construction (`build_frame`), split verification (`build_split_plan` +
`_PrecomputedFolds`), and aggregation (`summarise`) as functions; `main()` is the only
place that composes them. The module-level constants are the profile-doc-as-code and move
intact. The refactor is extraction, not redesign.

### Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `experiments/` registry (AIT) | REUSE | — | Shape consumed as-is per Key Decision 2; `__post_init__` validation doubles as load-time validation (F2) |
| `ml/persistence.py` (AIT) | ADAPT | — | Not imported — its idiom (SCHEMA_VERSION, sidecar JSON, raising loader) is the template for `experiments/io.py` (F1) |
| `capture_code_state` / `fingerprint_frame` | REUSE | — | Called as-is; second `capture_code_state(repo=toolkit_root)` call covers the toolkit-SHA mitigation (F7) |
| `runs/ml/lending/src/run.py` | ADAPT | — | Extract modules from existing seams (F10); constants survive verbatim |
| `runs/ml/fraud/tests/` pattern | ADAPT | — | Toolkit-free unit tests over synthetic fixtures; conftest sys.path insert; the nearest ML-test precedent in-repo (F8) |
| marketing-comms `evals/run.py --dry-run` | ADAPT | — | The bar itself: scripted adapter, full path, cases that fight the contract; pattern only, no code shared |
| `review/tests/fixtures/leaky_pipeline.py` + `clean_pipeline.py` | ADAPT | — | The fixture-twin precedent DESIGN-parity Decision 5 cites; shape reused for clean/planted-leak frames |
| `/proto-harden` skill | REUSE | — | Post-execute hardening checklist for run dirs; slots between execute and review, no changes needed |
| lending `report.html` as fraud fixture | SKIP | Yes — a committed *synthetic* report (dry-run output at a pinned toolkit SHA) could replace it as fraud's ground truth | Out of this item's scope to fix, but F4 entangles it: any resolution of the tracked report must not silently break `runs/ml/fraud/tests` |
| Old gitignore lending block | SKIP | Yes — two-line path fix (`runs/ml/lending/...`) restores intent | Stale since the rename (F5); the fix is trivial and belongs in this item's first step |

### Assumptions

- **Assumption:** The rendered template tree Ramsey points `ML_PACKAGE_ROOT` at includes
  `experiments/` alongside `ml/`. — **Evidence:** `_scaffold` layout (F6); not verified
  against the actual rendered tree, whose location this research did not find recorded. —
  **If wrong:** record assembly fails at import; fix is re-rendering the template. —
  **Confidence:** Medium.
- **Assumption:** `run_classification`'s result object exposes enough to build
  `metrics: dict[str, float]` without toolkit changes. — **Evidence:** `summarise()`
  already extracts PR-AUC/ROC-AUC/Brier per model from `result.models`
  (`run.py:308-373`). — **If wrong:** record assembly needs a toolkit accessor — an AIT
  change this item excluded. — **Confidence:** High.
- **Assumption:** A dry-run restricted to venv-available models (logistic; optionally
  catboost) still exercises the full harness path meaningfully. — **Evidence:** F8; the
  registry "skips" mechanism exists (`result.skipped` in `summarise()`). — **If wrong:**
  lightgbm joins the `ml` dependency group — one `uv add`. — **Confidence:** Medium.
- **Assumption:** AIT can absorb the `experiments/io.py` item promptly. — **Evidence:**
  empty open-issue backlog, merges dated 2026-08-15 (F9). — **If wrong:** the galactus
  item stalls on a cross-repo dependency; fallback is re-sequencing so harness+tests land
  first and record-writing lands second. — **Confidence:** High.

### Disconfirming Evidence

- **F1/F3 (AIT-side serializer):** The strongest counter-case would be the registry shape
  still churning (a galactus-side throwaway writer would then be cheaper to keep in sync).
  Checked: `record.py` is stable, docstring-complete, with 16 passing-shaped tests and two
  explicitly argued load-bearing decisions — churn evidence absent. Second counter-case:
  AIT too slow to sequence. Checked: backlog empty, PR #82 merged 2026-08-15 (F9).
- **F4 (report should be untracked):** The counter-case is that committing it was a
  *deliberate* revision of the aggregates-only position — fraud's conftest treats it as
  the only available toolkit ground truth, which reads as an intentional dependency.
  Looked for a recorded decision: none found in either DESIGN doc, the gitignore comment
  (which still argues the opposite), or commit messages. The contradiction is real either
  way; which side is wrong is Ramsey's call.
- **F6 (sibling import):** Counter-case: copier conditionally excludes `experiments/` for
  some configurations. Not checked against `copier.yaml`'s conditional rules — flagged in
  the first assumption rather than resolved.
- **Track routing:** Could this be `agent`-track (it is harness/infra work, no new model)?
  No — the deliverable *fits models* (the dry-run trains, calibrates, and thresholds; the
  real run reproduces Step 15), and the failure mode the work guards against is the
  ML-shaped one (a confident metric nobody checked). `ml` per the fitting-is-the-tell
  rule.

### Key Unknowns

1. **Baseline metric (mandatory until closed in plan).** Named before computation, per the
   track contract: the reproduction target is the frozen Step 15 table — logistic
   **PR-AUC 0.4213** (primary metric, prevalence floor 0.2056), `beats_baseline` honestly
   `False`-shaped (0.0002 margin). For the dry-run fixtures the baseline must be recomputed
   on the synthetic frame and *named in the fixture spec before the first run* — a
   synthetic frame that accidentally makes the tiny model look strong is the graded-on-its-
   own-curve failure.
2. **Leakage-check status: RED, named in advance.** The run currently *applies* the
   39-column exclusion but never *asserts* it — no guard fails if an excluded column
   re-enters the fitted frame, and the ≥0.95 single-feature-AUC alarm exists only as prose.
   What would leak and how: any `LEAKAGE_COLUMNS` member surviving into
   `run_classification`'s frame (the planted-leak fixture plants exactly this), and
   `group_key` re-entering as a feature (the toolkit-gap workaround regressing). Stays red
   until guards (a)–(d) of the MVP exist and the planted-leak dry-run asserts the abort.
3. **Serializer placement** — evidence assembled (F1, F2, F3, F9), decision is Ramsey's;
   see Recommendation. Blocks `/proto-plan` per DESIGN-parity Open Question 1.
4. **Demo-environment precondition** — what "clean checkout" includes (F8): rendered
   toolkit tree location, and whether toolkit-importing tests skip-with-reason or fail
   when `ML_PACKAGE_ROOT` is unset. A skip that reads as green is the zero-collected
   hazard in miniature; the plan must pick a posture explicitly.
5. **`report.html` resolution** (F4) — untrack + synthetic replacement fixture for fraud,
   or ratify the commit and correct the three documents. Either is coherent; silence is
   not. History exposure (32K of distributional detail since a253d94) is a separate call:
   private repo, rewrite-vs-accept is Ramsey's.
6. **`DESIGN.md` name collision** (DESIGN-parity Open Question 2) and **record-file
   naming** (Key Decision 8) — both deferred to `/proto-plan` by design; unchanged.

### Recommendation

Resolve Key Decision 3 as the design recommends — **`experiments/io.py` in
ai-project-template** — now with evidence beyond taste: the template already owns the
versioned-JSON-raising-loader idiom this needs (`ml/persistence.py`), dataclass
reconstruction gives load-time validation for free, and galactus#5 is a queued second
consumer that makes the fork cost of a galactus-side writer real. Sequence it as: file the
AIT issue (plus the three Step 15 toolkit findings, also unfiled) before `/proto-plan`
freezes steps, and let the plan treat the serializer as an upstream dependency with the
harness/tests/guards steps ordered to proceed without it. Fold into the plan's first step
the two hygiene fixes this research surfaced: the stale lending gitignore block and an
explicit position on the tracked `report.html` — the parity item's data-handling claims
are false until one of them lands.

---

## Research addendum — the other ML runs (2026-08-15)

Fan-out over `runs/ml/fraud/`, `runs/ml/customer segmentation/`, `runs/ml/credit/`, and
`runs/ml/LTV.ipynb`, each scored against the same five-element bar (tests-in-`testpaths`,
dry-run, guards, run record, data handling). Purpose: ratify or revise Key Decision 1
("one run to the bar first") with evidence, and inventory the follow-on work.

Full scout reports: [`../research/2026-08-15_ml-parity_fraud.md`](../research/2026-08-15_ml-parity_fraud.md),
[`_segmentation`](../research/2026-08-15_ml-parity_segmentation.md),
[`_credit`](../research/2026-08-15_ml-parity_credit.md),
[`_ltv`](../research/2026-08-15_ml-parity_ltv.md). This section is the synthesis;
the reports carry the full evidence and per-file citations.

### Scoreboard

| Run | Tests | Dry-run | Guards | Record | Data handling | Net |
|---|---|---|---|---|---|---|
| lending (this item) | absent | absent | partial — exclusion applied, never asserted | absent | **broken** — `report.html` tracked | ~0.5/5 |
| fraud | **met** (35 pass, `pyproject.toml:96`) | absent | **met** — `sufficiency.py` pure/deterministic/tested | absent | **met** — only run whose gitignore survived the rename | 3/5 |
| customer segmentation | **met** (49 pass, `pyproject.toml:97`) | absent | partial — 4 rules + twins, but refuse-not-abort; rule (b) is a constant `True` | absent | met for CSVs/docs; **gap: tracked third-party PDF** | 2.5/5 |
| credit | absent | absent | absent | absent | half — CSV caught by `*.csv` only | 0/5 |
| LTV.ipynb | absent | absent | absent | absent | **violated** — committed outputs carry real-data aggregates | 0/5 |

### Per-run findings

**Fraud — closest to the bar, and one premise of DESIGN-parity is stale. (High)** Its 35
tests are in `testpaths` (added 2026-08-15, after the design was drafted) and pass; its
sufficiency guard (`runs/ml/fraud/src/sufficiency.py`) is pure, reads the *minimum* fold
rather than the mean, and is the strongest guard implementation in the repo. Missing only
the dry-run and the record — and its headline is a **refusal**
(`refusal.min_positives_in_fold: 2`, PR-AUC ≈ prevalence floor, thresholds withheld), not
a model-comparison metric, so element 4 is arguably *inapplicable* rather than missing: a
RunRecord would register numbers the run itself disclaims. Fraud pins its toolkit by
branch+commit in prose (`AIT-67`, `0f8b2cf`) — better than lending, still unenforced.

**Customer segmentation — mechanically close, conceptually blocked. (High)** Modular
src, 49 substantive tests, four leakage rules with clean/dirty twins, and
`docs/segments.json` is already ~80% of a record payload (input hashes, verdicts, sweep,
chosen k — missing git SHA and canonical shape). It uses galactus's own venv (no
`ML_PACKAGE_ROOT`), so the What-Breaks-First toolkit-pinning risk does not apply — but
importing `experiments.*` would introduce that coupling for the first time. The blocker
is shape, not code: a k-means sweep has no held-out metric and no fold plan;
`RunRecord` is built for supervised comparison, and extending the shape is
ai-project-template's call, never galactus's.

**Credit — not a run; a prototype split across two trees. (High)** `runs/ml/credit/` is
one ignored CSV plus two *empty* directories; the actual prototype (README with real
findings, EDA notebook, `run.py`) is tracked at `pocs/ml/credit/` — on `main`, verified —
where `data/` does not exist. Each half lacks what the other has. `pocs/` also
contradicts CLAUDE.md's runs-layout rule, and `prototype-genesis/SKILL.md` still points
at `pocs/` paths. Its headline is an **anti-finding** (14 positives / 800 rows: fold
variance dwarfs model differences — "does not produce a trustworthy model"), already
recorded in prose. Reaching the bar needs a `git mv` reunification, then an operator
interview (label horizon, splitter, cost ratio — three deliberately-undefaulted gate-1a
items), then harness work. Data provenance is an unpinned copy from a private
`~/workspace/lebanese-blonde/` path.

**LTV.ipynb — not a parity candidate; a data-handling and honesty problem. (High)** A
Python 3.7 fragment of a private employer repo: imports (`utils.*`, Redshift/S3 helpers)
and data (`Data/*.csv`) that exist nowhere here; ~50 of 83 cells empty; one cell
committed with a live `NameError`. The headline claim (ML 23% vs cohort-mean 33%
weighted percentage error) is **unfalsifiable from the artifact**: the evaluation scores
forecast columns pre-baked into the input CSV — the models fitted in the notebook are
never wired into it — and the four cohort-eval cells reference undefined variables and
mislabel their months. Committed outputs violate the repo's own aggregates-only rule:
model-fit aggregates over real financial records, an 88-column production DWH schema
dump, a live external Google Sheets URL, and employer infrastructure identifiers. Salvage
is real but narrow: the scoping prose (named consumer, decision, 2-year horizon), the
~250-line feature taxonomy with its blacklist discipline, the revenue/cost decomposition
pattern, and the WPE metric *definition* — everything else is retype-cheaper-than-port.

### Cross-cutting findings

**X1 — The report.html coupling is a two-way trap. (High)** Confirmed independently by
the fraud scout: `runs/ml/fraud/tests/conftest.py:22-25` uses lending's tracked
`report.html` as the only real toolkit-markup fixture for 17 injection-anchor tests.
Fixing lending's gitignore/untracking the report breaks fraud's suite; leaving it keeps
tracked real-data-derived content. The fix must land as one sequenced change: generate a
synthetic replacement fixture (a dry-run report at a pinned toolkit SHA), retarget
fraud's `upstream_report` fixture, then untrack.

**X2 — The bar's guard semantics conflict with two runs' deliberate stance. (High)**
Lending's Key Decision 6 says guards **abort**; fraud and segmentation both **refuse and
exit 0** ("a run that refuses is not a run that failed"), loudness carried in the payload
and asserted by tests. This is a design decision, not a gap: either the bar admits two
failure modes (abort for leakage-class violations, refuse for sufficiency/structure
verdicts — the semantically honest split), or two runs change documented stances.

**X3 — "Record-worthiness" is the real axis, and it ratifies Key Decision 1. (High)**
Lending is the only run whose headline is a refutable trained-model metric comparison.
Fraud's is a refusal (record inapplicable), segmentation's is an internal-validity sweep
(record shape doesn't fit), credit's is an anti-finding in prose, LTV's is unverifiable.
Every path to a second record runs through decisions lending forces anyway (serializer,
`_index` layout) plus, for segmentation, an AIT shape question. Sequencing lending first
is confirmed with stronger evidence than the design had.

**X4 — The data-handling sweep found three tracked-content issues beyond lending's.
(High)** (a) `Trade Republic_Data Science Challenge.pdf` — a third party's live
recruiting assessment, tracked, uncovered by any rule; the run's docstring already
restates the framing, so untrack + short prose summary loses nothing. (b) LTV.ipynb's
committed outputs (above). (c) Credit's CSV protected only by the `*.csv` catch-all, no
path rule, no `.gitkeep`, provenance unpinned. All are operator calls (untrack vs
ratify), and all predate this work item.

### Asset verdicts (addendum — merged from scouts)

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `fraud/src/sufficiency.py` | REUSE | — | Pure, deterministic, min-fold, no toolkit dep; directly liftable pattern for other runs |
| `fraud/src/run.py`, `report.py` | ADAPT | — | Needs `--dry-run` + record assembly; module-scope `ml.*` import forces 3 test skips; report anchors need decoupling from lending's report.html (X1) |
| `fraud/tests/` (35) + fixtures | REUSE | — | `test_report.py` fixture retarget is the one ADAPT (X1) |
| `segmentation/src/` (load/features/prepare/cluster) | REUSE | — | Guards + baselines-in-same-call are the portable ideas; fix rule (b)'s constant `True` |
| `segmentation/src/run.py` | ADAPT | — | Add argparse/dry-run/record; `segments.json` payload is ~80% of a record already |
| `segmentation/tests/` (49) | REUSE | — | conftest synthetic generators are the ready dry-run substrate |
| Trade Republic PDF | SKIP | Yes — untrack; 3–5-line prose summary in a run README (currently absent) preserves the framing | Third-party assessment instrument, tracked, contributes nothing to the bar |
| `pocs/ml/credit/{README,notebooks,src}` | ADAPT | — | Working gate-3 script + real findings; needs `git mv` to `runs/ml/credit/` (relative `data/` path survives the move); two hardcoded restore-hint paths go stale |
| `runs/ml/credit/src|notebooks` (empty dirs) | SKIP | Yes — the move above fills them at cost of one `git mv` | `total 0`; nothing exists to assess |
| `runs/ml/credit/data/` | ADAPT | — | Real content, ignored only via `*.csv`; needs path rule + `.gitkeep` + pinned provenance |
| LTV scoping prose + feature taxonomy (cells 0, 5) | ADAPT | — | Seed of a future DESIGN.md + config module; strip the external URL |
| LTV model/eval/infra cells | SKIP | Yes — WPE metric definition (~15 lines) and three-way TRAIN/TEST/BASELINE report shape (~10 lines) are worth retyping; nothing else | Evaluation scores pre-baked columns, not its own models; infra is another organization's; ~60% of cells are empty |
| LTV committed outputs | SKIP | No — remove; restate the 23%-vs-33% numbers in prose *with* the unverified caveat | Real-data aggregates + employer DWH schema, the exact class the repo's gitignore excludes elsewhere |

### Addendum recommendation

Key Decision 1 is ratified with better evidence than it was made on: lending first, and
alone, in this work item. The addendum changes the follow-on map, not this plan:

1. **A repo-hygiene item, separable and urgent-ish** (`bug/` branch scale): the four
   tracked-content issues (lending report.html — sequenced with fraud's fixture per X1 —
   Trade Republic PDF, LTV outputs, stale gitignore block). All predate this item;
   bundling them into lending's plan would double its scope with work that isn't parity.
2. **Fraud and segmentation become small follow-ons once lending lands** — each needs
   only dry-run wiring plus record assembly, and each inherits the serializer and
   `_index` layout lending drives out. Fraud additionally needs an answer to "what does a
   record of a refusal carry?", segmentation to "does the shape admit unsupervised
   runs?" — both AIT questions, worth filing alongside the serializer issue.
3. **Credit is a reunification + operator interview**, not a parity item yet.
4. **LTV needs a disposition decision** (strip-and-keep-as-exhibit vs mine-and-drop),
   independent of parity.
5. **The bar itself needs one amendment** before it is applied beyond lending: guard
   semantics split abort vs refuse (X2).

### Skill-gate coverage for Track: ml

The AI track has gates at every band: design (`/proto-scope`, `/proto-design`), deliver
(BUILD + `/proto-review`), deploy (`/proto-harden`, whose checklist is the
marketing-comms hardening list). The ML track has research-stage tools (`/ml-transform`,
`/ml-select`) and a review dimension (`review-leakage`) but **no deliver/deploy gate
encoding**: the parity bar exists only as prose in one run's DESIGN-parity.md. Gaps, in
the order they bite:

1. **`/proto-harden` needs an ML checklist variant.** The five-element bar *is* that
   checklist (tests-in-`testpaths`, dry-run twins, guards, record + reproduce check,
   data-handling sweep). Encoding it in the skill turns "bring a run to the bar" from a
   bespoke design item into a standing gate every future ML run hits — which is what the
   Actors table's "this run is the template" promise actually requires.
2. **Guard-semantics taxonomy belongs in the checklist, not in each run's head**: abort
   for leakage-class violations (lending Decision 6), refuse-and-exit-0 for
   sufficiency/structure verdicts (fraud/segmentation stance). X2 resolved once,
   inherited everywhere.
3. **The ML "deploy" gate is the record**: for a training harness, deploy-readiness =
   RunRecord written + reproduce procedure documented + registry consumption possible —
   not Cloud Run packaging. `/proto-review`'s DoD assessment for `Track: ml` should ask
   for it once the registry lands.
4. **Doc-naming convention** (Open Question 2 generalized): `PROFILE.md` = data profile,
   `DESIGN.md` = system design, for every ML run — fraud has the same collision lending
   flagged.
5. **`prototype-genesis` still points at `pocs/` paths** — stale since the runs/ move;
   fix rides the credit reunification.

---

## Plan
Date: 2026-08-15
Based on: `## Research` + `## Research addendum` above, plus direct inspection of
`run.py`, `.gitignore`, `pyproject.toml`, fraud's `conftest.py`, and AIT's
`experiments/{record,provenance,fingerprint}.py`.

### Goal
Make the Step 15 lending finding mechanically reproducible — a tested, dry-runnable
harness whose runs write `RunRecord`s to `runs/_index/`, so a second person can refute or
reproduce "nothing beats the logistic baseline (PR-AUC 0.4213)" from the record alone.
(Confirmed by Ramsey, 2026-08-15.)

### Open Questions
Resolved by Ramsey 2026-08-15 unless marked as a plan default:

1. **Serializer placement** — RESOLVED: `experiments/io.py` in ai-project-template,
   filed as [AIT#83](https://github.com/ramseywise/ai-project-template/issues/83).
   Upstream dependency; Step 7 is blocked on it, Steps 1–6 are not. No galactus-side
   interim writer — a workaround would de-facto define the format (Key Decision 3).
2. **`report.html`** — RESOLVED: **ratify the commit.** Keep it tracked; correct the
   three documents claiming it is gitignored (Step 1). This also dissolves addendum X1:
   fraud's `upstream_report` fixture keeps its ground truth. History exposure accepted
   (private repo); no rewrite.
3. **`DESIGN.md` name collision** — RESOLVED: keep as-is, no rename.
4. **Toolkit-test posture** (plan default, flag at refine if wrong): fraud pattern —
   unit tests for `frame`/`guards`/fixtures are toolkit-free and always run;
   toolkit-importing tests (`splits`, dry-run, record) `pytest.skip` with an explicit
   reason naming `ML_PACKAGE_ROOT` when it is unset. The demo's "clean checkout"
   precondition (rendered AIT tree + env) is stated in README, not inherited silently (F8).
5. **Record file naming** (plan default): `{utc_timestamp}-{frame_hash[:8]}.json`,
   Key Decision 8's stated default. Dry-run records go to a temp path, never
   `runs/_index/` (Key Decision 5 / Open Question 3 default).
6. **Toolkit findings** — filed as
   [AIT#84](https://github.com/ramseywise/ai-project-template/issues/84) (group_col),
   [AIT#85](https://github.com/ramseywise/ai-project-template/issues/85) (beats_baseline),
   [AIT#86](https://github.com/ramseywise/ai-project-template/issues/86)
   (choose_threshold). Worked around, never patched locally (design Out list).

### Approach
Extract `run.py`'s existing seams into toolkit-free modules first (F10), so guards and
label logic get real unit tests inside galactus's venv; everything toolkit-coupled
(split plan, dry-run execution, record assembly) rides `ML_PACKAGE_ROOT` behind
skip-with-reason tests, mirroring fraud. Record persistence is last and blocked on
AIT#83, so the harness/tests/guards land value even if the upstream item slips.
Tradeoff accepted: the dry-run itself needs the rendered toolkit tree (F8) — a bare
galactus checkout runs the unit suite green with visible skips, not the full path.

### Out of Scope
- The three toolkit defects (AIT#84–86) — worked around via `splitter=` and
  `SELECTED_IN_SAMPLE` disclosure, not fixed here.
- Any modelling change; the Step 15 config is frozen.
- Other `runs/ml/` runs — fraud/segmentation follow-ons, credit reunification, LTV
  disposition are the addendum's follow-on map, not this item.
- The repo-hygiene sweep (Trade Republic PDF, LTV committed outputs, credit data rules)
  — separable `bug/` item per addendum recommendation 1. Only the *lending-scoped*
  hygiene (stale gitignore block, report.html doc ratification) lands here.
- Backfilling records for past runs; the first record is the next execution.
- The X2 bar amendment (abort vs refuse) — lending aborts (Key Decision 6); the
  cross-run policy is follow-on.

### Steps

#### Step 1: Lending hygiene — stale gitignore block + report.html ratification ✓ DONE — 2026-08-16
**Files**: `.gitignore` (lines 32–38), `runs/ml/lending/src/run.py` (lines 17–23),
`runs/ml/lending/docs/DESIGN-parity.md` (line 100)
**What**: Fix the dead `ml-lending/` paths (F5): `ml-lending/data/` →
`runs/ml/lending/data/` (+ matching `!…/.gitkeep`). Replace the
`ml-lending/docs/report.html` ignore line with a comment recording the ratification:
tracked deliberately since a253d94 as fraud's ground-truth toolkit fixture
(`runs/ml/fraud/tests/conftest.py:25`), private repo. Correct the DATA HANDLING
paragraph in `run.py`'s docstring and DESIGN-parity's Out list ("stays as-is, still
gitignored" → tracked-and-ratified, dated).
**Snippet**:
```
- ml-lending/data/
- !ml-lending/data/.gitkeep
- ml-lending/docs/report.html
+ runs/ml/lending/data/
+ !runs/ml/lending/data/.gitkeep
+ # runs/ml/lending/docs/report.html is TRACKED, ratified 2026-08-15: it is the only
+ # real write_report output in the repo and fraud's tests pin markup against it.
```
**Test**: `git check-ignore -v runs/ml/lending/data/x.txt` names the new rule;
`grep -rn "still gitignored" runs/ml/lending/` returns nothing.
**Done when**: no gitignore rule references `ml-lending/`; all three documents state the
tracked-and-ratified position; `git status` shows no newly-untracked surprises.

#### Step 2: Extract modules along the existing seams; tests dir + `testpaths` ✓ DONE — 2026-08-16
**Files**: `runs/ml/lending/src/run.py` (constants 72–165 → `frame.py`; `build_frame`
168–229 → `frame.py`; `_PrecomputedFolds` + `build_split_plan` 232–305 → `splits.py`;
`summarise` 308–373 → `summary.py`); new `runs/ml/lending/tests/conftest.py`,
`tests/test_frame.py`; `pyproject.toml` (testpaths list, ~line 97)
**What**: `frame.py` holds every Step 14 constant (verbatim — profile-doc-as-code) plus
the frame logic, **split at the CSV boundary** so fixtures can enter without a file:
`prepare_frame(df)` (label, survivorship drop, group key, column drops — pure pandas)
and a thin `load_frame(csv_path)` wrapping `pd.read_csv` + the existence guard.
`splits.py` keeps the toolkit imports (`make_splitter`, `SplitPlan`,
`assert_no_group_leakage`) and the LK-002 row-count guard unchanged. `summary.py` takes
`summarise` (imports `COST_FP/COST_FN` from `frame`). `run.py` keeps the docstring, the
`ML_PACKAGE_ROOT` import guard, argparse, and `main()` composing the modules. Fraud's
conftest `sys.path.insert` pattern (`conftest.py:18-19`) carries over. Add
`"runs/ml/lending/tests"` to `testpaths` **in this step** — the repo rule exists because
omission reads as passing.
**Snippet**:
```python
# frame.py — the CSV seam
def prepare_frame(df: pd.DataFrame) -> pd.DataFrame:   # pure; fixtures enter here
def load_frame(csv_path: Path) -> pd.DataFrame:        # read_csv + SystemExit guard
    return prepare_frame(pd.read_csv(csv_path, low_memory=False))
```
**Test**: `uv run pytest runs/ml/lending/tests -q` — label construction (both status
sets), unresolved-row drop count, group-key composition, drop-list behaviour when a
column is absent; all toolkit-free.
**Done when**: lending tests collected >0 under bare `uv run pytest`; `run.py` is
composition-only (~120 lines); full suite shows no new failures beyond the 6
pre-existing `review/tests/test_validate.py` ones.

#### Step 3: `guards.py` — deterministic leakage guards that abort ✓ DONE — 2026-08-16
**Files**: new `runs/ml/lending/src/guards.py`; `runs/ml/lending/src/run.py` (wiring in
`main()`); new `runs/ml/lending/tests/test_guards.py`
**What**: Four guards per MVP (a)–(d), Key Decision 6 semantics: **raise `GuardError`
naming the offending columns**, never warn. (a) `assert_excluded_absent(df)` — no member
of `LEAKAGE_COLUMNS + IDENTIFIER_COLUMNS + FREE_TEXT_COLUMNS + LABEL_SOURCE_COLUMNS +
GROUP_SOURCE_COLUMNS` (minus `TARGET`/`GROUP_COL` mechanics) present in the frame headed
to fit. (b) `single_feature_auc_alarm(df, target, threshold=0.95, allowlist=())` —
per-numeric-column ROC-AUC via sklearn on rank-comparable columns; a column over
threshold and not allowlisted aborts (the allowlist friction is the feature). (c) is
`assert_no_group_leakage`, already called in `build_split_plan` — unchanged, noted as
guard (c) in the docstring. (d) `final_metric_alarm(metrics, threshold=0.95)` — any
model ROC-AUC over threshold after `run_classification` aborts. Wire (a)+(b) in `main()`
between `prepare_frame` and `build_split_plan`; (d) after the fit. Toolkit-free module
(pandas + sklearn are in the `ml` dependency group).
**Snippet**:
```python
class GuardError(SystemExit):  # abort, not warn — a warning in a long log is silent failure
    ...
def assert_excluded_absent(df: pd.DataFrame) -> None:
    present = [c for c in EXCLUDED for-fit-columns if c in df.columns]
    if present: raise GuardError(f"excluded columns present in fitted frame: {present}")
```
**Test**: `uv run pytest runs/ml/lending/tests/test_guards.py -v` — planted excluded
column → raises naming it; target-copy column → AUC alarm trips; allowlisted column →
passes; clean tiny frame → all guards pass; metric alarm trips at 0.96, passes at 0.94.
**Done when**: all four guard paths have a tripping test *and* a passing twin (the
positive path is what makes the guard real — Phase C rule); guards import without
`ML_PACKAGE_ROOT`.

#### Step 4: Synthetic fixture twins — clean + planted-leak ✓ DONE — 2026-08-16
**Files**: new `runs/ml/lending/src/synthetic.py`; `runs/ml/lending/tests/conftest.py`
(fixtures); new `runs/ml/lending/tests/test_synthetic.py`
**What**: Seeded generator producing a schema-shaped frame (~400–800 rows): `loan_status`
mixing resolved/unresolved values, `emp_title`/`zip_code`/`annual_inc` for the group key,
a numeric feature block, prevalence near the real 20.56% so `sampling="class_weight"`
stays on the same code path. `clean_frame(seed)` passes every guard;
`planted_leak_frame(seed)` is the twin plus (i) a `LEAKAGE_COLUMNS` member surviving into
the frame and (ii) a near-copy-of-target column for the AUC alarm — the fixture-twin
precedent (`review/tests/fixtures/leaky_pipeline.py`). **Baseline named before the first
run (Key Unknown 1):** the module docstring states the fixture spec — synthetic
prevalence *is* the PR-AUC floor the dry-run's logistic must be compared against;
`beats_baseline` on synthetic data is asserted against that floor, never against 0.4213.
**Test**: `uv run pytest runs/ml/lending/tests/test_synthetic.py -v` — same seed → equal
frames (pandas `assert_frame_equal`); `prepare_frame(clean_frame())` passes guards;
`prepare_frame(planted_leak_frame())` trips (a) and (b) with the planted names in the
message.
**Done when**: both twins deterministic; guard trip/pass asserted through the *real*
`prepare_frame` path, toolkit-free.

#### Step 5: `--dry-run` — the full path on the clean twin ✓ DONE — 2026-08-16
**Files**: `runs/ml/lending/src/run.py` (argparse + `main()`); new
`runs/ml/lending/tests/test_dry_run.py`; `runs/ml/lending/README.md` (precondition)
**What**: `--dry-run` short-circuits `load_frame`: clean twin in-process →
`prepare_frame` → guards → `build_split_plan` → `run_classification` with
`models=["logistic"]` (venv-available; catboost optional later — no lightgbm, F8) →
calibrate → threshold → summarise → record assembly (Step 6) written to a temp path.
No network, no `data/` read, seconds. The planted-leak twin is exercised from tests, not
the CLI: invoking the dry-run path with it must abort via `GuardError` naming the
columns. Toolkit-importing tests skip-with-reason per Open Question 4's posture;
README's RUNNING IT section states the precondition: dry-run and toolkit tests need
`ML_PACKAGE_ROOT` at a rendered AIT tree (which renders `experiments/` as a sibling of
`ml/` — verify with `python -c "import experiments.record"` once, F6/Assumption 1).
**Snippet**:
```python
parser.add_argument("--dry-run", action="store_true",
    help="synthetic frame, tiny model set, record to a temp path; no data/, no network")
df = synthetic.clean_frame(SEED) if args.dry_run else load_frame(args.data)
```
**Test**: `ML_PACKAGE_ROOT=<tree> uv run pytest runs/ml/lending/tests/test_dry_run.py -v`
and `ML_PACKAGE_ROOT=<tree> uv run python runs/ml/lending/src/run.py --dry-run`
**Done when**: dry-run exits 0 in a checkout with no CSV; planted-twin abort asserted;
with `ML_PACKAGE_ROOT` unset the suite stays green with the toolkit tests visibly
skipped (reason names the env var).

#### Step 6: Record assembly — in-memory `RunRecord`, validated ✓ DONE — 2026-08-16
**Files**: new `runs/ml/lending/src/run_record.py` (named to avoid shadowing
`experiments.record` on the conftest `sys.path`); `runs/ml/lending/src/run.py` (call in
`main()`); `runs/ml/lending/tests/test_record.py`
**What**: `assemble_run_record(result, fitted_df, args) -> RunRecord`:
`capture_code_state(repo=<galactus root>)` for `code`; a **second**
`capture_code_state(repo=Path(os.environ["ML_PACKAGE_ROOT"]))` whose SHA/dirty go into
`resolved_config["toolkit"]` — the What-Breaks-First mitigation, zero new registry code
(F7); `fingerprint_frame(fitted_df)` for `data` (the frame as fitted, post-drops, minus
`GROUP_COL`/`TARGET` handling exactly as passed to `run_classification`);
`ExecutionConfig(seed=SEED, resolved_config=<post-parse, post-default merge — including
the module constants>, folds=<SplitPlan projected to kind/n_splits/reason — a plan
description, never indices>)`; `metrics` as a flat map (per-model `pr_auc`/`roc_auc`/
`brier` keys plus the prevalence floor), `headline_metric` naming the logistic PR-AUC
key; `run_kind="classification"`. Dataclass `__post_init__` gives validation free (F2).
Per Key Decision 2: a `NotApplicable` for seed or folds in *this* record is a bug — a
classification run has both.
**Test**: `ML_PACKAGE_ROOT=<tree> uv run pytest runs/ml/lending/tests/test_record.py -v`
— record builds from a dry-run result; `headline_metric ∈ metrics`; `git_sha` is a real
SHA; `resolved_config["toolkit"]` carries the toolkit SHA; constructing with `seed=None`
raises (regression pin on the registry contract).
**Done when**: dry-run produces a valid in-memory `RunRecord`; no bare `None` and no
`NotApplicable` in seed/folds; assembly test green.

#### Step 7: Persistence to `runs/_index/` + reproduce check — **UPSTREAM: AIT#83** ✓ DONE — 2026-08-16 (unblocked same day: `experiments/io.py` landed on AIT-83-experiments-io)
**Files**: `runs/ml/lending/src/run.py` (write call); new `runs/_index/README.md`; new
`runs/ml/lending/tests/test_reproduce.py`
**What**: **Blocked until AIT#83 lands `experiments/io.py`** — then: real runs write
`runs/_index/{utc_timestamp}-{frame_hash[:8]}.json` via `io.write_record`; dry-runs write
the same format to the temp path (Step 5 already routes this). Create `runs/_index/` with
a README stating the grain (one record per training execution — a different grain from
the run directory; records are committed, Key Decision 7: aggregates only, `folds` is a
plan description). Reproduce check per the Evaluation table: execute the dry-run path
twice at the same seed → `metrics` blocks byte-identical; round-trip
`io.read_record(io.write_record(...))` reconstructs the dataclasses and re-fires
validation. If AIT#83 has not landed when execute reaches this step: **stop here, land
Steps 1–6, report the block** — do not write a local serializer.
**Test**: `ML_PACKAGE_ROOT=<tree> uv run pytest runs/ml/lending/tests/test_reproduce.py -v`
**Done when**: dry-run record round-trips load→validate; double-execution metrics
identical; a real-run invocation (documented, not executed in tests) targets
`runs/_index/`.

#### Step 8: Docs parity — README, WALKTHROUGH, and the record story ✓ DONE — 2026-08-16
**Files**: `runs/ml/lending/README.md`, `runs/ml/lending/WALKTHROUGH.md`,
`runs/ml/lending/src/run.py` (docstring RUNNING IT)
**What**: Document what now exists: the module layout, the dry-run invocation and its
precondition (rendered tree + `ML_PACKAGE_ROOT`; skip posture), the record flow
(where records land, how to diff two records, and the What-Breaks-First reading: a diff
showing only `code.versions`/`toolkit` changed is the system *working*), and the
reproduce procedure for the real frame (same SHA + same `frame_hash` → identical
metrics). Sweep for stale claims (grep for "gitignored", "no tests", old paths).
**Test**: `grep -rn "gitignored" runs/ml/lending/docs runs/ml/lending/README.md
runs/ml/lending/src/run.py` shows only ratified/correct statements; full suite green.
**Done when**: a reader can run the dry-run and interpret a record diff from the docs
alone; no document contradicts the tracked-report or tests-exist reality.

### Test Plan
- **Baseline**: 568 passed / 6 failed (`review/tests/test_validate.py`, pre-existing,
  untouched by this item — must still be exactly those 6 at the end).
- Toolkit-free (always run, bare checkout): `test_frame.py`, `test_guards.py`,
  `test_synthetic.py` — the guard and label logic never depend on `ML_PACKAGE_ROOT`.
- Toolkit-coupled (skip-with-reason when env unset): `test_dry_run.py`,
  `test_record.py`, `test_reproduce.py`.
- Gate per step is its `**Test**` line; the item's exit gate is the POC demo target:
  `uv run pytest runs/ml/lending/tests -q` green (with visible, reasoned skips in a bare
  checkout) and `run.py --dry-run` exit 0 with no `data/` read.

### Risks & Rollback
- **AIT#83 slips** → Steps 1–6 land independently; Step 7 blocks loudly (no local
  writer). Fallback already sequenced (research Assumption 4).
- **Rendered tree lacks `experiments/`** (Assumption 1, Medium) → checked cheaply at
  Step 5 (`import experiments.record`); fix is re-rendering the template, not plan
  surgery.
- **Synthetic frame flatters the tiny model** → Step 4 names the synthetic prevalence
  floor in the fixture spec *before* the first run; assertions compare against it, never
  0.4213.
- **Concurrent edits to this doc** — an addendum landed mid-planning; execute sessions
  should re-read the doc header before trusting line numbers in Steps 1–2.
- **Branch/issue gate**: session is currently on `bug/marketing-comms-review-fixes`;
  execute must start from a fresh `GAL-{N}-lending-parity` branch off `main` with the
  galactus issue created at branch time (plan-doc header rule).
- **Rollback**: all changes ride the branch; nothing touches other runs except the three
  ratification doc lines (Step 1), which are additive comments/corrections. Soft-reset
  per session hygiene; `runs/_index/` is new, so removal is clean.

---

## Review
Date: 2026-08-16
Verdict: **comment** (computed via `review.cli verdict`; no blockers, 11 important)
Scope: full (feature branch + plan doc). Diff scoped to the lending work item —
`main...HEAD` also carries ~30 marketing-comms files from GAL-31, excluded as
out-of-item.

### 1. Overall Understanding

The eight steps landed as designed. `run.py` is composition-only, the extraction split at
the CSV boundary so fixtures enter without a file, four guards abort via
`GuardError(SystemExit)`, the twins are seed-deterministic, and record assembly plus
persistence exist. Full suite: **600 passed, 14 skipped, 0 failed** — better than the
plan's Test Plan baseline, which budgeted for 6 pre-existing `review/tests/test_validate.py`
failures that commits on this branch fixed. Lint clean.

The verdict is `comment` rather than `approve` because of one structural fact: **the 14
skipped tests are Steps 5–7's entire coverage, and no environment where they run has ever
existed on this machine.** The harness is well-built; what is unproven is that it works.

### 2. Plan Fidelity

| Step | Code shows | Tests | Status |
|---|---|---|---|
| 1 hygiene | `.gitignore` 34–38 rewritten to `runs/ml/lending/`; ratification comment present | `git check-ignore` verified | Match |
| 2 extraction | `frame/splits/summary.py` split at the CSV seam; `testpaths` includes lending | 25 pass bare | Match |
| 3 guards | four guards, all raise `GuardError` | (a)(b)(d) trip+pass; **(c) has no tripping test** | Deviation (TE-001) |
| 4 twins | `synthetic.py` clean + planted-leak, seeded | deterministic asserted | Match |
| 5 dry-run | `--dry-run` short-circuits `load_frame`; temp report | **skipped everywhere** (TE-004) | Match, unverified |
| 6 record | `run_record.py`, second `capture_code_state` for toolkit SHA | **skipped** | Match, unverified |
| 7 persistence | `experiments.io.write_record`, `runs/_index/README.md`, reproduce check | **skipped** | Match, unverified |
| 8 docs | README/WALKTHROUGH/docstring updated | grep sweep incomplete | Deviation (AR-001/2/3) |

No stubs, no `NotImplementedError`, no `TODO` on a critical path.

### 3. What Looks Strong

- **Guard abort semantics are honest.** `GuardError` subclasses `SystemExit`; every guard
  raises naming the offending columns. Key Decision 6 is implemented, not just documented.
- **The twins do real work.** The planted-leak frame trips guard (b) through the *real*
  `prepare_frame` path, and the tests state plainly that plant (i) cannot survive an intact
  `prepare_frame` by construction rather than faking a trip.
- **Record payload is aggregates-only, verified end to end.** `fingerprint_frame` emits
  digest/counts/column-names; `folds` is a plan string, never indices. Key Decision 7 holds.
- **The skip posture is disclosed, not hidden** — reasons name `ML_PACKAGE_ROOT`.
- **Baseline named before computation.** The synthetic prevalence floor is in the fixture
  spec and asserted against, never 0.4213.

### 4. Important Findings

**SF-001 (safety) — dry-run can clobber the tracked real report.** `run.py:207` guards with
`report_path == DEFAULT_REPORT`, comparing *unresolved* `Path`s. Verified by execution:
`Path("runs/ml/lending/docs/report.html") != DEFAULT_REPORT` is `True` while `.resolve()`
shows they are the same file. So `--dry-run --report runs/ml/lending/docs/report.html`
overwrites the ratified real-data report — which `runs/ml/fraud/tests/conftest.py:25` uses
as ground truth for 17 injection-anchor tests — with synthetic markup, and drops a stray
record JSON beside it. Fix: compare `.resolve()`.

**TE-004 (testing) — the 14 skipped tests have never executed.** Confirmed: `ML_PACKAGE_ROOT`
is unset, no rendered `experiments/` tree exists anywhere under `~/workspace`, and AIT holds
only unrendered jinja. Steps 5–7 — the dry-run exit gate, record validation, round-trip,
tamper detection — carry zero executed evidence.

**IN-001 (intent) — the AIT#83 precondition is stronger than documented.** AIT#83 is *closed*
but its branch is **unmerged**: `AIT-83-experiments-io` has 4 commits absent from AIT `main`,
which sits at PR #82. A reader following the README renders from `main`, gets no
`experiments/io.py`, and every run dies at module-scope import. No doc names the branch.

**SI-001 (silent_failure) — a broken tree skips as green.** `_toolkit_available` catches all
exceptions, so a *configured-but-broken* `ML_PACKAGE_ROOT` (the plan's own Assumption 1
failure mode) produces the same 600/14 output as a healthy bare checkout. The plan sanctions
skipping only when the var is *unset*.

**SI-002 (silent_failure) — guard (d) can silently disarm.** `getattr(m.metrics, "roc_auc",
None)` plus per-model `None`-tolerance means an upstream rename maps every model to `None`
and the final-metric alarm checks nothing while the run exits 0.

**LK-001 (leakage) — the AUC alarm is blind to its primary target's dominant shape.** Guard
(b) masks to `notna()` and skips single-class columns, and never scores missingness itself.
A column populated only for charged-off borrowers — exactly the settlement/hardship shape
`frame.py` documents — is skipped unscored. Fix: also score `series.notna().astype(int)`.

**CR-001 (correctness) — `beats_baseline` is recorded as a bound method.** Upstream changed
it from `@property` to a method taking a tolerance; `summary.py:29` stores it uncalled, so
`default=str` serializes a repr. The run's headline honesty question becomes unanswerable
from its own artifact, and no test asserts the field.

**TE-001 / TE-003** — guard (c) has no tripping test (Step 3's Done-when is unmet), and
`summary.py` is toolkit-free by design yet has no always-run tests.

**AR-001 / AR-002 (architecture, docs)** — `CLAUDE.md:69` still reads "Nothing writes here
yet … the lending baseline could be overturned but not reproduced", which this diff falsifies;
`README.md:19` still opens "**Framing only — no data, no model**" above sections documenting
the harness and run records. The Step 8 sweep missed both.

### 5. Suggestions and Nits

CR-002 `result.baseline` unguarded; LK-002 scan is numeric-only; TE-002/TE-006 untested pure
logic; SF-002 records embed operator-local absolute paths; AR-003 WALKTHROUGH self-contradicts;
AR-004 imports private `_NOT_APPLICABLE_KEY` across the repo boundary; AR-005 `synthetic.py`
re-derives the label rule; PF-001 full-frame drop computed twice. Nits: TE-005 skip reasons
misname their family, TE-007 missing assertion, AR-006 `run_record.py` absent from layout docs,
AR-007 dead `.gitkeep` negation, IN-002 stray `uvicorn` dep.

### 6. Definition of Done Assessment

| Item | Status | Note |
|---|---|---|
| Tests | gap | 25 real; Steps 5–7 covered only by never-executed tests (TE-004) |
| Lint | met | `ruff check` clean |
| Doc parity | gap | AR-001, AR-002, AR-003, IN-001 |
| Config | met | constants are profile-doc-as-code, moved verbatim |
| Errors | gap | SI-001, SI-002 |
| Seam conformance | met | toolkit-free/coupled split holds |
| Runnable demo | **unproven** | `--dry-run` has never been observed to run |
| Reversibility | met | branch-only; `runs/_index/` is new |

### 7. Dimension Dispatch Table

| Dimension | Status | Findings |
|---|---|---|
| intent | dispatched | 2 |
| correctness | dispatched | 2 |
| silent_failure | dispatched | 2 |
| testing | dispatched | 7 |
| safety | dispatched | 2 |
| architecture | dispatched | 7 |
| performance | dispatched | 1 |
| runtime | skipped (no agent-framework import or agent path in the changed files) | 0 |
| safeguards | skipped (no agent-framework import or agent path in the changed files) | 0 |
| contracts | skipped (no SANYI.md in the repo) | 0 |
| leakage | dispatched | 2 |
| plan-fidelity | ran | 2 deviations |
| lint/tests | ran | pass (600/14 skip/0 fail; ruff clean) |

Bounded corrective round: not entered — no agent-system signal surfaced.
`detect-signals` activated 8 of 11; injection hits: none.

### 8. Workspace Hygiene

- `worktrees/GAL-31-deploy-harden` has **uncommitted changes** and shares commit `0c63a5e`
  with this branch — `important`.
- No `worktree-agent-*` branches, no stale `: gone]` tracking branches — clean.

### 9. Merge Verdict

**comment** — the harness matches the plan and the code is sound where it is proven, but
Steps 5–7 rest on tests that have never executed, one path can overwrite a tracked
real-data fixture (SF-001), and four documents contradict the state the diff creates.
