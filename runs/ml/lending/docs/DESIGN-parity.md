# System Design — ml-lending parity (reproducible runs)

**Date:** 2026-08-15
**Status:** Draft
**Scoped by:** `/proto-scope` against the ML-track parity gap. Companion to
[`DESIGN.md`](DESIGN.md) (the Step 14 data profile — a different artifact; see Open
Questions #2) and [`README.md`](../README.md) (the domain framing, untouched here).

---

## Problem + Success Criteria

The lending run produced the repo's most load-bearing ML finding — *no candidate model
beats the logistic baseline* — and cannot reproduce it. Its metrics live in prose
([`DESIGN.md § Step 15 result`](DESIGN.md)) and a tracked `report.html`; the harness
([`src/run.py`](../src/run.py)) — as of this design's writing (2026-08-15, since
closed by GAL-32) — had no tests, was absent from `testpaths`, required
gitignored real data to execute at all, and wrote no run record. `runs/_index/` is
reserved for exactly this and nothing writes it. The leakage evidence — the run's whole
reason to exist — is a document, not a check the run performs.

`runs/ai/marketing-comms/` is the bar: layered `src/`, a test suite in `testpaths`, and an
evals harness with a `--dry-run` that exercises the full path against a scripted adapter
with no spend. This work item brings `runs/ml/lending/` to that bar.

**POC demo target:** from a clean checkout **without** the real CSV:
`uv run pytest runs/ml/lending/tests -q` is green, and
`run.py --dry-run` completes the full harness path — synthetic frame in, planted leak
tripped and reported, `RunRecord` produced — with no network and no real data. With the
real CSV present, a full run writes a record under `runs/_index/` such that a re-run at
the same git SHA and `frame_hash` reproduces identical metrics, or the record diff names
which input changed.

**Naive baseline:** the status quo — `summary.json`-style prose plus a tracked HTML
report. What the work must beat: a second person can *refute or reproduce* the
"nothing beats the baseline" finding from the record alone, without archaeology through
plan docs. If a re-run can't be compared to the recorded run mechanically, this work
added ceremony, not reproducibility.

---

## Actors

| Actor | Type | What they do today | What this work does for them |
|---|---|---|---|
| Ramsey (operator) | internal | Re-derives run context from plan docs and prose | Reads/diffs `runs/_index/` records; runs dry-run before touching real data |
| Review pipeline (`/proto-review`, `review-leakage`) | system | Reviews `run.py` as untested script | Gets tests to judge and in-run guards to verify |
| Future runs (ENAM Phase D, other `runs/ml/`) | system | Each improvises its own results story | Inherit the record-writing precedent — this run is the template |
| `experiments/` registry (ai-project-template) | system | Defines `RunRecord`/provenance/fingerprint; no consumer exists | Gains its first real consumer, which will surface its gaps (it already has one: no serializer) |

---

## System Context

The harness stays a script in galactus consuming two external contracts: the ML toolkit
(`ml.*`) and the experiments registry (`experiments.*`), both importable from the same
rendered ai-project-template tree via the existing `ML_PACKAGE_ROOT` mechanism
(`run.py` already prepends it to `sys.path`; `experiments/` renders as a sibling of
`ml/` under the same root, so no second env var). Records land in `runs/_index/`, one
file per training execution. galactus consumes the record shape; it never defines it
(CLAUDE.md `runs/_index` rule).

---

## MVP Scope

**In:**

- Refactor `src/run.py` into testable modules (label construction, exclusion/guard
  logic, record assembly, CLI) — the bar requires tests, and a 400-line `main()` can't
  have them. Constants stay the profile-doc-as-code they are.
- `runs/ml/lending/tests/` + the `testpaths` entry in `pyproject.toml` (repo rule: a
  test dir absent from `testpaths` collects zero and reads as passing).
- **Leakage checks in the run itself**, deterministic, failing loudly: (a) the 39-column
  exclusion list asserted against the fitted frame — an excluded column present is an
  error, not a warning; (b) the single-feature-AUC alarm (README's "any AUC above ~0.95
  on a first pass is a leakage alarm" line, as code); (c) the existing
  `assert_no_group_leakage` kept; (d) a final-metric alarm at the same threshold.
- **`--dry-run`**: synthetic fixture frame (schema-shaped like the real one, ~hundreds
  of rows) through the *full* path — load, guards, transform, split, tiny fast model
  set, calibrate, record assembly. Two fixtures, mirroring the marketing-comms dry-run
  whose cases fight the contract: a clean frame that passes, and a planted-leak frame
  the guard must trip on. No network, no real data, deterministic, seconds not minutes.
- **Record writing**: assemble a `RunRecord` (via `capture_code_state()` +
  `fingerprint_frame()` + resolved config) and persist one file per training execution
  to `runs/_index/`. Real runs write there; dry-runs write to a temp path (a dry-run is
  a harness test, not a run of record).
- A reproduce check: re-run at same SHA + same `frame_hash` → byte-identical metrics
  block, exercised in tests via the dry-run path.

**Out (explicitly):**

- The three toolkit findings from Step 15 (`group_col` target-encoded into features,
  `beats_baseline` strict-`>`, `choose_threshold` in-sample marking) — they are
  ai-project-template defects, filed as AIT issues, not patched around locally beyond
  the existing `splitter=` workaround.
- Any modelling change. The Step 15 config is frozen; this work must reproduce its
  numbers, not improve them.
- The other `runs/ml/` runs, `LTV.ipynb`, `credit/`. One run to the bar first.
- Domain progress on the six client unknowns (README) — untouched.
- An HTML/report redesign; `report.html` stays as-is — tracked and ratified 2026-08-15
  (it is fraud's ground-truth toolkit fixture, `runs/ml/fraud/tests/conftest.py`; the
  earlier claim here that it remained ignored was wrong — the ignore rule died in the
  `ml-lending/` → `runs/ml/lending/` rename).
- Backfilling records for past runs. The prose Step 15 numbers stay prose; the first
  record is the next execution.

**Open (decide before sprint 1):**

- Serializer placement — Key Decisions #3. The one genuinely open decision.

---

## Key Decisions

| Decision | Status | Choice | Rationale (chose X over Y, gave up Z) |
|---|---|---|---|
| 1. Which run to bring to the bar | Resolved — ratify | **lending** | Over fraud / customer-segmentation (both already have tests but no trained-model metric worth registering) and LTV/credit (notebook / bare CSV). Lending is the named reproducibility failure (CLAUDE.md: "the lending baseline could be overturned but not reproduced") and the only run whose headline finding is a metric comparison. Gave up: fraud/segmentation stay below the full bar for now. |
| 2. Record shape | Resolved (given) | `experiments.record.RunRecord` as-is | CLAUDE.md: galactus consumes the shape, never defines it. `NotApplicable` sentinels used honestly — this run has a real seed and fold plan, so none should appear in a classification record; one appearing is a bug, not a style choice. No alternative considered — the constraint is the point. |
| 3. Where the serializer lives | **Open** | *Recommended:* `experiments/io.py` in ai-project-template (JSON, `NotApplicable` round-trips as a tagged object, loader validates on read) | The registry has **no writer today** — dataclasses only. A galactus-side writer would de-facto define the on-disk format, violating decision 2's constraint one layer down. Cost of the recommendation: a small AIT work item this run depends on, cross-repo sequencing. Cost of the alternative: the format forks the moment a second consumer appears. Needs Ramsey: it creates work in another repo. |
| 4. Import mechanism for `experiments.*` | Resolved | Reuse `ML_PACKAGE_ROOT` | `experiments/` renders under the same root as `ml/`; one env var, one failure message, pattern already proven in `run.py`. Alternative (vendor the module into galactus) rejected: vendored copies drift, and the registry's value is being one shape across repos. |
| 5. Dry-run semantics | Resolved | Full path on synthetic fixtures; clean + planted-leak twins; tiny models; temp-path record | Mirrors the marketing-comms scripted adapter (whole harness, no spend, cases that fight the contract) and the Phase C fixture-twin precedent (`leaky_pipeline.py`/`clean_pipeline.py`). Alternative (skip training in dry-run) rejected: a dry-run that skips the fit exercises nothing the tests don't already. |
| 6. Guard failure mode | Resolved | Guards **abort** the run (planted-leak dry-run asserts the abort); alarms name the offending columns | Alternative (warn and continue) rejected: a warning in a long log is the silent-failure pattern the review family exists to catch. Gave up: a legitimate >0.95-AUC feature would need an explicit allowlist entry to run — that friction is the feature. |
| 7. Are `runs/_index/` records committed? | Resolved — ratify | Yes | Records carry metrics, counts, column names, hashes — aggregates only, same class of content the profile doc already publishes. Committing them *is* the reproducibility mechanism (diffable history). Gave up: nothing; the aggregates-only constraint in `run.py` already forbids row-level content, and `folds` records a plan description, not indices. |
| 8. Record file naming / `_index` layout | Deferred(`/proto-design`) | Default: one JSON per execution, name = timestamp + short `frame_hash` | Layout of the directory is galactus's to choose (the shape isn't). Deciding it now, before the serializer decision lands, would be guessing twice. |
| 9. Dirty-tree runs | Resolved | Record honestly (`dirty: true`), never refuse | `capture_code_state()` already takes this position; the run defers to it. No alternative considered — fighting the registry's semantics from the consumer side is decision 2 violated again. |

---

## Evaluation

| Metric | Target | How measured |
|---|---|---|
| Tests exist and are counted | `uv run pytest runs/ml/lending/tests -q` green, >0 collected, dir present in `testpaths` | pytest + a grep-level check on `pyproject.toml` |
| Dry-run completeness | exit 0, no network, no `data/*.csv` read, finishes in seconds | run in a checkout with no real CSV |
| Leakage guard detects | planted-leak fixture → run aborts naming the columns; clean fixture → passes | test asserting the raise, and the clean twin (the positive path is what makes the guard real — Phase C rule) |
| Reproducibility | same SHA + same `frame_hash` → identical `metrics` block | double-execution test on the dry-run path; documented procedure for the real frame |
| Record validity | every record round-trips load→validate; `headline_metric` ∈ `metrics`; no bare `None` where `NotApplicable` belongs | loader-side validation exercised in tests |

Derived from the naive baseline: the reproduce row is the margin over prose — if it
holds, the "overturned but not reproduced" failure is closed.

---

## What Breaks First

The external-toolkit coupling. `ML_PACKAGE_ROOT` points at a *rendered, unpinned*
template tree — "same git SHA" in galactus does not pin the toolkit that computed the
numbers. First failure looks like: a re-run at the same SHA produces different metrics
and the record diff shows only `code.versions` changed — which is the system working,
but it will read as a reproducibility bug. Noticed via: the record diff itself (this is
why `CodeState.versions` carrying sklearn/lightgbm versions is load-bearing, not
metadata). Cheap mitigation, in scope: the record's `resolved_config` also carries the
toolkit tree's own git SHA when discoverable. Out of scope: pinning/packaging the
toolkit — that is ai-project-template's distribution question.

---

## Non-Functional Constraints

- **Data classification:** internal. Real frame is public-source but gitignored;
  aggregates-only rule in `run.py` extends to records — metrics, counts, column names,
  hashes; never a row, index, or identifier value.
- **Multi-tenancy:** not applicable — single-operator repo.
- **Operator model:** Ramsey, solo; zero API spend anywhere in this work item (tabular
  ML, no LLM calls; dry-run is also free by construction).
- **Scale:** single-machine, single-frame; dry-run must stay fast enough to live in the
  test suite.

---

## Open Questions

1. **Serializer placement** (Key Decision 3) — *revisit:* before `/proto-plan` freezes
   steps — *close via:* Ramsey's call; if template-side, file the AIT issue first and
   sequence it as a dependency.
2. **The `DESIGN.md` name collision.** This run's `docs/DESIGN.md` is the Step 14 data
   profile; the marketing-comms convention is `docs/DESIGN.md` = system design. Rename
   profile → `PROFILE.md` and let this file take the canonical name? Touches links in
   `README.md`, `run.py`, and the parity plan doc — *revisit:* at `/proto-plan`, where
   the link sweep is one step — *close via:* Ramsey.
3. **Where dry-run records go** — temp path is the default here; if the fixture record
   is instead committed as a golden file, it doubles as the loader's test vector —
   *revisit:* `/proto-design` — *close via:* whoever writes the test plan.
4. **AIT issue numbers for the three toolkit findings** (out-of-scope list) — *revisit:*
   when filing, before the plan references them — *close via:* `gh issue create` in
   ai-project-template, per the issues-live-where-the-work-lands rule.

---

## Hand-off

Next phase: `/proto-research` (BUILD entry — it will set `Track: ml`), reading this
document plus [`DESIGN.md`](DESIGN.md) for the frozen Step 15 config. The five-layer
`/proto-design` spec is not required: this is a training harness, not an agent; the only
design-band question left is Open Question 3's record-layout detail, foldable into the
plan.
