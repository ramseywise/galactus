# ml frame sourcing — licensed, horizon-stated frames for credit and fraud
Date: 2026-08-18
Status: PLANNED
Track: ml

Design: [`../DESIGN-ml-frame-sourcing.md`](../DESIGN-ml-frame-sourcing.md)
Related: [`2026-08-16-credit-reunification.md`](2026-08-16-credit-reunification.md) (rename completed 2026-08-18),
[`2026-08-16-fraud-parity.md`](2026-08-16-fraud-parity.md)
GitHub issues: [galactus#36](https://github.com/ramseywise/galactus/issues/36) (credit), [galactus#34](https://github.com/ramseywise/galactus/issues/34) (fraud)

## Research

### Summary

The design's **credit → UCI** decision is confirmed on every claim, including the one it
flagged as unconfirmed: prevalence is **22.12%** (6,636/30,000), counted from the
downloaded file. Credit's blocking `label horizon: UNDEFINED` resolves at the source.

The **fraud → Kaggle `mlg-ulb/creditcardfraud`** decision does **not** survive research
intact. Two problems, one of them decisive: the frame has **no stated label horizon**, and
its **license could not be verified**. The design makes a stated horizon a hard constraint
("Inferred horizon = unavailable") and then selects a frame that fails it. This is not a
detail to note in passing — by the design's own sourcing standard, fraud's chosen frame is
*unavailable*, and the choice needs an operator decision before any plan is written.

The good news on fraud: the ODbL share-alike worry (Open Question 2) is resolved in the
design's favour **if** the license is in fact ODbL — a metrics report is a Produced Work,
which ODbL §4.5(b) explicitly exempts from share-alike.

### Scope

In: verifying the two proposed source frames against the design's three sourcing
constraints (license, stated horizon, prevalence), and verifying the design's codebase
claims about the guard, credit's leakage gap, and `summary.json` coverage.

Out: implementing any download script, editing loaders, or touching
`runs/ml/fraud/docs/DESIGN.md` (pre-registration — out of scope by operator instruction and
by the design doc). Lending was not re-verified; the design leaves it unchanged.

### Findings

#### F1 — Credit's UCI frame: every claim confirmed — High

Verified against `archive.ics.uci.edu/dataset/350` and by downloading the file.

| Claim | Verdict | Evidence |
|---|---|---|
| License CC BY 4.0 | CONFIRMED | dataset page, verbatim |
| 30,000 × 23 | CONFIRMED | downloaded file: 30,000 rows, 25 cols incl. `ID` + `Y` |
| Target `default payment next month` | CONFIRMED | UCI variables table (it is the *description*; the column **name** is `Y`) |
| **Horizon = one month, source-stated** | **CONFIRMED** | UCI-curated variable metadata, in 3 independent places |
| Prevalence ~22.1% | **CONFIRMED — 22.12% exact** | counted: 6,636/30,000 |
| Yeh (2009), DOI 10.24432/C55S3H | CONFIRMED | dataset page |
| No account needed | CONFIRMED | HTTP 200, no auth, no cookies |

Thinnest 5-fold test fold ≈ **1,327 positives** vs the floor of 10. Threshold supportable
by two orders of magnitude more than needed.

**Horizon nuance that matters for the citation.** "next month" appears in the *variables
table*, not the prose "Additional Information" block — the prose says only "a binary
variable, default payment (Yes = 1, No = 0)" with no horizon. The horizon is genuinely
source-stated, but it rests on UCI's curated variable metadata alone. Cite the variables
table, not the abstract. Features cover April–September 2005 (X6 = Sept 2005 repayment
status), so "next month" = October 2005 — consistent, and worth recording as the horizon's
concrete meaning rather than the bare phrase.

#### F2 — Fraud's frame has NO stated label horizon — High — **decisive**

`Class=1` is documented only as "1 in case of fraud and 0 otherwise." That is a label
*definition*, not a *horizon*. The source states nothing about the adjudication window:
chargeback lag, when labels were finalized, or whether late-arriving chargebacks were
backfilled or left as `Class=0`.

**The two-day figure is not the horizon and is routinely misread as one.** `Time` is
"seconds elapsed between each transaction and the first," fixing the *sampling* window at
~2 days (Sept 2013). The *labeling* window is independent and unstated.

The source forecloses recovery: "Due to confidentiality issues, we cannot provide the
original features and more background information about the data." No further searching
closes this — the gap is in the source by design.

**Against the design's own standard** (§Sourcing standard: "The source defines what the
label means over what window. Inferred horizon = unavailable") this frame is **unavailable**.
The design's Evaluation table targets "Frames with a stated label horizon: 3/3"; adopting
this frame caps that at **2/3** permanently.

Note the asymmetry with credit: the design used the horizon requirement as the decisive
argument *for* UCI ("This closes credit's blocking gap"), then selected a fraud frame that
fails the same test. Applying the standard to one run and not the other is the finding.

#### F3 — Fraud's ODbL license is UNVERIFIED — Medium confidence it is ODbL

Kaggle renders the license badge client-side; WebFetch retrieved only the page title, and
the public API returned `[]` without auth. No mirror restates the license. **ODbL is not
established.** The plausible confusion is real: Kaggle also offers "Database Contents
License (DbCL)" and CC0, and ODbL-vs-DbCL is precisely the distinction that changes the
redistribution analysis.

Closes via a human loading the page, or authenticated
`kaggle datasets metadata mlg-ulb/creditcardfraud` (returns `licenseName`).

Everything else about the frame is confirmed: 284,807 rows, 492 positives (0.172%), 28 PCA
components + `Time` + `Amount`, Worldline/ULB provenance, Dal Pozzolo et al. (2015) — the
paper independently verified via dblp.

#### F4 — ODbL share-alike does NOT attach to a committed metrics report — High

Open Question 2 resolves **in the design's favour**, conditional on F3.

ODbL distinguishes a **Derivative Database** ("a database based upon the Database") from a
**Produced Work** ("a work … resulting from using the whole or a Substantial part of the
Contents"). §4.5(b) is explicit:

> "Using this Database, a Derivative Database, or this Database as part of a Collective
> Database to create a Produced Work does not create a Derivative Database for purposes of
> Section 4.4."

§4.4 *is* the share-alike clause, so Produced Works are carved out by name. §4.3 requires
only an attribution notice on public use, with a model notice supplied by the license.

| Artifact | Category | Obligation |
|---|---|---|
| `summary.json`, AUC, PR curves, threshold sweeps, reliability bins, coefficients | Produced Work | Attribution notice. **No share-alike, no repo relicensing** |
| `creditcard.csv`, a resampled/split copy, feature-engineered row-level table, per-row predictions joined to source rows | Derivative Database | Share-alike **does** attach, plus §4.2 license delivery |

Two caveats recorded rather than smoothed over: (a) §4.5(c) — purely internal use is not
"Publicly Use," so a private repo triggers nothing, and galactus is private today; (b)
"summary.json" is unbounded as a spec — outputs fine-grained enough to reconstruct row-level
values edge toward "Substantial part of the Contents." Standard aggregate metrics are
nowhere near that line, but the spec should bound it.

#### F5 — Every codebase claim in the design verified — High

Checked directly rather than taken from the doc.

| Design claim | Verdict | Evidence |
|---|---|---|
| Stand-in is 800×43, 14 positives, 1.75% | CONFIRMED | counted: `Counter({'0': 786, '1': 14})` |
| Guard floor is 10 | CONFIRMED | `runs/ml/fraud/src/sufficiency.py:30` |
| Guard refuses today, passes on new frames | CONFIRMED | computed: ~2/fold REFUSE; 492→~98/fold PASS; 6,636→~1,327/fold PASS |
| Credit has no leakage exclusion list | CONFIRMED | `runs/ml/credit/src/run.py:70` — `ID_COLS = ["uuid"]` only |
| `summary.json` is 1/3 | CONFIRMED | only `runs/ml/fraud/docs/summary.json` exists |
| Guard tests pass, incl. `test_accepts_a_healthy_frame` | CONFIRMED | 35 passed, 3 skipped; `runs/ml/fraud/tests/test_sufficiency.py:18` |
| Doc-parity risk is real | CONFIRMED | `runs/ml/fraud/README.md:1`, `WALKTHROUGH.md:17,142` all assert the refusal |

One correction to the design: it states the notebook's `recovery_debt` exclusion is
"commented out." There is **no** `recovery_debt` or `has_paid` reference in
`runs/ml/credit/notebooks/eda.py` at all. The gap is larger than described — nothing to
uncomment.

#### F6 — UCI data quirks that will bite the transform — High

Confirmed in the downloaded file, not merely reported:

- **`PAY_0`/X6 and PAY_2–6**: documented scale starts at `-1` = "pay duly", but the data
  holds **-2 (n=2,759)** and **0 (n=14,737)** — ~58% of rows in two *undocumented* codes.
  The most consequential quirk and the least discussed.
- **EDUCATION/X3**: documented 1–4; data holds 0 (14), 5 (280), 6 (51) — 345 undocumented.
- **MARRIAGE/X4**: documented 1–3; data holds 0 (54).
- **`PAY_0, PAY_2, …PAY_6` — there is no `PAY_1`.** An off-by-one trap for generated column lists.
- **35 duplicate rows** excluding `ID`. Zero missing values.
- CSV header is `ID,X1..X23,Y` — cryptic. Friendly names (`LIMIT_BAL`, `PAY_0`…) exist only
  in the `.xls` second header row; the X→name map is in the API metadata.

**Download recommendation:** `https://archive.ics.uci.edu/static/public/350/data.csv`
(2.9 MB, CSV) over the page's `.zip`, which contains an `.xls` requiring `xlrd>=2.0.1`.

Provenance-capture caveat: the API's `license` and `dataset_doi` fields are both `null` —
license and DOI appear only in page HTML. Automated provenance capture from the API returns
empty for exactly the two fields the design most wants recorded.

### Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `runs/ml/fraud/src/sufficiency.py` | REUSE | — | Guard is correct and falsifiable; only its verdict changes. Design's "keep unchanged" is right |
| `runs/ml/fraud/tests/` (35 tests) | REUSE | — | All pass; `test_accepts_a_healthy_frame` already covers the passing branch |
| `runs/ml/credit/src/run.py` | ADAPT | — | Loader repoint + horizon constant + leakage list. Structure sound; gate-1a/1b scaffolding already present and correctly left unresolved |
| `runs/ml/credit/notebooks/eda.py` | ADAPT | — | Column-plan logic reusable, but written for the 43-col stand-in; UCI's 23 cryptic `X*` columns need remapping |
| UCI Default of Credit Card Clients | REUSE | — | Satisfies all three constraints; prevalence now download-verified |
| Kaggle `mlg-ulb/creditcardfraud` | **SKIP (as specified)** | **Yes — substantially.** Prevalence (492 pos, ~98/fold) genuinely satisfies constraint 3 and is exactly the "imbalance ≠ insufficiency" demonstration the design wants. Salvageable by *narrowing the claim*: adopt the frame with the horizon recorded as **unknown**, and drop the "3/3 horizon" target to 2/3 — rather than either pretending the horizon exists or discarding the frame | Fails constraint 2 (no stated horizon, unrecoverable by source design) and constraint 1 is unverified (F3) |
| `runs/ml/fraud/docs/DESIGN.md` | SKIP | Not applicable — deliberately untouched | Pre-registration; out of scope by instruction |
| `runs/ml/lending/` | REUSE | — | Design's quality bar; no gap to close |
| lebanese-blonde stand-in | SKIP | Yes — retained as archived historical reference so `before-guard` artifacts stay reproducible, per operator decision | Fails all three constraints; leaves the modelling path |

### Assumptions

- **Assumption:** galactus stays a private repo — **Evidence:** CLAUDE.md "Private repo; history exposure accepted" (`.gitignore:38`) — **If wrong:** ODbL §4.5(c) internal-use exemption stops applying and attribution notices become mandatory on the fraud artifacts — **Confidence:** High
- **Assumption:** UCI's variables-table horizon is authoritative enough to satisfy "source-stated" — **Evidence:** appears in 3 independent UCI-curated locations (page table, API, embedded JSON) — **If wrong:** credit loses the argument that closed its blocking gap — **Confidence:** High
- **Assumption:** the guard's 5-fold arithmetic holds on the new frames — **Evidence:** computed `pos//5` against `MIN_POSITIVES_PER_FOLD=10`; both clear by large margins — **If wrong:** only if fold count changes; margins are 10–130× so rounding is not a risk — **Confidence:** High
- **Assumption:** a metrics report is a Produced Work, not a Derivative Database — **Evidence:** ODbL §4.5(b) verbatim — **If wrong:** committed fraud reports would carry share-alike — **Confidence:** Medium-High (license text is explicit; the categorization of a given artifact is interpretation, and I am not a lawyer)

### Disconfirming Evidence

- **F1 (UCI horizon).** What would contradict it: the horizon existing only in third-party
  glosses. **Looked** — checked the prose block separately from the variables table and
  found the prose does *not* state it. That is a partial hit: the claim survives, but
  narrower than the design implies. Recorded in F1 rather than smoothed over.
- **F2 (fraud horizon).** What would contradict it: a stated horizon somewhere authoritative.
  **Looked** — Kaggle description, ULB/Worldline provenance, the Dal Pozzolo 2015 paper.
  The papers discuss chargeback label delay in card fraud *generally*; none binds a horizon
  to this extract. The source explicitly refuses to provide background. No contradiction found.
- **F3 (ODbL).** What would contradict it: the license being verifiable after all. **Looked** —
  six attempts across page fetch, public API, and mirrors; several mirrors explicitly noted
  they could not confirm it. Genuinely blocked without auth.
- **F4 (share-alike).** What would contradict it: share-alike reaching Produced Works.
  **Looked** — read §4.4, §4.5(b), §4.3, §4.2 rather than a summary. §4.5(b) carves them
  out by name. The gray zone (row-level reconstruction) is recorded rather than dismissed.
- **F5 (guard passes).** What would contradict it: the guard failing for a reason other than
  fold thinness. **Looked** — ran the suite (35 passed) and read the floor's docstring; the
  verdict depends only on positives in the thinnest test fold.

### Key Unknowns

Per the ml-track contract, the two mandatory unknowns are carried explicitly:

1. **Baseline metric — does not exist for either run.** Named before computing, per the
   contract: for credit on UCI, the majority-class baseline is **77.88% accuracy**
   (23,364/30,000 predicting "no default") and the **PR-AUC prevalence floor is 0.2212**.
   Any credit model must be read against 0.2212, not against 0.5. For fraud the floor
   would be **0.00172** — the number the stand-in's PR-AUC landed within 0.003 of, which is
   how the design knows the current result is arithmetic about three rows. **Status: named,
   not computed.** Open until a run persists it.
2. **Leakage check — red, and named red first.** Credit today has `ID_COLS = ["uuid"]` and
   nothing else. On the UCI frame the columns that would leak are the **`BILL_AMT1`/`PAY_AMT1`
   pair and `PAY_0`** — all dated September 2005, the month immediately before the October
   label. They are legitimate features *only if* the operating story is "predict next month
   from this month"; if any is recorded at or after default adjudication it is post-outcome.
   The split that would leak it: plain stratified k-fold with no time ordering, which is
   what `run.py` does today (`GROUP_COL`/`TIME_COL` both `None`). **Status: red.** Closes
   via the `leakage` dimension over the training path.

Additionally unresolved:

3. **Fraud's license** (F3) — blocks the redistribution analysis in F4.
4. **Fraud's horizon** (F2) — blocks the frame under the design's own standard. **Needs an
   operator decision, not more research.**
5. Whether credit's leakage list is authored fresh for UCI's 23 columns or ported from
   lending — the design's own open item. Research leans **fresh**: UCI's cryptic `X*`
   schema shares no column names with lending, so porting would be renaming, not reuse.

### Recommendation

Credit's decision is ready to plan: the frame is confirmed on all three constraints,
prevalence is download-verified, and the horizon that unblocks credit's threshold is
source-stated. Plan it with the F6 quirks treated as transform work rather than
discovered mid-execution, and author the leakage list fresh against UCI's schema.

Fraud is not ready, and the reason is a contradiction inside the design rather than a
missing fact. The design makes a stated horizon a hard availability constraint, uses that
constraint as the decisive argument for credit's frame, and then adopts a fraud frame with
no stated horizon. Research cannot resolve this — the source deliberately withholds the
information. It is an operator decision between narrowing the standard (adopt the frame,
record the horizon as unknown, drop the Evaluation target to 2/3) and holding the standard
(source a frame that publishes its labeling protocol, or go synthetic per the "2. synthetic
if not" half of the stated standard, which is currently unexercised). The share-alike worry
that looked like fraud's main obstacle is not one; the horizon is.

## Plan
Date: 2026-08-18
Based on: `## Research` above (F1, F5, F6 and the asset verdicts), plus direct inspection of
`runs/ml/credit/src/run.py`, `runs/ml/credit/notebooks/eda.py`, `runs/ml/lending/src/frame.py`,
`runs/ml/lending/src/summary.py`, `pyproject.toml`, and `.gitignore`.

**Scope: credit only (galactus#36).** Fraud (galactus#34) is deliberately unplanned — F2's
missing label horizon is an operator decision, not a research gap, and planning fraud before
that decision would encode the contradiction the research names.

### Goal

Bring `runs/ml/credit/` to lending's structural bar on a licensed, horizon-stated frame —
`frame.py` + `tests/` + persisted `summary.json` — so credit stops being a demonstration
against 14 positives and becomes a run whose result can be read.

### Open Questions

Resolved in the planning interview (2026-08-18), each recorded with what was given up:

1. **Goal — RESOLVED: structural parity with lending.** Not "unblock the threshold" and not
   "prove the sourcing standard," though both follow. This orders the steps: the frame swap
   serves the scaffolding, so `frame.py` is authored as a peer of `runs/ml/lending/src/frame.py`
   rather than as edits inside `run.py`.
2. **Scope — RESOLVED: loader + horizon + leakage list, F6 quirks, tests + summary.json.**
   Download script explicitly excluded (see Q6).
3. **Stand-in — RESOLVED: leave both, add alongside.** UCI enters as a second frame; the
   lebanese-blonde stand-in is neither archived nor removed this plan. Gave up: the design's
   §Deliverables line "Archive the lebanese-blonde frame … remove all modelling references"
   stays open. **This plan does not close that design deliverable** — recorded here so review
   does not read parity as completeness.
4. **Notebook — RESOLVED (follows from Q3): `notebooks/eda.py` is not remapped.** It stays
   written for the 43-column stand-in and becomes knowingly stale against the default frame.
   Step 6 adds the flag rather than the fix. Gave up: the README's claim that the notebook's
   column view and `run.py`'s "cannot drift apart" — after this plan they can, and do.
5. **Branch — RESOLVED: continue on `GAL-34-fraud-parity`.** Operator's call, made with the
   mixing known. Consequence recorded rather than smoothed: credit (#36) and fraud (#34) share
   one branch and one PR, so `Closes #36` must be explicit in the PR body or the issue silently
   survives the merge. Not a blocker; a thing to not forget.
6. **Default frame — RESOLVED: UCI is the default, stand-in is `--frame standin`.** Without
   this, `summary.json` would describe 800 rows and 14 positives — the "arithmetic about three
   rows" result the design exists to retire.

Open, and **not** decided by this plan:

7. **The UCI CSV is not obtainable by a scripted step in this plan** (Q2 excluded the download
   script) and `*.csv` is gitignored at [.gitignore:50](.gitignore#L50), so a fresh clone has
   neither frame. Step 1 captures provenance as constants and makes the error message name the
   exact URL; fetching stays a documented one-liner. **Assumed default:** acceptable, because
   lending has the same property today ([frame.py:178-182](runs/ml/lending/src/frame.py#L178-L182)
   raises `SystemExit` pointing at DESIGN.md). If review disagrees, the fix is one step, not a
   re-plan.
8. **`COST_FP`/`COST_FN` stay `None`.** The horizon unblocks the threshold *at the source*, but
   the cost **ratio** is still un-given — F1 resolves the window, not the economics. `run.py`
   keeps reporting no threshold. **Assumed default:** unchanged. Naming a ratio here would be
   lending's stipulated 4:1 borrowed without the operator's word, which is exactly the move
   [frame.py:106-115](runs/ml/lending/src/frame.py#L106-L115) documents as a guess.
9. **Gate 1b (`GROUP_COL`/`TIME_COL`) stays unresolved.** UCI is one row per account with no
   subject recurrence and no date column, so stratified k-fold is defensible here — but that is
   an argument, not a source statement. **Assumed default:** keep both `None`, and narrow the
   provisional-split warning to say why it is now *low-risk* rather than merely unresolved.

### Approach

Author `runs/ml/credit/src/frame.py` as the single home for every UCI decision — target,
horizon, leakage list, the F6 quirk handling — mirroring `runs/ml/lending/src/frame.py` so the
two runs can be diffed. `run.py` keeps its interview-decisions role and gains a `--frame`
switch that selects between the UCI frame and the stand-in loader it has today. Tests land in a
new `runs/ml/credit/tests/` registered in `testpaths`, driven by synthetic fixtures so they run
without the gitignored CSV. **The central tradeoff:** the leakage list is authored *fresh*
against UCI's schema rather than ported from lending (research Key Unknown 5) — which means it
is an argument from the horizon, not an inherited artifact, and Step 3 writes that argument down
where review can attack it.

### Out of Scope

- **All fraud work** (galactus#34) — blocked on F2's horizon decision. No edits to
  `runs/ml/fraud/**`, including `sufficiency.py`, its 35 tests, `README.md`, or `WALKTHROUGH.md`.
- **`runs/ml/fraud/docs/DESIGN.md`** — pre-registration, out of scope by standing instruction.
- **A download script** (Q2) — provenance constants and a documented URL only.
- **Archiving or deleting the lebanese-blonde stand-in** (Q3) — it stays runnable.
- **Remapping `notebooks/eda.py` to UCI's 23 columns** (Q4) — flagged stale, not fixed.
- **`runs/ml/lending/**`** — the design's quality bar; no gap to close.
- **Setting a cost ratio or resolving gate 1b** (Q8, Q9).
- **The `runs/_index/` run record** — galactus consumes `ai-project-template`'s registry and
  does not define the record shape; `summary.json` under the run's own `docs/` is this plan's
  target, matching lending.
- **Committing.** Execute stages changes; Ramsey commits.

### Steps

#### Step 1: Author `frame.py` — provenance, horizon, and the UCI schema map

**Files**: `runs/ml/credit/src/frame.py` (new, ~120 lines)

**What**: Create the decisions-as-code module. Provenance constants first (license, DOI,
citation, URL, horizon), because F6 records that UCI's API returns `null` for `license` and
`dataset_doi` — they exist only in page HTML, so they are hardcoded *with* their source noted
rather than fetched. `HORIZON` cites the variables table, not the abstract (F1's nuance), and
records the concrete meaning: features span April–September 2005, so "next month" = October 2005.
The `X1..X23` → friendly-name map lives here since the CSV header is cryptic and the map exists
only in the `.xls` second header row / API metadata.

**Snippet**:
```python
# after — runs/ml/credit/src/frame.py
SOURCE_URL = "https://archive.ics.uci.edu/static/public/350/data.csv"  # CSV, 2.9 MB
LICENSE = "CC BY 4.0"        # from the dataset page HTML; the API's `license` field is null
DOI = "10.24432/C55S3H"      # likewise page-only — the API's `dataset_doi` is null
CITATION = "Yeh, I-C. (2009). Default of Credit Card Clients. UCI ML Repository."

#: Source-stated, from UCI's *variables table* (not the prose block, which states no
#: horizon). Features cover Apr–Sep 2005, so "next month" is concretely October 2005.
HORIZON = "one month"
HORIZON_SOURCE = "UCI variables table for column Y ('default payment next month')"

TARGET = "Y"                 # the column *name*; "default payment next month" is its description
COLUMN_NAMES = {"X1": "LIMIT_BAL", "X2": "SEX", "X3": "EDUCATION", "X4": "MARRIAGE",
                "X5": "AGE", "X6": "PAY_0", "X7": "PAY_2", ...}  # note: no PAY_1 (F6)
```

**Test**: `cd ~/workspace/galactus && uv run python -c "import sys; sys.path.insert(0,'runs/ml/credit/src'); import frame; print(frame.HORIZON, frame.LICENSE, len(frame.COLUMN_NAMES))"`

**Done when**: prints `one month CC BY 4.0 23`, and `frame.py` imports with no dependency on
`ml.*` (toolkit-free, like lending's — so tests run without `ML_PACKAGE_ROOT`).

#### Step 2: Encode the F6 quirks as explicit, recorded decisions

**Files**: `runs/ml/credit/src/frame.py` (extend)

**What**: The undocumented codes are the highest-consequence finding in F6 and the least
discussed — `PAY_0`/`PAY_2..6` document a scale starting at `-1` but the data holds `-2`
(n=2,759) and `0` (n=14,737), ~58% of rows in codes the source never defines. The decision this
plan makes: **treat `PAY_*` as ordinal and keep the undocumented codes as their own levels** —
do not remap them to `-1`, and do not drop the rows. Collapsing 58% of the data into a
documented bucket would be inventing a meaning the source does not supply. Same posture for
`EDUCATION` (0/5/6, n=345) and `MARRIAGE` (0, n=54): keep, label `unknown`, never silently fold
into the documented levels. The 35 duplicate rows are dropped with a logged count, because a
duplicated row across a fold boundary is the same account on both sides of the split.

**Snippet**:
```python
# after
#: Documented as starting at -1 ("pay duly"); the data also holds -2 and 0, ~58% of rows,
#: in codes UCI never defines. Kept as distinct ordinal levels — remapping them to -1 would
#: assert a meaning the source does not state. F6.
PAY_COLUMNS = ["PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]  # no PAY_1
UNDOCUMENTED_PAY_CODES = {-2, 0}
UNDOCUMENTED_EDUCATION_CODES = {0, 5, 6}
UNDOCUMENTED_MARRIAGE_CODES = {0}

def prepare_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=COLUMN_NAMES)
    n_dupes = int(df.drop(columns=["ID"], errors="ignore").duplicated().sum())
    df = df.drop_duplicates(subset=[c for c in df.columns if c != "ID"])
    logger.info("dropped %d duplicate rows (excluding ID)", n_dupes)
    ...
```

**Test**: authored here, not in Step 5 — a "done when" cannot be checked by a test that does not
exist yet. Create `runs/ml/credit/tests/` with `conftest.py` and this first test now, and add the
`testpaths` line from Step 5 **in this step** so it does not collect zero:
`cd ~/workspace/galactus && uv run pytest "runs/ml/credit/tests/test_frame.py::test_undocumented_codes_survive_preparation" -v`
Step 5 then extends the directory rather than creating it.

**Done when**: `prepare_frame` on a fixture containing `PAY_0 ∈ {-2, -1, 0, 1}` returns all four
levels intact, and a fixture with 3 duplicate rows logs `dropped 3 duplicate rows`.

#### Step 3: Author the leakage exclusion list fresh, with its argument

**Files**: `runs/ml/credit/src/frame.py` (extend)

**What**: Research Key Unknown 2 names credit's leakage check **red** — today
[run.py:70](runs/ml/credit/src/run.py#L70) has `ID_COLS = ["uuid"]` and nothing else. Key Unknown
5 leans *fresh* over ported, because UCI's `X*` schema shares no column names with lending —
porting would be renaming, not reuse. The columns at issue are `BILL_AMT1`, `PAY_AMT1`, and
`PAY_0`, all dated September 2005, the month immediately before the October label.

The argument, written into the module because it is the whole basis of the decision: these are
legitimate features **if and only if** the operating story is "predict next month from this
month." UCI's stated one-month horizon (Step 1) is exactly that story — so under this frame's
own horizon they are *pre-outcome* and stay in. This is a decision that depends on the horizon,
which is why it could not be made before F1 confirmed it. `ID` is dropped as an identifier.

**Snippet**:
```python
# after
#: Empty, and that is the finding — not an oversight. Under UCI's stated one-month horizon
#: (see HORIZON), the September-2005 columns BILL_AMT1 / PAY_AMT1 / PAY_0 are the *inputs*
#: to an October-2005 label, not post-outcome records. They leak only if the operating story
#: changes. If HORIZON is ever restated, revisit this list first.
LEAKAGE_COLUMNS: list[str] = []

#: Row identifier. Never a feature.
IDENTIFIER_COLUMNS = ["ID"]

#: Named so the claim is falsifiable rather than implicit: these were *considered* and kept.
CONSIDERED_AND_KEPT = ["BILL_AMT1", "PAY_AMT1", "PAY_0"]
```

**Test**: `cd ~/workspace/galactus && uv run pytest "runs/ml/credit/tests/test_frame.py::test_identifier_dropped_and_considered_columns_kept" -v`

**Done when**: `prepare_frame` output contains `BILL_AMT1`, `PAY_AMT1`, `PAY_0` and does **not**
contain `ID`; the docstring states the horizon dependency.

#### Step 4: Repoint `run.py` — `--frame`, horizon, and the retired blocker line

**Files**: `runs/ml/credit/src/run.py` (lines 20, 63-70, 93-112, 115-132, 208-216)

**What**: Add `--frame {uci,standin}` defaulting to `uci` (Q6). UCI routes through
`frame.load_frame`; `standin` keeps today's semicolon-delimited path unchanged so the old
artifacts stay reproducible (Q3). Then retire the three stale assertions: the module docstring's
`label horizon … BLOCKING` (line 20), the `FileNotFoundError` recovery text that names only
lebanese-blonde (lines 100-104), and `report`'s closing
`label horizon: UNDEFINED — blocking for any shipped decision rule` (line 216) — **the single
line this whole plan exists to delete.** Narrow the provisional-split warning per Q9.

**Snippet**:
```python
# before — run.py:216
print("label horizon: UNDEFINED — blocking for any shipped decision rule.")

# after
print(f"label horizon: {frame.HORIZON} — stated by the source ({frame.HORIZON_SOURCE}).")
print(f"               license {frame.LICENSE}, DOI {frame.DOI}.")
```

**Test**: `cd ~/workspace/galactus && uv run python runs/ml/credit/src/run.py --models logistic --n-splits 5 2>&1 | tail -20`
(requires the CSV at `runs/ml/credit/data/uci_default_of_credit_card_clients.csv`; see Q7)

**Done when**: the run logs `frame: 29965 rows x 24 cols` (30,000 less the 35 duplicates),
`positives: 6631` at ~22.1%, prints the horizon line above, prints **no** `UNDEFINED` and no
`FEW POSITIVES PER FOLD` warning, and `--frame standin` still reproduces the 800-row output.

#### Step 5: Complete the test suite

**Files**: `runs/ml/credit/tests/test_frame.py` (extend — created in Step 2),
`runs/ml/credit/tests/test_run.py` (new), `pyproject.toml` (verify the Step 2 `testpaths` line)

**What**: Step 2 created the directory, its first test, and the `testpaths` registration; this
step completes coverage. Synthetic fixtures only — no gitignored CSV, so the suite runs on a
fresh clone. Add the provenance test (horizon constants non-empty — the cheapest guard against a
future edit quietly re-emptying the field that unblocked the run), the `--frame standin`
routing test, and a summary-shape test asserting no per-row field escapes into `summary.json`.
Re-verify the `testpaths` entry is present: CLAUDE.md records that an unregistered test dir
collects **zero tests, which reads exactly like passing**.

**Snippet**:
```toml
# before — pyproject.toml
    "runs/ml/lending/tests",
    "experiments/tests",

# after
    "runs/ml/lending/tests",
    "runs/ml/credit/tests",
    "experiments/tests",
```

**Test**: `cd ~/workspace/galactus && uv run pytest runs/ml/credit/tests -v`

**Done when**: the new tests pass **and** the count is non-zero in the collection line — and
`uv run pytest --tb=no -q` reports ≥ 624 passed (the baseline measured 2026-08-18) with no
regressions elsewhere.

#### Step 6: Persist `summary.json`; update README and the stale-notebook flag

**Files**: `runs/ml/credit/src/summary.py` (new), `runs/ml/credit/src/run.py` (report path),
`runs/ml/credit/README.md` (lines 8-30, 35-38, 48-50)

**What**: Port lending's `summarise` shape ([summary.py:14-79](runs/ml/lending/src/summary.py#L14-L79))
— aggregates only, never a row, an index, or an identifier — writing
`runs/ml/credit/docs/summary.json`. This takes `summary.json` coverage from 1/3 to 2/3 (F5).
Add the frame's provenance block (license, DOI, horizon, source URL) so the persisted result
carries the citation, and — per F4's caveat that "summary.json is unbounded as a spec" — bound
it explicitly to aggregates. README: replace the 800×43 data table with UCI's numbers, name the
one-month horizon, document `--frame`, and flag that `notebooks/eda.py` is written for the
stand-in and **no longer matches the default frame** (Q4), correcting the current "cannot drift
apart" claim at [README.md:48-50](runs/ml/credit/README.md#L48-L50).

**Snippet**:
```python
# after — credit's summary gains what lending's does not need
summary["frame"] = {
    "source": frame.SOURCE_URL, "license": frame.LICENSE, "doi": frame.DOI,
    "citation": frame.CITATION,
    "label_horizon": frame.HORIZON, "horizon_source": frame.HORIZON_SOURCE,
}
# Aggregates only. Outputs fine-grained enough to reconstruct row-level values would edge
# toward a "Substantial part of the Contents"; standard metrics are nowhere near that line.
```

**Test**: `cd ~/workspace/galactus && uv run python runs/ml/credit/src/run.py --models logistic && uv run python -c "import json; d=json.load(open('runs/ml/credit/docs/summary.json')); print(d['frame']['label_horizon'], d['n_rows'])"`

**Done when**: prints `one month 29965`; `summary.json` contains no per-row field; README's data
table matches the run's logged numbers; and `grep -rn "UNDEFINED" runs/ml/credit/` returns
nothing.

### Test Plan

| Level | Command | Asserts |
|---|---|---|
| Unit | `uv run pytest runs/ml/credit/tests -v` | F6 quirks preserved, `ID` dropped, considered-columns kept, provenance non-empty |
| Regression | `uv run pytest --tb=no -q` | ≥ 624 passed, 14 skipped — the 2026-08-18 baseline, no collateral damage |
| Integration | `uv run python runs/ml/credit/src/run.py --models logistic` | 29,965 rows, 6,631 positives, ~22.1%, no few-positives warning |
| Reproducibility | `uv run python runs/ml/credit/src/run.py --frame standin` | old 800-row path unchanged (Q3) |
| Doc parity | `grep -rn "UNDEFINED" runs/ml/credit/` | empty — the blocker is gone from code *and* docs |

**Baseline named before computing** (research Key Unknown 1, the ml-track contract): majority-class
accuracy **77.88%**, PR-AUC prevalence floor **0.2212**. Any credit model is read against 0.2212,
not 0.5. A logistic PR-AUC of ~0.30 is a real finding; ~0.22 is the prevalence restated.

### Risks & Rollback

| Risk | Likelihood | Mitigation | Rollback |
|---|---|---|---|
| The 35-duplicate drop changes row count from the research's 30,000, so "prevalence 22.12%" no longer matches the logged number | High — it *will* differ (29,965 / 6,631 ≈ 22.13%) | Steps 4/6 state post-dedup numbers explicitly; both are recorded so neither reads as an error | None needed — expected, not a defect |
| `run.py`'s `sys.path` surgery ([run.py:36-55](runs/ml/credit/src/run.py#L36-L55)) breaks when `frame.py` becomes a sibling import | Medium — `_HERE` is *removed* from `sys.path`, so `import frame` fails exactly as lending's does not | Lending solves this already ([summary.py:11](runs/ml/lending/src/summary.py#L11) does `from frame import ...`); mirror its import order — re-add `_HERE` after the `ml` root | Revert Step 4; Steps 1-3 stand alone |
| Leakage list is empty (Step 3) and review reads that as the check not being done | Medium | `CONSIDERED_AND_KEPT` + the horizon-dependency docstring make it an argued decision, not an omission; `review-leakage` is the dimension that should attack it | Populate the list if the horizon story is rejected — one constant |
| Notebook drift (Q4) is a knowing regression against the README's own claim | High — by construction | Step 6 flags it in the README | Out of scope to fix; carried openly |
| Credit and fraud share a branch (Q5), so `Closes #36` may be lost | Medium | Recorded in Q5; PR body must name both issues | — |

**Rollback overall**: every step is additive except Step 4's edits to `run.py` and Step 5's
one-line `pyproject.toml` change. `git checkout runs/ml/credit/src/run.py pyproject.toml` plus
deleting the new files restores the current state; no data migration, no external state.

### Open Questions

Carried forward for the reviewer (the resolved set is at the top of this plan):

- **Q7 — the UCI CSV is not fetchable by any step here.** Assumed acceptable; one step to fix if not.
- **Q8 — cost ratio still `None`**, so no threshold is reported even now that the horizon is stated.
- **Q9 — gate 1b stays unresolved**; stratified k-fold is argued as low-risk on UCI, not source-confirmed.
- **The design's "archive the stand-in" deliverable is not closed by this plan** (Q3) — it needs
  its own work item, or an explicit decision that it is dropped.
- **Fraud (galactus#34) remains blocked** on F2. Nothing here advances it, and nothing here
  depends on it.
