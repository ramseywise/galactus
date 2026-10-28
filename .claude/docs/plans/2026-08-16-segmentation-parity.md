# ml-segmentation parity — dry-run harness + a record shape that fits clustering
Date: 2026-08-16
Status: SUPERSEDED
From: REFINED
Superseded-by: [`2026-08-18-ml-parity-consolidated.md`](2026-08-18-ml-parity-consolidated.md)
Track: ml

> **Superseded for execution 2026-08-18 — do not execute these steps.** Consolidated with
> fraud into one pass so the shared `RunRecord`/`runs/_index/` seam is built once.
> **This doc remains the research and rationale record.**
>
> **Phase B's precondition block is obsolete in both of its conditions** — verified against
> the machine 2026-08-18:
> - `GAL-32-lending-parity` **is merged** (`git merge-base --is-ancestor … HEAD` → true).
> - The registry no longer needs rendering. `experiments/` is staged **natively in
>   galactus** and imports with `ML_PACKAGE_ROOT` unset; 24 tests pass. **Do not run
>   `make lint-render`, and do not build the `ML_PACKAGE_ROOT` seam** — old Step 5 is
>   dropped from scope as solving a problem that no longer exists. Lending already imports
>   the registry as a plain first-party package (`run_record.py:23`).
>
> Phase A (Steps 1–4) carries forward unchanged as the consolidated plan's Step 4;
> Phase B's record work becomes Step 5, now unblocked.
Branch-from: `GAL-32-lending-parity` (not `main`) — carries `runs/_index/` and the record precedent.
Epistemic: UNTESTED
Epistemic-by: dispatch failed — `resolve-capability fog` returned exit 0 (`.claude/agents/fog-advisor.md` exists), but the Agent tool rejected the dispatch: `Agent type 'fog-advisor' not found. Available agents: claude, claude-code-guide, Explore, general-purpose, Plan, statusline-setup`. The definition is repo-local to galactus and this session is rooted at `~/workspace`, where no `~/.claude/agents/` directory exists — so the agent registry never loaded it. No substitute was run (Stage 3: a substituted dispatch is a failed dispatch). Tracked as [galactus#39](https://github.com/ramseywise/galactus/issues/39); re-dispatch from a galactus-rooted session to close the pass.
Epistemic-at: 2026-08-18
Epistemic-findings: 0

Scout: [`../research/2026-08-15_ml-parity_segmentation.md`](../research/2026-08-15_ml-parity_segmentation.md)
Parent synthesis: [`2026-08-15-lending-parity.md`](2026-08-15-lending-parity.md) § Research addendum
Bar: the five parity elements from [`runs/ml/lending/docs/DESIGN-parity.md`](../../../runs/ml/lending/docs/DESIGN-parity.md)
GitHub issue: [galactus#35](https://github.com/ramseywise/galactus/issues/35) — branch `GAL-35-segmentation-parity`.

## Research

### Summary

`runs/ml/customer segmentation/` scores **2.5 of 5**: tests and data handling met (modulo
the tracked PDF, moved to the hygiene item), guards partial, dry-run and record missing.
Mechanically it is the *easiest* of the remaining runs — already modular, 49 substantive
tests, synthetic fixtures ready to serve as the dry-run substrate, and `docs/segments.json`
is already ~80% of a record payload. Conceptually it is the *hardest*: a k-means sweep has
no held-out metric and no fold plan, and `RunRecord` is shaped around a supervised
comparison. Making the shape fit is an ai-project-template decision, not galactus's.

This item is **partially blocked** — on
[AIT#83](https://github.com/ramseywise/ai-project-template/issues/83), on the `runs/_index/`
layout, and additionally on "does the record shape admit unsupervised runs?" Per the
2026-08-16 scoping decision, the plan is written in full with the record step marked
blocked; the dry-run and the guard fix land value independently.

### Scope

Investigated: the five bar elements against source; the dependency posture (no
`ML_PACKAGE_ROOT`); the record-shape mismatch; the guard rules and their twins. Out of
scope: the tracked Trade Republic PDF (moved to
[`2026-08-16-repo-hygiene-tracked-content.md`](2026-08-16-repo-hygiene-tracked-content.md)),
other runs, any modelling change to the sweep itself.

### Findings

**S1 — What the run is. (High)** Part 3 of the Trade Republic recruiting challenge:
k-means segmentation of 29,096 customers over 16 behavioural features, valued at
2020-12-31 (`src/run.py:5-8`, `docs/report.md:3`). Headline: **k=4 at silhouette 0.2548,
Davies–Bouldin 1.268**, beating a random-partition baseline (−0.0125) and the k=2 baseline
(0.2320). Full k=2..10 sweep reported (`src/run.py:96-101`); only k=3 and k=4 beat both
baselines. The artifact's own honest reading: silhouette ≈0.25 is weak separation, and the
code carries a "weak structure" refusal clause (`src/run.py:107-108`, `src/cluster.py:99-101`).

**S2 — Tests are MET. (High)** `pyproject.toml:97`;
`uv run --group ml pytest "runs/ml/customer segmentation/tests" -q` → **49 passed in
1.69s**. Substantive coverage, not surface: brace-array parsing including the `{""}` empty
sentinel and the day-first/month-first date hazard (`tests/test_load.py:10-68`); FIFO
buy/sell matching including oversell branches and hand-computed P&L
(`tests/test_features.py:15-109`); one class per leakage rule with failing *and* clean twins
plus the "empty list is not a pass" contract (`tests/test_prepare.py:24-105`);
sweep-peaks-at-true-k, noise-doesn't-beat-baselines, implausibility-fires, and seed
reproducibility (`tests/test_cluster.py:24-81`). No real row appears in any fixture
(`tests/conftest.py:1-9`).

**S3 — The dry-run is missing, and is the smallest of the five gaps. (High)** Zero
`dry_run`/`argparse` hits; `main()` (`src/run.py:60`) takes no arguments and reads the CSVs
unconditionally (`:67-69`). But the synthetic fixtures already exist
(`tests/conftest.py:22-90`), the run is fast and seeded, so the reproduce check is nearly
free. The work is largely wiring: argparse, a data-source parameter, and a temp-path record.

**S4 — Guards are MET in substance, partial on "loudly", with one real defect. (High)**
`check_leakage` runs *before any score exists* (`src/run.py:80-85`) — four rules in
`src/prepare.py:55-121` — and an implausibility alarm fires at silhouette >0.70
(`src/cluster.py:25,44-45`). Two caveats and one bug:

- **Refuse-not-abort**: exits 0 and declines to name a winner rather than aborting
  (`src/run.py:12,92-93,119`). Deliberate, inherited from fraud's stance. Per the
  2026-08-16 operator decision (addendum X2), **the bar now admits both modes** — abort for
  leakage-class violations, refuse-and-exit-0 for structure verdicts. Ratified, not a gap.
  But note the split cuts *through* this run: its leakage rules (a)–(d) are leakage-class
  and arguably should abort, while the weak-structure clause is a structure verdict that
  should refuse. The plan must decide whether the two currently share one exit path.
- **Rule (b) is a constant `True`** (`src/prepare.py:79-85`) — it asserts a contract rather
  than verifying it. A rule that cannot fail is not a guard, and the twins in
  `test_prepare.py` cannot have covered it in both directions. This is the one substantive
  code defect in the run and it is unblocked.

Portable ideas worth naming: the `Finding` dataclass plus the "empty list is not a pass"
contract (`src/prepare.py:45-61`); rule (d)'s matrix-health check (`:102-119`), which
catches a gutted feature build escaping through the weak-structure clause; and
`src/cluster.py:1-8,73-87`, where the baseline is computed **in the same call** as the
score, so no code path can yield a score without its comparator.

**S5 — The record is missing, and the shape does not obviously fit. (High)** No
`RunRecord`/`experiments.` references; `runs/_index/` does not exist; artifacts overwrite
fixed paths (`docs/segments.json`, `docs/report.md` — `src/run.py:134,215`) with the
docstring conceding the overwrite problem (`:20-24`); no git SHA anywhere.

`segments.json` is nonetheless **already a proto-record** (`src/run.py:110-134`): run_id,
valuation date, feature columns, per-input sha256(16) plus byte counts, all four leakage
verdicts, the refusal flag, n_customers, the full sweep, and chosen_k. Missing only the git
SHA, resolved-config-as-such, and a canonical shape and location.

The conceptual blocker (addendum X3): `RunRecord` is built around a supervised comparison —
headline metric, seed, fold plan. **A clustering run has no held-out metric and no fold
plan.** A segmentation record would be cheap and honest (KMeans is seeded —
`src/cluster.py:21,69,75` — and `test_reproducible_under_fixed_seed`,
`tests/test_cluster.py:40`, already asserts reproducibility), but it would carry an
*internal-validity index*, not a claim a second party can refute the way "nothing beats the
logistic baseline" can. Forcing it into the supervised shape risks the dishonest-
`NotApplicable` failure the registry's sentinel exists to prevent.

**S6 — Adding a record introduces `ML_PACKAGE_ROOT` coupling for the first time. (High)**
This run uses **galactus's own venv — no `ML_PACKAGE_ROOT`, no `ml.*` imports at all**.
Stated at `pyproject.toml:35-40` (which explicitly contrasts with fraud) and confirmed in
source (`src/run.py:38`, `src/cluster.py:15-16`, `src/prepare.py:24`; zero `os.environ`
hits). Invocation: `uv run --group ml python "runs/ml/customer segmentation/src/run.py"`.

Consequence: the What-Breaks-First toolkit-pinning risk **does not apply** — versions are
pinned in `uv.lock`. But importing `experiments.RunRecord` would introduce the
`ML_PACKAGE_ROOT` mechanism here for the first time — **net-new coupling, the opposite of
lending's situation, and a cost the record step must justify.**

**S7 — Data handling is MET for CSVs and docs. (High)** `csv/*.csv` ignored via
`.gitignore:48`; `docs/` via the explicit rule at `:47` ("aggregates derived from real
records are still real records"). `git ls-files` shows only `src/*.py`, `tests/*.py`, and
the PDF tracked. The report emits medians and cluster sizes, never a `customer_id`
(`src/run.py:186-205`). The PDF gap is real but belongs to the hygiene item.

`csv/` contents, all ignored and local: `trades.csv` 58.3 MB, `final_df.csv` 9.6 MB,
`prices.csv` 3.3 MB, `group_label.csv` 222 KB, `instruments.csv` 27 KB. **Only three are
read by the run** — `final_df.csv` and `group_label.csv` are orphaned intermediates from
Jan 2022. Also flagged: a `.DS_Store` at the run root (ignored).

### Asset verdicts (from the scout)

| Asset | Verdict | Reason |
|---|---|---|
| `src/prepare.py` | REUSE | Element 3 satisfied and tested both directions; `Finding` + "empty list is not a pass" portable. **Fix rule (b)'s constant `True`** (`:79-85`) |
| `src/cluster.py` | REUSE | Baseline computed in the same call as the score (`:1-8,73-87`); seeded (`:20-21`) |
| `src/features.py` | REUSE | FIFO P&L well-factored; `FORBIDDEN_COLUMNS` (`:61`) feeds guard rule (a); tested to the oversell branch |
| `src/load.py` | REUSE | Date-format hazard note (`:8-15`) plus a regression test — a measured hazard, not defensive style |
| `src/run.py` | ADAPT | Sound structure and provenance payload (`:110-133`); the locus of both missing elements — no argparse/dry-run, no git SHA, no `_index` write, outputs overwritten in place |
| `tests/` (49) | REUSE | conftest generators are the ready dry-run substrate |
| `docs/report.md` + `docs/segments.json` | ADAPT | Correctly ignored, aggregates-only; ~80% of a record; overwritten with no SHA — a record precursor, not a record |
| Trade Republic PDF | SKIP | Moved to the hygiene item |

### Open questions for `/proto-plan`

1. **Does the record step belong in this item at all?** It needs AIT#83 *plus* an answer to
   "does `RunRecord` admit unsupervised runs?" — a shape question galactus may not answer.
   Options: (a) plan it blocked, as lending Step 7; (b) scope this item to dry-run + guard
   fix + tests and file the record separately once the shape question resolves; (c) extend
   `segments.json` into a canonical local shape now and lift it later, accepting a
   format-fork risk that Key Decision 3 explicitly warns against.
2. **Is net-new `ML_PACKAGE_ROOT` coupling (S6) acceptable** for a record, when this is the
   one run that currently has none?
3. **Does the abort/refuse split cut through this run's own guards** (S4) — should the four
   leakage rules abort while the weak-structure clause continues to refuse?
4. **Rule (b)'s constant `True`** — fix in this item (it is unblocked and small) or file as
   its own bug?
5. **The orphaned CSVs** (`final_df.csv`, `group_label.csv`) — delete locally, or leave? No
   module reads them; they are ignored either way, so this is housekeeping, not policy.

### Dependencies

> **Superseded 2026-08-18** — this list is the research-phase record, kept as written.
> Both AIT items below have since resolved; the current dependency statement is Phase B's
> precondition block under `## Plan`. Read that one.

- **AIT#83** (`experiments/io.py` serializer) — blocks the record step.
  **[CLOSED — the serializer is written and its null-rejection contract verified in source.]**
- **"Does the record shape admit unsupervised runs?"** — an AIT question, unfiled as of
  2026-08-16. The addendum recommends filing it alongside the serializer.
  **[ANSWERED — `record.py:99-105` types both `seed` and `folds` as `X | NotApplicable`;
  no filing needed.]**
- **`runs/_index/` layout** — driven out by the lending plan. **[Still outstanding —
  `GAL-32-lending-parity` is unmerged.]**
- **A rendered AIT tree** — not identified during research, and the actual Phase B blocker.
  The registry ships only as an unrendered copier template. **[Outstanding — render recipe
  in the precondition block.]**
- The dry-run, the rule (b) fix, and any test work are **unblocked**.

## Plan
Date: 2026-08-18
Based on: `## Research` above, plus direct inspection of `src/{run,prepare,cluster,
features}.py`, `tests/conftest.py`, `pyproject.toml`, AIT's
`experiments/{record,io,fingerprint,provenance}.py` and `nbks/`, and the
`GAL-32-lending-parity` branch tree (`runs/_index/README.md`, `run_record.py`).

### Goal
Bring `runs/ml/customer segmentation/` to the five-element parity bar — a dry-runnable,
honestly-guarded harness whose runs write a `RunRecord` to `runs/_index/` — and, in doing
so, give this run the AIT coupling it currently lacks entirely: the toolkit import seam,
the experiments registry, and a staged notebook set. (Goal + decisions confirmed by
Ramsey, 2026-08-18.)

### Open Questions

Resolved by Ramsey 2026-08-18 unless marked as a plan default.

1. **Does the record step belong in this item?** — RESOLVED: **yes, live but blocked.**
   The sub-question "does `RunRecord` admit unsupervised runs?" is **answered, not open**:
   `experiments/record.py:99-105` types `seed` and `folds` as `X | NotApplicable` and its
   docstring explicitly names runs with no seed or split concept. `io.py:63-83` forbids a
   bare `null` for those fields on disk (`{"not_applicable": {"reason": ...}}` is the only
   legal absence), which is precisely the guard against the dishonest-`NotApplicable`
   failure S5 feared. So the shape fits — Phase B blocks on a *build step*, not a design
   question.

   **Re-verified 2026-08-18 (`/proto-refine`)**: `record.py:99-105` types `seed: int |
   NotApplicable` and `folds: str | NotApplicable`; its docstring names "the AI eval harness
   has no seed and no split concept (F7)" as the intended case, so Step 6's
   `folds=NotApplicable(...)` is the sanctioned use, not a workaround.
   `io.py:_decode_optional` raises on a bare `null` ("null is never a valid value for an
   optional field"). Both confirmed in source. **The correction is the word "merge":**
   AIT#83 is closed and nothing upstream is pending — what is missing is a *rendered* tree.
   See Phase B's precondition block.
2. **Is net-new `ML_PACKAGE_ROOT` coupling acceptable?** — RESOLVED: **accept and expand.**
   More coupling than exists today is wanted. Folded in: the toolkit import seam, the
   experiments registry, and an `nbks/`-style staged notebook set. Scope grew past 8 steps,
   so the plan is **split into two phases** per the skill's sizing rule. **Deliberately
   excluded**: adopting `ml.clustering.gmm` as a second model family (Ramsey, 2026-08-18) —
   that changes what the run *claims*, not just how it records, and the research doc puts
   modelling changes out of scope.
3. **Does the abort/refuse split cut through this run's own guards?** — plan's judgment.
   **Default: yes, split them.** Leakage rules (a)–(d) abort with a non-zero exit; the
   weak-structure and implausibility clauses continue to refuse-and-exit-0. Rationale: the
   X2 amendment makes the distinction *epistemic*, not stylistic. "A column restated the
   answer" means the matrix is not fit to score and there is nothing honest to report; "no
   k beat the baselines" **is** the report. The current code routes both through one
   `exit 0` path (`src/run.py:92-93,119`), which makes a leak look like a finding.
4. **Rule (b)'s constant `True`** — RESOLVED: **fix in this item** (Step 1).
5. **Orphaned CSVs** (`final_df.csv`, `group_label.csv`) — plan's judgment.
   **Default: leave them, document them.** They are gitignored, local-only, and read by
   nothing; deleting another person's local intermediates buys nothing and is
   unrecoverable. Step 4 records them as orphaned in the README instead. The `.DS_Store`
   is likewise left alone.

### Approach

Two phases split on a hard dependency boundary. **Phase A is entirely unblocked** and
carries the epistemic value: the rule (b) fix turns a decorative guard into a real one,
the abort/refuse split makes a leak distinguishable from a finding, and `--dry-run` makes
the whole path executable on synthetic fixtures that already exist. **Phase B is the
coupling expansion** and depends on a branch merge, not a design decision.

The branch cuts from `GAL-32-lending-parity`, not `main` (Ramsey, 2026-08-18): that branch
carries `runs/_index/README.md` and lending's `run_record.py`, the precedent this run's
record must match. Cutting from `main` would mean re-declaring `runs/_index/` and risking
the format fork Key Decision 3 warns against.

Tradeoff accepted: after Phase B, a bare galactus checkout no longer runs the *full* path —
the record and notebook tests need `ML_PACKAGE_ROOT` at a rendered AIT tree. Mitigated with
fraud's skip-with-reason posture, so the suite stays green with visible, reasoned skips
rather than silently collecting zero.

### Out of Scope

- **`ml.clustering.gmm` as a second model family** — the one Q2 expansion explicitly
  excluded. k-means stays the model; the sweep's claim is unchanged.
- Any other modelling change to the sweep (k range, feature set, `IMPLAUSIBLE_SILHOUETTE`,
  `LOG_COLUMNS`).
- The tracked Trade Republic PDF → `2026-08-16-repo-hygiene-tracked-content.md`.
- Deleting the orphaned CSVs or the `.DS_Store` (Open Question 5).
- Other `runs/ml/` runs; fraud parity is its own item.
- Backfilling records for past runs — the first record is the next execution.
- Fixing `experiments/io.py` or anything else upstream in AIT; Phase B consumes it as-is.

### Steps

Phase boundary between Step 4 and Step 5 is a review boundary **and** a session boundary.

---

#### Phase A — unblocked (Steps 1–4)

#### Step 1: Rule (b) — make the constant `True` a real check
**Files**: `runs/ml/customer segmentation/src/prepare.py` (lines 76–85, plus a new
module-level counter); `runs/ml/customer segmentation/tests/test_prepare.py` (add a
`TestRuleB` class alongside the existing `TestRuleA`)
**What**: Rule (b) currently asserts its contract instead of verifying it — it appends
`Finding(..., True, ...)` unconditionally, so it cannot fail and its twins cannot have
covered both directions. Make `prepare_matrix` observable: a module-level fit counter
incremented on each call, and rule (b) verifies that the number of scaler fits recorded
since the last reset is exactly one per matrix built. The rule's real content is "no
scaler was shared across calls", which is a *fact about this process*, and a counter is
the cheapest thing that can actually witness it.
**Snippet**:
```python
# before
findings.append(Finding("b_scaler_fitted_within_fold", True,
    "prepare_matrix fits a fresh StandardScaler per call; ..."))

# after
_FIT_LOG: list[int] = []   # one entry per prepare_matrix call, id() of its scaler

fits = len(_FIT_LOG)
distinct = len(set(_FIT_LOG))
passed = fits == distinct          # a reused scaler shows up as a repeated id
findings.append(Finding("b_scaler_fitted_within_fold", passed,
    f"{fits} scaler fit(s), {distinct} distinct — no scaler reused across calls"
    if passed else f"{fits} fits but only {distinct} distinct scaler(s): one was reused"))
```
`prepare_matrix` appends `id(scaler)` to `_FIT_LOG`; a `reset_fit_log()` helper lets tests
drive both directions.
**Test**: `uv run --group ml pytest "runs/ml/customer segmentation/tests/test_prepare.py" -v -k RuleB`
**Done when**: rule (b) has a test that makes it **FAIL** (a scaler reused across two
matrix builds) and one that makes it PASS, matching the both-directions posture every
other rule in this file already has. `grep -n "True," src/prepare.py` returns no
unconditional `Finding`.

#### Step 2: Split abort from refuse
**Files**: `runs/ml/customer segmentation/src/run.py` (lines 12, 80–93, 104–108, 119,
138); new `runs/ml/customer segmentation/tests/test_run_exit.py`; module docstring
(lines 10–13)
**What**: Per Open Question 3. A leakage FAIL is a matrix that is not fit to score —
abort with exit 2 after writing the report (so the evidence survives), and never reach the
sweep. A weak-structure or implausibility verdict is a *result* — keep exit 0 and the
existing refusal prose. The docstring's "A refusing run is a successful run" claim stays
true but is narrowed to structure verdicts, since it currently covers both and is what
makes the two indistinguishable.
**Snippet**:
```python
# before: one path, both cases exit 0
if not clean:
    print("\nREFUSING to report a winning k: ...")
# ... later
return 0

# after
if not clean:
    print("\nABORTING: the leakage guard reported at least one FAIL. "
          "The matrix is not fit to score; no k is reported.")
    # report still written below — the evidence outlives the abort
    _write_report(...); return 2
# structure verdicts below keep exit 0: "no k beat the baselines" IS the finding
```
**Test**: `uv run --group ml pytest "runs/ml/customer segmentation/tests/test_run_exit.py" -v`
**Done when**: a planted-leak frame drives `main()` to return **2** with `segments.json`
and `report.md` both written; a clean frame whose best k beats nothing returns **0** with
the weak-structure warning present. Both asserted, not just documented.

#### Step 3: `--dry-run` on the synthetic fixtures
**Files**: `runs/ml/customer segmentation/src/run.py` (`main()` signature at line 60,
lines 61–69, 134, 215); new `runs/ml/customer segmentation/src/synthetic.py`; new
`runs/ml/customer segmentation/tests/test_dry_run.py`
**What**: `main()` takes no arguments and reads the real CSVs unconditionally. Add
argparse with `--dry-run`, `--csv-dir`, and `--out-dir`. `synthetic.py` lifts the three
generators out of `tests/conftest.py` (they become the shared substrate; conftest imports
them rather than redefining, so there is one copy) and adds `clean_frame()` and
`planted_leak_frame()` twins. Dry-run routes every output to a temp dir — never `docs/`,
mirroring `runs/_index`'s "dry-runs never write here" rule.
**Snippet**:
```python
parser.add_argument("--dry-run", action="store_true",
    help="synthetic fixtures, outputs to a temp dir; no csv/ read, no network")
parser.add_argument("--csv-dir", type=Path, default=CSV)
parser.add_argument("--out-dir", type=Path, default=DOCS)
...
if args.dry_run:
    trades, instruments, prices = synthetic.clean_frame()
else:
    trades, report = load_trades(args.csv_dir / "trades.csv"); ...
```
**Test**: `uv run --group ml pytest "runs/ml/customer segmentation/tests/test_dry_run.py" -v`
and `uv run --group ml python "runs/ml/customer segmentation/src/run.py" --dry-run`
**Done when**: `--dry-run` exits 0 in a checkout with an empty `csv/`, writes nothing under
`docs/`, and completes in under 10s; the planted-leak twin drives the Step 2 abort (exit 2)
from a test; the existing 49 tests still pass.

#### Step 4: Phase A docs + the orphaned-CSV record
**Files**: new `runs/ml/customer segmentation/README.md`;
`runs/ml/customer segmentation/src/run.py` (docstring lines 1–28)
**What**: There is no README for this run — the only entry point is a docstring. Write one
covering: what the run is, the invocation (real and `--dry-run`), the exit-code contract
from Step 2 (0 = result or honest refusal, 2 = leakage abort), and a Data section naming
`final_df.csv` and `group_label.csv` as **orphaned Jan-2022 intermediates read by no
module** (Open Question 5 — recorded rather than deleted). Update the docstring's RUNNING
IT and its "refusing run" paragraph to match the split.
**Test**: `uv run --group ml pytest "runs/ml/customer segmentation/tests" -q` (full suite)
and `grep -rn "exits 0" "runs/ml/customer segmentation/src/run.py"` shows only
structure-verdict statements.
**Done when**: a reader can run both modes and predict the exit code from the README alone;
no document claims a leakage FAIL exits 0.

**Phase A gate**: full suite green (49 + new tests), `--dry-run` exits 0, `/proto-review`
before the first commit. Phase A is independently shippable — if Phase B blocks, this
still closes the dry-run and guard elements of the bar.

---

#### Phase B — coupling expansion (Steps 5–8) — **BLOCKED**

**Precondition, checked before Step 5 begins.** Two conditions, and the second is *not*
what an earlier draft of this plan claimed. Corrected 2026-08-18 during `/proto-refine`,
against the machine rather than against the issue tracker:

1. **`GAL-32-lending-parity` merged** — gives `runs/_index/` and the `run_record.py`
   precedent. Still outstanding: the branch exists (`origin/GAL-32-lending-parity`) but is
   unmerged, and `runs/_index/` is absent from any other working tree.

2. **A *rendered* ai-project-template tree exists, and `ML_PACKAGE_ROOT` points at it.**
   The earlier statement — "blocks on AIT#83 merging" — is **wrong and would send an
   execute session looking for an upstream PR that already landed.**
   [AIT#83](https://github.com/ramseywise/ai-project-template/issues/83) is **CLOSED**;
   `experiments/io.py` is written and carries exactly the `_decode_optional` null-rejection
   contract Open Question 1 relies on (verified in source, 2026-08-18).

   The real blocker is that the registry ships **only as an unrendered copier template**.
   It lives at `template/_scaffold/{{ py_project_root }}/experiments/` — a path containing
   literal Jinja braces, unimportable by construction. No rendered tree existed anywhere on
   the machine at plan time (`find ~/workspace -name record.py -path '*experiments*'`
   returned only the template). **This is a prerequisite action, not a risk to monitor.**

**Rendering the tree (the prerequisite, verified end-to-end 2026-08-18):**

```bash
cd ~/workspace/ai-project-template
make lint-render PROFILES=ml DST=<render-root>     # copier 9.17.0; ~161 files, lints clean
export ML_PACKAGE_ROOT=<render-root>/ml/backend    # py_project_root defaults to 'backend'
```

`ML_PACKAGE_ROOT` points at the **`backend/` directory, not the tree root** — `copier.yaml`
defaults `py_project_root` to `backend` (`use_flat_layout: false`), so the registry lands at
`<render-root>/ml/backend/experiments/`. Pointing it at the tree root is the obvious wrong
guess and fails with an unhelpful `ImportError`.

Confirmed working against a scratch render: `experiments.io.{write_record,read_record}`,
`experiments.record.{ExecutionConfig,NotApplicable,RunRecord}`,
`experiments.fingerprint.fingerprint_frame`, and `experiments.provenance.capture_code_state`
all import — the complete surface Steps 6 and 7 name.

**The render is disposable and must not be committed.** It is a build artifact of AIT, not
galactus content; render it outside the galactus tree (a scratch dir or `/tmp`). A rendered
tree inside `runs/` would be tracked content of the kind
[`2026-08-16-repo-hygiene-tracked-content.md`](2026-08-16-repo-hygiene-tracked-content.md)
exists to remove.

**Verification gate**, run before Step 5 begins — both must pass:

```bash
git merge-base --is-ancestor origin/GAL-32-lending-parity HEAD   # condition 1
ML_PACKAGE_ROOT=<path> uv run --group ml python -c \
  "import sys,os; sys.path.insert(0, os.environ['ML_PACKAGE_ROOT']); import experiments.io"
```

If either fails: **stop, land Phase A, report the block.** Do not write a galactus-side
serializer — Key Decision 3.

#### Step 5: The `ML_PACKAGE_ROOT` import seam
**Files**: `runs/ml/customer segmentation/src/run.py` (imports, after line 40);
`runs/ml/customer segmentation/tests/conftest.py` (skip marker);
`runs/ml/customer segmentation/README.md`
**What**: This run has zero `os.environ` hits and imports nothing from `ml.*` — Q2's
"accept and expand" starts here. Add fraud's guard verbatim in shape (`src/run.py:58-76`):
`ML_PACKAGE_ROOT` prepended to `sys.path`, the toolkit import in a `try` whose `except`
raises `SystemExit` with a sentence rather than a stack trace. Only `experiments.*` is
imported — the sweep still runs on galactus's own venv, so `--dry-run` and every Phase A
test stay toolkit-free.
**Snippet**:
```python
_ml_root = os.environ.get("ML_PACKAGE_ROOT")
if _ml_root:
    sys.path.insert(0, _ml_root)
try:
    from experiments.io import write_record
    from experiments.record import ExecutionConfig, NotApplicable, RunRecord
except ImportError as exc:
    raise SystemExit(f"could not import the experiments registry ({exc}). ...") from exc
```
Conftest gains `requires_toolkit = pytest.mark.skipif(not os.environ.get("ML_PACKAGE_ROOT"),
reason="needs ML_PACKAGE_ROOT at a rendered ai-project-template tree")`.
**Test**: `ML_PACKAGE_ROOT=<tree> uv run --group ml pytest "runs/ml/customer segmentation/tests" -q`
and the same bare.
**Done when**: with the env set, the registry imports and the suite is green; with it
unset, the suite is green with the toolkit tests **visibly skipped** and the reason naming
the variable. A bare checkout never errors.

#### Step 6: `segmentation_record.py` — the unsupervised `RunRecord`
**Files**: new `runs/ml/customer segmentation/src/segmentation_record.py`; new
`runs/ml/customer segmentation/tests/test_record.py`
**What**: `assemble_run_record(features, matrix_columns, findings, results, winner, args)`.
Named `segmentation_record`, not `record`, for the same `sys.path` shadowing reason lending
documents. The honest-absence decisions, which are the substance of this step:
- `seed=RANDOM_STATE` (`cluster.py:21`) — a real seed; KMeans is seeded and
  `test_reproducible_under_fixed_seed` already pins it. **`NotApplicable` here would be a
  bug.**
- `folds=NotApplicable("k-means over the full customer frame has no split concept — there
  is no held-out set and no fold plan; the sweep scores every k on the same matrix")` —
  the legitimate use, and exactly the case `record.py:100-105` names.
- `metrics` = flat map: `silhouette_k{k}`, `davies_bouldin_k{k}`, `baseline_random_k{k}`,
  `baseline_k2` for every k in the sweep. `headline_metric = f"silhouette_k{winner.k}"`.
- `run_kind="clustering"` — a new kind alongside lending's `"classification"`.
- `data=fingerprint_frame(features[list(matrix_columns)])` — the frame **as fitted**.
- `resolved_config` carries `FEATURE_COLUMNS`, `LOG_COLUMNS`, `VALUATION_DATE`,
  `k_range`, `IMPLAUSIBLE_SILHOUETTE`, `SILHOUETTE_SAMPLE`, the four leakage verdicts, the
  per-input sha256 block already built at `run.py:114-117`, and a `toolkit` entry from a
  second `capture_code_state(repo=Path(ML_PACKAGE_ROOT))` — lending's F7 mitigation.
**Test**: `ML_PACKAGE_ROOT=<tree> uv run --group ml pytest "runs/ml/customer segmentation/tests/test_record.py" -v`
**Done when**: a `--dry-run` produces a valid in-memory `RunRecord`; `headline_metric ∈
metrics`; `seed` is an int and `folds` is a `NotApplicable` **whose reason names the
absent split concept**; constructing with `folds=None` raises (regression pin on the
registry contract); `code.git_sha` is a real SHA.

#### Step 7: Persist to `runs/_index/` + the reproduce check
**Files**: `runs/ml/customer segmentation/src/run.py` (write call in `main()`); new
`runs/ml/customer segmentation/tests/test_reproduce.py`; `runs/_index/README.md` (one
line — a second harness now writes here)
**What**: Real runs write `runs/_index/{utc_timestamp}-{frame_hash[:8]}.json` via
`io.write_record`. Dry-runs write the identical format to the temp dir Step 3 already
routes to — never `runs/_index/`. Reproduce check: execute the dry-run path twice at the
same seed, assert the `metrics` blocks are byte-identical; round-trip
`read_record(write_record(...))` so the frozen dataclasses reconstruct and re-fire their
own validation. The `NotApplicable` on `folds` must survive the round-trip **as a tagged
object**, not a `null` — that is the assertion this run contributes that lending's could
not, since lending has no inapplicable field.
**Test**: `ML_PACKAGE_ROOT=<tree> uv run --group ml pytest "runs/ml/customer segmentation/tests/test_reproduce.py" -v`
**Done when**: dry-run record round-trips load→validate; double execution yields identical
metrics; the on-disk JSON shows `"folds": {"not_applicable": {"reason": ...}}` and **no
`null`** anywhere in the optional fields; `runs/_index/` gains no file from any test run.

#### Step 8: Staged notebooks
**Files**: new `runs/ml/customer segmentation/nbks/` — `00_data_contract.py`,
`01_eda.py`, `02_features.py`, `03_clustering.py`, `04_segments.py`, `README.md`
**What**: The second half of Q2's expansion. Follow AIT's `nbks/` conventions exactly:
`# %%` percent-style plain `.py` (git-diffable, Jupytext-openable), **logic lives in the
module — the notebook narrates and calls**, each notebook answers one named question, and
each falls back to `synthetic.py` (Step 3) when `csv/` is absent so all five run on a
fresh clone. Mapping to this run's stages, not AIT's supervised ones: `00` the brace-array
and date-format contract (`load.py`), `01` feature distributions and the skew that
justifies `LOG_COLUMNS`, `02` the FIFO P&L build, `03` the sweep and both baselines, `04`
the chosen-k segment profiles. No notebook computes a metric or a rule that isn't in a
module.
**Test**: `for f in "runs/ml/customer segmentation/nbks/"*.py; do uv run --group ml python
"$f" || exit 1; done` with `csv/` empty — all five exit 0 on synthetic data.
**Done when**: all five run headless on a fresh clone; each opens with a markdown cell
naming its question; a `grep` for `silhouette_score|StandardScaler|KMeans(` in `nbks/`
finds only calls into `src/`, never a reimplementation.

### Test Plan

- **Baseline**: `uv run --group ml pytest "runs/ml/customer segmentation/tests" -q` →
  **49 passed in 2.05s** (verified 2026-08-18). Must be 49 + new at every step, never fewer.
- **Toolkit-free** (always run, bare checkout): `test_load`, `test_features`,
  `test_prepare`, `test_cluster`, `test_run_exit`, `test_dry_run` — Phase A never touches
  `ML_PACKAGE_ROOT`.
- **Toolkit-coupled** (skip-with-reason when unset): `test_record`, `test_reproduce`.
- New test files must be picked up by the existing `testpaths` entry
  (`"runs/ml/customer segmentation/tests"`, `pyproject.toml:99`) — already present, so no
  `pyproject.toml` change is needed. Verify by count, not assumption.
- **Exit gate**: full suite green with visible reasoned skips in a bare checkout;
  `--dry-run` exits 0 with an empty `csv/`; a planted-leak run exits 2.

### Risks & Rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `GAL-32` doesn't merge before execute reaches Step 5 | Medium | Phase B stalls | Phase A is independently shippable and carries the epistemic value; Step 5's precondition stops loudly rather than forking the format |
| ~~Rendered AIT tree lacks `experiments/io.py`~~ **No rendered AIT tree exists at all** | ~~Medium~~ **Certain at plan time** | Steps 5–8 cannot start | **Not a risk — a prerequisite.** Promoted into Phase B's precondition block with the verified `make lint-render` recipe. Re-rated 2026-08-18: the registry is real and closed upstream (AIT#83), but ships only as an unrendered template, so the tree's absence is a present fact, not a probability. `experiments/io.py` itself is *not* missing — that framing was the error |
| `ML_PACKAGE_ROOT` pointed at the render root instead of `<render>/ml/backend` | Medium | Step 5 fails with a bare `ImportError` | `py_project_root` defaults to `backend`; the precondition block names the exact path and the gate command proves it before Step 5 writes anything |
| The rendered AIT tree gets committed to galactus | Low | Tracked build artifact — the hygiene item's exact failure | Precondition says render outside the galactus tree; it is AIT's build output, not galactus content |
| Step 1's fit-counter is process-global and leaks across tests | Medium | Flaky rule (b) | `reset_fit_log()` in a fixture; the counter is only read by `check_leakage`, never by the sweep |
| Step 2's exit-2 breaks a caller expecting 0 | Low | — | Nothing calls this run programmatically (`grep` for `run.main` finds only `__main__`); the README states the contract |
| Notebooks drift from `src/` | Medium | Docs rot | Step 8's grep gate plus headless execution in the test plan — a drifted notebook fails to run, not merely to match |
| Coupling makes a bare checkout less useful | Accepted | — | Named in Approach; skip-with-reason keeps the bare suite green and honest |

**Rollback**: branch-only, no persistent state, no external effect. `git reset --hard
GAL-32-lending-parity` discards everything. Phase A and Phase B are separately revertible
at the phase boundary.
