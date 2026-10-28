# System Design — ml-frame-sourcing

**Date:** 2026-08-18
**Status:** Draft
**Scope:** frame sourcing for `runs/ml/{credit,fraud,lending}`
**Supersedes (sourcing only):** `runs/ml/fraud/docs/DESIGN.md` §sourcing. That document
remains the GAL-23 HITL-gradient pre-registration and is **not edited here** — see
[What this does to fraud's pre-registration](#what-this-does-to-frauds-pre-registration).

---

## Problem + Success Criteria

Three ML runs claim to demonstrate different things about honest modelling. Two of them
are reading the same 800 rows.

`runs/ml/credit/data/credit_default.csv` and `runs/ml/fraud/data/dataset.csv` are the same
file under two names — the 800-row, 43-column, semicolon-delimited `lebanese-blonde`
sample, 14 positives, 1.75% prevalence. Verified by reading both loaders
(`credit/src/run.py:63`, `fraud/src/run.py:55`) and by counting the CSV directly. Only
`lending` has a frame of its own.

That frame fails all three sourcing constraints simultaneously: **no stated license**, **no
stated label horizon**, and **prevalence far too thin to support a threshold**.

**POC demo target:** each run demonstrates something the other two cannot, on a frame whose
license, label horizon, and prevalence are all stated and checkable.

**Naive baseline:** keep the stand-in and narrow every claim to "mechanics only." Cheap and
honest, but it leaves two runs demonstrating the same thing on the same rows, and leaves
real records about identifiable people inside the repo.

---

## The evidence that 800 rows cannot produce a result

Recorded because it is the load-bearing fact for every decision below, and it is measured
rather than asserted.

| Signal | Value | Source |
|---|---|---|
| Positives | **14 / 800 (1.75%)** | counted from the CSV |
| Positives per fold @ 5-fold | **~2.8** (measured min: **2**) | `fraud/docs/summary.json` |
| Threshold the toolkit produced | **0.0562** | `fraud/src/sufficiency.py:29-39` |
| Precision / recall at that threshold | **0.000 / 0.000** | same |
| True positives at that threshold | **0** | same |
| Warning emitted | **none** | same |
| Credit PR-AUC vs prevalence floor | within **0.003** of floor | `fraud/README.md:29-38` |

A model scored against ~3 events per fold, landing within 0.003 of the base rate, is not a
weak result — it is arithmetic about three rows. The operator's read ("the 800 isn't enough
to have any real results") is confirmed by the run's own captured artifacts.

---

## Actors

| Actor | Type | What they do today | What the change does for them |
|---|---|---|---|
| Operator (Ramsey) | internal | Reads run docs to judge whether a modelling claim is trustworthy | Gets three runs whose frames are licensed, horizon-stated, and prevalence-sufficient |
| Reviewer / future volunteer | internal | Clones galactus, cannot obtain the frames, cannot reproduce any number | Gets publicly downloadable frames with citations |
| `review-leakage` dimension | system | Reads run code for leakage | Gets an explicit exclusion list in credit, which currently has none |
| Data subjects in `lebanese-blonde` | external | Real people whose records sit in a gitignored CSV | Their records leave the modelling path entirely |

---

## Sourcing standard

Operator standard, stated 2026-08-18: **1. Kaggle/public if available, 2. synthetic if
not.** Applied per run below.

A frame is "available" only if all three constraints can be satisfied *from the source*:

| Constraint | Test |
|---|---|
| **License** | Named, permissive, and citable. Unstated license = unavailable. |
| **Stated label horizon** | The source defines what the label means over what window. Inferred horizon = unavailable. |
| **Prevalence sufficient for a threshold** | Thinnest test fold ≥ 10 positives, the floor already encoded at `fraud/src/sufficiency.py:29`. |

---

## Per-run decisions

### credit → UCI Default of Credit Card Clients

**Verified at source** (`archive.ics.uci.edu/dataset/350`):

| Property | Value |
|---|---|
| License | **CC BY 4.0** (verbatim on the dataset page) |
| Rows × features | **30,000 × 23** |
| Target | `default payment next month` (Yes = 1, No = 0) |
| **Stated horizon** | **one month** — stated by the source, not inferred |
| Coverage | April–September 2005, Taiwan |
| Citation | Yeh, I. (2009). UCI ML Repository. https://doi.org/10.24432/C55S3H |
| Prevalence | ~22.1% (6,636/30,000) — **confirm on download**, not stated on the page |

At ~22% over 30k rows, the thinnest 5-fold test fold holds ~1,327 positives — three orders
of magnitude above the floor. A threshold is supportable.

**This closes credit's blocking gap.** `credit/src/run.py:20,216` currently prints
`label horizon: UNDEFINED — blocking for any shipped decision rule`. The UCI target is
defined at a stated one-month horizon, so the blocker resolves at the source rather than
by stipulation.

**Note on prevalence:** credit's own README targeted a 90k-customer extract at **1.4%**
default. That is *lower* than UCI's 22%. The goal for credit is therefore **volume, not
balance** — 1.4% × 90k = 1,260 positives would also clear the floor. UCI is chosen because
it is licensed, horizon-stated, and downloadable without an account; a low-prevalence
high-volume alternative would also satisfy the standard.

### fraud → Kaggle `mlg-ulb/creditcardfraud`

**Operator decision, 2026-08-18, reaffirmed after the cost was stated:** fraud gets real
data and the guard demo retires.

| Property | Value |
|---|---|
| License | **ODbL** (Open Database License) — attribution + share-alike |
| Rows | **284,807** |
| Positives | **492 (0.172%)** |
| Features | 28 PCA components + `Time` + `Amount` |
| Provenance | Worldline / ULB Machine Learning Group |
| Citation | Dal Pozzolo et al. (2015), *Calibrating Probability with Undersampling for Unbalanced Classification* |

**The guard passes on this frame, and that is the point of the change.** 492 positives over
5 folds is ~98 per fold, comfortably above the floor of 10. `assess_sufficiency` returns
`sufficient=True`, no refusal banner renders, and fraud reports a real operating point for
the first time.

Fraud is genuinely low-prevalence (0.172%, thinner than the stand-in's 1.75%) while having
enough absolute positives to support a threshold. That is the honest version of what fraud
was gesturing at: **imbalance is not the same problem as insufficiency**, and this frame
separates them.

### lending → unchanged

Already satisfies all three constraints and needs no sourcing work.

| Property | Value |
|---|---|
| License | **CC0-1.0**, `codesignal/lending-club-loan-accepted` |
| Rows | 45,224 → **39,770** resolved |
| Target | `charged_off`, derived from `loan_status` |
| Horizon | loan-lifetime, **stated and explicitly distinguished** from the client's |
| Prevalence | **20.56%** (8,177/39,770) |

Verified against the CSV on disk: the label table reproduces row-for-row. Lending's
`DESIGN.md` is the quality bar the other two runs are being brought up to.

---

## What this does to fraud's pre-registration

Stated plainly because it is the real cost of the decision, and the operator accepted it
after it was raised twice.

`runs/ml/fraud/docs/DESIGN.md` is the GAL-23 HITL-gradient trail: a **pre-registration**
document with three arms (L1, L2, L3) measured against it, whose own rules forbid
post-hoc amendment ("amending it after seeing one arm is precisely what pre-registration
forbids").

**What is lost:** the *demonstrated run outcome*. Fraud's README titles itself "a refusal,
not a metric"; `WALKTHROUGH.md:17` fixes the pass condition as "the run declined to report
an operating point." On the new frame the guard passes, so the refusal is no longer
something the run *does*.

**What survives:** the guard code and all of its coverage. `sufficiency.py` is unchanged,
its 6 direct tests still pass — including `test_accepts_a_healthy_frame`, which exists
precisely so the guard is falsifiable rather than a constant `False`. The refusal becomes
a **unit-test-level fact** rather than a run outcome. `docs/before-guard.json` and
`docs/summary.json` are committed artifacts and preserve the measured evidence
permanently.

**What this costs the gradient:** the HITL gradient loses its only remaining live subject.
L4 was already blocked on GAL-27, and all three run arms terminated at the toolkit-import
guard before reaching the model run. Re-framing fraud retires the trail as a *live
instrument*; it stands as history.

**This document does not edit that file.** It records a sourcing decision that supersedes
its sourcing assumptions, and leaves the pre-registration intact — the same discipline the
document applies to itself.

---

## Retirement of the lebanese-blonde frame

**Operator decision:** *keep as a documented historical reference.*

- The frame is **removed from every modelling path** — no run loads it after this change.
- It is **retained, archived, and provenance-noted** so the `before-guard` artifacts
  remain reproducible and the audit trail survives.
- `~/workspace/lebanese-blonde` is untouched: separate repo, read-only, the operator's own
  2020 work.
- The retained copy stays gitignored. `.gitignore:32` describes it as "personal financial
  information about identifiable people" — that characterization is why it leaves the
  modelling path, and why the archived copy is never committed.

**Recorded tension:** retention keeps real records inside the galactus tree. The exposure
is bounded (gitignored, never committed, no code path reads it) but it is not zero. The
alternative — deleting the local copy — was offered and not taken; recorded so the choice
is visible rather than implicit.

---

## MVP Scope

**In:**

- Download scripts + documented provenance for the UCI credit frame and the Kaggle fraud frame
- Credit: repoint the loader, set the label horizon to the stated one-month definition, add a leakage exclusion list
- Fraud: repoint the loader; guard stays in code and now passes; report renders no refusal banner
- Archive the lebanese-blonde frame with a provenance note; remove all modelling references
- Both runs persist a `summary.json` (neither does today)

**Out (explicitly):**

- Editing `runs/ml/fraud/docs/DESIGN.md` — pre-registration, superseded for sourcing only
- Changing `MIN_POSITIVES_PER_FOLD` or any guard logic — the guard is correct; only the frame changes
- Any change to `runs/ml/lending/` beyond leaving it alone
- Resolving lending's `DESIGN.md` vs `WALKTHROUGH.md` metric contradiction (separate issue)
- ~~Completing the `pocs/ml/credit → runs/ml/credit` rename~~ — done 2026-08-18, ahead of this pass; see Open Questions
- `runs/ml/customer segmentation/` — not in scope for this pass

**Open (decide before sprint 1):**

- Whether credit's leakage exclusion list is authored fresh for UCI's 23 columns or ported from lending's pattern

---

## Key Decisions

| Decision | Status | Choice | Rationale (chose X over Y, gave up Z) |
|---|---|---|---|
| Sourcing standard | Resolved | Kaggle/public first, synthetic only if unavailable | Operator standard. Chose over per-run improvisation, which produced two runs sharing one unlicensed frame. Gave up: synthetic's total reproducibility |
| credit frame | Resolved | UCI Default of Credit Card Clients (CC BY 4.0) | Chose over synthetic and over the 90k extract credit's README named. UCI is licensed, **horizon-stated**, account-free. Gave up: the 1.4%-prevalence realism of the original target |
| fraud frame | Resolved | Kaggle `mlg-ulb/creditcardfraud` (ODbL) | **Operator decision, reaffirmed.** Chose over synthetic-at-matched-thinness, which would have kept the refusal demo. Gave up: the demonstrated refusal, and fraud's role as the HITL gradient's live subject |
| fraud guard code | Resolved | Keep unchanged; it now passes | Chose over deleting it. `test_accepts_a_healthy_frame` already covers the passing branch. Gave up: nothing — the guard is correct, only its verdict changes |
| lebanese-blonde disposition | Resolved | Archive as documented historical reference | **Operator decision.** Chose over deleting the local copy. Preserves `before-guard` reproducibility. Gave up: full removal of real records from the tree |
| lending | Resolved | Unchanged | Already satisfies all three constraints. No alternative considered — there is no gap to close |
| fraud's DESIGN.md | Resolved | Not edited; superseded for sourcing only | Chose over rewriting it to match the new frame. Pre-registration that is rewritten after the fact stops being evidence. Gave up: a single self-consistent fraud doc |

---

## Open Questions

- ~~**UCI prevalence unconfirmed at source**~~ — **CLOSED 2026-08-18** by `/proto-research`. Downloaded `archive.ics.uci.edu/static/public/350/data.csv` and counted: **6,636/30,000 = 22.12%**. Confirmed still not stated on the dataset page — the figure is download-verified, not source-stated, and should be cited that way.
- ~~**ODbL share-alike obligations for derived artifacts**~~ — **CLOSED 2026-08-18** by `/proto-research`, in this design's favour. ODbL §4.5(b) exempts a **Produced Work** from §4.4 share-alike by name; a metrics report / `summary.json` is a Produced Work, owing only an attribution notice (§4.3). Share-alike attaches only to a **Derivative Database** — a committed CSV, resampled copy, or per-row artifact. **Conditional on the license actually being ODbL, which is now itself an open question (below).**
- **Fraud's license is unverified** — Kaggle renders the license client-side and the public API needs auth; six attempts failed. ODbL is **not established**, and Kaggle also offers DbCL and CC0 — a distinction that changes the analysis above. _revisit:_ before relying on the ODbL analysis. _close via:_ loading the dataset page by hand, or authenticated `kaggle datasets metadata mlg-ulb/creditcardfraud`.
- **Fraud's frame has no stated label horizon — blocking under this document's own standard.** `Class=1` is defined ("1 in case of fraud") but never scoped to an adjudication window; `Time`'s ~2-day span is the *sampling* window, not the labeling one, and is routinely misread as the horizon. The source forecloses recovery ("we cannot provide … more background information"). Under §Sourcing standard, an inferred horizon means **unavailable** — so the frame chosen for fraud fails the same test that was the decisive argument for credit's. _revisit:_ **now, before any fraud planning.** _close via:_ operator decision — narrow the standard (adopt, record horizon as unknown, Evaluation target drops to 2/3) or hold it (source a frame publishing its labeling protocol, or exercise the unused "2. synthetic" half of the standard).
- ~~**Credit's tracked path is stale**~~ — **CLOSED 2026-08-18.** All four tracked files (`README.md`, `src/run.py`, `notebooks/eda.py`, `notebooks/01-eda.ipynb`) were restored from `HEAD` and `git mv`d to `runs/ml/credit/`, recorded as renames so history follows. Stale `pocs/` references repaired in `run.py` (incl. the load-bearing `parents[4]` namespace-package comment) and `eda.py`; both verified to import at the new path. The README's Layout block also mis-stated `src/eda.py` — corrected to `notebooks/eda.py`, which is where the notebook's bare `import eda` actually resolves.
- **Does the HITL gradient get a new subject?** Retiring fraud's refusal leaves the gradient without a live target. _revisit:_ when GAL-27 lands and L4 becomes runnable. _close via:_ operator decision — a different run, or accept the gradient as closed at three arms.

---

## Evaluation

| Metric | Target | How measured |
|---|---|---|
| Frames with a stated license | **3 / 3** | Each run's DESIGN/README names license + citation |
| Frames with a stated label horizon | **3 / 3** — ⚠️ **unachievable as scoped**; see Open Questions. The Kaggle fraud frame states no horizon and the source refuses to supply one, capping this at **2 / 3** unless fraud's frame changes | Credit's `UNDEFINED — blocking` line is gone; horizon cited to source |
| Runs whose thinnest fold clears the floor | **3 / 3** | `assess_sufficiency` reports `sufficient=True` |
| Credit leakage exclusions | **> 0**, explicit in code | Exclusion list exists; `has_paid` / `recovery_debt` no longer applicable post-frame-swap |
| Runs persisting `summary.json` | **3 / 3** | File exists after a run; currently 1/3 (fraud only) |
| Real records on the modelling path | **0** | No loader resolves to the archived frame |

Derived from the risks below: rows 3 and 4 are the leakage/insufficiency risks, row 6 is
the PII risk, and row 1 is the baseline-justifying margin (an unlicensed frame is the
"do nothing" state).

---

## What Breaks First

- **The download step.** Both new frames need a fetch that a fresh clone can run. Kaggle's
  requires an account/API token; UCI's does not. Failure looks like a run that cannot
  start — `loud-surface`, the good kind. Cheap mitigation: a documented fetch script with
  a clear error, in POC scope.
- **Credit's leakage exclusions, silently.** Credit has **no exclusion list at all** today
  and the notebook's `recovery_debt` exclusion is commented out. Swapping frames does not
  create one. Failure looks like a confident high AUC — `silent-verdict`, the dangerous
  kind. Mitigation: author the list with the frame swap, and dispatch `review-leakage`. In
  scope.
- **Nobody notices fraud stopped refusing.** The report simply renders no banner. Anyone
  reading fraud's README still sees "a refusal, not a metric" against a run that now
  reports one. Mitigation: update fraud's README and WALKTHROUGH in the same change — a
  doc-parity failure, and the reason this is called out here.

---

## Non-Functional Constraints

- **Data classification:** archived frame — **restricted** (real records, gitignored,
  never committed, off the modelling path). New frames — **public** (CC BY 4.0 / ODbL).
- **Multi-tenancy:** not required.
- **Operator model:** single operator; free-tier only. UCI is account-free; Kaggle needs a
  free account.
- **Scale:** 285k × 31 (fraud) is the largest frame; fits in memory, fits CI.
- **Observability:** every run persists a `summary.json` carrying license, citation, row
  count, prevalence, and the sufficiency verdict — so a reader never infers a frame's
  provenance from prose.

---

## Handoff to /proto-design

| This design settled | Feeds |
|---|---|
| Three licensed frames with stated horizons | the context layer — what may enter a model at all |
| Guard stays, verdict flips to pass | the harness layer — refusal remains reachable, now test-covered |
| Archive-not-delete for the real frame | data-classification boundary |
| `summary.json` in all three runs | the metric surface `/proto-design` closes on |
| Credit's missing exclusion list | first real work item — it is a `silent-verdict` gap |

Deferred items carry their triggers across unchanged.
