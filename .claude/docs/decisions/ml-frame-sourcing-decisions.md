# Decision record — ml-frame-sourcing

**Date:** 2026-08-18
**Skill:** `/proto-scope` (design mode)
**Design:** [`DESIGN-ml-frame-sourcing.md`](../DESIGN-ml-frame-sourcing.md)

Every decision settled in this interview, with the answer proposed, what the operator
did with it, and how cheaply it reverses. Recorded so the propose-and-confirm routing is
auditable — a reviewer can dispute a reversibility claim.

**Note on the spec:** `/proto-scope` Step 5.5 cites
`.claude/specs/decision-record-shape.md`, which does not exist in this repo, and
`.claude/docs/decisions/` did not exist either (created here). This record follows the
shape the skill describes inline. Flagged rather than silently improvised.

---

## Reversibility classes

| Class | Meaning |
|---|---|
| **Trivial** | Rerun, delete, or edit a line |
| **Costly** | Reversible, but work is lost or an external commitment is touched |
| **Irreversible** | Cannot be undone — data deletion, external write, destroyed evidence |

---

## Decisions

| # | Decision | Proposed default | Outcome | Reversibility | Notes |
|---|---|---|---|---|---|
| 1 | Sourcing standard | Per-run judgment | **Overridden** → "Kaggle if available, synthetic if not" | Trivial | Operator supplied a general standard rather than answering per-run. Now the rule the other decisions are derived from |
| 2 | credit frame | Real Kaggle credit dataset (UCI Taiwan) | **Confirmed** | Costly | Frame swap invalidates any prior credit number. No prior numbers exist — the run persists nothing — so the cost is near zero today |
| 3 | credit label horizon | — (blocked; `UNDEFINED` in code) | **Resolved as a consequence** — UCI states one month | Trivial | Not asked separately; the frame choice closed it. Recorded because it was credit's stated blocker |
| 4 | fraud frame | Synthetic at matched thinness (800/14) | **Overridden** → real Kaggle `mlg-ulb/creditcardfraud` | **Costly** | The load-bearing decision. See dissent below |
| 5 | fraud guard code | Delete if unused | **Not taken** — guard stays, verdict flips to pass | Trivial | Not offered as an option; taken as the obvious reading of "retire the demo, not the code." `test_accepts_a_healthy_frame` already covers the passing branch |
| 6 | fraud's `docs/DESIGN.md` | Rewrite to match new frame | **Not taken** — left unedited, superseded for sourcing only | **Irreversible if taken** | Scoping judgment made without asking. Rewriting pre-registration destroys what makes it evidence; leaving it costs only a pointer |
| 7 | lebanese-blonde disposition | Delete local copy, remove all code paths | **Overridden** → keep as documented historical reference | Trivial (retention) / **Irreversible** (deletion) | Operator chose the reversible option. Deletion remains available later; the reverse is not |
| 8 | lending | Leave unchanged | **Confirmed implicitly** — no gap raised | Trivial | Already satisfies all three constraints |
| 9 | Scope of this pass | Three runs named in the prompt | **Confirmed** | Trivial | `customer segmentation` excluded — not raised by the operator, no frame constraint stated for it |

---

## Dissent recorded — decision 4

The skill's routing puts irreversible and evidence-destroying decisions in the
"always ask open" tier. This one was raised **twice** and reaffirmed, so it proceeds as
the operator's decision. The reasoning against is recorded here, not to relitigate it,
but because the design doc would otherwise carry only the outcome.

**The case against giving fraud a healthy frame:**

- Fraud's demo *is* the refusal. `README.md:1` — "a refusal, not a metric";
  `WALKTHROUGH.md:17` — "The run **declined to report an operating point**, and that is
  the pass condition." On a frame where the guard passes, the run demonstrates what
  lending already demonstrates.
- Fraud's own `DESIGN.md` no-list pre-committed to the alternative: *"Would reconsider if
  a synthetic frame with the same thinness (800 rows, 14 positives) were built — which
  would make the model run exercisable with no real records."* The synthetic option was
  the pre-registered answer to exactly this question.
- It retires the HITL gradient's only remaining live subject.

**The case for, as the operator framed it:** *"ideally we would have nice data and not
this restriction."* Fraud has never once executed its model run — all three arms died at
the toolkit-import guard. A real frame makes fraud a working run rather than a permanently
blocked one.

**What makes it defensible:** `mlg-ulb/creditcardfraud` is 0.172% prevalence — *thinner*
than the stand-in's 1.75% — with 492 positives. It separates **imbalance** from
**insufficiency**, which is a real and useful distinction, and arguably the one fraud was
reaching for. The guard's passing branch is genuinely exercised for the first time.

**Reversibility:** Costly, not irreversible. `sufficiency.py` and its tests are untouched,
and `docs/before-guard.json` / `docs/summary.json` are committed artifacts preserving the
measured refusal permanently. Restoring the refusal demo means restoring a thin frame —
the code is all still there.

---

## Questions the interview did not need to ask

Pre-answered by existing docs, per Step 0. Ratified rather than re-decided:

| Pre-answered by | What it settled |
|---|---|
| `runs/ml/lending/docs/DESIGN.md` | Lending's license (CC0-1.0), horizon, prevalence, and the rejected Zenodo alternative |
| `runs/ml/fraud/docs/DESIGN.md` no-list | The synthetic-at-matched-thinness option, and its trigger |
| `runs/ml/fraud/src/sufficiency.py:29` | The sufficiency floor (10/fold) — reused as this design's prevalence test |
| `.gitignore:32` | The data classification of the stand-in frame |

---

## Not asked, and why

- **`human_approval`** — no autonomous external write is in scope. This design sources
  data files; it commissions no agent.
- **Load / latency / spend** — batch modelling runs on ≤285k rows, free-tier, no SLA.
  Weekend-sprint tier defaults apply and are recorded as resolved, not parked.
