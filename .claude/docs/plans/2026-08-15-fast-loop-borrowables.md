# Fast-loop architecture — what to borrow from ai-project-template's genesis/lifecycle design
Date: 2026-08-15
Status: RESEARCH

Scope note: this is **not** GAL-23. GAL-23 measures the current sequential `proto-*` chain;
this doc asks what the chain should become. Separated deliberately — the dry-run's value as
a baseline depends on it measuring the pipeline as it stands, not as it is being redesigned.
Issue: **galactus#27** — "Band contract + HITL gates + automated skill triggering for the
fast loop". Written as research, not a plan; no steps, no `Track:` (that is
`/proto-research`'s field to write when this becomes a work item).

**Scoping decisions taken 2026-08-15** (recorded on #27, repeated here because they
foreclose options this doc leaves open): bands sit **over** `Status:` rather than replacing
it, so neither hook changes; triggering is **`Workflow` orchestration**, so the seven
`disable-model-invocation: true` flags stay set; and the template's gate-check is reused as
**discipline vendored into triage**, not as a skill — the skill lives inside the rendered
payload (`template/.claude/skills/`) and only loads after copier renders a project, which
galactus never was. Long-term the operator's intent is for galactus to render from
`ai-project-template`; the short-term vendoring matches how `ml-*` already arrived.

## The target, as stated by the operator (2026-08-15)

A ~60-minute loop that routes itself and stops only at decision-tree confirmations:

| Band | Budget | Human role | Operator doing in parallel |
|---|---|---|---|
| 1. Triage | 5–10 min | confirm the decision tree | — |
| 2. Prototype | 20–30 min | none — must not block | notebooks: EDA + model dev |
| 3. Optimize + review code | 10–15 min | none | — |
| 4. Harden (deploy, scale) | 10–15 min | gate confirmation | — |

45–70 min total. Band 2 is *concurrent* with operator notebook work, so the pipeline must be
**non-blocking** there, not merely fast. The framing is discovery → develop → deploy with
checks passed at each — the template's lifecycle shape, at a tenth of the duration.

---

## First, what galactus already has

Stating this before the borrow list, because the genesis doc's own headline warning applies
here verbatim: **"The largest risk in this work is rebuilding what exists."** There, five
components already existed and the real deliverable was three surgical changes.

| Capability | Where | Assessment |
|---|---|---|
| Readiness gate with a Definition of Ready | `/proto-refine` | **Sharper than the template's.** Seven DoR checks; sole writer of `REFINED`/`READY` |
| Error-vs-failed-gate distinction | `proto-refine/SKILL.md:28-33` | *"An unreadable or empty target is an **error, not a failed gate**."* The template's gate-check has no equivalent |
| Cost ladder on the gate itself | `proto-refine/SKILL.md:48-55` | Light vs Full path. Light keeps all seven DoR checks and drops only the adversarial apparatus — *"the expensive half… that only earns its cost when something irreversible is at stake"* |
| Hook-enforced state machine | `plan_status_validate.sh`, `plan_transition_validate.sh` | 8 states, byte-identical to global, verified registered |
| `Deferred(<trigger>)`-or-blocker rule | `proto-scope/SKILL.md:49-53` | Identical to the template's. Already shared vocabulary |
| Pre-commit quality gate | `/proto-review` | Plan fidelity + multi-reporter + DoD + merge verdict |
| Adversarial capabilities, callable anytime | `/assumption-audit`, `/war-game`, `/fog` | CROSS band — cheap, read-only, never touch `Status:` |

**So the gap is not "galactus has no gates."** It has a better gate than the thing being
borrowed from. The gaps are narrower and more specific, below.

---

## What is genuinely missing

### M1 — A phase-level status contract that something *other than the pipeline* can read

`/gate-check` writes `LIFECYCLE.md`, described as "the committed status contract that
project-mgmt-ai and other tooling read." galactus's `Status:` line is per-plan-doc and
per-work-item. There is no project-level "which band is this run in, and what is blocking
the next one" that a second process could consult.

This matters specifically for band 2's non-blocking requirement: if the operator is in
notebooks while the pipeline runs, **the status contract is the only channel by which they
learn a gate went red.** Today that information exists only in the session transcript.

Evidence it is missing: `proto-scope/SKILL.md:53` refers to "not genesis, not the G1 gate" —
a live reference to a lifecycle vocabulary that galactus never carried over. The pointer is
vestigial.

### M2 — "Audit, don't assert" as an explicit, enforced discipline

`gate-check/SKILL.md`: *"Audit, don't assert: every checkbox is the result of looking at a
real artifact this run… If a check can't be verified, it stays `false` — never mark a gate
item true on memory or intent."*

`/proto-refine` runs seven DoR checks but does not state this rule. Under a 60-minute budget
this is the discipline most likely to erode, and the GAL-23 research found **two live
instances of exactly this failure class already in the repo**, both found by reading
artifacts rather than running anything:

- `runs/ml/fraud/docs/summary.json` nests `operating_point_reported` under `refusal`, while
  the superseded plan's precondition table asserts it top-level — a check keyed on the flat
  name reads `None`, evaluates falsy, and reads as "no refusal reported."
- `"skipped": {"catboost": …}` — a model silently absent from the comparison, with
  `beats_baseline: false` computed over the survivors and nothing gating on `skipped`
  being non-empty.

Speed pressure is precisely when a check gets marked green on intent. This is the single
most valuable borrow and it costs one paragraph.

### M3 — Confirmations that carry a proposed answer

The genesis lifecycle doc's Q1 (`2026-07-19-genesis-lifecycle-architecture.md:120-144`,
`Status: EXECUTED`, evidenced across three sessions) is the triage band's intake spec,
already worked out:

> "shrinking the *asked* set ≠ shrinking the *interviewed* set… the skill asks ~6 open
> questions and ~4 confirmations, and the confirmations are cheap because they carry a
> proposed answer. That is a genuinely shorter interview than today's 14 blind prompts
> *and* it is more careful, not less."

**A confirmation costs seconds; an open question costs minutes.** That asymmetry is how a
5–10 min triage band gets built without becoming reckless — and it is a *reasoning* layer,
not a prompt-count optimization. The doc is explicit that this trap ("the skill is not a
prompt-count optimizer") is what the design must avoid.

The routing criterion comes with it, from the same lineage: **a default is safe to apply
silently in proportion to how cheaply it can be reversed.** Blast radius, not importance,
decides what interrupts the human.

And the one carve-out: **never derive `human_approval`** — "a silent default has an
irreversible failure mode (an autonomous agent making an external write nobody sanctioned)."

`/proto-scope` currently interviews; it does not propose-and-confirm. That is the change.

### M4 — A router

"Route to the right skill when needed" has no implementation in either repo. Every
transition today is the operator typing a slash command; `disable-model-invocation: true` on
`proto-research` (and its siblings) makes that explicit — the skills are deliberately not
self-dispatching.

This is the largest genuinely-unbuilt piece, and the one place where nothing can be
borrowed. The CROSS-band precedent is the closest thing: those skills *are* model-reachable
("the only skills the model may reach for on its own: cheap, read-only, and exactly what
should be available the moment a load-bearing assumption shows up"). The property that makes
them safe to auto-invoke — cheap, read-only, never touch `Status:` — is the property a
router would need to reason about before dispatching anything.

### M5 — Legal backward transitions

`gate-check`: *"Regressing phase (delivery back to discovery) is allowed and normal."*

**Checked 2026-08-15 — smaller gap than it appears.** `plan_status_validate.sh:26-27`
validates the *vocabulary* (nine tokens) and per-state field requirements (`EXECUTED`
requires `Review:`; `COMPLETE` requires `Review: passed` + `Completed:`; `SUPERSEDED`
requires `Superseded-by:`). Neither hook enforces an *ordering*. So backward transitions
are **not blocked today** — the arrow in CLAUDE.md's `RESEARCH → … → COMPLETE` is
documentation, not enforcement.

What is missing is therefore not permission to regress but the template's *norm* —
gate-check states regression is "allowed and normal," making it a legible move rather than
an anomaly. For the fast loop the real question is narrower: when band 3 sends work back to
band 1, is that recorded anywhere, or does the doc simply show an earlier `Status:` with no
trace it moved backward? A loop that regresses silently cannot be measured.

### M6 — Stage-gated inertness

`template/design.yaml.jinja:27-33`: nothing in the file is read until `/gate-check` marks its
stage `complete`. This is what makes the answers-file/design.yaml loop non-circular — the
artifact is *inert* until a gate blesses it.

galactus has no equivalent. A fast loop writing artifacts that later bands read needs
something like it, or band 3 will consume band 2's half-written output. The general form:
**an artifact is not readable until the gate that owns it says so.**

---

## What NOT to borrow

| Thing | Why not |
|---|---|
| Copier render path, `make project`, `.copier-answers.yml` | Operator: "we don't want to do that exactly." galactus runs are subdirectories under `runs/`, not generated repos; CLAUDE.md puts scaffolding in `ai-project-template` and says "scaffolding is not a band here." **Salvageable at lower cost:** the *answers-file seam* — decide first, render second, so decisions are reviewable before anything hits disk. That idea is what makes a triage band's output inspectable, and it transfers without copier |
| `LIFECYCLE.md`'s G1/G2 check tables verbatim | Keyed to template-owned machinery (`make eval-gate`, `evals/targets.yaml`, `SANYI.md`, `/sanyi audit`). Borrow the *shape* — artifact-verified booleans with a named verifier — not the rows |
| "Serial by default" (`archived/design-prototype/SKILL.md:109`) | *"Parallel agents are faster and unwatchable; on a recorded exercise the narration IS the deliverable."* Written for a **watchable, recorded** exercise. Band 2 is the opposite case — the operator is deliberately in notebooks. **Scope this rule to bands 1 and 4.** Carrying it in unexamined would forbid exactly the parallelism the 20–30 min budget depends on |
| Three-phase Discovery/Delivery/Deployment naming | The operator's four bands split "develop" into prototype and optimize. Adopting the template's three would flatten a distinction the budget treats as real |

---

## The budget's evidence base

**Bands 1 and 2 have measurements. Bands 3 and 4 have none in either repo.**

**Band 1 — supported, with margin.** `archived/design-prototype/SKILL.md:76`: Copier "was
measured at ~12 min against ~2 min for this. Total budget: 2 minutes." A conversational
intake at 2 min against a scaffolding tool at 12 min is the only head-to-head timing
measurement in either repo. 5–10 min for triage has room.

**Band 2 — the one-hour claim was tested once and failed.**
`runs/ml/lending/WALKTHROUGH.md:202-216`, "Verdict on the one-hour claim": ***"Not yet — but
the blocker was structural, not conceptual."*** Two causes, which behave differently under
the band split:

1. **Fit time dominated** — logistic at 270s per configuration, ~36 fits for a three-model
   comparison with calibration. The mitigation is stated and already supported by the CLI:
   cap folds and models. The observation that makes it work: ***"the winning model fits in
   11.6s. The hour is spent on the baseline, not the candidate."***
2. **The composition layer had to be written first.** A one-time structural cost the band
   model **relocates into band 2 rather than removing.** Bands do not make a missing layer
   cheaper.

The verdict's own scope line is what to plan against: the claim *"holds for reaching a
defensible model choice on a real frame; it does not hold for a full multi-model sweep at
this row count without capping folds."*

**Consequence:** the 20–30 min prototype band is achievable **only with the cap as a declared
default, not an available flag.** That is the most concrete constraint the target
architecture inherits, and it is measured rather than assumed.

---

## Open questions — in the order they need answering

1. **Do the four bands replace the eight-state `Status:` machine, or sit over it as a
   coarser view?** This gates every other decision here. If they replace it,
   `plan_status_validate.sh` and `plan_transition_validate.sh` change, and CLAUDE.md's
   claim that the two hook trees are byte-identical becomes a maintenance obligation
   across the rewrite.
2. **What does routing mean mechanically** — model-driven dispatch, a deterministic decision
   table, or `Workflow`-style orchestration? M4. Nothing to borrow; everything to decide.
3. **Is band 2's non-blocking requirement compatible with HITL at all?** If the operator is
   in notebooks, the pipeline cannot stop for confirmation there — so every human decision
   hoists into band 1 or defers to band 4. But M3's carve-out says `human_approval` cannot
   be deferred. Either triage must be complete enough to pre-clear every irreversible
   decision, or band 2 needs an asynchronous confirmation channel (which is M1).
4. **Who owns the gate mechanism — galactus or ai-project-template?** `/gate-check` lives in
   the template and writes `LIFECYCLE.md` there. CLAUDE.md is explicit that scaffolding is
   the template's stage. Copying it into galactus risks the divergence the layering rules
   warn about; reaching across repos at runtime is the seam that has broken before
   (`ML_PACKAGE_ROOT`). A third option — galactus defines the band contract, the template
   renders it — matches how `runs/_index/` already works ("galactus does not define the
   record shape").
5. **Where do bands 3 and 4 get their budgets from?** No measurement exists. Until one does,
   10–15 min each is a target, not an estimate.

## Recommendation

Borrow **M2 first** — "audit, don't assert" is one paragraph, costs nothing, and defends the
exact failure class this repo has already produced four documented instances of. Then **M3**,
because the propose-and-confirm intake is the mechanism that makes a 5–10 min triage band
honest rather than merely fast, and it is already worked out in an `EXECUTED` design doc with
three sessions of evidence behind it.

**M1 and M6 are one decision, not two** — a status contract other processes read, and
artifacts that stay inert until a gate blesses them, are the same mechanism seen from the
producer and consumer sides. They are what band 2's concurrency actually requires; without
them, "the operator works in notebooks while the pipeline runs" has no channel through which
a red gate reaches the operator.

**M4 is the real work** and should not be attempted until question 1 is answered, since a
router routes between states and the state vocabulary is exactly what is unsettled.

Resist the temptation to start from the template's three-phase lifecycle. galactus's
`/proto-refine` gate is better than `/gate-check` in two specific respects — the
error-vs-failed-gate distinction and the Light/Full cost ladder — and the Light path's
governing principle (*drop the adversarial half; keep every cheap check*) is itself the
sharpest available idea for how a 60-minute loop should decide what to skip.
