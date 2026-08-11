# enam — tabular ML case study

The second case study in this repo. Where [`ml6/`](../ml6) is **generation under a
contract** (an LLM writes, deterministic code decides whether it fits), `enam/` is
**prediction under uncertainty**: a supervised classification problem on messy tabular
data, where the model outputs a probability and deterministic code decides what to do
with it.

The two share a thesis. In `ml6/` the model's cooperation is an optimisation, not a
dependency — the validator is the binding constraint. Here the equivalent binding
constraint is **calibration and the decision rule**: a ranked score is not a decision,
and the threshold that turns one into the other is arithmetic over costs, not a modelling
choice.

> **Predicting who will pay is a model's job. Deciding who to call is not.**

## Status

**Framing only — no data, no model.** This document records the problem as currently
understood and, more importantly, what is *not* known. It is written before the dataset
has been seen, which is the point: the assumptions below are falsifiable, and the first
contact with real data is expected to kill several of them.

Nothing here is a claim about the client's actual business. Every domain statement is
labelled either **Given** (stated by the client) or **Assumed** (our inference, pending
confirmation).

## The problem

**Given:** the case study is machine learning, not agentic. It is a classification
problem, and the data needs cleaning.

**Assumed:** the target is a debtor-level propensity — at collection intake, will this
account pay (self-cure / settle) or roll into dunning and escalation? This is the
standard shape of the problem in debt collection and insurance receivables, but it is
inference, not instruction.

The domain distinction that matters, and that a naive framing collapses:

| | Question | Modelled by |
|---|---|---|
| **Ability** to pay | *Can* they pay? | Income, exposure, existing debt load |
| **Propensity** to pay | *Will* they choose to, now? | Payment history, contact response, tenure, channel |

These are different targets with different features and different interventions. A model
that conflates them will look accurate and be useless — it will rank the wealthy above
the willing, and collections effort goes to people who were going to pay anyway.

## Open questions — resolve before modelling

These are blocking in the sense that a wrong guess invalidates the work, not in the sense
that we sit idle until they are answered.

1. **What is the label, exactly?** "Paid" over what horizon — 30/60/90 days? Full
   settlement or any payment? A label defined at the wrong horizon is the single most
   expensive error available here.
2. **What is the decision the score feeds?** Who to contact, which channel, when to
   escalate to legal, or what settlement to offer? The decision sets the metric. Nobody
   acts on ROC-AUC.
3. **What are the costs?** Cost of a wasted contact vs. cost of a missed collectable
   account. Asymmetric and almost certainly not 1:1 — this sets the threshold, and it is
   a business input, not a hyperparameter.
4. **Is there a treatment effect?** If historical collection actions are in the data, a
   pure propensity model learns *"accounts we chased, paid"* and recommends chasing
   everyone. The genuinely correct target may be **uplift**, not propensity. Flag early;
   it changes the entire modelling approach.
5. **What is the time structure?** Cohort dates, seasonality, regime changes (policy
   changes, portfolio purchases). Determines whether the split is temporal or random —
   see leakage below.
6. **Regulatory posture.** Debt collection is a regulated activity in most jurisdictions.
   If decisions must be explainable to a regulator or a consumer, that constrains model
   choice at the outset rather than at deployment.

## Expected data problems

Stated in advance so they can be checked rather than discovered late. Each is a known
failure mode of this data shape:

- **Class imbalance.** The interesting class is usually the minority. Accuracy is
  meaningless; PR-AUC and precision@k are the honest metrics.
- **Target leakage.** The most dangerous defect in this dataset shape. Post-outcome
  fields — final balance, closure reason, last payment date, collection-action logs —
  correlate with the label because they are *caused* by it. A leaked feature produces a
  suspiciously excellent model that fails silently in production. Any AUC above ~0.95 on
  a first pass is treated as a leakage alarm, not a success.
- **Temporal leakage.** Random splits on time-structured data train on the future and
  test on the past. Split by cohort date.
- **Missingness that is not random.** In collections, a missing phone number or absent
  bureau record *is* signal. Imputing it to a median destroys information; a sentinel or
  explicit missing-indicator preserves it.
- **High-cardinality categoricals.** Employer, region, product, agency, agent ID. Naive
  one-hot explodes the feature space; target encoding leaks unless done inside the CV
  fold.
- **Duplicate and near-duplicate debtors.** The same person across accounts. If they land
  in both train and test, the score is optimistic. Group-aware splitting.
- **Fairness.** Protected characteristics and their proxies (postcode is the classic).
  Requires an explicit position, not silence.

## Modelling position

**Gradient-boosted trees, CatBoost first.** Not a default — a conclusion from the
benchmark evidence. On tabular data, GBDTs remain the strongest practical choice, and
CatBoost's edge is largest exactly where this dataset sits: mixed-type, categorical-heavy
features, handled natively with ordered boosting rather than manual encoding. Tabular
foundation models (TabPFN et al.) now lead on single-model Elo, but CatBoost moves back
ahead without multi-config ensembling — and it costs nothing to interpret or deploy.

**BERT is the wrong tool** unless free-text is present (call notes, agent transcripts,
correspondence). Text is not the primary signal in a tabular collections problem. If
notes exist, the right move is to encode them into a handful of features that feed the
tree model — not to replace the tabular model with a transformer.

**A regularised logistic regression is the baseline, and it is not a formality.** It sets
the floor, it is trivially explainable to a regulator, and if boosting cannot beat it
meaningfully the honest finding is that the features are weak — which is a real result
about the data, not a failure of the model.

**Calibration is a first-class requirement, not a finishing touch.** If the output feeds a
cost-based threshold, the probability has to mean what it says. Ranking is not enough;
0.7 must correspond to roughly 70% of such accounts paying. Brier score and a reliability
curve alongside the discrimination metrics.

**On the bandit.** [`atlas`](../../atlas) has a bandit in its agent learner
(`src/agents/learner/rl_interface.py`). It is deliberately *not* phase one here. Bandits
answer "which action for this account?" — a policy question that only becomes tractable
once a calibrated propensity score exists and outcomes are being logged. It is the
natural phase-three extension (contact-strategy allocation), listed here so the door is
left open and not designed against.

## Layout

```
enam/
├── README.md    This document — problem framing and standing assumptions
├── docs/        DESIGN.md and analysis notes (written as the work proceeds)
└── data/        Gitignored. Real debtor data never enters this repo.
```

## Data handling

The data is personal financial information about identifiable people. It does not get
committed, and it does not get pasted into a model context. `data/` is gitignored;
worked examples in tests and docs use synthetic fixtures.
