---
name: ml-select
description: >
  Model-selection interview for a tabular ML problem — produces a `(family, output)` pair
  and a runnable config the training workflow consumes. Asks the two questions that
  determine everything (prediction / classification / clustering, and output shape) plus
  target definition, time structure, grouping, and cost asymmetry.
  Triggers on: "which model should I use", "select a model", "what family is this",
  "set up the training config", "ml-select", "/ml-select".
  Refuses to select before the data has been profiled — run `/ml-transform` first.
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash, Write
---

# /ml-select

The 2-D selection matrix made conversational. The registry is keyed by **(family,
output)**; everything else in the config is a consequence of the answers below.

This skill does not fit anything. It produces the config that `run_classification` /
`run_clustering` / `run_prediction` consume, and the parked-question list that says which
parts of that config are guesses.

## Usage

```
/ml-select [--profile path/to/profile.md] [--output path/to/ml-config.md]
```

| Arg | Default | Description |
|-----|---------|-------------|
| `--profile` | most recent `/ml-transform` output | The data profile this selection rests on |
| `--output` | `.claude/docs/ml-config.md` | Where the config + parked questions are written |

---

## Precondition — profile, then select

**Refuse to name a model before the frame has been profiled.** Not a style rule: the
answers that decide the config (time structure, grouping, target balance, cardinality)
are properties of the data, and a selection made without them is a preference dressed as
a decision.

- If a profile exists, read it and say which of the questions below it already answers.
- If none exists, stop and run `/ml-transform` first. Say so plainly — do not proceed
  with "assuming a typical frame."
- **The one exception**: the data has not arrived yet, and the operator is doing the
  framing deliberately in advance (the ENAM case). Then proceed, and stamp the config
  `Status: PRE-DATA` — every derived field is provisional and re-runs when the frame
  lands. A pre-data config is a hypothesis, not a plan.

## Interview conventions

**"I don't know" is a first-class answer.** Any question below can be answered *unknown*
— park it, do not force a guess.

- Record it under `## Parked` with a **concrete revisit trigger** — the observable event
  that resolves it ("when the first extract lands", "before the threshold is set",
  "resolve with the client before modelling"). A parked item with a real trigger blocks
  nothing; a parked item without one is an unknown pretending to be handled, and is
  recorded as **blocking**.
- **A parked question is never silently filled with a default.** If the workflow needs a
  value to run at all, write the placeholder *and* the park entry, and mark the field
  `provisional`. A config field that reads as decided when nobody decided it is the exact
  failure the parking convention exists to prevent.
- Never present a non-decision as a choice. The logistic/linear baseline always runs —
  say that it runs; do not offer it as an option.

**When a field's own question is parked but another source asserts the value directly**
— the brief states a requirement that Q4 would otherwise have set, say — take the value
and record where it came from, on the field, in the config. `calibrate: true  # from the
brief's stated requirement, not from Q4 (parked)`. The rule this follows: a value with a
named source is decided; a value with no source is a default wearing a decision's
clothes. Do not park a field that something actually answered, and do not let a parked
question silently fill from the skill's own examples.

**When the interview cannot run — no operator to answer, a dry-run, a batch invocation —
say so and downgrade, do not simulate consent.** Every field that the conventions require
a read-back for is emitted `provisional` and parked with the trigger *"confirm with the
operator before the first run"*. A non-interactive invocation produces a **draft config**,
never a confirmed one. The read-back is the mechanism by which the pair stops being an
inference; without it, nothing has been confirmed, and a config that does not say so is
claiming an agreement that never happened.

**Re-running is cheap and expected.** Idempotent over the config file: a later run reads
what is there, ratifies what is resolved, and interviews only the gaps and anything the
new profile contradicts.

---

## The two questions that decide everything

Ask these first, and ask them out loud. Every later answer refines the config; these two
pick the registry key, and a wrong answer here invalidates the rest.

### Q1 — Family: prediction, classification, or clustering?

Ask it as *what comes out and who consumes it*, not as a taxonomy quiz.

| Family | The question it answers | Output |
|---|---|---|
| `classification` | Which class does this row belong to — or with what probability? | `binary`, `multiclass` |
| `prediction` | How much / how many / how long? | `continuous` |
| `clustering` | What groups exist here, when nobody labelled them? | `unsupervised` |

The distinguishing question when the operator is unsure: **is there a labelled outcome
column, and does the decision downstream need a category or a quantity?** No label →
`clustering`. Label that is a category → `classification`. Label that is a number where
being close counts → `prediction`.

Beware the framing that is really two problems: *"predict who will pay and how much"* is
a classification and a prediction, not one model. Say so; pick the one the decision
actually consumes first.

**Then ask the question underneath Q1: is the target an outcome or an effect?**

If the historical data contains the actions someone already took — a contact log, a
campaign flag, a treatment column — then a model trained on the outcome learns *"the
ones we acted on responded"* and recommends acting on everyone. The correct target may
be **uplift** (the effect of the action) rather than propensity (the outcome).

This is not a refinement of Q1; it can invalidate it. Uplift is a different modelling
approach, not a different config, and the registry does not serve it. So:

- Ask it before the pair is confirmed, not after.
- If action/treatment columns are present or suspected, park it as **blocking**, with the
  trigger *"check for action-log columns during profiling"* — and say in the config
  header that the family itself is provisional.
- Do not silently proceed with propensity because it is the family the registry knows.
  A tool's coverage is not evidence about the problem.

### Q2 — Output shape

Within the family, the registry's second key. `binary` vs `multiclass` changes the
metrics, the sampling strategy, and the threshold arithmetic; `continuous` changes them
all again. A pair the registry does not know raises, listing the valid pairs — do not
invent a key.

**Confirm the pair explicitly before continuing**: *"classification / binary — the model
outputs P(pays), one number per account. Correct?"* This is the field the whole config
hangs off; it gets a read-back.

---

## The five that change the config

Ask these after the pair is fixed. Each maps to a specific field, and each has a
consequence that is stated when it is asked — the operator answers better when they can
see what turns on it.

### Q3 — What is the target, exactly?

Not "the label column" — the **definition**. Over what horizon, counted how, from which
event.

> "Paid" over 30 / 60 / 90 days? Full settlement or any payment?

*Why it matters:* a label defined at the wrong horizon is the most expensive available
error, and it is invisible in every metric — the model learns the wrong question
perfectly. Nothing downstream detects it.

Sets: `target`, and the horizon note in the config header.

### Q4 — What decision does the score feed?

Who to contact, what to offer, when to escalate, whether to review by hand.

*Why it matters:* the decision sets the metric. Nobody acts on ROC-AUC. If the score
feeds a cost-based threshold, **calibration becomes a requirement rather than a
finishing touch** — a ranked score is not a decision, and the arithmetic that turns one
into the other needs the probability to mean what it says.

Sets: `calibrate`, primary metric, and whether precision@k is the reporting metric.

### Q5 — Is there time structure?

Cohort dates, seasonality, a policy change mid-history, a portfolio bought in one month.

*Why it matters:* this picks the splitter. Time-structured data split randomly trains on
the future and tests on the past, and the resulting score is optimistic in a way no
amount of cross-validation reveals. Temporal structure → temporal split, no exceptions.

Sets: `splitter` (temporal vs random), and the leakage-check the review dimension will
run against.

### Q6 — Is there grouping?

The same entity across multiple rows — a debtor with several accounts, a customer with
several visits, a device with several readings.

*Why it matters:* the same entity on both sides of the split is leakage. The model
recognises the entity, not the pattern. Grouping → group-aware split, and it composes
with Q5 (both structures present means both constraints hold).

Sets: `group_column`, and `splitter` again.

### Q7 — What is the cost asymmetry?

Cost of a false positive against cost of a false negative. A ratio is enough; an exact
currency figure is better and rarely available.

*Why it matters:* this sets the threshold, and it is a **business input, not a
hyperparameter**. It also decides the sampling strategy — heavy imbalance with a costly
minority class is the case for class weights or resampling, and both of those are
decisions about cost, not about data.

Sets: `sampling`, the decision threshold, and the metric weighting.

**This one is parked more often than any other, and it must not be defaulted to 1:1.**
1:1 is itself a strong claim about the business. If it is unknown, park it with the
trigger *"before the threshold is set"* and mark the threshold `provisional` — the model
still trains, the decision rule does not ship.

### Q8 — Regulatory or explainability constraint?

Does a decision have to be explainable to a regulator, an auditor, or the person it is
about?

*Why it matters:* it constrains model choice **at the outset rather than at deployment**,
which is the difference between a constraint and a rewrite. A hard explainability
requirement can make the regularised linear baseline the shipped model rather than the
floor.

Sets: `models` (the candidate list), and a note on the reporting requirement.

---

## Emit the config

Write to `--output`. Two sections, both mandatory — a config without its parked list
reads as fully decided.

Placeholders in the shape below are written `<...>` on purpose. **A worked example that
carries a plausible concrete value teaches the default it forbids** — an unresolved
horizon copied from an illustration is indistinguishable from one somebody chose. If a
field is parked, its value in the emitted config is a placeholder that cannot be mistaken
for an answer.

**`Status:` is two independent axes, not one enum.** Data state and confirmation state
compose — a pre-data framing run with no operator present is both, and a config that
records only one of them overstates itself. Write both, always:

| Axis | Values | Set by |
|---|---|---|
| data | `PRE-DATA` / `PROFILED` | whether a profile backs the selection |
| confirmation | `UNCONFIRMED` / `CONFIRMED` | whether an operator read the pair back |

`Status: PRE-DATA / UNCONFIRMED` is the honest stamp for a framing dry-run.
`PROFILED / CONFIRMED` is the only combination that authorises a run.

```markdown
# ML config — <problem name>
Status: <PRE-DATA|PROFILED> / <UNCONFIRMED|CONFIRMED>
Profile: <path to the /ml-transform output, or "none — pre-data">

## Selection
family:        classification
output:        binary
target:        <label_column>      # provisional — see Parked #1
group_column:  patient_id          # source: Q6 — repeated visits per patient
splitter:      temporal            # source: Q5 — admission_date; group-aware on patient_id
sampling:      <strategy>          # provisional — see Parked #3
calibrate:     true                # score feeds a cost threshold — source: Q4
models:        [logistic, <candidate>]   # logistic is the baseline, always; every
                                         # other entry names its source or is not here
metric:        pr_auc              # source: Q4 — minority class is the decision class
seed:          42                  # arbitrary by design — see below

## Parked
1. **Label horizon** — readmission within 30d or 90d unconfirmed. Trigger: resolve with
   the clinical lead before modelling. `target` carries a placeholder, not a chosen
   horizon; a change re-runs everything.
2. **Treatment effect — BLOCKING.** If prior interventions are in the data, the model
   learns "patients we followed up, returned less". Trigger: check for intervention
   columns during profiling. Would change the **family**, not just the config, so
   `family` above is provisional until this resolves.
3. **Cost asymmetry** — unknown, NOT assumed 1:1. Trigger: before the threshold is set.
   Sampling is provisional and the decision rule does not ship until this resolves.
```

The worked example above is a **different domain on purpose**. An example drawn from the
problem the skill is most often run against is not an illustration — it is a pre-filled
answer sheet, and the values in it get carried across because they look derived.

**`seed` is the one field that is arbitrary and should say so.** No question sets it,
nothing about the data implies it, and it needs a value for the run to be reproducible.
Write it, and write *why it is not a finding*: it exists so two runs match, not because
42 was chosen over 7 for a reason. Parking it would be false precision; silently
inheriting it as though it were derived is the failure this line prevents. Any field
that reaches the config without passing through a question gets the same treatment —
named as arbitrary, in place, rather than left to look decided.

**Baselines are not optional.** `logistic` (classification) and `linear` (prediction)
are always in `models`. If boosting cannot beat the baseline meaningfully, that is a real
finding about the features — which requires the baseline to have run.

**Every non-baseline candidate carries its source, inline, or it does not go in the
list.** `catboost  # source: brief's modelling position` earns its place; a name that
arrived because it is a reasonable thing to try does not. This is the rule that most
often fails silently, because a plausible model list is indistinguishable from a
justified one at a glance — and unlike a horizon or a threshold, nothing downstream ever
contradicts it. An unsourced candidate is not a harmless extra: it spends fold budget,
it enters the comparison table as though someone chose it, and if it wins, the report
attributes the result to a decision nobody made.

## Hand off

| Config field | Consumed by |
|---|---|
| `family` + `output` | the registry — `get_models(family, output, include=models)` |
| `target`, `splitter`, `group_column` | the training workflow's fold construction |
| `sampling`, `calibrate`, `seed` | `run_classification(...)` / `run_prediction(...)` |
| `## Parked` | the plan doc's open questions, and the leakage review's context |

Then: `/ml-transform` for the column plan if it has not run, and the training workflow
with this config. The parked list travels with the config — it is what the run report
cites when a number looks better than it should.

## Constraints

1. **Never name a model before the family/output pair is confirmed by read-back** — or,
   when no operator is present to confirm it, before the pair is emitted `provisional`
   and parked under the non-interactive rule above. The pair is the registry key; a model
   named first is a preference searching for a justification.
2. **Never fill a parked question with a default** — including from this file's own
   worked example. Placeholder plus park entry plus `provisional`, or nothing. Every
   concrete value in the emitted config either cites a source or is a `<placeholder>`;
   there is no third category, and "it is a reasonable thing to try" is not a source.
3. **The pair travels together.** Whatever is done to `family` is done to `output` —
   confirmed together, parked together, marked provisional together. Half a confirmed
   registry key is an unconfirmed registry key.
4. **Never emit a config without its `## Parked` section**, even when empty — an absent
   section and a genuinely empty one must not look the same. Empty reads `## Parked\n
   None — every question above was answered.`
5. **Do not select on a described problem alone when the data exists.** Unprofiled data
   plus an available frame is a refusal, not a caveat.
6. State the consequence when asking. Every question above carries its *why it matters*;
   an operator who cannot see what turns on an answer guesses.
