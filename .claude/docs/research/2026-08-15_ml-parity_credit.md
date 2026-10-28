# ml-parity — credit angle
Date: 2026-08-15
Work item: [`../plans/2026-08-15-lending-parity.md`](../plans/2026-08-15-lending-parity.md) (synthesis in its Research addendum)
Bar: the five parity elements from `runs/ml/lending/docs/DESIGN-parity.md`

## Headline

**`runs/ml/credit/` is not a run — it is a dataset with two empty directories beside
it.** `src/` and `notebooks/` are literally empty (`ls -laR` → `total 0`). No README, no
harness, no metric, no finding, no test, no config, no notebook, no line of code.

The critical discovery: **the credit *code* exists at a different path** —
`pocs/ml/credit/` (tracked, committed, **confirmed on `main`** by the dispatcher:
`git ls-tree main -- pocs/ml/credit/` lists `README.md`, `notebooks/`, `src/`) holds
`README.md`, `notebooks/01-eda.ipynb`, `notebooks/eda.py`, `src/run.py`. And
`pocs/ml/credit/data/` **does not exist**. The code half and the data half of one
prototype are split across two trees, each missing what the other has. `runs/ml/credit/`
is the orphaned data half.

## 1. What it IS

- `runs/ml/credit/data/credit_default.csv` — the only file. 200K, 801 lines (800 rows +
  header), semicolon-delimited, 43 columns.
- `runs/ml/credit/src/` and `runs/ml/credit/notebooks/` — empty shells, mtime Aug 15
  14:06, never filled.
- **Git provenance: none.** `git log -- "runs/ml/credit"` returns nothing on any branch;
  `git status --porcelain --ignored` shows `!! runs/ml/credit/` — invisible to git.
- **Verdict: parked artifact, not a run of the pipeline.**

The real prototype at `pocs/ml/credit/` came from commit `b7fb680` (Aug 12, "Refactor
code structure..."), added alongside `prototype-genesis/SKILL.md` and
`review-leakage/SKILL.md`. The data CSV mtime (Aug 12 12:14) predates that commit — data
staged first, code written against it, code committed to `pocs/` while the data stayed at
`runs/`.

**Documented findings exist — in `pocs/ml/credit/README.md`, not here.** README.md:20-30:
14 positives of 800 (1.75%), ~2.8 positives per 5-fold, 41 of 43 columns with nulls,
named leakage candidates `has_paid` / `recovery_debt`. Its own limit at :27-30: "This
sample demonstrates the mechanics honestly; it does not produce a trustworthy model."

## 2. Data handling

| Property | Value |
|---|---|
| Tracked? | No (`git ls-files runs/ml/credit` → empty) |
| Ignored? | Yes — but only via `.gitignore:48` (`*.csv` catch-all) |

No path rule, no `.gitkeep` (lending has one), so the directory vanishes on a fresh
clone. **PII risk real and flagged in-repo**: `.gitignore:32` labels this class "personal
financial information about identifiable people"; first column is `uuid`, `age` present
(a protected characteristic per
`.claude/docs/plans/2026-08-11-gal-4-phase2-ml-fraud-poc.md:187`); remaining columns are
behavioral financial aggregates keyed to a per-person identifier.

**Provenance is an uncontrolled local path**: `pocs/ml/credit/README.md:13-16` and
`src/run.py:102-103` restore the file by copying from
`~/workspace/lebanese-blonde/src/data/dataset.csv` — operator-private, no hash, no
version pin.

## 3. State vs the 5 bar elements

| # | Element | Status |
|---|---|---|
| 1 | Tests in `testpaths` | Absent (`pyproject.toml:97-102` lists four dirs, not this) |
| 2 | `--dry-run` | Absent — no code at this path; even `pocs/.../run.py` has only `--models` |
| 3 | Guards | Absent here; delegated (not owned) in `pocs/` — leakage assertion lives in `ml/workflows/classification.py`; zero `seed`/`random_state` hits in `run.py` |
| 4 | Record to `runs/_index/` | Absent — the target directory does not exist repo-wide |
| 5 | Data ignored / aggregates-only | Half — data ignored (incidentally); no outputs exist, so aggregates-only is vacuous |

**Score: 0 of 5.** Note element 4 is not credit-specific — nothing writes `runs/_index/`
anywhere yet.

## 4. What reaching the bar would require

**The headline is an anti-finding, already written down**: with ~2.8 positives per fold,
"fold-to-fold variance dwarfs any plausible model difference"
(`pocs/ml/credit/README.md:22-30`). Making *that* reproducible is cheap; making a *model
metric* reproducible is not worth doing — the README already says the metric would not be
trustworthy. A real run needs the full extract ("90k customers, 1.4% default"), not in
the repo.

The work splits:

1. **Reunify the split prototype (cheap, high value).** `pocs/` contradicts CLAUDE.md's
   runs-layout rule, and `prototype-genesis/SKILL.md:87,245,248,341,342` still points at
   `pocs/ml/credit/...` paths. Moving `pocs/ml/credit/*` → `runs/ml/credit/` fills the
   empty dirs, gives `run.py` its `data/` (`run.py:63` derives `DATA` from
   `parents[1]/"data"`, so the move works unedited), and fixes doc-vs-layout drift. The
   two hardcoded restore hints (`run.py:102-103`, `README.md:15`) go stale.
2. **Gate 1a is blocked on a human answer.** `run.py:19-21` lists three
   deliberately-undefaulted items, one BLOCKING: no stated label horizon for `default`
   (blocks the threshold); splitter awaits the gate-1b EDA answer on time structure; cost
   posture has a direction (FN > FP) but no ratio. No harness work resolves these.
3. **Then the bar items** in dependency order: tests + `testpaths` registration;
   `--dry-run` synthetic path; explicit seeding; record the finding per existing
   convention (`docs/summary.json`) until the registry lands.

**It does not need the whole pipeline from `/proto-research` first** — the frame work
(EDA, column plan, leakage candidates, gate-1a config) exists. The gating constraint is
human input, not missing code.

## 5. Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `runs/ml/credit/src/` | SKIP | Yes — the destination is free: `pocs/ml/credit/src/run.py` (220 lines, working gate-3 script delegating fold-safe fitting to the toolkit) moves here for one `git mv`, no rewrite | Empty directory; nothing to assess |
| `runs/ml/credit/notebooks/` | SKIP | Yes — same move: `01-eda.ipynb` + `eda.py` (570 + 472 lines) follow the narrative-vs-logic split (`README.md:43-46`); `eda.py:column_plan` wraps `ml.transform.columns.infer_column_types` so notebook and `run.py` cannot drift | Empty directory |
| `runs/ml/credit/data/` | ADAPT | — | The one asset with content and the only thing `pocs/` lacks. Needs a path-specific ignore rule, a `.gitkeep`, and pinned provenance (currently an unversioned copy from an operator-private path). The 800-row sample is a demo slice, not the 90k extract a real run needs |

## Caveats

- Branch context at scan time: `bug/marketing-comms-review-fixes`. The `pocs/ml/credit/`
  on-`main` question was subsequently **verified by the dispatcher** (present on main).
- CSV row contents not read; column names from the header line only. The 1.75% / 41-nulls
  figures are quoted from `pocs/ml/credit/README.md:22-24`, not recomputed.
- `worktrees/GAL-31-deploy-harden/` contains a duplicate `prototype-genesis` skill with
  the same stale `pocs/` paths; excluded as a worktree copy.
