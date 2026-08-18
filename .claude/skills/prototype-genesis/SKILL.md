---
name: prototype-genesis
description: >
  Front door for a new prototype in this repo. Routes AI-shaped from ML-shaped work at
  gate 0, then walks the branch's gates in order — loading only that branch's specs and
  materializing only that branch's payload. Composes /scope-poc, /ml-transform, /ml-select
  rather than re-asking their questions. Dry-run by default: proposes at every gate and
  waits for confirmation before writing anything.
  Triggers on: "new prototype", "start a prototype", "prototyping a new project",
  "back at it again", "new poc", "/prototype-genesis".
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, AskUserQuestion
---

# /prototype-genesis

The gate-0 router the pipeline was missing. `/scope-poc` asks *what to build* and
`/project-genesis` asks *how to scaffold it* — both assume the work is AI-shaped. Tabular
ML has a different spine: the dominant risk lives in the data you were handed, and it is
found by looking, not by reasoning.

This skill picks the branch first, then walks it.

## Usage

```bash
/prototype-genesis [--branch ai|ml] [--poc pocs/<branch>/<slug>] [--execute]
```

| Arg | Default | Description |
|-----|---------|-------------|
| `--branch` | ask at gate 0 | Skip the routing question when you already know |
| `--poc` | derived from the problem name | Where the prototype lands |
| `--execute` | off — **dry-run** | Without it, every gate proposes and waits |

**Dry-run is the default and it is not a formality.** Without `--execute`, this skill
writes nothing: it names the file it would write and the command it would run, then stops
for confirmation. A gate that "just" scaffolds boilerplate is still a gate — the operator
decides, every time.

---

## Interview conventions

Inherited verbatim from `/ml-select` and `/scope-poc`, because a second dialect of the
same discipline is how the discipline erodes:

- **"I don't know" is a first-class answer.** Park it with a concrete revisit trigger.
  A parked item with a real trigger blocks nothing; one without a trigger is an unknown
  pretending to be handled, and is recorded as **blocking**.
- **Never fill a parked question with a default** — including from this file's examples.
  Placeholder plus park entry plus `provisional`, or nothing.
- **State the consequence when asking.** An operator who cannot see what turns on an
  answer guesses.
- **Re-running is cheap and expected.** Idempotent over the POC directory: a later run
  ratifies what exists and walks only the unfinished gates.
- **Never present a non-decision as a choice.** The baseline model always runs. Say that
  it runs; do not offer it as an option.

---

## Gate 0 — Route

Ask one question, then commit to a branch. Greet the returning operator like a colleague,
not a form.

> "Prototyping again. Is this **AI-shaped** — an agent, RAG, a generation service, an LLM
> in the loop — or **ML-shaped**: tabular data, a target column, a model that predicts?"

The distinguishing question when it is unclear: **is there a labelled outcome column in a
frame you already have?** If yes, it is ML however much an LLM might also appear later.
If the deliverable is a system that reasons over text and there is no target column, it is
AI.

**Some projects are both.** A fraud model with an LLM narrative layer is an ML prototype
with an AI consumer. Say so out loud, pick the branch that owns the *risk*, and note the
other as a downstream consumer. Do not walk both branches in one session — the gates
interleave badly and the specs contradict each other on purpose.

### What the branch decides

| | AI branch | ML branch |
|---|---|---|
| Specs loaded | `.claude/specs/agent-*.md` (start `agent-architecture`), plus `agent-uncertainty` | `python.md` only; **no `agent-*` spec is read** |
| Design skill | `/scope-poc` → `/project-genesis` | this skill's gates 1–7 |
| Payload | `src/` agents, evals, guardrails | `ml/` — vendored at repo root, 33 modules |
| Reference POC | `runs/ai/marketing-comms/` (277 tests) | `runs/ml/credit/` |
| Dominant risk | ungrounded generation, silent contract breach | **leakage**, imbalance, uncalibrated scores |

**Say which specs you are skipping and why.** "ML branch — I am not loading the ten
`agent-*` specs" is the observable proof the routing worked. Silent routing is
indistinguishable from no routing.

**Payload note (current, 2026-08-12):** the ML payload is vendored at `ml/` in this repo
and passes its own suite (158 passed, 6 skipped). The template's `include_ml=true` renders
ML *on top of* a full agentic scaffold rather than selecting an ML-shaped project — so
there is no clean ML branch to render from yet. Use the vendored `ml/`; do not run copier
for the ML branch until the template has a real `ml` project type. Record what this
walkthrough needed at gate 7 — that list is the spec for the template's ML branch.

---

# ML branch — gates 1 through 7

## Gate 1 — The problem, before the data

**Split into 1a and 1b, and do not merge them.** Some framing questions only the operator
can answer; others only the data can. Asking a data question in the pre-data gate produces
"we need to look at the data to answer this" — a correct answer that wasted a turn and made
the interview feel like a checklist rather than a conversation.

| | Gate 1a — pre-data | Gate 1b — after EDA |
|---|---|---|
| Answered by | the operator's domain knowledge | the frame |
| Questions | problem, decision consumer, what happens today, success measure, **cost asymmetry** | recurrence, time structure, prediction moment, cardinality, balance |
| Blocks | naming a model | choosing the splitter |
| If unanswerable | park with a trigger | it is a data question — it resolves at gate 4 by construction |

Gate 1a runs before the frame is opened. Gate 1b runs **after** the notebook, folded into
gate 4's read-back — by then the answers are on screen and the operator is confirming what
the data shows rather than recalling it.

**Do not read the frame before gate 1a. Do not profile, correlate, or rank columns.**

This is the gate most likely to be run wrong, and the failure is subtle: an agent with
file access reads the CSV, pre-computes the interesting findings, and arrives at gate 1
holding conclusions. The operator is then reviewing homework instead of framing a problem.
The interview becomes theatre — every question already has an answer attached, and the
operator's own knowledge of the domain never enters.

**Start vanilla.** First time through, no assumptions:

> "Before we touch the data — what problem are we solving, and who acts on the answer?"

Have the actual conversation. What decision does this feed? Who is on the other end of it?
What happens today without a model? What would make this useful versus interesting? An
operator who has worked the domain knows things the schema cannot tell you, and they only
say them if asked before you have shown them a table.

Then, still without profiling:

1. **Family and output** — `/ml-select` Q1/Q2. Ask what comes out and who consumes it, not
   as a taxonomy quiz. Read the `(family, output)` pair back and confirm it: it is the
   registry key and everything downstream hangs off it.
2. **Outcome or effect** — does the history contain actions someone already took? A contact
   log, a campaign flag, a treatment column. If so the correct target may be **uplift**,
   which the registry does not serve. Ask it; do not go looking for the columns yourself
   yet. Park as **blocking** if the operator suspects they exist.
3. **The target definition** — over what horizon, counted how, from which event. Not the
   column name, the definition. A label defined at the wrong horizon is the most expensive
   available error and it is invisible in every metric.

**Leakage is NOT a gate-1 topic.** At gate 1 nobody knows yet — that is the honest state,
and asking "which columns exist only because the outcome happened?" before anyone has seen
the columns invites a guess dressed as a decision. Leakage is discovered at gate 4, in the
notebook, by the operator looking at real columns with real domain knowledge.

The temptation to front-run it is strong precisely because the agent *can*. Resist it: a
leakage call made from a correlation ranking is a statistical artifact, while the same call
made by someone who knows how the data was collected is a fact. **Wait for gate 4.**

**Cost asymmetry is the one pre-data question that must not be skipped**, and it must not
default to 1:1 — that is itself a strong claim about the business. Ask it as two concrete
mistakes, never as a ratio in the abstract:

> "Which is worse: approving someone who then defaults, or declining someone who would
> have repaid?"

Then **restate the answer in confusion-matrix terms and confirm it**, because natural
language inverts easily here. With `default = 1` as the positive class, approving a
defaulter is a **false negative**; declining a good customer is a **false positive**. An
operator saying "I want high precision" while describing false-negative costs is not
confused about their business — they are using "precision" colloquially, and taking it
literally would move the threshold the wrong way. Read it back before it reaches a config.

**Watch for the two-threshold case.** "Automatic application of predictions" usually means
banding, not a single cutoff: auto-approve a low-risk tail, auto-decline or review a
high-risk tail, humans handle the middle. Those bands have *different* metrics — precision
on the safe class for auto-approve, recall on the default class for the flag band — and
collapsing them into one number optimises neither. If the operator describes automating
decisions, ask which decisions get automated, and expect two thresholds and a coverage
number rather than one metric.

### Gate 1b — the questions that need the data

Ask these **after** the notebook, at gate 4. Naming them at 1a is fine — as a parked list,
not as questions awaiting an answer:

- **Recurrence.** Can the same subject appear more than once — pay off one loan, then take
  another? Sets `group_column` and makes the split group-aware.
- **Time structure.** Cohort dates, a policy change mid-history, seasonality. Sets the
  splitter to temporal; a time-structured frame split randomly trains on the future and
  tests on the past, and the resulting score is optimistic in a way no cross-validation
  reveals.
- **The prediction moment.** Is this scored at application time for a stranger, or
  mid-relationship for someone with history? This decides what counts as a leak: for a
  returning customer, prior payment behaviour is exactly the signal a lender legitimately
  uses; for a brand-new applicant it does not exist yet.

Recurrence plus history changes the frame from independent rows toward time-series, and
that reframing changes what counts as leakage. It cannot be settled before the data is
seen — which is precisely why it is 1b and not 1a.

## Gate 2 — Candidate models

Read the registry rather than recalling it — `ml/selection/registry.py` is the authority
on what `(family, output)` actually serves:

```bash
uv run python -c "
from ml.selection.registry import get_specs
for spec in get_specs('classification', 'binary'):
    print(f'{spec.name:14} baseline={spec.is_baseline} available={spec.available} {spec.notes}')
"
```

Use `get_specs` here, not `get_models`: specs carry the metadata this gate needs
(`is_baseline`, `available`, `notes`), while `get_models` returns *built estimators* and
silently omits anything whose optional dependency is missing. Proposing from `get_models`
means never mentioning the candidates that are one `uv add` away.

Propose the candidates **that exist**, and say which are unavailable for a missing
optional dependency (`catboost`, `lightgbm` are declared but not installed here — the
comparison runs one model shorter, cleanly, with a logged warning). The operator picks a
subset or all of them.

**The baseline is not on the menu.** Logistic (classification) and linear (prediction)
always run — they are the explainability floor and the thing every other model has to be
better than. If boosting cannot beat the baseline meaningfully, that is a real finding
about the features, and it requires the baseline to have run.

**Every non-baseline candidate carries its source, inline, or it does not go in the list.**
"It is a reasonable thing to try" is not a source. An unsourced candidate spends fold
budget, enters the comparison table as though someone chose it, and if it wins, the report
attributes the result to a decision nobody made.

## Gate 3 — Split: scaffold and explore in parallel

This is the gate that makes the hour work, and it is deliberately two things at once.

**Claude scaffolds** the run script from `ml/workflows/` — the pipeline, the split plan,
the candidate list from gate 2. Nothing is invented: the workflow already handles per-fold
fitting, out-of-fold prediction, calibration, and threshold choice.

**The operator opens the notebook** — `runs/ml/credit/notebooks/01-eda.ipynb`, templated
from the operator's own 2020 EDA. Bivariate-first by design: every section compares a
feature against the target rather than cataloguing columns. Its cells are thin calls into
`runs/ml/credit/notebooks/eda.py`, which is where the analysis actually lives.

Say both halves out loud when the gate opens, and say where to look:

> "I am writing the run script. You open `01-eda.ipynb` — the cells that matter are the
> leakage audit and the feature-type inference; inference will read rank codes as
> magnitudes and it needs your correction."

Do not proceed to gate 4 until the operator reports back. The notebook's last cell is the
handoff, and it will not fill itself.

## Gate 4 — Feature decisions

The notebook's final cell emits four lists — `CATEGORICAL`, `NUMERIC`, `ORDINAL`,
`EXCLUDED` — and reconciles them against the feature total. **Unaccounted columns are the
gate.** A column in none of the lists is silently dropped, and silent drops are how a
feature nobody decided about disappears.

Read the lists back with the counts, and confirm two specific things the inference gets
wrong on this shape of data:

- **Rank codes read as numeric.** `status_*` / `worst_status_*` columns are ordinal
  ranks, not magnitudes. Inference cannot tell.
- **Leakage exclusions carry their reason**, in the `EXCLUDED` dict, not in memory.

### This is where leakage is decided — not before

Gate 1 deliberately left it open. Now there are real columns on screen and an operator who
knows how the data was collected, which is the only combination that can settle it.

Ask, do not assert. The correlation scan in the notebook produces *candidates*; the operator
produces the *verdict*. A column that correlates strongly with the target is equally
consistent with "leak" and "the best feature you have", and nothing in the numbers
distinguishes them.

**A prior-history column is not a leak just because it is predictive.** If gate 1 established
that subjects recur — someone pays off a loan, then takes another — then previous payment
behaviour is exactly the signal a lender would legitimately use. The question is never "is
this correlated?" but:

> "At the moment we would make this prediction, would this value already be known?"

Knowable at decision time → feature, however predictive. Recorded because the outcome
happened → leak, however weak. **Same column, different answer depending on when the frame
is cut** — which is why this is a conversation, not a rule the skill can apply.

Where the answer depends on unavailable provenance, park it as **blocking** with the trigger
that would resolve it, and mark the run provisional. Do not resolve it by picking the
conservative option silently: excluding a real feature and including a real leak are both
errors, and only one of them is visible later.

## Gate 5 — Feature engineering brainstorm

Before writing a transform, ask the question the pipeline cannot:

> "What do you know about this domain that the data does not say?"

Ratios that matter. Thresholds that are meaningful. Time windows that should be compared
rather than used raw. **Overlapping aggregation windows** (0–12m, 12–24m, 0–24m) are both
an opportunity — a 0–12m vs 12–24m ratio is a trend signal — and a trap, because 0–24m is
not independent of either.

Write the candidates down *before* implementing them. Then implement via
`ml/feature_engineering/`, which already has the mining and selection primitives.

## Gate 6 — Train, and read the result honestly

Run the workflow. Then report the three things that decide whether the number means
anything:

1. **The margin over baseline, against fold variance.** `ml/workflows/classification.py`
   sets `BASELINE_TOLERANCE = 0.01` — a margin inside the noise band is a coin flip being
   reported as a finding. Report the spread, not just the mean.
2. **Positives per fold.** With few positives, cross-validated metrics are extremely
   noisy. State the count; do not let a good-looking PR-AUC pass unqualified.
3. **The leakage assertion.** `RunResult` carries the no-transform-leakage claim
   explicitly so the run script can assert it. Assert it, and say that you did.

A result that looks better than it should is the signal to re-read gate 1's leakage
answer, not to celebrate.

## Gate 7 — What this skill did not know how to do

The gate that makes the tool improve, and the reason the walkthrough is worth doing at
all. Ask directly:

> "What did I get wrong, ask badly, or not have a template for?"

Then **write it back**, in the right place:

| Gap | Lands in |
|---|---|
| A question asked badly, or missing | this file's gate |
| A missing notebook cell | `pocs/ml/credit/notebooks/01-eda.ipynb` (narrative) |
| A missing EDA function | `pocs/ml/credit/src/eda.py` (logic) |
| A missing pipeline capability | `ml/` — and upstream in `ai-project-template` |
| Something the template's ML branch needs | `.claude/docs/plans/` — the ML-branch spec |
| A convention that should be enforced, not asked | a hook, a linter rule, or a test |

That last row is the repo's own standard: a rule you rely on belongs in a hook, not in
prose. If a gate above can be skipped with no consequence, it is documentation — encode it
at the strongest available layer instead.

---

# AI branch — gates 1 through 5

The AI branch is not a stub, but it is **not walked in the same session as the ML branch**.
It composes existing skills rather than adding gates:

| Gate | Skill | Produces |
|---|---|---|
| 1 · Design | `/scope-poc` | `DESIGN.md` — problem, actors, MVP scope, key decisions |
| 2 · Specs | read `.claude/specs/agent-architecture.md`, then the layers it indexes | the five layers answered or explicitly deferred |
| 3 · Scaffold | `/project-genesis` → copier | project structure, evals, guardrails |
| 4 · Build | `/workflow-plan` → `/workflow-execute` | code, plan doc as the bus |
| 5 · Review | `/workflow-review` + the `review-*` dimensions | verdict against `## Plan` |

Gate 2 is where the branches genuinely diverge: `agent-uncertainty.md` cuts across every
layer and owns abstention, asymmetric cost, and reversibility. Read it alongside the layer
ref, not instead of one. `agent-voice.md` applies **only** to duplex/streaming designs;
where the design is request → response → done, ignore it entirely.

---

## Constraints

1. **Route before loading anything.** Reading ten `agent-*` specs for a tabular ML problem
   is the failure this skill exists to prevent — it burns the context the data work needs.
2. **Do not read the data before gate 1 ends.** No profiling, no correlations, no column
   ranking. An agent that arrives at the framing conversation already holding the findings
   has replaced the interview with a review of its own homework, and the operator's domain
   knowledge — the only thing the frame cannot supply — never gets asked for. This is the
   constraint most likely to be violated, because the tools to violate it are right there.
3. **Never name a model before gate 1's pair is confirmed.** A model named first is a
   preference searching for a justification.
4. **Leakage belongs to gate 4, with the operator.** A leakage verdict derived from a
   correlation ranking is a statistical artifact. The same verdict from someone who knows
   how the data was collected is a fact. The skill surfaces candidates; it never decides.
5. **Never skip the notebook.** Gate 3's split is the point: templated code arrives while
   the operator looks at real data. A walkthrough where Claude does both is a code
   generator, not a prototyping tool.
6. **Dry-run means dry.** Without `--execute`, name the write and stop. Do not create
   "just" a directory.
7. **Gate 7 is not optional.** A walkthrough that teaches the skill nothing was a
   transcript, not a session.

## Demo mode versus automated mode

The two modes have opposite defaults, and conflating them is what makes a demo feel
pre-chewed. State which mode is running when the session opens.

| | Demo / first run | Automated workflow |
|---|---|---|
| Posture | vanilla — assume nothing, ask everything | pre-compute what is derivable, surface only the open questions |
| Data access before gate 1 | **none** | profile up front; the operator is not waiting |
| Leakage | discovered with the operator at gate 4 | candidates ranked and proposed, operator ratifies |
| Pace | one gate per exchange, discussion encouraged | batched; gates collapse where nothing is contested |
| Output | a walked-through prototype plus gate-7 findings | a config plus a parked list |

**Demo mode is the default when a human is present and this is the first pass.** The
pre-emptive behaviour that is correct in the automated path — reading the frame, ranking
leak candidates, arriving with a table — is exactly wrong in a demo, because the point of a
demo is the conversation, not the artifact.

**Per-option delivery agents.** Where a gate offers genuine alternatives (three candidate
models, two framings, temporal versus grouped split), those alternatives can be delivered
by separate agents in parallel rather than serialised through one context — one agent per
option, each producing its own runnable result for comparison. Keep the *interview* in the
main session; fan out only the *delivery*. The gate stays a conversation; the work behind it
parallelises.
