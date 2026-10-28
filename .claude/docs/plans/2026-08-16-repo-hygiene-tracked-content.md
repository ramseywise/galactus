# Repo hygiene — tracked content that the repo's own rules exclude
Date: 2026-08-16
Status: PLANNED
Track: ml
Epistemic: CONFLICTED
Epistemic-by: fog-advisor
Epistemic-at: 2026-08-16
Epistemic-findings: 6

Scouts: [`../research/2026-08-15_ml-parity_segmentation.md`](../research/2026-08-15_ml-parity_segmentation.md),
[`_ltv`](../research/2026-08-15_ml-parity_ltv.md),
[`_credit`](../research/2026-08-15_ml-parity_credit.md)
Parent synthesis: [`2026-08-15-lending-parity.md`](2026-08-15-lending-parity.md) § Research addendum, X4 + recommendation 1
GitHub issue: [galactus#33](https://github.com/ramseywise/galactus/issues/33) — branch `bug/repo-hygiene-tracked-content` (bug-scale sweep, no PREFIX-NUM per the addendum).

## Research

### Summary

Three pieces of content are tracked in git that the repo's own `.gitignore` policy
excludes for every other run, plus one directory whose data is protected only by a
catch-all. All predate the lending parity work item, none are parity work, and the
addendum recommends them as a separable `bug/`-scale sweep rather than scope bolted onto
a parity plan. This item is **fully unblocked** — it depends on no upstream decision, no
serializer, and no `runs/_index/` layout.

The lending half of the sweep (stale `ml-lending/` gitignore block, `report.html`
ratification) is **already done** — it landed as Step 1 of the lending plan on 2026-08-16
and is out of scope here. Verified: `.gitignore:34-38` now names `runs/ml/lending/` paths
and carries the ratification comment.

### Scope

In: the tracked Trade Republic PDF, `runs/ml/LTV.ipynb`'s committed outputs, and
`runs/ml/credit/data/`'s missing path rule. Out: everything the parity bar covers
(dry-run, guards, records, tests), the credit reunification `git mv`, and any LTV
disposition beyond the outputs.

### Findings

**H1 — A third party's live recruiting assessment is tracked. (High)**
`runs/ml/customer segmentation/Trade Republic_Data Science Challenge.pdf` (132 KB) is
Trade Republic's verbatim recruiting take-home brief ("RECRUITING / DATA SCIENCE
CHALLENGE"; Part 1 SQL, Part 2 trading activity, Part 3 clustering — the part the run
implements; "submit your solution … via email"). Verified tracked: `git ls-files` lists
it; `git check-ignore` returns NOT IGNORED, while the sibling `csv/*.csv` hits
`.gitignore:48` and `docs/` hits `.gitignore:47`. The run's DATA HANDLING docstring
(`runs/ml/customer segmentation/src/run.py:14-18`) discusses only `csv/` and `docs/` —
the PDF is unaddressed by any rule or any prose.

This is a different class from the CSV concern: not the operator's data to publish, in a
repo whose stated purpose is external readers. The challenge framing is **already
restated** in `src/run.py:5-8`, so untracking loses nothing substantive. The run has no
README to carry a prose summary — one would need creating.

**H2 — `LTV.ipynb` ships committed outputs of exactly the class the gitignore excludes
three times over. (High)** Tracked with outputs (`git ls-files runs/ml/` →
`runs/ml/LTV.ipynb`); working tree clean, so all of it is committed content. Eleven
output-bearing cells, enumerated by the scout:

| Cell(s) | Content class |
|---|---|
| 2, 3 | pip logs — interpreter path + versions (employer-machine environment fingerprint) |
| 8, 15 | **88-column production DWH schema dump** (`user_id`, `kyc_first_completed`, `two_y_profit`, `amount_grocery_market`, …) — column names only, zero row values |
| 12 | sklearn warning implying heavy zero-mass in target distributions |
| 16 | **Aggregate model metrics over real records** — R²/MAE/MedAE/MSE; MAE ≈ 39–47 in currency units discloses real per-user 2-year profit magnitude |
| 23–26 + md 17 | **Aggregate weighted percentage errors** per validation month over cohort-summed real profit |
| 76 | traceback only (live `NameError`) |

No raw rows, no identifiers, no `head()` dumps, no plots. But the gitignore asserts three
separate times that "aggregates derived from real records are still real records" and
ignores exactly this content class for lending, fraud, and segmentation. Two additional
disclosure classes the sibling runs do not have: the production DWH schema, and — in
markdown cell 0 — a **live external Google Sheets URL** for cohort definitions. Cells
79–81 additionally name another organization's infrastructure (an S3 bucket, a Redshift
IAM ARN, `/app/utils/CONFIG.ini`).

No nbstripout, no `.gitattributes` filter, no `.gitignore` mention — nothing exists that
would have caught this or will catch the next notebook.

**H3 — Credit's data is protected only by the `*.csv` catch-all. (Medium)**
`runs/ml/credit/data/credit_default.csv` (200K, 800 rows + header, semicolon-delimited,
43 columns) is ignored — but only incidentally, via `.gitignore:48` (`*.csv`). No path
rule, no `.gitkeep` (lending has one), so the directory vanishes on a fresh clone and any
non-CSV artifact dropped there would be tracked by default.

PII class is real and already flagged in-repo: `.gitignore:32` labels this class "personal
financial information about identifiable people"; the first column is `uuid`, `age` is
present (a protected characteristic per
`2026-08-11-gal-4-phase2-ml-fraud-poc.md:187`), and the remaining columns are behavioural
financial aggregates keyed to a per-person identifier.

Provenance is an uncontrolled local path: `pocs/ml/credit/README.md:13-16` and
`pocs/ml/credit/src/run.py:102-103` restore the file by copying from
`~/workspace/lebanese-blonde/src/data/dataset.csv` — operator-private, no hash, no
version pin.

**H4 — Each item is an operator call, not a mechanical fix. (High)** Untrack vs ratify is
a judgment the plan cannot make: lending's `report.html` was *ratified* (kept tracked,
docs corrected) rather than untracked, on the grounds that it is load-bearing as fraud's
test fixture and the repo is private. The same two options exist for each item here, and
the answers plausibly differ per item. `/proto-plan`'s goal elicitation is the right place
to settle them.

**H5 — `git rm --cached`, never `rm`. (Medium)** Per the operator's shell rules: untracking
preserves the file locally and in reflog. History exposure is not resolved by untracking —
only by a rewrite, which lending explicitly declined for `report.html` on the private-repo
grounds. Whether that precedent extends to a third party's document is an open question
for the plan, not a settled one.

### Open questions for `/proto-plan`

1. **PDF**: untrack + write a run README with a 3–5-line prose summary, or ratify like
   `report.html`? (Scout verdict: SKIP/untrack — it contributes nothing to the bar and the
   framing is already in `run.py:5-8`.)
2. **LTV outputs**: strip in place (nbstripout + `.gitattributes` filter, keeping the
   notebook as a documented historical exhibit), or is the notebook's whole disposition a
   separate decision that this sweep should not pre-empt? The scout's recommended
   disposition is (a) strip-and-keep or (b) mine-and-drop — but notes the outputs problem
   is *independent of* and more urgent than the disposition choice.
3. **Does the sweep install a mechanism or only fix instances?** An nbstripout filter or a
   notebook-output check would prevent recurrence; without one the next committed notebook
   repeats H2. Scout evidence: nothing currently exists at any layer.
4. **History**: accept exposure (lending's precedent, private repo) or rewrite? A third
   party's document may warrant a different answer than the operator's own aggregates.

### Risks

- **`git rm --cached` on a path with a live consumer.** Verified none of these three has
  one: the PDF is read by no module (`run.py:5-8` restates it in prose), LTV.ipynb is
  referenced by no `pyproject.toml`/`.gitignore`/`.gitattributes` entry and has no tests,
  and credit's CSV is read only by `pocs/ml/credit/src/run.py` which is unaffected by an
  ignore rule. This is the trap X1 sprang on lending's `report.html`; it does not recur
  here.
- Stripping notebook outputs is a whole-file rewrite in git terms — the diff will be large
  and unreviewable line-by-line. The check is the rendered notebook, not the diff.
## Plan
Date: 2026-08-16
Based on: `## Research` above, re-verified against the working tree on 2026-08-16.

### Goal

Install the mechanism that stops output-bearing notebooks and stray run artifacts from
being committed again, and clear the three existing instances as its first application.

### Open Questions

All four research questions were settled in goal elicitation on 2026-08-16. Recorded here
with their answers so execute inherits decisions, not deliberation.

1. **PDF — untrack or ratify?** RESOLVED 2026-08-16: **untrack + write a run README.**
   It is a third party's document, not the operator's to publish; the challenge framing is
   already restated in `src/run.py:5-8`, and the run currently has no README to carry a
   prose summary.
2. **LTV outputs — strip, or defer to a disposition decision?** RESOLVED 2026-08-16:
   **strip outputs AND scrub the source references.** The notebook stays as a historical
   exhibit.
3. **Mechanism or instances only?** RESOLVED 2026-08-16: **mechanism** — nbstripout in the
   existing `.pre-commit-config.yaml`, plus `pre-commit install` and a demonstrated strip.
   This is the goal, not a side quest.
4. **History — accept exposure or rewrite?** RESOLVED 2026-08-16: **accept**, following the
   `report.html` precedent (private repo). Untracking stops future distribution; it does not
   erase history, and this plan does not rewrite it. Flagged in Risks.
5. **NEW — `runs/ml/credit/` is entirely untracked.** Research described only a missing
   `data/` path rule; verification found the whole run dir (src, README, data) has zero
   tracked files. RESOLVED 2026-08-16: **path rule + `.gitkeep` only.** Why the rest of the
   dir is untracked belongs to `2026-08-16-credit-reunification.md`, not this sweep.
   Re-confirmed 2026-08-16: `git ls-files runs/ml/credit/` → 0 files; on disk the dir holds
   `data/credit_default.csv`, an empty `notebooks/`, and an empty `src/`. Note the README
   the Step-4 comment cites (`runs/ml/credit/README.md`) **does not exist** — the provenance
   note lives at `pocs/ml/credit/README.md:13-16`. Point the comment there.

### Re-verification (2026-08-16)

The plan was re-verified line-by-line against the working tree and against `origin/main`
before refine. Findings that changed the plan:

| # | Finding | Where fixed |
|---|---|---|
| V1 | **Baseline was wrong in every part** — recorded 6 failed/593 passed; actual is 8 failed/565 passed/1 skipped at `origin/main`, and 0 failed on the current dirty checkout. Two causes, neither the one recorded. | Preconditions |
| V2 | **`uv sync --group ml` is mandatory** in a fresh worktree; without it, collection aborts on missing `sklearn`. `--all-extras` does **not** work — `ml` is a dependency group. | Preconditions |
| V3 | **This plan doc is gitignored** (`~/.gitignore_global`), so it will not exist in the worktree. Execute must read it from the main checkout. | Preconditions (BLOCKER) |
| V4 | **Step 4's `data/` rule made its `!` negation inert** — git does not descend into an excluded directory. Corrected to `data/*`. Empirically verified both forms. | Step 4 |
| V5 | **Step 4's `git add -f` would have masked V4**, force-adding past a broken rule and greening a test over a non-working rule. | Step 4 |
| V6 | **`git check-ignore` is silent on tracked paths** — Step 2's untrack-then-check order is load-bearing, not incidental. Documented so it is not "tidied" into the wrong order. | Step 2 |
| V7 | Gitleaks block is **not** last in `.pre-commit-config.yaml`; a `local` block follows at lines 33-39. | Step 1 |
| V8 | Working-tree count stale (4 modified, not 6 modified + 7 untracked). | Preconditions |

Confirmed unchanged: 11 output cells in `LTV.ipynb`; all three Step-3 scrub greps return 1;
`01-eda.ipynb` has zero outputs (hook is a no-op there); `nbstripout` 0.9.1 is current;
`.git/hooks/pre-commit` absent; PDF tracked and unignored; credit CSV caught only by
`*.csv:48`; no `.gitattributes` exists.

### Failure pass — fog-advisor, 2026-08-16 (6 findings, UNRESOLVED)

Dispatched at refine. Six findings; four rated `certain`. Three independently re-verified
by the gate. **These must be closed in `/proto-plan` before this doc can reach `READY`.**

| # | Finding | Sev | Verified by gate |
|---|---|---|---|
| FA-001 | **Step 4 operates on a directory absent from `origin/main`.** `git ls-tree -r origin/main \| grep '^runs/ml/credit'` → 0 matches; the CSV exists only in the main checkout's working tree. In the mandated worktree, `touch runs/ml/credit/data/.gitkeep` hits a missing dir. Because `check-ignore` is a pure path-pattern query, Step 4's assertions **pass green over a path with no file behind it** — shipping a PII-warning comment for content the branch has never held. | certain / costly | ✅ confirmed |
| FA-002 | **Step 4's negation assertion has the exit code inverted.** `git check-ignore -v` returns rc=**0** on a negation match; only bare `check-ignore` returns rc=1. `:456-457`'s `test $? -eq 1` therefore prints nothing exactly when the rule is *correct* — driving execute toward the `git add -f` that V5 forbids. V4's fix breaks V5's test. | certain / costly | ✅ confirmed in scratch repo |
| FA-003 | **"nbstripout is a no-op on `01-eda.ipynb`" is false.** Zero output cells is true; no-op is not. The hook rewrites **303 lines** of that 570-line file via `execution` metadata + cell-id renumbering (`c2145418` → `0`). Renumbering is positional, so one inserted cell shifts every later id — every notebook diff becomes whole-file, permanently. `--keep-id` reduces it to 209, not 0. Also invalidates `:413-414`'s "diff is smaller than H2 implies". | certain / costly | ✅ confirmed by running 0.9.1 |
| FA-004 | **The 8-failed baseline is a property of a moving ref**, and `:269`'s re-measure instruction makes the success condition tautological. `origin/main` is already 3 commits behind HEAD, and `b744b46` has already repointed the `quoted_span` fixtures — 6 of the 8 recorded failures are already fixed on this branch. A scalar count cannot distinguish "6 fixed" from "6 no longer collected". | likely / recoverable | ✅ fixture drift confirmed (111→125) |
| FA-005 | **`pre-commit install` has no rollback entry.** `:516-519` enumerates four change categories and claims they "restore the prior state completely"; `.git/hooks/pre-commit` is none of them, and no `pre-commit uninstall` appears anywhere. A mid-flight abort leaves an active hook set installed from a config just reverted. | certain / recoverable | ✅ `.git/hooks/pre-commit` absent today |
| FA-006 | **History-exposure "accept" defers to a condition nobody watches.** `:505-507` says record a blocker "on any open-sourcing item"; no such item exists, and the only record is *this doc*, which `~/.gitignore_global:1` excludes from git. Research H5 flagged the third-party-document distinction as open; the Plan resolved it by citing the `report.html` precedent without engaging it. | likely / costly | ✅ 0 tracked files under `.claude/docs/` |

**Advisor's could-not-evaluate list** (carry into plan, do not treat as clear):
gitleaks was never run and LTV.ipynb is its target class (config paths, username, Sheets
URL) — Step 1's `--no-verify` escape may be needed for the notebook the sweep is editing;
Step 3's scrub completeness at cell depth (the 88-column DWH schema may survive in *source*
cells even after outputs strip); and `pocs/ml/credit/src/run.py:63` reads
`pocs/ml/credit/data/credit_default.csv`, a path that **does not exist on disk** — so
`:502`'s "credit's CSV is read only by `pocs/.../run.py`" describes a consumer pointed at a
different, empty path.

### Approach

Mechanism first, then instances — so the instance fixes are the mechanism's first proof
rather than a manual pass that happens to coincide with it. Step 1 installs nbstripout
(with `--keep-id`) and demonstrates it stripping a real notebook; Steps 2–3 clear the PDF
and the LTV notebook. **Three steps, not four** — Step 4 was descoped to the credit
reunification item after verification found its target directory absent from `origin/main`.
The tradeoff: `pre-commit install` writes to `.git/hooks/`, which is
machine-local and invisible to CI and to a fresh clone, so the hook is a guard for this
working copy and a documented setup step for anyone else. A CI-side check would close that
gap and is deliberately out of scope for a `bug/`-scale sweep.

### Out of Scope

- Rewriting git history for any of the three items (question 4, resolved: accept).
- `LTV.ipynb`'s ultimate disposition — strip-and-keep vs mine-and-drop. This plan strips;
  whether the notebook stays long-term is a separate call.
- Why `runs/ml/credit/` is wholly untracked, and the credit `git mv` — both belong to
  `2026-08-16-credit-reunification.md`. **As of 2026-08-16 this also includes the `data/`
  path rule and `.gitkeep`** (the former Step 4), descoped because the directory does not
  exist on `origin/main`. See the Step 4 section for the handoff facts.
- Fixing lending's latent `data/` negation form at `.gitignore:34-35` — not load-bearing
  today (its `.gitkeep` is tracked). Recorded in Open Issues.
- `LTV.ipynb`'s executability. It was never executable without warehouse credentials it
  does not carry; the schema redaction does not change that.
- Everything the ML parity bar covers: dry-run, guards, run records, tests.
- The lending half of the sweep (stale `ml-lending/` block, `report.html` ratification) —
  landed 2026-08-16 as Step 1 of the lending plan. Verified present at `.gitignore:34-38`.
- A CI job enforcing notebook-output cleanliness (see Approach tradeoff).

### Preconditions

**The working tree is not clean.** Branch `GAL-32-lending-parity` carries uncommitted
lending-parity work (4 modified files under `runs/ml/lending/`; re-verified 2026-08-16 —
the earlier "6 modified, 7 untracked" count is stale, the untracked paths have since been
absorbed).

Execute must therefore either (a) land the lending work first, or (b) create
`bug/repo-hygiene-tracked-content` from `origin/main` in a separate worktree. **Option (b)
is confirmed** (operator, 2026-08-16). Do not mix this sweep's commits into the lending
branch — issue galactus#33 is a separate item.

**BLOCKER — this plan doc will not exist in the worktree.** `.claude/docs/plans/` is
gitignored via the operator's *global* ignore file (`~/.gitignore_global:1: .claude/docs/*`),
so no plan doc is tracked in galactus and a fresh worktree from `origin/main` contains none
of them. Execute cannot `Read` its own plan from inside the worktree. Two consequences:

- **Execute must read the plan from the main checkout** —
  `~/workspace/galactus/.claude/docs/plans/2026-08-16-repo-hygiene-tracked-content.md` —
  while running its commands against the worktree. The spawn prompt must carry the absolute
  main-checkout path, not a worktree-relative one.
- **`Status:` updates land on the main-checkout copy**, which is the only copy. This is
  consistent with the state machine — the hook guards the file, not the branch.

**Create the worktree in galactus itself**, per the operator's cross-repo dispatch rule:

```bash
git -C ~/workspace/galactus worktree add \
  ~/workspace/galactus/worktrees/repo-hygiene \
  -b bug/repo-hygiene-tracked-content origin/main --no-track
```

`--no-track` is mandatory — branching from `origin/main` without it silently sets upstream
tracking to main and breaks the push flow.

**`uv sync --group ml` is required in the fresh worktree, before the baseline run.**
Re-verified 2026-08-16: a fresh worktree without it aborts collection with
`ModuleNotFoundError: No module named 'sklearn'` on the two `runs/ml/customer segmentation/`
test modules — 2 collection errors, zero tests run. `ml` is a **dependency group**, not an
extra, so `uv sync --all-extras` does **not** pull it; only `--group ml` does. Getting this
wrong makes the baseline unreadable and would be misread as this sweep's damage.

**Baseline test state — corrected 2026-08-16.** The prior figure (6 failed / 593 passed /
10 skipped, attributed to a drifted `quoted_span`) was measured on neither relevant ref and
is wrong in every part. Measured directly:

| Ref | Result |
|---|---|
| `origin/main` @ `db3b6a5` (the option-(b) branch point) + `uv sync --group ml` | **8 failed, 565 passed, 1 skipped** |
| current dirty `GAL-32-lending-parity` checkout @ `b744b46` | 600 passed, 14 skipped |

**Record the baseline as a tuple, not a triple (FA-004).** A bare pass/fail count is a
property of a moving ref, and `origin/main` is *already* 3 commits behind this branch. Two
of those commits (`6e617e2`, `b744b46`) have **already repointed the `quoted_span` fixtures
111 → 125** — that is cause 1 below, meaning 6 of the 8 recorded failures are fixed the
moment lending merges. Execute must therefore record:

```
{origin/main sha, failed, passed, skipped, collected}
```

The **sha** is what makes it a baseline rather than a number: it tells execute whether the
recorded causes still apply. The **collected count** (`uv run pytest --collect-only -q | tail -1`)
is what distinguishes "6 tests fixed" from "6 tests no longer collected" — a pass/fail
scalar cannot see the difference, and this repo's own CLAUDE.md warns that a missing
`testpaths` entry "collects zero tests, which reads exactly like passing."

**Execute's success condition**: the tuple measured *after* the sweep equals the tuple
measured *before* it, both in the same worktree, with the sha and collected-count identical.
If `origin/main` has moved, re-measure and expect **2 failed**, not 8 — cause 1 will be gone.

The 8 pre-existing failures have **two** distinct causes, neither the one previously
recorded, and **execute must fix neither and read neither as damage**:

1. **6 in `review/tests/test_validate.py`** — fixtures pin `quoted_span` to
   `runs/ai/marketing-comms/src/model/gateway.py:111-111 (±1 line)`, but line 111 is a
   docstring line; the fixtures' `ANCHOR_TEXT` (`import anthropic`) actually sits at
   **gateway.py:125**. The test's own failure message says to repoint the fixtures and
   never to weaken the check. Out of scope here.
2. **2 in `review/tests/test_signals.py`** — the hand-labelled corpus asserts 12 named docs
   exist in `.claude/docs/plans/`, which is **gitignored**, so a fresh worktree from
   `origin/main` contains none of them. This failure is *structural to option (b)* and will
   appear the moment the worktree is created. It is not caused by anything this sweep does.

Cause 2 has a consequence for Step 1's `pre-commit install`: see Step 1's note.

### Steps

#### Step 1: Install nbstripout as a real, demonstrated pre-commit hook

**Files**: `.pre-commit-config.yaml` — insert a repo block **between the gitleaks block
(lines 27-31) and the `- repo: local` block (lines 33-39)**, i.e. at line 32.

Corrected 2026-08-16: the prior "append after the gitleaks block, lines 27-31" reads as
appending at end-of-file, but gitleaks is **not** the last block — a `local` repo block
carrying the `no-dotenv-staged` hook follows it. Append-at-EOF still parses, but insert at
line 32 to keep third-party repos grouped above the local block.

**What**: Add nbstripout so notebook outputs are stripped on commit repo-wide, then
actually install pre-commit into `.git/hooks/` — it is configured but **not installed**
(re-verified 2026-08-16: `.git/hooks/pre-commit` does not exist), so every hook in this file
currently runs nowhere. Installing is the step's substance; the config line alone would be a
declared mechanism, not a working one.

**Note — `pre-commit install` in the worktree.** `pre-commit` is on PATH
(`/opt/homebrew/bin/pre-commit`, 4.5.1), so no install of the tool itself is needed. But
once the hook is active, **every commit in this sweep runs the full hook set**, and the
worktree is a fresh clone-equivalent: hooks that were never exercised here may fire on
files this sweep does not touch. If a hook unrelated to notebooks blocks a commit, that is
the mechanism working on pre-existing state — record it and use `git commit --no-verify`
for that commit rather than fixing unrelated files inside a `bug/`-scale sweep.

**Expect gitleaks to fire on `LTV.ipynb` specifically.** It has never scanned this repo, and
the notebook is its exact target class: an employer username, an internal config path
(`/app/utils/CONFIG.ini`), and a live Google Sheets URL. Step 3 removes all three — so
**sequence Step 3 before the first commit that stages the notebook**, and gitleaks should
pass on its own. If it still fires, read what it flags before reaching for `--no-verify`:
using `--no-verify` on the notebook commit would skip the very mechanism this step installs,
which is the one case where the escape hatch above does not apply. Verified clean already:
ruff, ruff-format, trailing-whitespace, end-of-file-fixer, and `check-added-large-files`.

**`--keep-id` is mandatory, not optional (FA-003).** The default configuration does more
than strip outputs, and the earlier claim that the hook is "a no-op" on
`pocs/ml/credit/notebooks/01-eda.ipynb` was **false** — corrected 2026-08-16 by running
0.9.1 against a copy:

| Config | Diff on `01-eda.ipynb` (570 lines, 0 output cells) |
|---|---|
| defaults | **303 lines changed** |
| `--keep-id` | 209 lines changed |

Zero output cells was true; *no-op* was an inference from it, and wrong. Two behaviours the
plan did not account for: nbstripout strips per-cell `execution` metadata (iopub timestamps,
on 19 of 33 cells), and it **renumbers every cell `id` to a sequential integer**
(`c2145418` → `0`, `11c18918` → `1`, …). The renumbering is *positional*, so inserting one
cell at the top of any notebook shifts every subsequent id and produces a whole-file diff —
**permanently**. A mechanism installed to make notebooks reviewable would have made every
notebook diff unreviewable. `--keep-id` closes that.

The residual 209 lines is `execution` timestamp metadata. Note `--keep-metadata-keys=execution`
does **not** retain it (verified — that flag governs notebook-level, not cell-level, keys).
This residue is accepted: execution timestamps fingerprint when the work ran, so stripping
them is desirable, and it is a **one-time** rewrite rather than recurring churn. Expect
`01-eda.ipynb` to change by ~209 lines on its first commit; that is the mechanism working,
not damage.

**Snippet** — insert at line 32, between the gitleaks and `local` blocks:
```yaml
  - repo: https://github.com/kynan/nbstripout
    rev: 0.9.1   # latest as of 2026-08-16, verified against the GitHub releases API
    hooks:
      - id: nbstripout
        name: strip notebook outputs
        # --keep-id is load-bearing: without it nbstripout renumbers cell ids
        # positionally, so a one-cell insert rewrites the whole file forever.
        args: ["--keep-id"]
```

**Test**:
```bash
pre-commit install
# prove it works on a real notebook rather than trusting the config:
python3 -c "import json;nb=json.load(open('runs/ml/LTV.ipynb'));print(sum(1 for c in nb['cells'] if c.get('outputs')))"  # 11
git add runs/ml/LTV.ipynb && pre-commit run nbstripout --files runs/ml/LTV.ipynb
python3 -c "import json;nb=json.load(open('runs/ml/LTV.ipynb'));print(sum(1 for c in nb['cells'] if c.get('outputs')))"  # 0
# prove --keep-id took effect — ids must NOT be sequential integers:
python3 -c "import json;nb=json.load(open('runs/ml/LTV.ipynb'));ids=[c.get('id') for c in nb['cells'][:5]];print(ids);assert ids!=['0','1','2','3','4'],'--keep-id not applied'"
```

**Done when**: `.git/hooks/pre-commit` exists, and the commands above print `11` then `0` —
a demonstrated strip, not a config entry. This step also performs Step 3's output-stripping
as its proof; Step 3 covers only the source scrub.

#### Step 2: Untrack the Trade Republic PDF and give the run a README

**Files**: `runs/ml/customer segmentation/Trade Republic_Data Science Challenge.pdf` (untrack),
`.gitignore` (add rule near the segmentation block at line 46), new
`runs/ml/customer segmentation/README.md`

**What**: `git rm --cached` the PDF — never `rm`; untracking preserves the file locally and
in reflog. Add a path rule so it cannot be re-added, and write the run's first README
carrying a 3–5 line prose summary of the challenge so untracking loses nothing readable.
Verified no live consumer: no module reads the PDF, and `src/run.py:5-8` already restates
the framing.

**Snippet**:
```gitignore
# A third party's recruiting brief — Trade Republic's document, not ours to publish.
# Untracked 2026-08-16 (galactus#33). The challenge framing it carries is restated in
# `src/run.py:5-8` and README.md; nothing in the run reads the file.
# NOTE: untracking does not erase history — the file remains reachable in this repo's
# git history. Rewrite (git filter-repo) BEFORE any public publication or external
# clone-access grant. This note is the carrier for that blocker; do not delete it.
runs/ml/customer segmentation/*.pdf
```

**The history note is load-bearing (FA-006).** Question 4 accepts history exposure on the
`report.html` precedent, and `Risks` says to "record it as a blocker on any open-sourcing
item" — but no such item exists, and the only other record is *this plan doc*, which
`~/.gitignore_global:1` excludes from git (verified: 0 tracked files under `.claude/docs/`).
A mitigation that lives only in a gitignored file on one machine has no carrier. The
`.gitignore` comment is tracked, ships with the repo, and sits at the exact path a future
reader would check — so the blocker travels with the artifact rather than with the plan.
Note the asymmetry research H5 drew and question 4 did not engage: `report.html` is the
operator's own derived aggregate; this is a third party's verbatim document.

**Test**:
```bash
git rm --cached "runs/ml/customer segmentation/Trade Republic_Data Science Challenge.pdf"
git check-ignore -v "runs/ml/customer segmentation/Trade Republic_Data Science Challenge.pdf"  # must MATCH
test -f "runs/ml/customer segmentation/Trade Republic_Data Science Challenge.pdf" && echo "local copy intact"
test -f "runs/ml/customer segmentation/README.md" && echo "README written"
```

**Order matters — verified 2026-08-16.** `git check-ignore` reports *nothing* (rc=1) for a
**tracked** path, regardless of how well a rule matches: tracked files bypass ignore rules
entirely. So the `git rm --cached` must come first, exactly as written above. Running the
check before untracking yields rc=1 and reads as "my rule is broken" when the rule is fine.
Empirically confirmed in a scratch worktree: same rule, rc=1 while tracked → rc=0 after
`git rm --cached`.

The unescaped space in `runs/ml/customer segmentation/*.pdf` is **correct** — gitignore only
requires escaping for *trailing* spaces. Verified matching in the scratch worktree.

**Done when**: `git ls-files` no longer lists the PDF, `git check-ignore` matches the new
rule, the file still exists on disk, and `README.md` explains what the run does and what
challenge it answers without reproducing the brief.

#### Step 3: Scrub LTV.ipynb's source references

**Files**: `runs/ml/LTV.ipynb` — markdown cell 0, **code cell 4**, code cell 79

**What**: Outputs are already gone (Step 1's proof stripped all 11 cells). This step removes
what stripping cannot reach, because it lives in *source*: the production DWH schema in
cell 4, a live external Google Sheets URL in cell 0, and an employer username plus internal
config path in cell 79.

**Correction to research H2**: the S3 bucket and Redshift IAM ARN are **not** disclosed.
`s3_bucket` and `redshift_iam_arn` appear in cells 80–81 only as unbound variable
references — verified never assigned a literal anywhere in the notebook. Cells 80–81 need
no change.

**NEW 2026-08-16 — the 88-column DWH schema is in SOURCE, not outputs.** Research H2 placed
it in output cells 8/15 and inferred that stripping removes it. Verified false: cell 4
carries it as a literal `DWH_COLUMNS = {...}` set (5,617 chars — `user_id`,
`kyc_first_completed`, `two_y_profit`, `amount_grocery_market`, `is_expat`, `gender`, …),
plus a second `DWH_COLUMNS_COHORTS`. **Output-stripping does not touch it.** This is the
largest single disclosure in the notebook and the original Step 3 did not mention it.

It is **load-bearing** — cell 81 consumes it
(`set(list(DWH_COLUMNS) + ["two_y_cost", "two_y_revenue", "two_y_profit"])`), so it cannot
simply be deleted. RESOLVED 2026-08-16 (operator): **redact to an illustrative subset**,
keeping the notebook structurally readable as a historical exhibit.

So the real scrub surface is **three items, not two and not five**.

**Snippet**:
```python
# cell 0 (markdown) — replace the bare URL
- ...follow the marketing hierarchy framework (https://docs.google.com/spreadsheets/d/1js2.../edit#gid=...)
+ ...follow the marketing hierarchy framework (internal cohort-definition sheet; link removed)

# cell 4 (code) — redact the production schema, keep the shape
- DWH_COLUMNS = {
-     "user_created", "user_id", "country_tnc_legal", "age_group", "age", "is_expat",
-     "gender", "newsletter_opt_in", ... 88 columns total ...
- }
+ # Production DWH schema redacted 2026-08-16 (galactus#33) — a former employer's
+ # warehouse column list is not ours to publish. An illustrative subset is retained
+ # so the cohort-validation call in cell 81 still reads structurally.
+ DWH_COLUMNS = {
+     "user_id",
+     "age_group",
+     "amount_act_total",
+     "n_act_total",
+     "two_y_profit",
+ }
# DWH_COLUMNS_COHORTS: redact the same way, same comment.

# cell 79 (code)
- os.environ['LOCAL_USER'] = "ramsey.wise"
- config_file = "/app/utils/CONFIG.ini"
+ os.environ['LOCAL_USER'] = os.environ.get("LOCAL_USER", "<user>")
+ config_file = os.environ.get("DWH_CONFIG", "<path-to-config>.ini")
```

Keep `two_y_profit` in the retained subset — cell 81 references it explicitly, so dropping
it breaks the cell's readability. The notebook is not executable post-redaction (it was not
executable before either: it needs warehouse credentials it never carried), so "still runs"
is not the bar. **Structural readability is the bar.**

**Test**:
```bash
grep -c "docs.google.com/spreadsheets" runs/ml/LTV.ipynb   # 0
grep -c "ramsey.wise" runs/ml/LTV.ipynb                    # 0
grep -c "/app/utils/CONFIG.ini" runs/ml/LTV.ipynb          # 0
# schema redaction — a few sentinel columns that must be gone:
grep -c "kyc_first_completed" runs/ml/LTV.ipynb            # 0
grep -c "amount_grocery_market" runs/ml/LTV.ipynb          # 0
grep -c "max_diff_between_logins" runs/ml/LTV.ipynb        # 0
# and the retained set must still be a set of reasonable size, not empty:
python3 -c "import json;nb=json.load(open('runs/ml/LTV.ipynb'));s=''.join(nb['cells'][4]['source']);assert 'DWH_COLUMNS' in s and s.count(chr(34))<40,'cell 4 not redacted';print('cell 4 redacted')"
python3 -c "import json;json.load(open('runs/ml/LTV.ipynb'));print('valid json')"
```

**Done when**: all six greps return `0`, the cell-4 assertion passes, the notebook is still
valid JSON, and it opens and renders. **Check the rendered notebook, not the diff.** Correcting
`:413-414`'s reassurance: the diff is **not** small — measured at **413 changed lines** of
`LTV.ipynb` from stripping alone, before this step's source edits, because cell-id and
metadata churn dominate the ~3.9 KB output payload. With `--keep-id` (Step 1) that number
drops, but the diff is still not line-by-line reviewable. The rendered notebook is the check.

#### Step 4: REMOVED — descoped to the credit reunification item

**RESOLVED 2026-08-16 (operator): Step 4 is not part of this sweep.** The sweep is three
steps.

The step assumed `runs/ml/credit/data/credit_default.csv` exists on the branch. It does
not. Verified: `git ls-tree -r origin/main --name-only | grep '^runs/ml/credit'` returns
**zero matches** — the directory and its CSV are artifacts of the *main checkout's working
tree only*, and `worktrees/` is excluded via `.git/info/exclude:1`, which is machine-local
and never cloned.

Preconditions mandate option (b): a fresh worktree from `origin/main`. In that worktree
`runs/ml/credit/` does not exist at all, so the step's first command
(`touch runs/ml/credit/data/.gitkeep`) fails on a missing directory. The dangerous part is
what comes next: **`git check-ignore` is a pure path-pattern query and answers identically
on a nonexistent path.** So after an `mkdir -p` to make the `touch` work, all of the step's
assertions go green — over a directory containing nothing — and the sweep would commit a
`.gitignore` block warning about "800 rows of per-person financial behaviour keyed to a
uuid" for a file that has never existed on that branch. Every other finding in the failure
pass announces itself; this one produced a clean, wrong result.

The plan already drew this boundary and then stepped over it: Out of Scope says the
reunification doc owns "why `runs/ml/credit/` is wholly untracked."

**Handoff to `2026-08-16-credit-reunification.md`** — carry these verified facts:

- `git ls-files runs/ml/credit/` → 0 files; `origin/main` → 0 matching paths.
- On disk in the main checkout: `data/credit_default.csv` (200K, 800 rows, 43 cols,
  semicolon-delimited), an empty `notebooks/`, an empty `src/`.
- The CSV is ignored **only** incidentally by the `*.csv` catch-all at `.gitignore:48`
  (verified: `check-ignore -v` names that line). It is PII-class — first column `uuid`,
  `age` present.
- **A live bug for that item to resolve**: `pocs/ml/credit/src/run.py:63` computes
  `DATA = Path(__file__).resolve().parents[1] / "data" / "credit_default.csv"` →
  `pocs/ml/credit/data/credit_default.csv`, and **that directory does not exist** (verified).
  The CSV lives only under `runs/ml/credit/data/`. So the earlier claim that "credit's CSV is
  read only by `pocs/ml/credit/src/run.py`" describes a consumer pointed at an empty path.
- When that item does add the rule, use **`data/*` + `!...gitkeep`**, never the `data/`
  directory form: git does not descend into an excluded directory, so the negation goes
  inert. Empirically verified both forms.
- And assert the negation with **bare `git check-ignore`, not `-v`** — see the note below.

**Two corrections preserved here so they are not re-derived** (both were Step 4's, both
still apply wherever that rule eventually lands):

1. **`git check-ignore -v` returns rc=0 on a negation match**, not rc=1. The `-v` flag
   reports "a pattern matched," including `!` patterns; bare `check-ignore` reports "the path
   is ignored." Verified in a scratch repo with the exact `data/*` + `!` form:
   `check-ignore -v .gitkeep` → prints `.gitignore:2:!b/data/.gitkeep`, **rc=0**;
   bare `check-ignore .gitkeep` → prints nothing, **rc=1**. The old assertion
   (`check-ignore -v ...; test $? -eq 1`) therefore printed nothing exactly when the rule was
   **correct** — and the natural repair is the `git add -f` that the plan elsewhere forbids.
   Use `-v` for diagnostics, bare for the rc assertion. One command, two exit contracts.
2. **Lending's block at `.gitignore:34-35` has the same latent `data/` bug.** Its `.gitkeep`
   is already tracked, and tracked files bypass ignore rules, so nothing is broken today
   (verified: `check-ignore -v` on it → rc=1). Left as-is; recorded in Open Issues.

### Test Plan

- **Per step**: the commands above. Each is a state assertion (tracked/ignored/present),
  not a unit test — this sweep changes no importable code, so no new pytest cases are added.
- **Whole sweep — record the tuple, before and after**, both in the worktree after
  `uv sync --group ml`:
  ```bash
  git rev-parse origin/main                          # the sha that makes it a baseline
  uv run pytest --tb=no -q | tail -1                 # failed / passed / skipped
  uv run pytest --collect-only -q | tail -1          # collected — catches silent un-collection
  ```
  The after-tuple must equal the before-tuple in **every field**. Expect
  `8 failed / 565 passed / 1 skipped` at `db3b6a5`, but **do not trust that number** — if
  `origin/main` has advanced past the lending merge, expect **2 failed**, because
  `6e617e2`/`b744b46` already fixed cause 1. Re-measure; the freshly measured tuple governs.
  A moved `collected` count invalidates the pass/fail comparison entirely rather than
  merely changing it.
- **Regression the mechanism claims to prevent**: create a throwaway notebook with one
  output cell, `git add` it, run `pre-commit run nbstripout --files <path>`, confirm the
  output is gone **and that its cell ids are not sequential integers** (proving `--keep-id`),
  then delete it. This is the only test that proves the goal was met rather than the
  instances cleared.
- **Clone check** (proves Step 2's rule from the outside — the only test that sees what a
  fresh reader gets). Clone the **branch**, into *this session's* scratchpad:
  ```bash
  DEST="${CLAUDE_SCRATCHPAD:-/tmp}/gal-hygiene-check"   # do NOT hardcode a session UUID
  rm -rf "$DEST"
  git clone --branch bug/repo-hygiene-tracked-content . "$DEST"
  ls "$DEST/runs/ml/customer segmentation/"          # no .pdf
  test -f "$DEST/runs/ml/LTV.ipynb" && python3 -c "import json;nb=json.load(open('$DEST/runs/ml/LTV.ipynb'));print('output cells:',sum(1 for c in nb['cells'] if c.get('outputs')))"  # 0
  grep -rc "kyc_first_completed" "$DEST/runs/ml/LTV.ipynb"   # 0
  ```
  The previous version hardcoded a **stale session scratchpad UUID** that will not exist in
  execute's session — resolve the path at runtime. The credit assertions are gone with
  Step 4. A clone only carries **committed** state, so run this *after* the sweep's commits,
  not against the working tree. Delete `$DEST` when done.

### Risks & Rollback

- **`git rm --cached` on a path with a live consumer.** Verified neither of the two has one:
  the PDF is read by no module (`src/run.py:5-8` restates its framing in prose), and
  `LTV.ipynb` is referenced by no `pyproject.toml` / `.gitignore` / `.gitattributes` entry
  and has no tests. This is the trap that sprang on lending's `report.html`; it does not
  recur here. **Rollback**: `git add -f <path>`. (Credit's CSV is no longer in scope —
  Step 4 descoped.)
- **History exposure is not resolved by untracking** (research H5, question 4). The PDF, the
  pre-strip outputs, and the pre-redaction DWH schema all remain in history. Accepted on the
  private-repo precedent. **The carrier for this blocker is the tracked `.gitignore` comment
  written in Step 2**, not this doc — this doc is gitignored and exists on one machine
  (verified: 0 tracked files under `.claude/docs/`). If the repo is ever made public or
  clone access is granted externally, rewrite (`git filter-repo`) **before** publishing.
- **The hook is machine-local.** `pre-commit install` writes `.git/hooks/pre-commit`, which
  is not cloned and not run in CI. A fresh clone gets the config but no active guard until
  someone runs `pre-commit install`. Mitigation: note it in the repo's setup docs; a CI check
  is the real fix and is out of scope.
- **nbstripout rewrites `pocs/ml/credit/notebooks/01-eda.ipynb`, which is out of scope.**
  Corrected 2026-08-16 — the earlier "verified harmless / no-op" claim was **false**. Zero
  output cells is true, but the hook also strips per-cell `execution` metadata and (without
  `--keep-id`) renumbers cell ids: **303 lines changed** at defaults, **209** with
  `--keep-id`. Consequence: if that notebook is ever staged — including by a reflexive
  `git add -A` — the hook modifies it, exits nonzero, and aborts the commit with an
  unrequested diff in a file this sweep does not touch. That is the mechanism working on
  pre-existing state. Accept the one-time 209-line rewrite, or stage narrowly
  (`git add <specific paths>`) to avoid pulling it in.
- **Rollback for the whole sweep**: every tracked change is a `.gitignore` line, a
  `git rm --cached`, a new file, or a notebook edit — `git checkout -- .gitignore`,
  `git add -f` the untracked paths, and `git checkout -- runs/ml/LTV.ipynb` restore those.
  **Plus one change git cannot undo**: `pre-commit install` writes `.git/hooks/pre-commit`,
  which is outside git's reach and survives every command above. Full rollback is therefore:
  ```bash
  git checkout -- .gitignore runs/ml/LTV.ipynb
  git add -f "runs/ml/customer segmentation/Trade Republic_Data Science Challenge.pdf"
  pre-commit uninstall      # <- the step the four categories above miss
  ```
  Without the last line, an abandoned sweep leaves an active hook set installed from a
  config whose nbstripout entry has just been reverted — every later commit on the branch
  then runs ruff/gitleaks/eof-fixer for the first time. No destructive operation is proposed;
  `rm` appears nowhere.
