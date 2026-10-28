# ml-credit reunification — rejoin a prototype split across two trees
Date: 2026-08-16
Status: EXECUTED
Review: pending
Track: ml

Scout: [`../research/2026-08-15_ml-parity_credit.md`](../research/2026-08-15_ml-parity_credit.md)
Parent synthesis: [`2026-08-15-lending-parity.md`](2026-08-15-lending-parity.md) § Research addendum
Bar: the five parity elements from [`runs/ml/lending/docs/DESIGN-parity.md`](../../../runs/ml/lending/docs/DESIGN-parity.md)
GitHub issue: [galactus#36](https://github.com/ramseywise/galactus/issues/36) — branch `GAL-36-credit-reunification`.

## Research

### Summary

`runs/ml/credit/` is **not a run** — it is one ignored CSV beside two empty directories.
The credit *code* exists at a different path, `pocs/ml/credit/`, where `data/` does not
exist. **Each half lacks exactly what the other has.** Scored against the bar,
`runs/ml/credit/` is 0 of 5, but that number is misleading: the gap is not missing work, it
is a directory split plus three unanswered configuration questions.

This item is therefore **not a parity item yet**. It has two phases with a hard seam
between them: a mechanical reunification that is fully unblocked and cheap, and a harness
build that is **blocked on operator input**, not on code. The addendum states it plainly:
"The gating constraint is human input, not missing code."

### Scope

In: reunifying the two halves, fixing the doc-vs-layout drift the split created, and
scoping what a real credit run would need. Out: `runs/ml/credit/data/`'s missing path rule
and `.gitkeep` (moved to
[`2026-08-16-repo-hygiene-tracked-content.md`](2026-08-16-repo-hygiene-tracked-content.md)),
and the harness itself if the operator interview does not resolve.

### Findings

**C1 — The prototype is split across two trees, both halves incomplete. (High)**
`runs/ml/credit/` holds `data/credit_default.csv` (200K, 801 lines = 800 rows + header,
semicolon-delimited, 43 columns) and two literally empty directories — `src/` and
`notebooks/`, `ls -laR` → `total 0`, mtime Aug 15 14:06, never filled. No README, no
harness, no metric, no finding, no test, no config, no notebook, no line of code.

The real prototype is at `pocs/ml/credit/` — tracked and **confirmed on `main`**
(`git ls-tree main -- pocs/ml/credit/` lists `README.md`, `notebooks/`, `src/`; re-verified
2026-08-16). It holds `README.md`, `notebooks/01-eda.ipynb`, `notebooks/eda.py`,
`src/run.py`. And `pocs/ml/credit/data/` **does not exist**.

Git provenance for the `runs/` half: **none.** `git log -- "runs/ml/credit"` returns
nothing on any branch; `git status --porcelain --ignored` shows `!! runs/ml/credit/` —
invisible to git. The `pocs/` half came from commit `b7fb680` (Aug 12, "Refactor code
structure…"), added alongside `prototype-genesis/SKILL.md` and `review-leakage/SKILL.md`.
The CSV's mtime (Aug 12 12:14) predates that commit: **data staged first, code written
against it, code committed to `pocs/` while the data stayed at `runs/`.**

**C2 — The move is one `git mv` and needs no code edit. (High)**
`pocs/ml/credit/src/run.py:63` derives `DATA` from `parents[1]/"data"` — a relative path,
so moving `pocs/ml/credit/*` → `runs/ml/credit/` gives `run.py` its `data/` **unedited**.
The two hardcoded restore hints (`run.py:102-103`, `README.md:15`) go stale on the move and
need updating.

**C3 — The split created doc-vs-layout drift that outlives it. (Medium)** `pocs/`
contradicts CLAUDE.md's runs-layout rule ("a run of the pipeline is a subdirectory under
`runs/ai/` or `runs/ml/`"), and `prototype-genesis/SKILL.md:87,245,248,341,342` **still
points at `pocs/ml/credit/…` paths** — stale since the runs/ move. The addendum's
skill-gate item 5 notes the fix rides this reunification. Also flagged by the scout:
`worktrees/GAL-31-deploy-harden/` contains a duplicate `prototype-genesis` skill with the
same stale paths (excluded as a worktree copy, but it will need the same fix or will
reintroduce them).

**C4 — The findings exist, in prose, at the other path. (High)**
`pocs/ml/credit/README.md:20-30` records: 14 positives of 800 (1.75%), ~2.8 positives per
5-fold, 41 of 43 columns with nulls, named leakage candidates `has_paid` and
`recovery_debt`. Its own stated limit (`:27-30`): *"This sample demonstrates the mechanics
honestly; it does not produce a trustworthy model."*

**The headline is an anti-finding**: with ~2.8 positives per fold, "fold-to-fold variance
dwarfs any plausible model difference." Making *that* reproducible is cheap; making a
*model metric* reproducible is not worth doing, because the README already says the metric
would not be trustworthy. A real run needs the full extract ("90k customers, 1.4%
default") — not in the repo. This is the same shape as fraud's refusal, and the same
record question applies (addendum X3).

**C5 — Gate 1a is blocked on a human answer, and no harness work resolves it. (High)**
`pocs/ml/credit/src/run.py:19-21` lists three deliberately-undefaulted items:

1. **No stated label horizon for `default`** — marked BLOCKING; it blocks the threshold.
2. **Splitter** — awaits the gate-1b EDA answer on time structure.
3. **Cost posture** — has a direction (FN > FP) but no ratio.

Zero `seed`/`random_state` hits in `run.py`, so the current script is not reproducible even
once the data is in place.

**C6 — Guards are delegated, not owned. (Medium)** The leakage assertion lives in the
toolkit (`ml/workflows/classification.py`), not in this run. Fraud and segmentation both
own a local, unit-tested guard module; credit has none. Whatever the harness becomes,
element 3 is unmet in the sense the bar means it.

**C7 — Data provenance is an uncontrolled local path. (Medium)**
`pocs/ml/credit/README.md:13-16` and `src/run.py:102-103` restore the CSV by copying from
`~/workspace/lebanese-blonde/src/data/dataset.csv` — operator-private, no hash, no version
pin. The 800-row sample is a demo slice, not the 90k extract a real run needs. PII class is
real: first column `uuid`, `age` present, remainder behavioural financial aggregates keyed
to a per-person identifier. (The missing ignore-rule half of this is the hygiene item's;
the *provenance* half is this item's.)

### Bar score, and why it is misleading

| # | Element | Status |
|---|---|---|
| 1 | Tests in `testpaths` | Absent (`pyproject.toml:97-102` lists four dirs, not this) |
| 2 | `--dry-run` | Absent — no code at this path; even `pocs/…/run.py` has only `--models` |
| 3 | Guards | Absent here; delegated in `pocs/` (C6) |
| 4 | Record to `runs/_index/` | Absent — the target directory does not exist repo-wide |
| 5 | Data ignored / aggregates-only | Half — ignored incidentally via `*.csv`; no outputs exist, so aggregates-only is vacuous |

**0 of 5** — but element 4 is not credit-specific (nothing writes `runs/_index/` anywhere),
and elements 1–3 score zero because the code is at another path, not because the work is
undone. `pocs/ml/credit/src/run.py` is a working 220-line gate-3 script.

### Asset verdicts (from the scout)

| Asset | Verdict | Reason |
|---|---|---|
| `pocs/ml/credit/src/run.py` | ADAPT | 220-line working gate-3 script delegating fold-safe fitting to the toolkit; one `git mv`, no rewrite |
| `pocs/ml/credit/notebooks/` | ADAPT | `01-eda.ipynb` + `eda.py` (570 + 472 lines) follow the narrative-vs-logic split (`README.md:43-46`); `eda.py:column_plan` wraps `ml.transform.columns.infer_column_types` so notebook and `run.py` cannot drift |
| `pocs/ml/credit/README.md` | ADAPT | Carries the real findings (C4); two restore-hint paths go stale on the move |
| `runs/ml/credit/src|notebooks` | SKIP | `total 0`; the move fills them at the cost of one `git mv` |
| `runs/ml/credit/data/` | ADAPT | The one asset with content and the only thing `pocs/` lacks; needs pinned provenance (C7) |

### Open questions for `/proto-plan`

1. **Does this item stop at reunification?** The move plus the stale-path fixes are cheap,
   unblocked, and independently valuable. Everything after gate 1a needs the operator
   interview. Recommended seam: reunification is this item, the harness is a follow-on
   filed once C5's three answers exist.
2. **The three gate-1a answers** (label horizon, splitter, cost ratio) — settle them in
   this plan's goal elicitation, or defer? If they are settled here, the harness step
   becomes plannable in the same item.
3. **Does the notebook come too, or only `src/`?** The notebooks are 1,042 lines of EDA;
   they belong with the run, but the `pocs/` → `runs/` move is also the moment to ask
   whether `pocs/` should exist at all after this (it would then hold nothing).
4. **`prototype-genesis/SKILL.md`'s five stale paths** — fix in this item (they break the
   moment the move lands) or separately? They break *because of* this move, so bundling is
   the safer call.
5. **Is the anti-finding worth recording** in the fraud sense (a refusal record), or does it
   stay as prose in the README? Same open question fraud carries, and the answers should
   probably match.

### Dependencies

- **Operator input on the three gate-1a items (C5)** — blocks all harness work; blocks
  nothing in the reunification.
- The `git mv`, the restore-hint updates, and the `prototype-genesis` path fixes are
  **fully unblocked**.
- No dependency on AIT#83 or `runs/_index/` unless the item extends to a record.

---

## Plan
Date: 2026-08-18
Based on: `## Research` above, plus direct inspection on 2026-08-18 which **falsified
research finding C1** — see Research drift below.

### Goal

Make `runs/ml/credit/` the single, tracked home of the credit prototype, so that the
runs-layout rule holds and `/prototype-genesis` stops pointing at paths that are about to
disappear. **Reunification only** — no harness, no metric, no frame decision.

### Research drift — read before the steps

Three research claims no longer hold as of 2026-08-18. The steps below are written against
what is on disk now, not against C1/C2.

1. **`runs/ml/credit/src|notebooks` are no longer empty.** C1 says `ls -laR` → `total 0`.
   All four files are present and **untracked** (`git status` → `?? runs/ml/credit/`).
   Someone copied rather than moved. So step 1 is a *reconciliation*, not a `git mv`.
2. **The two copies are not identical.** `README.md`, `notebooks/eda.py`, `src/run.py` are
   byte-identical (`cmp`); `notebooks/01-eda.ipynb` differs. The diff is a markdown
   formatter pass (`*emphasis*` → `_emphasis_`, one added blank line) **plus one
   regression**: cell 1's `import eda` was rewritten to
   `import galactus.runs.ml.credit.notebooks.eda as eda`. No `__init__.py` exists anywhere
   in that chain (`find runs pocs -name __init__.py` — the credit path is absent), so the
   `runs/` notebook does not run. The `pocs/` copy is therefore the good one; the `runs/`
   copy is discarded, not merged.
3. **The move needs no `sys.path` edit, for a second reason C2 does not give.**
   The brief notes `run.py:63` derives `DATA` from `parents[1]` — correct. But `run.py:48`
   also derives `_ROOT` from `parents[4]`, which the brief does not mention. That also
   survives: `runs/ml/credit/src` is the same depth as `pocs/ml/credit/src` (4 up = repo
   root in both). Verified by the guard at `:49-50`, which raises if `ml/__init__.py` is
   not found at `_ROOT`. **Do not "fix" `parents[4]` during the move.**

A fourth, minor: `README.md:37-39` documents `src/eda.py`, but the file is at
`notebooks/eda.py`. Pre-existing drift, corrected in step 4 since that README is being
edited anyway.

### Open Questions

1. **Label horizon for `default`** — RESOLVED 2026-08-18: **90 days past due**, recorded as
   **provisional**. It is a Basel-style convention, not derived from the extract; whatever
   frame is eventually sourced supersedes it. Recorded as a comment in `run.py` only —
   this plan ships no threshold, so nothing consumes it yet.
2. **Splitter** — RESOLVED 2026-08-18: decide from EDA, **not in this plan**. The notebook
   exists but has not been run against the frame. Stays `GROUP_COL = TIME_COL = None` with
   the PROVISIONAL warning intact. Filed as follow-on.
3. **Cost ratio** — RESOLVED 2026-08-18: **stays `None`**. With ~2.8 positives per fold a
   cost-minimising threshold is fitted to ~3 events; a ratio would manufacture a decision
   the data cannot support. `run.py:213-215` already prints this as a refusal.
4. **`prototype-genesis` stale paths** — RESOLVED 2026-08-18: **bundle here** (research Q4).
   They break the moment the move lands. Note: **six** references, not the five C3 counts —
   `SKILL.md:27` is a usage template (`--poc pocs/<branch>/<slug>`) that C3's grep for
   `pocs/ml/credit` missed.
5. **Anti-finding record** — RESOLVED 2026-08-18: **prose only in this plan**, matching
   fraud's *framing* but not yet its machinery. Fraud earns its `refusal` block in
   `summary.json` with a tested `sufficiency.py`; credit has no harness to hang one on.
   Deferred with the harness, not dropped.
6. **Credit vs lending consolidation** — UNRESOLVED, deliberately out of scope. Operator's
   read (2026-08-18): same underlying question, differing mainly by dataset. Code's
   counter-evidence: `runs/ml/lending/README.md:40-47` names ability-to-pay vs
   propensity-to-pay and calls collapsing them the failure mode ("rank the wealthy above
   the willing"); lending's open Q4 (uplift vs propensity) has no underwriting analogue.
   Settled for now as **same machinery, different decision** — credit is
   ability-at-origination, lending is propensity-at-collection. Two runs, one toolkit.
   Needs its own session; see Open Issues.
7. **Frame sourcing** — UNRESOLVED, out of scope. The 800-row lebanese-blonde CSV is a
   stand-in for every ML run; real frames are to come from Kaggle or be synthesised. No
   item exists for this anywhere in `.claude/docs/plans/`. See Open Issues.

### Approach

Reconcile rather than move. `runs/ml/credit/` already holds an untracked copy, so the work
is: delete the untracked copy (keeping only `data/`, the one thing `pocs/` lacks),
`git mv` the tracked `pocs/` files into place, then repair the references that the move
invalidates. The tradeoff accepted: discarding the `runs/` notebook loses a cosmetic
formatter pass in order to lose a broken import with it — re-running a formatter is
cheaper than debugging a dotted import that was never valid.

### Out of Scope

- **Any harness work** — guard module, `--dry-run`, `testpaths` entry, `runs/_index/`
  record. Blocked on the frame decision, not on effort. `pyproject.toml` is untouched.
- **A credit-local sufficiency guard.** Deferred with the harness.
- **Replacing the 800-row stand-in.** Separate item (Open Question 7).
- **Merging credit into lending.** Separate item (Open Question 6).
- **Running the EDA notebook** to settle the splitter. Follow-on.
- **`runs/ml/credit/data/`'s ignore rule and `.gitkeep`** — already owned by
  [`2026-08-16-repo-hygiene-tracked-content.md`](2026-08-16-repo-hygiene-tracked-content.md).
- **`worktrees/GAL-31-deploy-harden/`'s duplicate skill copy** (C3). A worktree checkout;
  it resolves when that branch rebases.
- **Setting `COST_FP`/`COST_FN`, or reporting any threshold or metric.**

### Steps

#### Step 1: Discard the untracked `runs/` copy, keeping `data/`

**Files**: `runs/ml/credit/README.md`, `runs/ml/credit/notebooks/`, `runs/ml/credit/src/`
(all untracked — `git status --porcelain` shows `?? runs/ml/credit/`)

**What**: Remove the three copied paths so `git mv` has a clean target. `data/` stays —
it is the only asset `pocs/` lacks. Nothing here is tracked, so there is no git history to
preserve and `rm` is the correct tool; the tracked originals under `pocs/` are untouched
by this step and are the recovery path if anything goes wrong.

**Snippet**:
```bash
# before: runs/ml/credit/{data,notebooks,src,README.md}, all but data/ untracked
rm -rf runs/ml/credit/README.md runs/ml/credit/notebooks runs/ml/credit/src
# after:  runs/ml/credit/data/credit_default.csv only
```

**Test**: `ls -A runs/ml/credit/` → `data` alone; `git status --porcelain runs/ml/credit`
→ no `??` lines except the ignored `data/`.

**Done when**: `runs/ml/credit/` contains exactly `data/`, and
`git status --porcelain pocs/ml/credit` is empty (originals untouched).

#### Step 2: `git mv` the tracked prototype into `runs/ml/credit/`

**Files**: all four tracked paths under `pocs/ml/credit/` → `runs/ml/credit/`

**What**: Move with `git mv` so history follows. `pocs/` is then empty and is removed —
after the move it holds nothing (research Q3), and leaving an empty `pocs/ml/` would keep
satisfying `import ml` as a namespace package, which is exactly the failure `run.py:41-47`
documents.

**Snippet**:
```bash
git mv pocs/ml/credit/README.md          runs/ml/credit/README.md
git mv pocs/ml/credit/notebooks/01-eda.ipynb runs/ml/credit/notebooks/01-eda.ipynb
git mv pocs/ml/credit/notebooks/eda.py   runs/ml/credit/notebooks/eda.py
git mv pocs/ml/credit/src/run.py         runs/ml/credit/src/run.py
# then, only if genuinely empty:
find pocs -type f -not -path "*__pycache__*"   # must print nothing
rm -rf pocs
```
**Do not edit `run.py:48` (`parents[4]`) or `run.py:63` (`parents[1]`).** Both are
depth-invariant across this move — see Research drift item 3.

**Test**: `uv run python runs/ml/credit/src/run.py --models logistic --n-splits 5`
— must load the frame and print the comparison table. This is the real check that both
path derivations survived.

**Done when**: `git status` shows four renames (`R`); `pocs/` no longer exists; the run
script executes and prints `positives: 14 (1.75%)` plus the FEW POSITIVES PER FOLD warning.

#### Step 3: Repair the two stale restore hints

**Files**: `runs/ml/credit/src/run.py` (lines 102-103, and the `Run:` line at 24),
`runs/ml/credit/README.md` (lines 13-16)

**What**: Both hardcode `pocs/ml/credit/…` as the copy destination, and `run.py:24`'s usage
line names the old invocation path. All three go stale the moment step 2 lands. While here,
add the provisional label-horizon note (Open Question 1) as a comment beside the existing
"Still open" block — it is the one gate-1a answer this plan records.

**Snippet**:
```python
# run.py:102-103  before
"  cp ~/workspace/lebanese-blonde/src/data/dataset.csv "
"pocs/ml/credit/data/credit_default.csv"
# after
"  cp ~/workspace/lebanese-blonde/src/data/dataset.csv "
"runs/ml/credit/data/credit_default.csv"

# run.py:20  before
#     label horizon   `default` has no stated window. BLOCKING for the threshold.
# after
#     label horizon   PROVISIONAL 2026-08-18: 90 days past due (Basel convention),
#                     not derived from this extract. Still BLOCKING for a shipped
#                     threshold — a sourced frame's own definition supersedes it.
```

**Test**: `grep -rn "pocs/" runs/ml/credit/` → no matches.

**Done when**: no `pocs/` reference survives under `runs/ml/credit/`, and the run script
still executes (re-run the step 2 command).

#### Step 4: Fix `prototype-genesis/SKILL.md`'s six stale paths + README layout drift

**Files**: `.claude/skills/prototype-genesis/SKILL.md` lines 27, 87, 245, 248, 341, 342;
`runs/ml/credit/README.md` lines 3-4 and 37-39

**What**: Repoint every `pocs/ml/credit/…` at `runs/ml/credit/…`, and generalise the
usage template at `:27` from `pocs/<branch>/<slug>` to `runs/<branch>/<slug>`. Note
`:245`/`:341` reference `01-eda.ipynb` and `:248`/`:342` reference `src/eda.py` — the
latter is **wrong twice over**: the file is at `notebooks/eda.py`. Fix path and location
together. Same correction in the README's own layout block (`:37-39`), and the README's
opening lines still call this a POC referencing `pocs/ai/marketing-comms/`, which moved to
`runs/ai/marketing-comms/`.

**Snippet**:
```
SKILL.md:27   --poc pocs/<branch>/<slug>        →  --poc runs/<branch>/<slug>
SKILL.md:33   | `--poc` | … | Where the prototype lands |  (row text: name the runs/ tree)
SKILL.md:87   `pocs/ml/credit/`                 →  `runs/ml/credit/`
SKILL.md:245  pocs/ml/credit/notebooks/01-eda.ipynb → runs/ml/credit/notebooks/01-eda.ipynb
SKILL.md:248  pocs/ml/credit/src/eda.py         →  runs/ml/credit/notebooks/eda.py
SKILL.md:341  pocs/ml/credit/notebooks/01-eda.ipynb → runs/ml/credit/notebooks/01-eda.ipynb
SKILL.md:342  pocs/ml/credit/src/eda.py         →  runs/ml/credit/notebooks/eda.py
README.md:37  src/eda.py                        →  notebooks/eda.py
README.md:3-4 pocs/ai/marketing-comms/          →  runs/ai/marketing-comms/
```
**Keep the flag named `--poc`; change only its path default.** Verified 2026-08-18: `--poc`
occurs exactly twice (`:27` usage line, `:33` arg table), both inside the same usage block.
Renaming it to `--run` is defensible but is a skill-interface change, not a path repair —
out of scope for a reunification item. Note the residual inconsistency (a flag named
`--poc` pointing into `runs/`) for whoever next touches this skill.

**Test**: `grep -rn "pocs/" .claude/skills/prototype-genesis/SKILL.md` → no matches;
`grep -rn "src/eda.py" .claude/skills/prototype-genesis/SKILL.md runs/ml/credit/README.md`
→ no matches.

**Done when**: neither file references `pocs/` or `src/eda.py`, and every path named in
`SKILL.md` resolves on disk (spot-check each with `ls`).

#### Step 5: Record the anti-finding in the README

**Files**: `runs/ml/credit/README.md` (the block at 24-31)

**What**: The README already carries the substance ("does not produce a trustworthy
model"). Sharpen it into an explicit anti-finding in fraud's voice, and state plainly that
this is prose, not a machine-readable refusal — so a later reader knows the absence of a
`refusal` block is a deferral, not an oversight.

**Snippet**:
```markdown
## The finding

**The headline result is an anti-finding.** With ~2.8 positives per 5-fold, fold-to-fold
variance dwarfs any plausible model difference. Reproducing *that* is cheap and worth
doing; reproducing a *model metric* is not, because no metric computed here is
trustworthy.

Unlike [`../fraud/`](../fraud), this is recorded as prose only. Fraud earns a
machine-readable `refusal` block in its `summary.json` via a tested `sufficiency.py`;
credit has no harness to hang one on yet. That is deferred, not declined.
```

**Test**: `uv run pytest --tb=no -q` — must stay at 609 passed, 14 skipped. No test
covers this run, which is itself the point; the check is that nothing regressed.

**Done when**: the README states the anti-finding and its prose-only status, and the
suite is unchanged from baseline.

### Test Plan

Baseline captured 2026-08-18: **609 passed, 14 skipped** in 5.87s.

| After step | Check |
|---|---|
| 1 | `ls -A runs/ml/credit/` → `data` only |
| 2 | `git status` shows 4 renames; run script executes end-to-end |
| 3 | `grep -rn "pocs/" runs/ml/credit/` → empty |
| 4 | `grep -rn "pocs/" .claude/skills/prototype-genesis/SKILL.md` → empty |
| 5 | `uv run pytest --tb=no -q` → 609 passed, 14 skipped |

No new tests. This plan adds no code — it moves files and repairs references. The
end-to-end guard is step 2's actual execution of `run.py`, which exercises both path
derivations that the move could plausibly have broken.

### Risks & Rollback

| Risk | Likelihood | Mitigation |
|---|---|---|
| Discarding the `runs/` notebook loses real work | Low | Diffed cell-by-cell: formatter pass + one broken import. Nothing substantive. If doubted, `cp` it aside before step 1. |
| `parents[4]` breaks on the move | Very low | Depth is identical; `run.py:49-50` raises loudly rather than failing silently. Step 2's test catches it immediately. |
| `rm -rf pocs` deletes something unnoticed | Low | Guarded by the `find` in step 2 — it must print nothing first. Everything under `pocs/` is tracked, so `git checkout` restores. |
| `--poc` → `--run` rename ripples through the skill | Medium | Step 4 says: if other occurrences exist, keep the flag name and change only the path. |
| The frame is never sourced and this run stays inert | Medium | Accepted. This plan makes the prototype findable and correct; it does not claim to make it runnable against real data. |

Rollback is `git checkout -- .` plus restoring `runs/ml/credit/data/` (never tracked,
never touched by any step).

---

## Execution record — 2026-08-18

Executed directly in the planning session at the operator's instruction; `/proto-refine`
was **deliberately skipped** — five mechanical file operations do not warrant a readiness
gate. Suite verified green before and after: **609 passed, 14 skipped**.

### What differed from the plan

1. **Both trees were committed by the time execution began.** The plan was written against
   `?? runs/ml/credit/` (untracked copy). Commit `fe537c8` ("Add EDA functions and main run
   script…") tracked the `runs/` copy in between, on branch
   `GAL-39-resolve-capability-registry` — not the `GAL-36` branch the plan assumed. So the
   broken-import notebook was **the canonical one in git**, which raised the urgency rather
   than lowering it. Step 1's `rm -rf` of an untracked copy became `git rm -r pocs/` after
   copying the working notebook over the broken one.
2. **Step 2's `git mv` was unnecessary.** `runs/ml/credit/` already held all four files
   tracked; only the duplicate `pocs/` tree needed removing. Git records the result as a
   deletion of `pocs/`, not a rename — history for the credit files already lives at the
   `runs/` path via `fe537c8`.
3. **Nine stale `pocs/` references, not six.** The research found five, this plan found a
   sixth (`SKILL.md:27`). Execution found three more the earlier greps missed, all inside
   files being moved rather than referencing them: `notebooks/eda.py:37,92` and
   `README.md:53`.
4. **`--poc` was renamed to `--run` after all.** The plan deferred this as a skill-interface
   change; the operator overruled — a flag named for a directory that no longer exists is
   simply wrong. Both occurrences (`SKILL.md:27,33`) changed together.
5. **A tenth path error, inside the notebook.** Cell 0 linked `[`../src/eda.py`](../src/eda.py)`
   — wrong on both the `src/` vs `notebooks/` axis and the relative-path axis. Rewritten to
   `[`eda.py`](eda.py)`; notebook re-serialised and re-validated as JSON (33 cells, nbformat 4).

### Verification performed

| Check | Result |
|---|---|
| `uv run python runs/ml/credit/src/run.py --models logistic` | Runs; `positives: 14 (1.75%)`, FEW-POSITIVES warning, PROVISIONAL split, threshold NOT REPORTED |
| `import eda` from `runs/ml/credit/notebooks/` | OK; `column_plan` present |
| `grep -rn "pocs/" runs/ml/credit/ .claude/skills/prototype-genesis/` | No matches |
| `grep -rn "src/eda.py" runs/ml/credit/ .claude/skills/…` | No matches |
| Notebook JSON validity | Valid, 33 cells, nbformat 4 |
| `uv run pytest --tb=no -q` | 609 passed, 14 skipped — unchanged from baseline |

`parents[4]` and `parents[1]` were left untouched as the plan directed, and the run
script's successful execution from the `runs/` path confirms both survived.

### Not done (unchanged from Out of Scope)

Harness, sufficiency guard, `--dry-run`, `testpaths` entry, `runs/_index/` record, frame
sourcing, credit/lending merge, running the EDA to settle the splitter. `pyproject.toml`
untouched. `COST_FP`/`COST_FN` still `None`; no threshold or metric is claimed.

### Open Questions (post-plan, for `/proto-refine`)

Both are out of scope here and neither blocks execution:

1. **Credit vs lending consolidation** (Open Question 6) — needs a scoping session, not a
   line in a plan doc.
2. **Frame sourcing for every ML run** (Open Question 7) — no item exists; the 800-row
   stand-in is load-bearing across credit, fraud, and lending simultaneously.
