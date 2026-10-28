# ml parity — one execute across fraud, segmentation, and credit sourcing
Date: 2026-08-18
Status: READY
Track: ml
Epistemic: NO_CONFLICT
Epistemic-by: fog
Epistemic-at: 2026-08-18
Epistemic-findings: 7
Epistemic-resolved-at: 2026-08-20
Epistemic-resolved-note: All 7 fog findings addressed — M1–M5 closed in replan steps (landed via PR #41, 2026-08-18); M6 and M7 explicitly deferred by operator decision and do not block execution.
Replan-at: 2026-08-18
Replan-closes: M1, M2, M3, M4, M5
Replan-open: M6, M7

> **Gate 2026-08-18: NOT-READY.** Four blocking findings, all independently verified by the
> gate rather than taken from the advisor. See `## Refinement — what is missing`.
>
> **Re-plan 2026-08-18 (this pass): M1–M4 closed in the steps below.** Each was re-verified
> against the machine a second time before being written into a step — and that second pass
> **falsified M2's prescribed fix** (see `## Re-plan — how M1–M4 are closed`). New Step 0
> lands the import/skip seam; Step 1 gains an enforcing `persist()` plus a lending call-site
> switch; Step 5 takes `seed=RANDOM_STATE`; Step 6 no longer overwrites. M5 is written into
> Step 3. M6 and M7 remain open and out of scope, by decision.

> **Refine 2026-08-20: READY.** All plan steps landed in PR #41 (merged 2026-08-18 as
> `GAL-34-fraud-parity`). Verified against `origin/main`: `experiments/` (10 files),
> `runs/_shared/parity.py`, `runs/ml/fraud/src/fraud_record.py`,
> `runs/ml/customer segmentation/src/segmentation_record.py`,
> `runs/ml/credit/docs/PROVENANCE.md` all tracked. Full suite: **653 passed, 0 skipped**
> (baseline was 624/14 skipped — all 14 skip gaps closed). Lending tests: 39 passed, 0
> skipped; importability probe in place. `persist()` is the sole chokepoint into
> `runs/_index/` (lending call site confirmed at `run.py:235`). Branch `GAL-34-fraud-parity`
> no longer exists (merged). `Epistemic: CONFLICTED` → `NO_CONFLICT`: M1–M5 findings
> resolved by the landed steps; M6 and M7 deferred by operator decision and do not block.
> Issue #35 remains open — see DoD note below.

Supersedes (execution only): [`2026-08-16-fraud-parity.md`](2026-08-16-fraud-parity.md),
[`2026-08-16-segmentation-parity.md`](2026-08-16-segmentation-parity.md). Both remain the
research + rationale record; **this doc is the only one an execute session follows.**
Research for the credit slice: [`2026-08-18-ml-frame-sourcing.md`](2026-08-18-ml-frame-sourcing.md)
Design: [`../DESIGN-ml-frame-sourcing.md`](../DESIGN-ml-frame-sourcing.md)
Bar: [`runs/ml/lending/docs/DESIGN-parity.md`](../../../runs/ml/lending/docs/DESIGN-parity.md)
GitHub issues: [galactus#34](https://github.com/ramseywise/galactus/issues/34) (fraud),
[galactus#35](https://github.com/ramseywise/galactus/issues/35) (segmentation),
[galactus#36](https://github.com/ramseywise/galactus/issues/36) (credit)

## Why this doc exists

Three plans, written 2026-08-16, each ending in a step that persists a `RunRecord` to
`runs/_index/`. Executing them separately means standing up the same seam three times and
reconciling three record shapes afterwards. **Consolidated into one execute** because the
shared work is genuinely one task, not three similar ones.

More importantly: **the blockers those plans stopped on are gone.** Verified 2026-08-18
against the machine, not the issue tracker.

| Blocker as written | State 2026-08-18 | Evidence |
|---|---|---|
| `runs/_index/` does not exist (fraud Step 5, seg Phase B cond. 1) | **RESOLVED — exists and is tracked** | `git ls-files runs/_index` → `README.md`; the cross-run grain contract is already written |
| Registry ships only as an unrendered copier template; needs `make lint-render` + `ML_PACKAGE_ROOT` (seg Phase B cond. 2) | **RESOLVED — obsolete** | `experiments/` is staged **natively in galactus**; `import experiments.io` works with `ML_PACKAGE_ROOT` unset. 24 tests pass; registered in `testpaths:112` |
| `GAL-32-lending-parity` unmerged (seg Phase B cond. 1) | **RESOLVED — merged** | `git merge-base --is-ancestor origin/GAL-32-lending-parity HEAD` → true |
| Lending Step 7 marked `✓ DONE` but did not land (fraud OQ6) | **STALE — it landed** | `runs/ml/lending/src/run_record.py` exists and imports `experiments.record` directly (`:23`); `tests/test_reproduce.py` exists |

**The `ML_PACKAGE_ROOT` seam is dropped from scope.** Segmentation's Step 5 existed to
build an import seam to a rendered external tree. Lending already imports the registry as a
plain first-party package. Building the seam now would add coupling to solve a problem that
no longer exists.

## What changed today, and what it invalidates

1. **Credit rename landed** (issue #36's mechanical half). `runs/ml/credit/` now holds all
   four tracked files; `run.py` and `eda.py` verified importing at the new path.
2. **Credit's frame decision is confirmed** — UCI, CC BY 4.0, horizon source-stated,
   prevalence download-verified at 22.12%.
3. **Fraud's frame decision is NOT settled.** The chosen Kaggle frame has no stated label
   horizon, failing the design's own hard constraint. **This invalidates the premise of
   `2026-08-16-fraud-parity.md`**, which is titled "a record for a refusal" and hard-codes
   the refusal's measured values (PR-AUC 0.0200, `min_positives_in_fold: 2`,
   `threshold: null`). On the proposed frame the guard passes and there is no refusal to
   record.

**Consequence for scope:** fraud's *harness* work (dry-run, record assembly, persistence)
is frame-independent and proceeds. Fraud's *frame swap* does not, and is deliberately out
of scope here pending an operator decision.

## Plan

### Goal

One execute pass that brings fraud and segmentation to the five-element parity bar and
lands credit's UCI sourcing, sharing a single record/persistence seam — without touching
the fraud frame decision that is still open.

### Open Questions

All inherited questions from the two source plans are resolved there and carried forward
unchanged; they are not re-litigated here. Two remain live:

1. **Fraud's label horizon / frame choice** — **BLOCKING for the frame swap only, not for
   this plan's steps.** Needs an operator decision (narrow the standard and adopt Kaggle
   with the horizon recorded as unknown, or hold it and source/synthesize a frame). Every
   step below is written to be correct under either outcome, because none of them changes
   which CSV fraud loads.
2. **Fraud's Kaggle license unverified** — blocks committing any fraud artifact *derived
   from that frame*. Does not block this plan, which commits no such artifact.

**Resolved this pass (operator, 2026-08-18):**

3. **How to close M3a — guard the call site or the directory?** → **Guard the directory.**
   `persist()` refuses any target under `INDEX_ROOT` when `dry_run`, *and* lending is routed
   through it in the same pass. One enforcing chokepoint; `record_destination` degrades to a
   naming helper. Rejected: leaving lending advisory (keeps the two-write-path window open),
   and a pre-commit hook on `runs/_index/` (right layer per CLAUDE.md, but heavier than this
   plan needs — revisit when a real record is first published).
4. **What Step 0 does if the un-skip surfaces failures?** → **Stop and report.** Landing the
   fix and repairing whatever it exposes, in one step, would destroy the evidence that M1
   was real. The one coupling already identified (`test_record.py:74` ↔
   `_toolkit_code_state`) is named in the step and fixed there; anything further is a
   finding, and it blocks Steps 1–5.
5. **How to protect credit's outgoing CSV (M3b)?** → **Hash-and-record, then write UCI
   alongside.** No overwrite at all, so the irreversibility disappears rather than being
   mitigated. Rejected: overwrite-after-hashing (still destroys the only copy), and
   verifying the external lebanese-blonde checkout (makes the plan depend on a tree outside
   this repo).
6. **Does M7 (the tracked-but-"ignored" PDF) enter scope?** → **No.** It stays recorded in
   `## Refinement` as its own item. Step 7 must not write prose asserting that file's
   gitignore status while the contradiction stands.
7. **Does M6 (Step 2's fixture-agrees-with-implementation weakness) enter scope?** → **No,
   this pass.** Left explicitly open below.

### Approach

Step 0 makes the existing suite honest. Steps 1–2 are the shared seam, done once. Steps 3–5
are per-run and independent of each other. Step 6 is credit's sourcing slice. Step 7 is docs.

**Ordering constraint:** **Step 0 is a hard gate before everything.** It lands alone and its
result is reported before Step 1 opens — the seam Steps 1–5 build on is currently unverified
by 14 tests that do not run, so building first and un-skipping later would mean discovering
a broken precedent after three runs already depend on it. Then Step 1 before Steps 3–5 (they
consume the helper). Steps 3, 4, 5 may land in any order. Step 6 is independent of the seam
and may run any time after Step 0.

### Out of Scope

- **Swapping fraud's frame** — blocked on Open Question 1. No step edits fraud's
  `DEFAULT_DATA` or loads the Kaggle CSV.
- **Editing `runs/ml/fraud/docs/DESIGN.md`** — pre-registration; out by operator
  instruction and by the design doc.
- **The `ML_PACKAGE_ROOT` import seam** (old seg Step 5) — obsolete, see above.
- **Rendering an AIT tree** (old seg Phase B precondition) — obsolete.
- Adopting `ml.clustering.gmm` as a second family — excluded by Ramsey 2026-08-18.
- Fixing `experiments/` upstream — consumed as-is.
- Credit's gate-1a/1b harness work (label horizon *config*, splitter, cost ratio) — still
  blocked on operator input per issue #36; the frame swap does not unblock it.
- Lending, beyond reading it as precedent.

### Steps

#### Step 0: un-skip the seam — make the 14 green-by-omission tests run (closes M1, M2)
**Files**: `runs/ml/lending/tests/test_dry_run.py` (~27–52), `runs/ml/lending/tests/test_record.py`
(~1–10, 70–82), `runs/ml/fraud/tests/test_summary.py` (~10–48), `runs/ml/fraud/tests/conftest.py`
(~18–26); `runs/ml/lending/src/run_record.py` (~56–75)
**What**: Nothing below may be built on a seam whose tests do not run. This step lands first
and alone.

**M2's prescribed fix does not work, and the step must not attempt it.** The gate wrote
"with the repo root on `pythonpath`, the full suite goes 624 passed/14 skipped → 638
passed/0 skipped." Re-verified 2026-08-18 by patching `pythonpath = [".", …]` and running
the full suite: **624 passed, 14 skipped — unchanged.** The reason is in the predicate, not
the path: `test_dry_run.py:42-44` reads `os.environ.get("ML_PACKAGE_ROOT")` and returns
`False` *before* attempting any import, so no `sys.path` change can reach it. The lever that
actually moves the number is the env var (`ML_PACKAGE_ROOT=$PWD uv run pytest -q` → **638
passed, 0 skipped**, re-verified). `pythonpath` is therefore neither necessary nor
sufficient; the predicates themselves are the change.

Replace the env-var gate with an **importability probe** in all three predicates — gate on
whether `import ml.workflows.classification` and `import experiments.record` actually
succeed, not on whether a variable is set. Both packages are first-party and tracked
(`git ls-files ml` → 36 files, 33 `.py`; `experiments/` → 10 files, now **committed**), so
the probe succeeds bare and the tests run. Keep the skip as a real fallback for a checkout
where the import genuinely fails — a probe that cannot skip is just a crash.

**Correct the two stale reasons rather than deleting them** (both are load-bearing prose
that is now false):
- fraud `test_summary.py:47` — "ml/ holds only stale `__pycache__`" is false.
- lending `test_dry_run.py:39-41` — "un-skipping would run against a tree with no
  `experiments/`" is false; `experiments/` is at the repo root and committed.

**The un-skip exposes one real coupling — fix it here, in this step.** `test_record.py:74`
asserts `toolkit["root"]` is truthy, and it passes today *only because the un-skip is driven
by setting `ML_PACKAGE_ROOT`. With the env var unset, `_toolkit_code_state()`
(`run_record.py:62-75`) returns `{"root": None, …}` and that assertion fails.
`_toolkit_code_state` keys on the env var for **provenance**, not imports, and its
`NotApplicable` reason ("the toolkit reached sys.path by other means") is now stale in the
same way the skip reasons are: the toolkit is first-party, and the tree to fingerprint is
this repo. Have it fall back to `capture_code_state(repo=GALACTUS_ROOT)` with `root` naming
the in-repo path when the env var is unset, and update `test_record.py`'s assertion to
accept that. This keeps the invariant the test exists to protect — *the record always names
a fingerprintable tree; `None` is never an answer* — which is exactly what M1 says was going
unchecked.
**Snippet** (the predicate, all three sites):
```python
# before — gates on the variable, so a skip renders identically to a pass
def _toolkit_available() -> bool:
    root = os.environ.get("ML_PACKAGE_ROOT")
    if not root:
        return False
    ...

# after — gates on whether the import works; the env var only *adds* a path
def _toolkit_available() -> bool:
    root = os.environ.get("ML_PACKAGE_ROOT")
    if root and root not in sys.path:
        sys.path.insert(0, root)
    try:
        import experiments.record  # noqa: F401
        import ml.workflows.classification  # noqa: F401
    except Exception:  # noqa: BLE001 — cannot test ≠ crash
        return False
    return True
```
**Test**: `uv run pytest -q` — bare, no env var.
**Done when**: the bare suite reports **638 passed, 0 skipped**; `ML_PACKAGE_ROOT=$PWD uv run
pytest -q` reports the same, so the two paths agree; and no test file gates on the env var's
presence.
**If any of the 14 fails instead of passing** (beyond the `test_record.py:74` coupling named
above, which this step fixes): **stop and report — do not repair it inside this step.**
Confirmed with the operator 2026-08-18. The un-skip's whole purpose is to find out what was
hidden; a session that quietly fixes what it finds destroys the evidence that M1 was real.
A failure here is a finding for the operator, and it blocks Steps 1–5 rather than being
worked around.

#### Step 1: `runs/_shared/parity.py` — the record helper, written once
**Files**: new `runs/_shared/__init__.py`, `runs/_shared/parity.py`; new
`runs/_shared/tests/test_parity.py`; `pyproject.toml` (`testpaths`);
`runs/ml/lending/src/run.py` (~236–244, the call site only)
**Depends on**: Step 0 green. Do not start this step while any of the 14 are skipped.
**What**: Lift the parts of `runs/ml/lending/src/run_record.py` that are run-agnostic:
`_tagged()` (the `NotApplicable` → on-disk tagged-dict coercion, `run_record.py:46-54`),
`_toolkit_code_state()` (`:56-75`), and a `persist(record, *, dry_run, target)` wrapper
enforcing the one invariant both plans state independently: **a dry-run never writes under
`runs/_index/`**.
**Why a new module rather than importing lending's**: `run_record.py` is run-specific below
line 77 (`assemble_run_record` knows lending's args and metrics). Importing it from fraud
would couple two runs through a file that is not a contract.
**Do not re-implement serialization.** `experiments.io.write_record` is the writer.

**`persist()` guards the directory, not the call site (closes M3a).** Confirmed with the
operator 2026-08-18. The invariant is a property of `runs/_index/` — a committed directory
whose records cannot be un-published by `git revert` — so it must be enforced where the
write happens, once, for every caller. Lending's `record_destination`
(`run.py:115-122`) is **advisory**: its `dry_run` branch *redirects* the path, but nothing
stops a caller handing it an index path, and it returns a `Path` that `write_record` then
writes unconditionally (`run.py:235-244`). Two write paths to a committed directory is the
irreversibility M3 names.
```python
# runs/_shared/parity.py
INDEX_ROOT = GALACTUS_ROOT / "runs" / "_index"

def persist(record, *, dry_run: bool, target: Path) -> Path:
    """The one chokepoint into `runs/_index/`. A dry-run never writes there — enforced
    against the resolved target, so no caller can opt out by constructing its own path."""
    resolved = target.resolve()
    if dry_run and (resolved == INDEX_ROOT or INDEX_ROOT in resolved.parents):
        raise ValueError(f"dry-run may not write under {INDEX_ROOT}: {resolved}")
    return write_record(record, target)
```
**Route lending through it in the same pass** — the call-site switch, not a refactor of
`assemble_run_record`:
```python
# runs/ml/lending/src/run.py:235 — before
written = write_record(record, record_destination(dry_run=args.dry_run, ...))
# after — same destination logic, now behind the enforcing chokepoint
written = persist(record, dry_run=args.dry_run,
                  target=record_destination(dry_run=args.dry_run, ...))
```
This is deliberately the *smallest* change that closes the second write path: `record_destination`
keeps owning naming, `persist` owns the invariant. Converging lending's `_tagged` /
`_toolkit_code_state` onto the shared copies stays a named follow-up — **the risk table's
"two record shapes" entry survives this step and is not claimed as closed.**
**Test**: dry-run target under `runs/_index/` raises; dry-run target *outside* it succeeds;
a real-run target under `runs/_index/` succeeds; a caller passing a hand-built index path
under `dry_run=True` still raises (the call-site-bypass case that motivates the guard);
`read_record(write_record(r)) == r` round-trips and re-fires validation.
**Done when**: `uv run pytest runs/_shared/tests -q` passes; `testpaths` includes
`runs/_shared/tests` (per CLAUDE.md — an unregistered test dir collects zero tests, which
reads exactly like passing); and `grep -rn 'write_record(' runs/` shows **no direct call
outside `runs/_shared/parity.py`**.

#### Step 2: `runs/_index/` write path proven end-to-end
**Files**: `runs/_shared/tests/test_parity.py`
**What**: One test that writes a real record to a temp dir in `runs/_index/` *format* and
reads it back, asserting the naming contract from `runs/_index/README.md`
(`{utc_timestamp}-{frame_hash[:8]}.json`) and that the record carries **aggregates only** —
no row, row index, or identifier value. The README already defines this repo-wide; this
step makes it executable rather than prose.
**Test**: `uv run pytest runs/_shared/tests -q`
**Done when**: the grain contract is enforced by a test, not a README.

#### Step 3: fraud — `--dry-run`, synthetic frame, record, persistence
**Files**: `runs/ml/fraud/src/run.py`; new `runs/ml/fraud/src/fraud_record.py`; new
`runs/ml/fraud/tests/test_dry_run.py`, `tests/test_reproduce.py`
**What**: Fraud's old Steps 1, 2, 4, 5 collapsed into one, now that Step 5 is unblocked.
Add `build_synthetic_frame(n_rows, n_positives, seed)` beside `build_frame`, matching the
real column contract (`default` target, a `uuid` column so the drop path is genuinely
exercised). Add `--dry-run`, `--n-rows`, `--n-positives` to the parser. Branch **the frame
source only** in `main()` — `assess_sufficiency`, `run_classification`, `summarise`, and
`write_fraud_report` stay on one path so the dry-run exercises the real pipeline.
**Two shapes, per the old plan's reasoning, which survives the frame question**: the
default mirrors the measured 800/14 frame so the dry-run refuses exactly as the real run
does; a second shape passes the guard so the threshold-formatting branch
(`run.py:207-219`) is exercised rather than staying dark forever. **This is now the
falsifiability argument for the guard, and it does not depend on which CSV fraud
eventually loads** — which is precisely why this step is safe to execute with Open
Question 1 still open.
Then `assemble_run_record()` per lending's precedent: real metrics,
`headline_metric: "average_precision"`, and the refusal (when it occurs) carried in
`execution.resolved_config` as the withheld-costs fact. **`NotApplicable` is not used** —
every field here has meaning (fraud's resolved OQ1).
**Assert the guard's contract, never the frame's shape (closes M5).** The "frame-independent"
argument holds for the loader but leaks at the test oracle: calibrating the synthetic default
to 800/14 *because that is today's frame* and then asserting "it refuses" produces a test that
still passes, and still means nothing, if the frame swap later lands and the real run stops
refusing. Write the oracle against the guard's own predicate — **positives-per-fold below the
floor ⇒ refusal, and the refusal names the floor it violated** — parameterised over both
shapes, so the passing shape proves the branch and the refusing shape proves the guard.
Do not hard-code `0.0200`, `2`, or `null` as expected values anywhere in the tests; those are
measurements of a frame under an open question (OQ1), not contract.
**Test**: `uv run pytest runs/ml/fraud/tests -q`; two dry-runs at one seed → identical
`metrics`.
**Done when**: fraud scores 5/5 against the bar; dry-run asserts it never calls
`build_frame` and never writes under `runs/_index/`; and no fraud test asserts a value
that would have to change when the frame does.

#### Step 4: segmentation Phase A — rule (b), abort-vs-refuse, dry-run
**Files**: `runs/ml/customer segmentation/src/prepare.py` (~76–85);
`runs/ml/customer segmentation/src/run.py` (~92–93, 119);
`tests/test_prepare.py` (new `TestRuleB`)
**What**: Unchanged from segmentation's Phase A, which was never blocked.
- **Rule (b)** currently appends `Finding(..., True, ...)` unconditionally — it asserts its
  contract instead of verifying it, so it cannot fail. Add a module-level scaler-fit counter
  and have rule (b) verify exactly one fit per matrix built. The rule's real content is "no
  scaler was shared across calls," a fact about this process, and a counter is the cheapest
  thing that can witness it.
- **Split abort from refuse**: leakage rules (a)–(d) abort non-zero; weak-structure and
  implausibility clauses refuse-and-exit-0. Today both route through one `exit 0`, which
  makes a leak look like a finding.
- **`--dry-run`** on the existing synthetic fixtures.
**Test**: `uv run pytest "runs/ml/customer segmentation/tests" -q`
**Done when**: rule (b) can fail; a leak exits non-zero; a null result exits 0.

#### Step 5: segmentation Phase B — the unsupervised record
**Files**: new `runs/ml/customer segmentation/src/segmentation_record.py`;
`tests/test_record.py`, `tests/test_reproduce.py`
**What**: Formerly BLOCKED, **now unblocked** — `experiments/` is importable natively and
`runs/_index/` exists. Build the `RunRecord` for a run with **no split concept**:
`folds=NotApplicable(reason=...)` per `record.py:99-105`, whose docstring names exactly this
case.

**`seed` takes `RANDOM_STATE` — it is not `NotApplicable` (closes M4).** The earlier draft
described this run as having "no seed," which is false. Re-verified 2026-08-18:
`cluster.py:21` defines `RANDOM_STATE = 0` and four sites consume it — `random_state=` at
`:56`, `np.random.default_rng(RANDOM_STATE)` at `:63`, and `KMeans(..., random_state=)` at
`:69` and `:75`. The run's `silhouette` and `baseline_random` move with that RNG, so tagging
`seed` as `NotApplicable` would assert "this field has no meaning for this run kind"
(`record.py:33-40`) about a field that determines the reported numbers.
**And `_decode_optional` cannot catch it.** The plan previously cited its null-rejection as
"the reason the shape fits" — but that guard catches *forgetting* (a bare `null`), not
*asserting*: a tagged sentinel carrying a false reason round-trips perfectly clean. The
distinction is the whole point of the sentinel, so the correctness of each `NotApplicable`
has to be argued per field, not inherited from the encoding. Here: `folds` genuinely has no
meaning (no split exists); `seed` genuinely does.
**Test additionally**: `record.execution.seed == RANDOM_STATE`, imported from `cluster.py`
rather than restated as a literal — a copy of `0` in the test would drift silently the moment
the constant changes.
**Consume `runs/_shared/parity.py` from Step 1.** Do not write a galactus-side serializer.
**Test**: `uv run pytest "runs/ml/customer segmentation/tests" -q`
**Done when**: segmentation persists a record whose absent fields are tagged, not null.

#### Step 6: credit — UCI sourcing
**Files**: `runs/ml/credit/src/run.py`; `runs/ml/credit/README.md`; new
`runs/ml/credit/docs/PROVENANCE.md`; `.gitignore`
**What**: Land the confirmed sourcing decision. A documented fetch of
`https://archive.ics.uci.edu/static/public/350/data.csv` (2.9 MB, CSV, **no account**) —
prefer it over the page's `.zip`, which contains an `.xls` needing `xlrd>=2.0.1`.
Record provenance: CC BY 4.0, Yeh (2009), DOI `10.24432/C55S3H`, horizon **one month**
cited **to the UCI variables table** (the prose block does not state it — cite precisely),
prevalence **22.12% (6,636/30,000), download-verified, not source-stated**.
**Handle the quirks as transform work rather than discovering them mid-run** (research F6):
`PAY_0`/X6 and PAY_2–6 hold undocumented codes **-2 (n=2,759)** and **0 (n=14,737)** —
~58% of rows; EDUCATION holds 0/5/6 (345 rows); MARRIAGE holds 0 (54 rows); the sequence is
`PAY_0, PAY_2…PAY_6` with **no `PAY_1`** (an off-by-one trap for generated column lists);
35 duplicate rows excluding `ID`; header is cryptic `ID,X1..X23,Y`.
**Author the leakage exclusion list fresh** — credit today has `ID_COLS = ["uuid"]` and
nothing else. UCI's `X*` schema shares no column names with lending, so porting would be
renaming, not reuse (research recommendation). Name the September-2005 columns
(`BILL_AMT1`/`PAY_AMT1`/`PAY_0`) explicitly as the leak candidates against an October label.
**Do not resolve gate-1a/1b** (splitter, cost ratio) — still blocked on operator input.

**Add the UCI file alongside; never overwrite the existing CSV (closes M3b).** Confirmed
with the operator 2026-08-18. `runs/ml/credit/data/credit_default.csv` (201,777 bytes,
verified present) is **untracked** — `.gitignore:50` is a bare `*.csv`, `git ls-files
runs/ml/credit` returns only README, notebooks, and `src/run.py` — so it has **no git
history at all**, and it is the 800-row lebanese-blonde sample. `git revert` would restore
the loader and not the file. The README's recovery path is a `cp` from an external checkout
this plan has never verified, so it does not count as a backup.
Therefore: land UCI under its own name (`data/uci_default_of_credit_card_clients.csv`),
leave the existing file untouched on disk, and make the **loader switch the only change** —
which is then genuinely revertible, as the Rollback section claims. Before anything else in
this step, record the outgoing file's `sha256` and row count in `docs/PROVENANCE.md` so its
identity survives even if the local copy is later lost.
**Test**: loader reads the UCI CSV; prevalence assertion == 6,636/30,000;
`data/credit_default.csv` still exists and its sha256 matches the one recorded in
`PROVENANCE.md`.
**Done when**: credit's `label horizon: UNDEFINED — blocking` line is gone, replaced by the
cited one-month horizon.

#### Step 7: docs — taxonomy and parity story
**Files**: `runs/ml/fraud/README.md`; `runs/ml/customer segmentation/README.md`;
`runs/ml/credit/README.md`
**What**: Write the abort-vs-refuse taxonomy as run-local prose in fraud's README,
cross-linking lending's `DESIGN-parity.md` Key Decision 6 (which states only the abort
half). Record segmentation's orphaned CSVs (`final_df.csv`, `group_label.csv`) as
gitignored local-only intermediates rather than deleting them.
**If and only if the frame swap is later approved**, fraud's README:1 ("a refusal, not a
metric") and `WALKTHROUGH.md:17,142` must change in the same commit as the swap — the
doc-parity failure the design names. **Not this step's job**, flagged so it is not lost.

### Test Plan

```bash
uv run pytest -q                                  # full suite, all testpaths
uv run pytest runs/_shared/tests -q               # the shared seam
uv run pytest runs/ml/fraud/tests -q              # currently 35 passed, 3 skipped
uv run pytest "runs/ml/customer segmentation/tests" -q
uv run python runs/ml/fraud/src/run.py --dry-run  # refuses, exits 0
```

**Baseline, re-measured 2026-08-18 (not inherited):**

| Command | Now | After Step 0 |
|---|---|---|
| `uv run pytest -q` | **624 passed, 14 skipped** | **638 passed, 0 skipped** |
| `ML_PACKAGE_ROOT=$PWD uv run pytest -q` | 638 passed, 0 skipped | 638 passed, 0 skipped |
| `uv run pytest runs/ml/lending/tests -q` | 25 passed, 14 skipped | 39 passed, 0 skipped |

The two rows must agree after Step 0 — that agreement *is* the step's proof, and it is why
the bare command is the one quoted in every later "Done when."

**Regression floor**: **0 skips, not "green."** The old floor read "lending is untouched and
green," which M1 falsified — lending was silent, not green. From Step 0 onward a skip in
`runs/ml/**` is a failure of this plan, not a baseline. `experiments/`'s 24 must stay green.

### Risks & Rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Fraud's frame decision lands mid-execute and contradicts Step 3 | Medium | Rework of the record's refusal field | Step 3 changes no loader path; the frame swap is a separate commit by construction. **Step 3's oracle now keys on the guard's contract, not the frame's shape (M5)**, so a swap does not silently invalidate the test |
| `runs/_shared/` becomes a dumping ground | Medium | Coupling across runs | Scope it to the two helpers plus `persist()` named in Step 1; anything run-specific stays in the run |
| Step 1's helper diverges from lending's copy | Medium | Two record shapes after all | **Still open — not closed by this pass.** Step 1 routes lending's *call site* through `persist()`, which closes the two-*write-path* hazard (M3a) but not the two-*shape* one: `_tagged` and `_toolkit_code_state` still exist in both files. What changed is that the divergence is now detectable — Step 0 makes lending's 14 record tests actually run, so a drift fails the suite instead of passing silently |
| Step 0 exposes a genuine failure in the 14 un-skipped tests | Medium | Steps 1–5 blocked until resolved | Precisely the intended outcome — better before the seam has three consumers than after. Step 0 stops and reports rather than repairing, by operator decision |
| Credit's UCI quirks surface mid-transform | Low | Silent miscoding of 58% of PAY rows | Enumerated in Step 6 from verified counts, not left to discovery |

**Rollback**: each step is a separate commit on `GAL-34-fraud-parity`.

**Corrected 2026-08-18 — "independently revertible" was false (M3), and is now true by
construction rather than by assertion:**
- **Step 6** no longer overwrites `data/credit_default.csv`; the UCI file lands beside it
  under its own name and the loader switch is the only reverted change. The outgoing file's
  sha256 is recorded in `PROVENANCE.md` before anything is written.
- **Step 1** closes the second write path into `runs/_index/` by routing lending through
  `persist()`, so for the duration of this plan exactly one enforcing chokepoint reaches the
  committed directory.
- **What remains genuinely irreversible**: any record actually published under
  `runs/_index/`. `git revert` restores the writer, never the published numbers. No step in
  this plan writes a real record — all persistence is exercised against temp targets and
  dry-runs — so the plan does not enter that state. **A step that does publish one is out of
  scope and needs its own decision.**
- **Step 0** touches only test predicates and one provenance fallback; reverting it restores
  the skips (and the blindness).

## Refinement — what is missing

Gate run 2026-08-18. Verdict **NOT-READY** (DoR checks 3 and 7 failed). Path: **Full** —
15+ files, persistent state (`runs/_index/`), and a new shared module other runs load.
`fog-advisor` dispatched (resolved exit 0); **every finding below was re-verified by the
gate against the machine**, not accepted on the advisor's word.

**M1 — 17 tests are green-by-omission across the exact seam this plan builds on.**
**BLOCKING (DoR 3 — acceptance not checkable).** Verified:
`uv run pytest runs/ml/lending/tests -q` → **25 passed, 14 skipped**; with
`ML_PACKAGE_ROOT=$PWD` → **39 passed, 0 skipped**. The 14 include every test exercising
`_tagged`, `_toolkit_code_state`, `assemble_run_record`, and the `read_record(write_record(r))`
round-trip — i.e. *all* of the precedent Step 1 lifts from. Fraud skips 3 more on the same
gate. The skip predicate keys on the **env var's presence, not importability**
(`test_dry_run.py:42-44`), so a skip renders identically to a pass under `-q`.
**This invalidates the plan's stated regression floor**, which reads "lending is untouched
and green" — lending is not green, it is silent, and the divergence risk the plan
*explicitly accepts* is therefore undetectable by the suite meant to catch it.

**M2 — the `ML_PACKAGE_ROOT` blocker was not resolved; it moved.** **BLOCKING (DoR 5).**
The plan resolves it on `experiments` evidence (`import experiments.io` works bare) and
then drops the seam. But the *runs* import `ml`, a different package: `run.py` needs
`ml.workflows.classification`. `pyproject.toml:118` does **not** put the repo root on
`pythonpath`, so both resolve only by cwd accident. Steps 3 and 5 are written assuming a
harness path that does not execute by default.
**Both skip reasons are now factually stale and must be corrected, not just bypassed:**
fraud's says "`ml/` holds only stale `__pycache__`" (false — `git ls-files ml` → 36 files,
33 `.py`), and lending's says un-skipping would run "against a tree with no `experiments/`"
(false — `experiments/` is at the root). **Verified fix:** with the repo root on
`pythonpath`, the full suite goes **624 passed/14 skipped → 638 passed/0 skipped**, no
failures. Land that first, as its own step, before anything consumes the seam.

**M3 — "independently revertible" is false for Steps 3 and 6.** **BLOCKING (DoR 7 — no
rollback).** Two irreversible effects outside git:
(a) `runs/_index/` is a *committed* directory (`README.md:7` — "Records are committed") with
**two write paths** for the duration of this plan — the new enforcing `persist()` and
lending's existing advisory `record_destination`, which Step 1 explicitly leaves untouched.
Reverting a commit does not un-publish a record's numbers.
(b) Step 6 replaces `runs/ml/credit/data/credit_default.csv` — gitignored (`*.csv`), **no
history**, and it is the 800-row lebanese-blonde sample. `git revert` restores the loader,
not the file; the README's recovery path is a `cp` from an external checkout the plan never
verifies. Fix: route lending through `persist()` in the same pass (or guard the directory,
not the call site), and hash-and-record the outgoing CSV before replacing it.

**M4 — Step 5 would write a dishonest `NotApplicable` for `seed`.** **BLOCKING (DoR 3).**
Settled by the grep the advisor named: segmentation **is seeded** —
`cluster.py:56,63,69,75` all consume `RANDOM_STATE` (KMeans `random_state`,
`np.random.default_rng`, the silhouette sample). Tagging `seed` as `NotApplicable` asserts
"this field has no meaning for this run kind" (`record.py:33-40`) about a run whose
`silhouette` and `baseline_random` move with the RNG. The plan cites `_decode_optional`'s
null-rejection as the guard that "is the reason the shape fits" — but that guard catches
*forgetting*, not *asserting*: a tagged sentinel with a false reason round-trips cleanly.
`folds=NotApplicable` remains correct; `seed` must take `RANDOM_STATE`.

**M5 — Step 3 hardcodes the refusal it is meant to test.** **Non-blocking but must be
written into the step.** The "frame-independent" argument holds for the loader and leaks at
the test oracle: Step 3 calibrates the synthetic default to 800/14 *because* that is the
current frame, then asserts refusal. If the frame swap later lands, the fixture still
refuses and the test still passes while fraud's real run no longer refuses — green, and
meaningless. Step 7 catches the doc half of this; the test half is the one that stays
silent. Fix: assert the refusal against the *guard's contract* (positives-per-fold < floor),
not against a frame shape.

**M6 (advisory, not blocking) — Step 2 proves less than it claims.** It writes to a temp dir
in `runs/_index/` *format* and asserts a filename regex; that tests the naming function, not
the real directory, and the aggregates-only constraint is asserted against a fixture the
test itself built. Fraud's own `conftest.py:31-34` records being burned by exactly this
("a fixture that agrees with the implementation cannot catch that").

**M7 (out of scope here, worth a separate item) — a false gitignore assurance.**
`.gitignore:45` ignores `runs/ml/customer segmentation/Trade Republic_Data Science
Challenge.pdf`, commented "Third-party recruiting brief — verbatim copyrighted content" —
but the file **is tracked** (`git ls-files` returns it), and gitignore does not affect
tracked files. Step 7 would write prose asserting gitignore status next to this. Fix with
`git rm --cached` (untrack, preserve locally) as its own change.

### Unverifiable at gate time

- **Step 6's UCI quirk counts** describe a file not in this checkout. They come from the
  research doc's own download and are cited there; the gate did not re-fetch.
- **Whether `runs/_index/` has ever received a real record** — it holds only `README.md`,
  and lending's record tests were skipped, so the "precedent" may be unexercised as well as
  untested.

## Re-plan — how M1–M4 are closed

Re-plan pass 2026-08-18, after the NOT-READY gate. **Every finding was re-verified against
the machine a second time before being written into a step** — the gate's own evidence was
not taken on trust, and that scepticism paid: one of the four prescribed fixes does not work.

| # | Finding | Closed by | Re-verified |
|---|---|---|---|
| M1 | 17 tests green-by-omission across the seam Step 1 lifts from | **Step 0** — importability probe replaces the env-var gate; regression floor becomes *0 skips*, not *green* | `uv run pytest runs/ml/lending/tests -q` → 25 passed, **14 skipped**; full suite 624/14 |
| M2 | The `ML_PACKAGE_ROOT` blocker moved rather than resolved | **Step 0** — predicates changed, both stale reasons corrected, `_toolkit_code_state` given an in-repo fallback | **Gate's fix falsified** — see below. `ML_PACKAGE_ROOT=$PWD` → 638/0 confirmed |
| M3 | "Independently revertible" false for Steps 3 and 6 | **Step 1** (`persist()` + lending call site) and **Step 6** (add-alongside, hash first); Rollback section rewritten | `record_destination` read at `run.py:115-122` — redirects, does not enforce. `credit_default.csv` untracked, 201,777 B, no history |
| M4 | Step 5 would tag `seed` as a dishonest `NotApplicable` | **Step 5** — `seed=RANDOM_STATE`, asserted against the imported constant; `folds` stays `NotApplicable` | `cluster.py:21` `RANDOM_STATE = 0`, consumed at `:56`, `:63`, `:69`, `:75` |
| M5 | Step 3 hardcodes the refusal it tests | **Step 3** — oracle keyed to the guard's contract, not the frame's shape | Written into the step, as the gate required |
| M6 | Step 2 proves less than it claims | **Not closed — open by decision** (OQ 7) | — |
| M7 | Tracked PDF under a gitignore rule that cannot apply | **Not closed — separate item** (OQ 6) | `git ls-files` returns `runs/ml/customer segmentation/Trade Republic_Data Science Challenge.pdf` |

### The gate's M2 fix does not work — corrected here

M2 prescribed: *"with the repo root on `pythonpath`, the full suite goes 624 passed/14
skipped → 638 passed/0 skipped, no failures. Land that first."* A step written to that
instruction would have landed a `pyproject.toml` edit, observed **no change**, and either
declared victory on a stale number or spent the session debugging the wrong layer.

Measured 2026-08-18 by patching `pythonpath = [".", "runs/ai/marketing-comms/src",
"runs/ai/marketing-comms"]` and running the bare suite: **624 passed, 14 skipped —
identical to baseline.** (Patch reverted; working tree clean.)

The cause is that the skip predicate never reaches an import when the variable is unset:

```python
root = os.environ.get("ML_PACKAGE_ROOT")
if not root:
    return False          # ← returns here; sys.path is irrelevant
```

`pythonpath` is therefore **neither necessary nor sufficient**. The 638/0 figure is real but
is produced by *setting the env var*, which is the very coupling M2 asks us to remove — so
adopting it as the fix would have preserved the problem under a new name. Step 0 changes the
predicates instead, which is the only layer that can make the bare command report 0 skips.

**This is also why Step 0 exists as a separate, blocking step rather than a bullet inside
Step 1**: the correction was only visible by running the experiment, and the same is likely
true of whatever the 14 tests have been hiding.

### Still open after this pass

- **M6** — Step 2's aggregates-only assertion still runs against a fixture the test itself
  built, which fraud's `conftest.py:31-34` records being burned by ("a fixture that agrees
  with the implementation cannot catch that"). Out of scope by decision; worth its own item.
- **M7** — the tracked PDF. Fix with `git rm --cached` as its own change. **Step 7 must not
  write prose asserting gitignore status for that file while this stands.**
- **Two record shapes** — `_tagged` / `_toolkit_code_state` still exist in both
  `runs/_shared/parity.py` and `runs/ml/lending/src/run_record.py`. Now *detectable* (Step 0
  makes lending's record tests run) but not *converged*.
- **Both entries under `### Unverifiable at gate time`** remain unverified: the UCI quirk
  counts come from the research doc's download, and whether `runs/_index/` has ever received
  a real record is still unknown — it holds only `README.md`, and lending's record tests
  were skipped, so the precedent may be unexercised as well as untested. **Step 0 settles
  the second one as a side effect** by making those tests run.

### Dependencies

- ~~**`experiments/` staged but uncommitted.**~~ **RESOLVED 2026-08-18 — it is committed.**
  `git ls-files experiments` returns all 10 files and `git status --short` is clean on
  `GAL-34-fraud-parity`. Execute may treat it as present on a fresh checkout of this branch.
- `runs/_index/README.md` — tracked; defines the grain. Do not redefine it from inside a run.
- Branch: work continues on `GAL-34-fraud-parity`, which already carries the staged
  `experiments/` tree and today's credit rename.
