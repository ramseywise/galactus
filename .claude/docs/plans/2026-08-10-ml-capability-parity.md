# ML capability parity — tabular ML readiness across galactus and ai-project-template

Status: IN_PROGRESS
Date: 2026-08-10
Prefix: GAL

<!-- 2026-08-14: corrected PLANNED → IN_PROGRESS, and Prefix GUA → GAL.

     Status. Phases A–C have landed; Phase D has not, so neither PLANNED nor
     EXECUTED is right. Verified on the filesystem:
       - Phase A/B (template `ml/`): all 11 subpackages present, including
         `workflows/` — selection, transform, sampling, evaluation, reporting,
         feature_engineering, model_comparison, clustering, regression,
         stats_testing, timeseries.
       - Phase C: `.claude/skills/ml-select/` and `ml-transform/` exist;
         `review-leakage` is registered as code, not convention — `LEAKAGE =
         "leakage"` on the `Reporter` enum (review/models.py:94) with prefix `LK`
         (review/models.py:110), and `is_ml_code` drives activation in
         review/signals.py:212-247, which is what Step 10 specified.
       - Phase D: open. No `enam/ml/run.py`, no `enam/docs/DESIGN.md`.
         `GUA-2-enam-baseline` exists only as a remote branch with no local work.
         Still blocked on Open Question 8 (the six ENAM domain unknowns) and on
         real data, exactly as the Phase D header states.

     Prefix. Per the prefix rule — prefix = repo being changed, not where the issue
     lives — this doc's galactus work is `GAL-`, not `GUA-`. `GUA` predates the GAL
     prefix. Phase C's and Phase D's branch names are corrected in place below;
     Phase A/B keep `AIT-` because they target ai-project-template, which is
     correct as written.

     Note the count drift, which is a real divergence from the plan but not a
     defect: Phase C's Done-when predicts `test_prefix_map.py` green at ten
     dimensions, and the reporter set is now **eleven**. `.claude/skills/` holds
     twelve `review-*` directories — the eleven dimensions plus `review-shared`,
     which test_prefix_map.py excludes as a non-dimension. The eleventh,
     `review-performance` (prefix `PF`), is fully registered and was added after
     this plan was written: `PERFORMANCE = "performance"` on the `Reporter` enum,
     `"PF"` in `REPORTER_ID_PREFIX`, matching `prefix: PF` frontmatter, and listed
     in `_ALWAYS_ON` (review/signals.py:191) — so seven always-on dimensions and
     four conditional (runtime, safeguards, leakage, contracts). `uv run pytest
     review/tests -q` is green at 88 passed, test_prefix_map.py included. Read the
     Done-when's "ten" as the count at planning time, not as a current target. -->


## Context

The ENAM case study is tabular ML, not agentic. Neither the galactus skill pipeline nor
the `ai-project-template` ML scaffold is ready for it. This document records what exists,
what is missing, and the recommended strategy — so the capability is built once, in the
same shape as the agentic tooling, rather than improvised per project.

The framing artifact for the case study itself is [`enam/README.md`](../../../enam/README.md).

---

## Research

### Finding 1 — the skill pipeline has no ML-shaped phase, and the gap is specific

The galactus pipeline (design → research → plan → refine → execute → review) is
**domain-neutral in its spine and agentic in every leaf**. 30 skills, 13 specs. The spine
transfers to ML unchanged; the leaves do not.

What is missing is not "an ML skill." It is that **the pipeline has no phase where the
data is interrogated before the plan is written.** In the agentic pipeline, `/workflow-research`
answers questions about *the system to be built*. In ML the dominant risk lives in *the
data you were handed*, and it is discovered by looking, not by reasoning. Planning an ML
project before profiling the data produces a plan against an imagined dataset.

The nine `review-*` reporters encode agentic failure modes (silent failure, contracts,
runtime, safety). The tabular-ML equivalents — leakage, imbalance, calibration drift,
train/serve skew — have **no reporter**. This is the highest-leverage gap, because these
failures are exactly the kind the repo's own thesis targets: they are *silent*. A leaked
feature does not raise an error. It returns AUC 0.97 and reads as success.

`/design-prototype quick-start` (the time-boxed spike mode) is the closest existing fit
and transfers well — its stage table is already the right shape. It needs an ML variant
of stages 4–5, where "the failing test that defines done" becomes a baseline metric and a
leakage check rather than a unit test.

### Finding 2 — the template's `ml/` toolkit is a statistics library, not an ML pipeline

`template/_scaffold/{{ py_project_root }}/{{ ml_source_root }}/` — 1,539 lines across six
modules (regression, timeseries, stats_testing, feature_engineering, model_comparison,
clustering). The code quality is good and the docs are honest. It is genuinely useful for
*discovery*.

It is not a delivery path. Verified by grep across the whole subtree:

| Capability | Present | Notes |
|---|---|---|
| Baseline comparison | ✅ | `compare_classifiers` — LR / RF / LightGBM on shared CV folds |
| Feature importance | ✅ | MI, correlation, permutation |
| Interpretable regression | ✅ | RFE logit + coefficient significance |
| Lag/rolling/calendar features | ✅ | Time-series oriented |
| **Probability calibration** | ❌ | No `CalibratedClassifierCV`, no Brier, no reliability curve |
| **Class imbalance handling** | ❌ | No `class_weight`, `scale_pos_weight`, or resampling |
| **Leakage detection** | ❌ | One comment about cross-series lag leakage; no target-leakage check |
| **Temporal / grouped splitting** | ❌ | `StratifiedKFold` only — no `TimeSeriesSplit`, no `GroupKFold` |
| **Model persistence** | ❌ | No joblib/save/load — nothing leaves the process |
| **Inference path** | ❌ | No predict entry point; train and serve cannot share code |
| **Drift / monitoring** | ❌ | Absent |
| **CatBoost** | ❌ | LightGBM only, and it is an optional import |
| **Threshold selection** | ❌ | No cost-based decision rule — the step that turns a score into an action |

Two structural observations:

- **The global ML ref already mandates several of these** (`~/.claude/refs/ml.md`:
  "wrap all preprocessing + model in sklearn `Pipeline` — prevents data leakage",
  "`CalibratedClassifierCV` for calibrated probability outputs", "save artifacts with
  joblib"). **The rules exist; the scaffold does not implement them.** This is precisely
  the `CLAUDE.md` anti-pattern the repo names — a rule that lives only in prose is
  probabilistic. Closing this gap is mostly *implementing conventions already written*.
- The ref says "no pandas in ML code — Polars in, numpy to sklearn." The template's `ml/`
  is **pandas throughout**. Atlas is Polars. This is a live contradiction between the ref
  and the scaffold that needs deciding, not inheriting.

Notable and useful: `model_comparison/compare.py` documents that `TabularPreprocessor`
was genericized from *"a real, deployed LightGBM credit-scoring pipeline"* — the nearest
existing prior art to ENAM, already in the template.

### Finding 3 — atlas is the strongest ML asset and is not reusable as-is

~4,100 lines of real ML: `core/preprocessing/` (541-line `Preprocessor` with
fit/transform/inverse, outlier treatment, stationarity, scalers), `core/segmentation/`
(algorithms, evaluation, naming), `core/preprocessing/features.py` (446 lines, Polars).

Two things matter here:

- **It is a genuine parity reference.** `features.py` exists in *both* atlas (Polars, 446
  lines) and the template (pandas, 240 lines) with overlapping function names —
  `add_lag_features`, `mutual_information_importance`, `permutation_importance`,
  `build_feature_matrix`. The template version is a pandas port of the atlas one. Fixing
  the gap should consolidate, not fork a third copy.
- **Its shape is forecasting/segmentation, not supervised classification.** Preprocessing
  is time-series-centric (stationarity, differencing). Useful primitives, wrong spine.

**On the bandit:** atlas has one — `src/agents/learner/rl_interface.py` with tests at
`tests/src/agents/learner/test_bandit.py`, plus `evals/comparison_learner.py`. It is an
*agent learner* interface, not a tabular ML asset. It is genuinely interesting for ENAM,
but as **phase three**, not phase one: a bandit allocates *actions* (which channel, when
to escalate) and only becomes tractable once a calibrated propensity score exists and
outcomes are logged. Reaching for it first would be solving the policy problem before the
prediction problem.

### Finding 3b — listen-wiseer already solves half the "missing" list (harvest, not build)

Discovered after Finding 2 was written, and it **downgrades the phase-2 estimate
substantially**. `listen-wiseer/src/recommend/` is 3,496 lines of production ML — GMM
clustering + LightGBM/CatBoost reranking, Polars-native, sklearn `Pipeline`-wrapped.

Capability grep against the phase-2 gap list:

| Capability | Template | listen-wiseer | Location |
|---|---|---|---|
| CatBoost | ❌ | ✅ | `modules/classifiers.py`, `train.py` |
| Probability calibration | ❌ | ✅ | `CalibratedClassifierCV` + Brier in `classifiers.py` |
| Class imbalance | ❌ | ✅ | `class_weight="balanced"` / `auto_class_weights="Balanced"` |
| Model persistence | ❌ | ✅ | `save_classifier` / `load_classifier` (joblib) |
| Train/serve shared code | ❌ | ✅ | `engine.py` loads what `train.py` saved |
| Model comparison harness | partial | ✅ | `train.compare_models` — side-by-side, writes metrics JSON |
| Clustering + quality metric | partial | ✅ | GMM + KMeans, silhouette in `train.py` |
| Metrics reporting | ❌ | ✅ | `MetricsWriter` → `models/metrics/` |
| Sampling (SMOTE/under/over) | ❌ | ❌ | absent both — genuinely new |
| Leakage-safe splitting | ❌ | ❌ | no `GroupKFold`/`TimeSeriesSplit` either |
| PR curves / average_precision | ❌ | ❌ | ROC-AUC only; no PR-AUC |
| DBSCAN | ❌ | ❌ | GMM/KMeans only |
| Drift monitoring | ❌ | ❌ | absent both |

Two patterns are directly liftable and should anchor the toolkit's shape:

- **`_create_estimator(model_type, ...)`** (`classifiers.py:103`) — a factory returning an
  unfitted estimator per model name, all params in the constructor so `sklearn.clone`
  works. This is exactly the registry the model-selection matrix needs; extend it with a
  family dimension rather than inventing a new abstraction.
- **`compare_models(...)`** (`train.py:329`) — trains each candidate on identical data,
  logs side-by-side metrics, writes JSON, and **does not save models** ("informational
  only"). The templated per-family workflow is a generalisation of this function.

**Consequence:** phase 2 is substantially *extract and generalise*, not *write from
scratch*. The pandas/Polars question (open question 7) is now the one real friction —
listen-wiseer and atlas are Polars, the template is pandas.

### Finding 4 — the modelling strategy question is settled by evidence

**CatBoost first, and this is a conclusion rather than a preference.** Current benchmarks
(TabArena; the 2026 gradient-boosting comparative analysis) find CatBoost's advantage
*"most pronounced on mixed-type and categorical-heavy datasets, where native categorical
handling and ordered boosting delivered decisive wins"* — which is exactly the shape of a
collections dataset. Tabular foundation models (TabPFN-3, TabICLv2) now lead single-model
Elo by ~240 points, **but CatBoost moves back ahead of neural approaches without
multi-configuration ensembling** — and it is cheaper to interpret, deploy, and defend to
a regulator.

**BERT is the wrong tool for the primary model.** It earns a place only if free-text
exists (call notes, agent transcripts). Then the correct move is to encode text into a
few features feeding the tree model — not to replace the tabular model.

**Logistic regression is the mandatory baseline**, not a formality: it is the
explainability floor for a regulated domain, and if boosting cannot beat it meaningfully,
that is a real finding about feature quality.

**Domain framing.** The literature is consistent that *ability to pay* (can they?) and
*propensity to pay* (will they, now?) are distinct targets with distinct features. A model
that conflates them ranks the wealthy above the willing and sends collections effort to
people who would have paid anyway. Also flagged early: if historical collection actions
are in the data, a naive propensity model learns "accounts we chased, paid" and recommends
chasing everyone — the correct target may be **uplift**, not propensity.

### Finding 5 — the binding constraint is a decision rule, not a model

This is the finding that makes ENAM fit galactus rather than sit beside it.

`ml6/`'s thesis: *counting characters is a job for code; the model's job is content.* The
validator is a pure function, and the model's cooperation is an optimisation rather than
a dependency.

The tabular analogue is exact. **A ranked score is not a decision.** The threshold that
converts a probability into "call this person" is arithmetic over the cost of a wasted
contact versus the cost of a missed collectable account — a business input, not a
hyperparameter. That makes calibration a correctness property rather than a nicety: if a
cost-based threshold consumes the output, 0.7 must mean roughly 70% pay, or the arithmetic
is computed on a number that does not mean what it says.

So ENAM's binding constraint is **calibration + a deterministic decision rule**, mirroring
ml6's validator. Both case studies then say the same thing in two domains: *the model
produces the content; deterministic code owns the decision.*

---

## Recommended strategy

### Principle

Build the ML capability **in the shape of the existing agentic tooling** — same pipeline
spine, same enforcement ladder (hook > linter > test > tool schema > instruction), same
"reporters catch silent failures" pattern. Do not build a parallel ML process.

### Sequencing

**Phase 1 — the reporter and the profiling phase (highest leverage).**
The gap that costs the most is silent ML failure. Two additions:

- A `review-leakage` reporter joining the existing nine — target leakage, temporal leakage,
  group leakage, train/serve skew. This is the ML analogue of `review-silent-failure`,
  and the same argument justifies it: no findings must not be indistinguishable from
  clean. Heuristics are mechanical enough to be largely deterministic (suspiciously high
  AUC, features correlated with the target above a threshold, post-outcome column-name
  patterns, fit-before-split ordering).
- An ML variant of `/design-prototype quick-start`, inserting a **data profiling stage
  before planning** — profile, then plan. Reuses the existing stage table; changes stages
  4–5 so "the failing test that defines done" is a baseline metric plus a passing leakage
  check.

**Phase 2 — close the template's delivery gap.**
Implement the conventions `~/.claude/refs/ml.md` already mandates: calibration, imbalance
handling, leakage-safe splitting (`TimeSeriesSplit` / `GroupKFold`), sklearn `Pipeline`
wrapping, joblib persistence, an inference entry point sharing code with training, and
cost-based threshold selection. Add CatBoost alongside LightGBM. Resolve the
pandas/Polars contradiction explicitly rather than inheriting it.

**Phase 3 — ENAM as the proving run, and the bandit if it earns its place.**
Build the case study with the new skills, which is also how they get tested. The bandit
(contact-strategy allocation) becomes tractable only after a calibrated score and logged
outcomes exist.

### Ordering note

Phase 1 before phase 2 is deliberate. The reporter and the profiling stage are what make
phase 2's library *correct*; a library built without a leakage check is a faster way to
produce a confidently wrong model.

---

## Open questions

Blocking for ENAM modelling, not for phases 1–2:

1. Label definition and horizon (30/60/90 days; full settlement vs. any payment).
2. The decision the score feeds — this sets the metric.
3. Cost asymmetry — wasted contact vs. missed collectable account.
4. Whether historical collection actions are present (propensity vs. uplift).
5. Time structure — cohort dates, regime changes.
6. Regulatory explainability posture.

Blocking for phase 2:

7. ~~**pandas or Polars for the template's `ml/`?**~~ **RESOLVED 2026-08-10 — pandas.**
   Operator decision. The toolkit is pandas-in / numpy-to-sklearn, matching the existing
   template `ml/` rather than atlas and listen-wiseer.

   Two consequences to carry into the plan, neither blocking:
   - `~/.claude/refs/ml.md` currently says *"No pandas in ML code — Polars in, numpy
     arrays to sklearn."* That line now contradicts the decision and must be amended, or
     the ref becomes a rule the scaffold knowingly violates.
   - Harvesting from listen-wiseer (Finding 3b) now costs a Polars→pandas port at the
     boundary. The *logic* (estimator factory, calibration, comparison harness) is
     frame-agnostic; only the I/O edges change.

---

## Sources

- [TabArena: A Living Benchmark for Machine Learning on Tabular Data](https://openreview.net/forum?id=jZqCqpCLdU)
- [Gradient Boosting Revisited: Comparative Analysis on Real-World Tabular Data](https://www.sciencepublishinggroup.com/article/10.11648/j.mlr.20261101.14)
- [Are Tabular Foundation Models Ready to Replace Gradient Boosting Models?](https://pub.towardsai.net/are-tabular-foundation-models-ready-to-replace-gradient-boosting-models-cb039b955162)
- [A Survey on Tabular Data: From Tree-based Methods to Tabular Deep Learning](https://dl.acm.org/doi/10.1145/3807777)
- [Propensity-to-Pay: Machine Learning for Estimating Prediction Uncertainty](https://arxiv.org/pdf/2008.12065)
- [Machine learning for predicting propensity-to-pay energy bills](https://www.sciencedirect.com/science/article/pii/S2667305323000017)
- [Debt Collection Model for Mass Receivables Based on Decision Rules](https://www.mdpi.com/2071-1050/16/14/5885)
- [What Is the Propensity to Pay in Debt Collection?](https://colektia.com/en/blog/propensity-to-pay)

---

## Plan
Date: 2026-08-10
Based on: `## Research` above (Findings 1–5, incl. 3b)

### Goal

Give the pipeline a **model-selection spine** — pick the family and output shape, then run
a templated workflow that transforms, samples, trains, calibrates, evaluates, and reports —
so ENAM is executed with tooling rather than improvisation, and every later tabular project
inherits the same path.

### Open Questions

Resolved in this session (2026-08-10), listed first because they shape every step:

1. ~~pandas or Polars?~~ **pandas.** Operator decision. Consequence: `~/.claude/refs/ml.md`
   line *"No pandas in ML code — Polars in"* now contradicts the scaffold and is amended in
   Step 0. Harvesting from listen-wiseer costs a Polars→pandas port at the I/O edges only.
2. ~~Depth vs. breadth?~~ **Both, sequenced.** All three families registered in the registry;
   only **classification** implemented deeply now. Clustering/prediction get real-but-minimal
   implementations, expanded after ENAM.
3. ~~Where does code live?~~ **Split by kind.** Library code → `ai-project-template`'s `ml/`.
   Skills (`ml-select`, `ml-transform`, `review-leakage`) → `galactus/.claude/skills/`.
   Matches the config-layering rule: generic capability is canon in one place.
4. ~~Reporting output?~~ **Self-contained HTML**, following `ml6/docs/presentation.html`
   precedent — single file, inlined CSS, inline SVG charts, opens offline, no CDN.

Resolved during refinement (2026-08-10), each settled by running the thing rather than
reasoning about it:

5. ~~**How does `review-leakage` get registered?**~~ **As a tenth `Reporter` enum member,
   not a directory.** The reporter set is closed Python, not a skills-folder convention:
   `review/models.py:71-88` (`Reporter`), `review/models.py:93-103` (`REPORTER_ID_PREFIX`),
   guarded by `review/tests/test_prefix_map.py` — which passes today (3 passed) and goes
   red the moment a tenth `review-*` directory appears without a matching enum entry.
   Prefix `LK` (the nine taken are IN/CR/SI/TE/SF/AR/RT/SG/CT). Step 10 owns all five files.
   **Correction carried through the doc: there are nine existing reporters, not ten** —
   `review-shared` is excluded as a non-dimension at `test_prefix_map.py:30`.
6. ~~**How does `review-leakage` activate?**~~ **Conditional on a new ML signal.**
   `detect_signals` returns exactly two booleans and `_ALWAYS_ON` is six hardcoded names
   (`review/signals.py:101-114`, `:125-152`) — there is no ML notion anywhere in the
   dispatch path. Rejected the one-line alternative (adding `leakage` to `_ALWAYS_ON`)
   because dispatching a leakage reporter against prose diffs trains the operator to
   ignore it. **The failure mode being avoided is this plan's own thesis turned on itself:**
   a dimension that never activates is recorded as `skipped` *with a reason*, so leakage
   silence reads as deliberate non-activation rather than as a gap.
7. ~~**Are the Phase A/B test commands runnable?**~~ **Yes, against the rendered tree —
   the plan pointed at the wrong directory.** `ai-project-template` has no `pyproject.toml`
   and no pytest; `uv run pytest` there fails with `Failed to spawn: pytest`. But
   `scripts/validate_paths.py:694` (`run_render_tests`) already renders a
   `"python ml + all metrics"` matrix entry with `include_ml=true` — it just greps for
   unrendered Jinja and discards the tree without running pytest. Rendering that entry by
   hand and running the suite: **30 passed in 68s**. Rendered layout is `backend/ml/` for
   source, `tests/unit/ml/` for tests, imports as `from ml.<module> import ...` via
   `pythonpath = ["backend/src", "backend", "."]`. Step 0.5 encodes this.

Still open, non-blocking for Phases A–C:

8. **ENAM's six domain unknowns** (label horizon, decision consumed, cost asymmetry,
   uplift-vs-propensity, time structure, regulatory posture) — see `enam/README.md`.
   Blocking for **Phase D only**.

### Approach

Extract-and-generalise rather than write-from-scratch. listen-wiseer's
`_create_estimator` factory (`classifiers.py:103`) and `compare_models` harness
(`train.py:329`) are the proven shape; the new `ml/selection/` registry is those two ideas
generalised across a **2-D matrix — family × output** — with every other module
(transform, sampling, evaluation, reporting) written to be driven by that registry.

The tradeoff accepted: a registry adds indirection over "just call CatBoost." It earns that
by making the templated per-family workflows real code paths instead of documentation, and
by giving the leakage reporter a single place to intercept every fit.

**Sequencing rationale.** Phase C (leakage reporter) is deliberately *not* last. A library
built without a leakage check is a faster way to produce a confidently wrong model — but it
also cannot be written before the fit-paths it inspects exist. It lands immediately after
the training spine and before ENAM touches real data.

### Out of Scope

- **Uplift/causal modelling.** Flagged in research as possibly ENAM's true target. Not built
  until Open Question 5 resolves — it changes the whole approach and would be speculative now.
- **The bandit.** Phase-three extension per research Finding 3; requires calibrated scores and
  logged outcomes first. Registered as a `prediction` family entry, not implemented.
- **BERT / text features.** Only earns a place if ENAM has free-text. Registry reserves the
  slot; no implementation.
- **Tabular foundation models** (TabPFN et al.). Research says CatBoost still wins without
  multi-config ensembling. Not worth the dependency now.
- **Deployment, serving, retraining schedulers.** The toolkit produces a saved artifact and a
  report; shipping it is a project concern.
- **Live drift monitoring.** Step 9 computes drift *metrics* on a held-out/incoming frame; it
  does not stand up a monitoring service.
- **Migrating atlas or listen-wiseer** to the new toolkit. They are harvest sources, not
  refactor targets. Neither repo is modified by this plan.
- **Touching `ml6/`.** Repo rule: it is the case study, not scratch space.
- **Real ENAM data in the repo.** `enam/data/` is gitignored; synthetic fixtures only.

---

## Phase A — the spine: registry, transform, sampling

Branch: `AIT-62-ml-toolkit-spine` off template `main`. Target repo: **ai-project-template**.
Base path below abbreviated `ML/` = `template/_scaffold/{{ py_project_root }}/{{ ml_source_root }}/`.

> **`<n>` is a placeholder in three branch names** (`AIT-62-ml-toolkit-spine`,
> `AIT-62-ml-toolkit-training`, `GAL-1-ml-skills`). Step 0.5 creates the issues and
> substitutes the real numbers. Do not start Phase A with `<n>` unresolved.
> <!-- 2026-08-14: `GUA-1-ml-skills` → `GAL-1-ml-skills` here too; see the Phase C
>      header. Phases A–C have landed, so the `<n>` instruction now applies only to
>      Phase D's `GAL-<n>-enam-baseline`. -->


#### Step 0.5: Preconditions — issues, clean branch point, render harness
**Files**: `ai-project-template/Makefile`, `ai-project-template/scripts/validate_paths.py`,
`ai-project-template/template/_scaffold/pyproject.toml.jinja`
**What**: Three things that must be true before any code is written. Each was a prose
mitigation in the risk table; prose is the weakest rung of the enforcement ladder, so each
becomes a command that either succeeds or stops the phase.

1. **Create both GitHub issues.** `gh issue list` is empty in both repos today. Template
   work is `AIT-`, galactus work is `GUA-` (prefix = repo being changed). Substitute the
   real numbers for `<n>` in all three branch names in this doc.
2. **Branch from clean `main`.** The template is checked out on
   `AIT-56-drop-temperature-param`, 4 commits ahead of `main` with unrelated work. A bare
   `git checkout -b` forks from it and silently carries that work into Phase A's diff.
   Verify clean tree, `git checkout main && git pull`, *then* branch `--no-track`.
3. **Add a `test_render` target** so the nine Done-when commands have something to call.
   `run_render_tests()` (`scripts/validate_paths.py:694`) already renders the
   `"python ml + all metrics"` entry and then throws the tree away without running pytest.
   That gap is the template's, not this plan's — fixing it here is the smaller change and
   benefits every future ML step.
4. **Declare the two optional deps.** `catboost` and `imbalanced-learn` are absent from the
   `{%- if include_ml %}` block (`pyproject.toml.jinja:76-83`). Steps 1 and 3 import
   packages the template never declares.

**Snippet** — the verified render-and-test invocation the `test_render` target wraps:
```bash
copier copy --overwrite --defaults --trust \
  -d project_name=TestProject -d scaffold_full_project=true \
  -d primary_backend_language=python -d primary_chat_agent=lg_agent \
  -d include_ml=true -d include_agent_reference_library=false \
  -d global_skills_source=none -d enable_macos_notifications=false \
  . "$DST"
cd "$DST" && uv sync && uv run pytest tests/unit/ml -q
```
**Test**: `make test_render` — green on the untouched template (baseline: **30 passed**).
**Done when**: Both issues exist and `<n>` is substituted everywhere; `git log --oneline
main..HEAD` on the new branch is empty before the first commit; `make test_render` passes;
`catboost` and `imbalanced-learn` render into the ML dependency block.

> **Test-command convention for every step below.** `ML/` paths are *template* paths —
> code is written there, but tests run against the **rendered** tree, where source is
> `backend/ml/` and tests are `tests/unit/ml/`. Each step's listed pytest command runs
> inside the rendered output produced by `make test_render`, never from the template repo
> root (which has no `pyproject.toml` and no pytest). Imports in tests resolve as
> `from ml.<module> import ...` via `pythonpath = ["backend/src", "backend", "."]`.

#### Step 0: Amend the pandas rule in the global ML ref
**Files**: `~/.claude/refs/ml.md` (the `## Don'ts` block, line ~1 of that section)
**What**: The ref currently forbids pandas in ML code. The decision is pandas. Amend the line
so the scaffold does not knowingly violate its own convention ref.
**Snippet**:
```
before: - No pandas in ML code — Polars in, numpy arrays to sklearn
after:  - `ml/` toolkit is pandas-native (numpy arrays to sklearn). Polars is
          preferred for ETL/ingest paths (atlas, listen-wiseer); do not mix
          frames within one module — convert at the boundary.
```
**Rollback**: `~/.claude` is a git repo (verified — HEAD `e240fe3`), so this edit has a
revert path despite living outside both target repos. Commit it on its own so it can be
reverted independently of Phases A–C; the plan's "each phase is one branch" rollback story
does not otherwise cover a file in the operator's home directory.
**Sequencing**: run this step **last in Phase A**, not first. Amending the ref before the
scaffold is pandas-native makes the ref describe a state that does not exist; amending it
after means the ref never lies.
**Test**: `grep -n 'pandas' ~/.claude/refs/ml.md` shows the amended line, no contradiction.
**Done when**: Ref and scaffold agree; a reader of both cannot derive conflicting rules; the
amendment is a standalone commit in `~/.claude`.

#### Step 1: Model registry — the 2-D selection matrix
**Files**: `ML/selection/__init__.py`, `ML/selection/registry.py` (new, ~180 lines)
**What**: The spine. A `ModelSpec` dataclass + registry keyed by **(family, output)**.
Generalises listen-wiseer's `_create_estimator` — all params in the constructor so
`sklearn.clone` works. Every family registered; only classification densely populated.

| family | output | entries |
|---|---|---|
| `classification` | `binary`, `multiclass` | `logistic` (baseline, always), `random_forest`, `catboost`, `lightgbm` |
| `clustering` | `unsupervised` | `kmeans`, `dbscan`, `gmm`, `agglomerative` |
| `prediction` | `continuous` | `linear`, `hierarchical`, `lightgbm_reg`; `bandit` reserved (raises `NotImplementedError` with a pointer to research Finding 3) |

**Snippet**:
```python
@dataclass(frozen=True)
class ModelSpec:
    name: str
    family: Literal["classification", "clustering", "prediction"]
    outputs: tuple[str, ...]
    factory: Callable[..., Any]
    supports_categorical: bool = False   # CatBoost native handling
    is_baseline: bool = False            # logistic/linear — always included
    optional_dep: str | None = None      # skip cleanly if not installed

def get_models(family: str, output: str, include: list[str] | None = None) -> dict[str, Any]:
    """Return unfitted estimators for a family/output pair. Baselines always included."""
```
**Test**: `uv run pytest tests/unit/ml/test_selection.py -v`
**Done when**: `get_models("classification", "binary")` returns logistic + RF + catboost
(lightgbm if installed); an unknown pair raises with the valid pairs listed; a missing
optional dep is skipped, not fatal; every spec is `clone()`-able.

#### Step 2: Transform layer — encoders, scalers, imputers
**Files**: `ML/transform/__init__.py`, `ML/transform/columns.py`, `ML/transform/encoders.py` (new, ~280 lines)
**What**: Column-type inference + a `ColumnTransformer` builder. Extends the existing
`TabularPreprocessor` (`ML/model_comparison/compare.py:29`) rather than replacing it —
that class stays, and is re-exported. Adds: numeric (standard/minmax/robust/none),
categorical (one-hot / ordinal / **target-encoding computed inside the CV fold**), missing
indicators, high-cardinality detection, datetime decomposition.
**Snippet**:
```python
def infer_column_types(df, target=None, high_card_threshold=50) -> ColumnPlan: ...
def build_transformer(plan: ColumnPlan, *, numeric="standard",
                      categorical="onehot", add_missing_indicators=True) -> ColumnTransformer: ...
```
**Test**: `uv run pytest tests/unit/ml/test_transform.py -v`
**Done when**: Mixed-type frame with NaNs and a 200-category column infers correctly;
target encoding fitted on a fold does not see that fold's rows (asserted); missing
indicators preserve not-missing-at-random signal (research Finding: expected data problems).

#### Step 3: Sampling — SMOTE, under/over, outliers
**Files**: `ML/sampling/__init__.py`, `ML/sampling/resample.py`, `ML/sampling/outliers.py` (new, ~260 lines)
**What**: Imbalance strategies as **pipeline-safe** components: class weights (default —
listen-wiseer's proven choice), random under/over, SMOTE / SMOTENC (categorical-aware),
Tomek/ENN cleaning. Plus outlier removal (IQR, z-score, IsolationForest).
`imbalanced-learn` added as an **optional** dependency; class-weight fallback when absent.
**Critical invariant**: resampling happens *inside* the CV fold on training data only —
never on validation, never before the split. Encoded as a runtime guard, not a comment.
**Snippet**:
```python
def build_sampler(strategy: Literal["none","class_weight","smote","smotenc",
                                    "under","over","smote_tomek"] = "class_weight",
                  *, categorical_indices=None, random_state=42): ...
# raises SamplingLeakageError if handed a frame flagged as validation
```
**Test**: `uv run pytest tests/unit/ml/test_sampling.py -v`
**Done when**: Each strategy rebalances a synthetic 95/5 frame; SMOTENC handles categoricals;
applying a sampler to validation data raises `SamplingLeakageError`; absent `imbalanced-learn`
degrades to class weights with a logged warning rather than an ImportError.

#### Step 4: Feature engineering — data-mining extractions
**Files**: `ML/feature_engineering/mining.py` (new, ~200 lines); `ML/feature_engineering/features.py` (existing, untouched)
**What**: Cross-sectional extractions the existing time-series-oriented module lacks:
aggregation-by-group (count/mean/std/min/max/nunique per entity), recency-frequency-monetary,
ratio and interaction features, binning (quantile/tree-based), rare-category collapsing.
Chosen because they are the standard vocabulary for a debtor-level tabular problem.
**Snippet**:
```python
def add_group_aggregates(df, group_col, value_cols, aggs=("mean","std","count")) -> pd.DataFrame: ...
def add_rfm_features(df, entity_col, date_col, amount_col, as_of) -> pd.DataFrame: ...
def collapse_rare_categories(df, cols, min_freq=0.01) -> pd.DataFrame: ...
```
**Test**: `uv run pytest tests/unit/ml/test_feature_mining.py -v`
**Done when**: Each builder returns correctly-named columns on a synthetic transaction frame;
RFM's `as_of` cutoff excludes future rows (temporal-leakage guard asserted).

**── Phase A review gate ──** `/workflow-review`. Registry + transform + sampling land together;
nothing downstream is written until this is reviewed.

---

## Phase B — training, evaluation, reporting

Branch: `AIT-62-ml-toolkit-training`. Target repo: **ai-project-template**.

#### Step 5: Leakage-safe splitting
**Files**: `ML/evaluation/splitting.py` (new, ~150 lines)
**What**: The gap flagged in Finding 2 — the current toolkit has `StratifiedKFold` only.
Adds `GroupKFold` (same debtor across accounts), `TimeSeriesSplit` / cohort-date splits, and
`StratifiedGroupKFold`. A single `make_splitter(...)` chooses based on declared data
structure and **refuses to return a random splitter when a time column is declared**.
**Snippet**:
```python
def make_splitter(*, n_splits=5, group_col=None, time_col=None, stratify=True):
    """Declaring time_col and requesting a random split raises — it trains on the future."""
```
**Test**: `uv run pytest tests/unit/ml/test_splitting.py -v`
**Done when**: Group splits never place one group in both sides; time splits never place a
later fold in train relative to test; requesting random + `time_col` raises.

#### Step 6: Training workflow — the templated per-family runner
**Files**: `ML/workflows/__init__.py`, `ML/workflows/classification.py`, `ML/workflows/clustering.py`, `ML/workflows/prediction.py` (new, ~450 lines total)
**What**: The templated workflows. Generalises `compare_models` (`train.py:329`): assemble
transform → sampler → estimator as one sklearn `Pipeline` (leakage-safe by construction),
fit every registry candidate on **identical folds**, collect metrics, return a
`RunResult`. Classification is the deep one; clustering (k-sweep, silhouette/DB/CH) and
prediction (RMSE/MAE/MAPE) are real but minimal per decision 2.
**Snippet**:
```python
def run_classification(df, target, *, output="binary", models=None, sampling="class_weight",
                       splitter=None, calibrate=True, seed=42) -> RunResult: ...
```
**Test**: `uv run pytest tests/unit/ml/test_workflows.py -v`
**Done when**: `run_classification` on sklearn's `breast_cancer` returns a populated
comparison across ≥3 models with the logistic baseline present; the fitted object is a
single `Pipeline` (asserted — no transform outside it); seed produces identical metrics twice.

#### Step 7: Evaluation — PR curves, calibration, thresholds
**Files**: `ML/evaluation/metrics.py`, `ML/evaluation/calibration.py`, `ML/evaluation/threshold.py` (new, ~320 lines)
**What**: The metrics the research says decide this problem. PR-AUC/average-precision
(primary under imbalance — ROC-AUC is misleading there), precision@k, per-class multiclass
metrics, confusion at a chosen threshold. Calibration via `CalibratedClassifierCV`
(sigmoid/isotonic) + Brier + reliability curve — harvested from listen-wiseer.
**Cost-based threshold selection** is the ml6-analogue: a pure function of a cost matrix and
predicted probabilities, deterministic, no model involvement.
**Snippet**:
```python
def choose_threshold(y_true, y_prob, *, cost_fp: float, cost_fn: float) -> ThresholdResult:
    """Pure function. The decision rule is arithmetic over costs, not a hyperparameter."""
```
**Test**: `uv run pytest tests/unit/ml/test_evaluation.py -v`
**Done when**: PR-AUC computed and reported above ROC-AUC for imbalanced targets;
calibration measurably improves Brier on a deliberately miscalibrated model; `choose_threshold`
is pure and matches a hand-computed optimum on a known cost matrix.

#### Step 8: HTML reporting arm
**Files**: `ML/reporting/__init__.py`, `ML/reporting/html.py`, `ML/reporting/charts.py`, `ML/reporting/style.css` (new, ~400 lines)
**What**: `RunResult` → one self-contained HTML file. Follows `ml6/docs/presentation.html`:
inlined CSS, **inline SVG charts (no matplotlib PNG, no CDN)**, opens offline. Sections: run
metadata + seed + data shape, model comparison table, PR/ROC/calibration curves, confusion at
chosen threshold, feature importance, and a **data-quality panel** surfacing leakage warnings
from Step 10. Theme-aware light/dark via CSS custom properties.
**Snippet**:
```python
def write_report(result: RunResult, out_path: Path, *, title: str) -> Path: ...
```
**Test**: `uv run pytest tests/unit/ml/test_reporting.py -v`
**Done when**: A `RunResult` produces a single `.html` with **zero external references**
(asserted by regex over `src=`/`href=` for `http`); renders in a browser; curves are SVG paths.

#### Step 9: Persistence, retraining, drift
**Files**: `ML/persistence.py`, `ML/monitoring/drift.py` (new, ~240 lines)
**What**: Closes the "nothing leaves the process" gap. joblib save/load of the whole
`Pipeline` (transform + sampler-free inference path + estimator) with a metadata sidecar —
seed, versions, feature names, chosen threshold, training date. Load-time **feature-name and
schema check** so train/serve skew fails loudly. Drift: PSI + KS per feature, prediction
drift, with a `retrain_recommended` flag.
**Snippet**:
```python
def save_model(pipeline, path, *, metadata: ModelMetadata) -> Path: ...
def load_model(path) -> tuple[Pipeline, ModelMetadata]:  # raises SchemaMismatchError
def compute_drift(reference_df, current_df, *, features) -> DriftReport: ...
```
**Test**: `uv run pytest tests/unit/ml/test_persistence.py tests/unit/ml/test_drift.py -v`
**Done when**: Round-trip save/load reproduces identical predictions; a frame with renamed/
missing columns raises `SchemaMismatchError`; PSI flags a synthetically shifted feature.

**── Phase B review gate ──** `/workflow-review`. The library is now complete and usable
standalone; Phase C wraps it in skills.

---

## Phase C — the skills and the leakage reporter

Branch: `GAL-1-ml-skills`. Target repo: **galactus**.
<!-- 2026-08-14: was `GUA-1-ml-skills`. The work targets galactus, so the prefix is
     `GAL-`; `GUA-` predates that prefix existing. Phase C has landed, so this name
     is now a record of what should have been used, not an instruction. -->


#### Step 10: `review-leakage` reporter — skill, registration, and activation
**Files** (all five are required — a SKILL.md alone breaks the build):
- `galactus/.claude/skills/review-leakage/SKILL.md` (new) — frontmatter carries `prefix: LK`
- `galactus/review/models.py` (edit) — `LEAKAGE = "leakage"` on `Reporter` (`:71-88`) and the
  `REPORTER_ID_PREFIX` entry (`:93-103`)
- `galactus/review/signals.py` (edit) — the ML signal and its activation rule
- `galactus/.claude/skills/review-shared/references/finding-schema.md` (edit, `:70-83`) — the
  mirrored prefix table
- `galactus/.claude/skills/workflow-review/SKILL.md` (edit, `:129-138`) — the dimension table
- `galactus/review/tests/fixtures/leaky_pipeline.py`, `clean_pipeline.py` (new, ~30 lines each)

**What**: The highest-leverage item in the research. The ML analogue of
`review-silent-failure`, and justified by the same argument: **a leaked feature does not
error — it returns AUC 0.97 and reads as success.** Detects: target leakage (post-outcome
column names, feature-target correlation above threshold, suspiciously high AUC), temporal
leakage (random split on time-structured data), group leakage (entity in both sides),
fit-before-split ordering, resampling outside the fold, and target encoding fitted outside
the CV fold.

**Registration is code, not convention** (Open Question 5). The reporter set is a closed
enum with a cross-artifact test: `test_prefix_map.py` globs `.claude/skills/review-*`, maps
each to a dimension, and asserts the set matches `REPORTER_ID_PREFIX` exactly. Creating the
skill directory alone turns a currently-passing test red. Prefix `LK`.

**Activation is a new signal** (Open Question 6). `detect_signals` gains an `is_ml_code`
boolean beside `is_agent_code`, following that function's existing shape — content-based
import patterns (`sklearn`, `pandas`, `catboost`, `lightgbm`, `imblearn`) plus call-shape
patterns (`.fit(`, `.predict(`, `.fit_transform(`) and ML path patterns. `active_dimensions`
activates `leakage` on it and records a reason when skipped.

Mirrors `review-shared/references/context-brief.md`: **an empty diff is an error, not a
clean review** — it must fail loudly rather than return no findings.

**Test**:
```bash
uv run pytest review/tests/test_prefix_map.py review/tests/test_signals.py -q
```
plus dispatching the reporter against the two fixtures.
**Done when**: `test_prefix_map.py` is green with ten dimensions (it must be *run*, not
assumed — it passes at 3 tests today and is the tripwire for this step); a changed-file list
of ML code activates `leakage` and a prose-only list skips it *with a recorded reason*; the
reporter flags the planted leak in `leaky_pipeline.py`, returns clean on `clean_pipeline.py`,
and errors on empty input. **The positive path is what makes this step real** — a reporter
verified only by its error path has untested detection logic.

> **Fixture scope.** `leaky_pipeline.py` / `clean_pipeline.py` are minimal twins (a fit
> before a split, and the same code with the split first) — an acceptance artifact of this
> step, not a step of their own, and not a substitute for Step 15's exercise against real
> data.

#### Step 11: `ml-select` skill — the model-selection interview
**Files**: `galactus/.claude/skills/ml-select/SKILL.md` (new)
**What**: The 2-D decision made conversational, then handed to the registry. Asks the two
questions that determine everything — **(1) prediction / classification / clustering,
(2) output shape** — plus target definition, time structure, grouping, cost asymmetry.
Emits a config that drives Step 6's workflow. Follows the `scope-poc` interview convention:
*"I don't know" is a first-class answer* — park it with a revisit trigger.
Refuses to select a model before the data has been profiled (research Finding 1: profile,
then plan).
**Test**: Invoke against the ENAM framing; confirm it produces a runnable config and parks
the six unknowns rather than guessing.
**Done when**: Produces a valid `(family, output)` pair + config for a described problem;
unanswered questions land as parked items with triggers, not defaults.

#### Step 12: `ml-transform` skill — the transformation advisor
**Files**: `galactus/.claude/skills/ml-transform/SKILL.md` (new)
**What**: The "knows what to apply to this dataset" skill. Profiles a frame (dtypes,
cardinality, missingness pattern, skew, outliers, target balance) and **recommends** a
transform + sampling config with a stated reason per column, then emits the `ColumnPlan`
Step 2 consumes. Advisory and explicit — it proposes, the operator approves; it never
silently transforms.
**Test**: Run against a synthetic frame with planted problems (high-cardinality column,
NMAR missingness, 95/5 imbalance, skewed numeric).
**Done when**: Recommends target/rare-collapse for high-cardinality, missing-indicators for
NMAR, a sampling strategy for the imbalance — each with a reason; output loads into `build_transformer`.

#### Step 13: ML mode for `design-prototype quick-start`
**Files**: `galactus/.claude/skills/design-prototype/SKILL.md` (edit — add ML routing + stage variant)
**What**: Research Finding 1's other half: the pipeline has no phase where data is
interrogated *before* the plan. Adds an ML variant whose stage 4 "failing test that defines
done" is **a baseline metric plus a passing leakage check**, and inserts a profiling stage
before planning. Reuses the existing stage table rather than forking the skill.
**Routing** — first-word matching is the weakest rung of the enforcement ladder, and the
plan's central insight (profile before planning) should not be guarded by a string compare.
A prompt like *"profile this dataset then plan"* takes the agentic path silently. So the
routing line is a **fallback, not the mechanism**: route on `ml` as the first word *or* on
ML intent in the request (a dataset/frame/target/model mentioned as the subject), and when
the match is ambiguous, ask rather than defaulting to the agentic path.

**Snippet**: routing line — `first word 'ml', or ML intent in the request → ML quick-start
mode; ambiguous → ask, do not default`.

**Test**: `/design-prototype ml` dry-run against the ENAM framing, plus the three non-ML
regression prompts below.
**Done when**: The ML path runs profile → baseline → leakage-check before any modelling step;
and the non-ML path is **unchanged on three named prompts** — one bare `/design-prototype`,
one `quick-start` invocation, one prose request with no ML subject — compared stage-table to
stage-table before and after the edit. ("Byte-identical" was the criterion here and is
struck: the file is one document, so adding a routing branch necessarily changes the bytes
every invocation sees. A behavioural check on named prompts is falsifiable; a byte claim is
either trivially false or silently reinterpreted.)

**── Phase C review gate ──** `/workflow-review`.

---

## Phase D — ENAM as the proving run

Blocked on Open Question 8 (the six domain unknowns) and on real data arriving.
Branch: `GAL-<n>-enam-baseline`. Target repo: **galactus**.
<!-- 2026-08-14: was `GUA-<n>-enam-baseline` — same prefix correction as Phase C.
     `<n>` is still unresolved because Phase D has not started; substitute the real
     issue number before branching. A remote `GUA-2-enam-baseline` exists with no
     local work; if that branch is picked up rather than recreated, its name is the
     stale one. -->


#### Step 14: Profile and interrogate the real data
**Files**: `enam/docs/DESIGN.md` (new), `enam/data/` (gitignored)
**What**: Run `ml-transform` profiling + `review-leakage` before any modelling. Answer as many
of the six unknowns as the data itself settles; record the rest as still-open with triggers.
**Done when**: DESIGN.md states the actual label, horizon, class balance, time structure, and
the leakage candidates found — replacing the **Assumed** labels in `enam/README.md` with
**Given** where the data or client confirms them.

#### Step 15: Baseline → CatBoost → calibrated score → report
**Files**: `enam/ml/run.py` (new), `enam/docs/report.html` (generated, gitignored if it embeds real data)
**What**: The end-to-end proving run using only Phase A–C tooling. Logistic baseline first
(the explainability floor), then the registry candidates, calibration, cost-based threshold,
HTML report. Any capability gap found here is a finding against the toolkit, not a local patch.
**Done when**: A calibrated model beats the logistic baseline on PR-AUC — **or** the honest
finding is recorded that it does not (research Finding 4: that is a real result about feature
quality, not a failure); report renders; no real data committed.

---

### Test Plan

- **Where tests run**: code is written at the template's `ML/` paths; **every `uv run pytest`
  command in this plan runs in the rendered tree**, never from the template root (which has
  no `pyproject.toml` — `uv run pytest` there fails with `Failed to spawn: pytest`). Render
  via Step 0.5's `make test_render`, then run inside the output.
- **Per step**: the listed `uv run pytest` command, all green before the next step. Re-render
  after editing template files — the rendered tree is a copy, not a symlink.
- **Fixtures**: synthetic or sklearn-bundled only (`breast_cancer`, `make_classification`,
  `make_blobs`) — matches existing `tests/unit/ml/` convention and the ref's
  "never load real data in unit tests".
- **Determinism**: every test seeds (`random_state=42`); a repeat-run test asserts identical
  metrics.
- **Leakage as a test class**: each leakage-safety invariant has a test that *asserts it
  raises* — the guard is only real if its failure is exercised.
- **Phase gates**: full `uv run pytest tests/unit/ml -q` in a **freshly rendered** tree, plus
  `/workflow-review`, at A, B, C. Rendering fresh at the gate is what catches a step that
  passed only against a stale render.
- **Integration**: Step 6 + 7 + 8 end-to-end on `breast_cancer` — frame in, HTML out.
- **Phase C is the exception**: Steps 10–13 change galactus (`review/`, `.claude/skills/`),
  not the template, so their tests run in the galactus checkout — `uv run pytest review/tests -q`.

### Risks & Rollback

| Risk | Mitigation |
|---|---|
| **Registry over-abstraction** — indirection exceeding its value | Phase A gate explicitly checks: can a caller still reach a raw estimator in one line? If not, flatten. |
| **Scope sprawl** (13 steps across 2 repos) | Phase gates are hard stops; Phases A/B/C are independently revertable branches. |
| **Optional deps** (catboost, imbalanced-learn) breaking installs | All optional, `try/except ImportError`, degrade with a logged warning — the pattern already proven at `compare.py:111`. Declared in the `include_ml` block by Step 0.5. |
| **pandas/Polars friction** when harvesting | Port only at I/O edges; the harvested logic is frame-agnostic. |
| **Template branch collision** — `AIT-56` in flight | Step 0.5 makes this a checked precondition, not prose: verify clean tree, `checkout main`, branch `--no-track`, and assert `git log --oneline main..HEAD` is empty before the first commit. |
| **`review-leakage` registered but never dispatched** | The specific danger: a dimension that never activates is recorded as `skipped` *with a reason*, so its silence reads as deliberate. Step 10's Done-when asserts activation on an ML file list **and** a recorded skip-reason on a prose-only one. |
| **Steps marked done on tests that never ran** | Nine Done-when commands were unrunnable from the template root. Step 0.5's `make test_render` gives them a real target; its baseline (30 passed) is the signal that the harness itself works. |
| **ENAM data never arrives / differs wildly** | Phases A–C have zero dependency on ENAM specifics; they stand alone. |
| **Rollback** | Each phase is one branch, revertable without touching the others. Step 0's `~/.claude/refs/ml.md` edit is the one change outside both repos — it is a standalone commit in that repo (which is version-controlled) and reverts independently. Nothing modifies atlas, listen-wiseer, or `ml6/`. |

### Definition of Done

- `get_models(family, output)` covers all three families; classification deeply implemented.
- A frame goes in and a calibrated model + self-contained HTML report comes out, in one call.
- Every leakage invariant has a test that asserts it raises.
- `review-leakage` is **registered** (`Reporter` enum + `REPORTER_ID_PREFIX` + both mirrored
  tables), **activates** on an ML changed-file list, and **detects** — it flags the planted
  leak in `leaky_pipeline.py`, not merely errors on empty input. `test_prefix_map.py` green
  at ten dimensions.
- `ml-select` and `ml-transform` are invocable and exercised.
- Every step's test command has been *run*, in the rendered tree, not assumed from the
  template root.
- `~/.claude/refs/ml.md` and the scaffold no longer contradict each other, and the ref edit
  is a standalone revertable commit.
- Two GitHub issues exist (`AIT-` for template, `GUA-` for galactus) and `<n>` is substituted
  in all three branch names.

_compact: 2026-08-15 14:17_

_compact: 2026-08-15 20:16_
