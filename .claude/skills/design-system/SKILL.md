---
name: design-system
description: "Translate a product requirement into an agent system spec, then stress it before any code exists. Grounds the requirement (consumer, correctness, cost of wrong, and scale), walks the five layers — prompt, context, harness, loop, graph — forcing an explicit answer or named deferral at each, simulates the design against adversarial scenarios, and closes with success metrics. Output is a spec that feeds /workflow-research. Triggers: 'design an agent for X', 'spec out X before we build', 'system design for X', 'dry run this design', 'what should this system look like', '/design-system'."
job: design
disable-model-invocation: true
allowed-tools: Read Grep Glob Write
---

You are running a design dry run: producing an agent spec from a requirement, then
attacking that spec before a line of code is written. Cheapest place to find a design
flaw is here.

**Output:** `.claude/docs/specs/YYYY-MM-DD-<slug>.md`. Nothing else. Write no
implementation code — not even a sketch.

## Input

`$ARGUMENTS` is a product requirement in the user's words. If it is one line
("an agent that reconciles ledgers"), do not expand it yourself — ask for the two or
three facts Stage 0 needs, then proceed.

If `$ARGUMENTS` names an existing spec file, skip to Stage 2 and stress that spec.

---

## Stage 0 — Ground the requirement

Three questions, answered before any layer work. Ask the user if unknown; do not invent.

1. **Who or what consumes the output, and what do they do with it?** An answer like
   "a human reads it" and "another service parses it" produce different designs at every
   layer below.
2. **What does "correct" mean, checkably?** Push for a deterministic check. "Good copy"
   is not a spec; "≤ 150 characters, every claim traceable to the source PDF" is.
3. **What is the cost of a wrong answer?** Silent-wrong-and-cheap and
   silent-wrong-and-expensive justify different verification budgets.

If question 2 has no deterministic answer, say so plainly in the spec and continue. An
agent without an acceptance baseline can still be built — it just cannot be verified,
and the spec must say that out loud rather than fake a rubric.

### Stage 0b — Put numbers on it

Three questions, four if there is a loop. **Order-of-magnitude answers are the goal;
precision is not.** The purpose is not a capacity plan — it is that several layer
decisions below are unanswerable without a rough scale, and a design that never states
one silently assumes the demo case.

1. **How many, how often?** Requests per day → per second → peak. One line of arithmetic.
2. **What is the latency budget, and who is waiting?** A human watching a spinner and a
   nightly batch job justify opposite designs at the context and loop layers.
3. **What does one run cost, and what is the ceiling?** Tokens × price × runs. An agent
   loop without a cost ceiling is a denial-of-wallet surface, not a budget question.
4. **If there is a loop: what bounds it?** Max iterations, max spend, wall-clock cap.

Then state the non-functional requirements **explicitly, as a list**, rather than letting
them appear implicitly at each layer: availability, latency, consistency, durability,
cost ceiling, and whether any of them is actually load-bearing. Most agent designs
genuinely need only two or three — naming which ones is the point, and "this one does not
matter here" is a real answer that prevents over-engineering later.

**Then tie every later decision back to one of these.** A layer decision that traces to no
stated requirement is either unmotivated or serving a requirement nobody wrote down.

**Offer tier defaults rather than demanding numbers.** Asking "what's your p95 target?"
of someone who has not thought about it produces either a fabricated number or a parked
question. Offer a row instead:

| Tier | Load | Latency | Spend ceiling |
|---|---|---|---|
| Prototype | demo-scale, <10 users | none — demo tolerance | free tier / trivial |
| Real but small | tens of users, <1k runs/day | name one target (e.g. p95 < 10s) | a real monthly number |
| Production | a stated projection | p95 target, with alerting | a real monthly number, with alerting |

**An accepted default is a resolved answer, not an unknown.** Record it with its
provenance — `~500 runs/day (real-but-small tier default, unvalidated)` — and move on.
Do **not** park it as an open question; open questions are for things that block, and an
accepted default does not block. Park it only when the user says the number genuinely
matters *and* does not know it.

Wrong-by-10× is recoverable and visible. Unstated is neither.

### Stage 0c — Observability and blast radius

Two questions the scaffold cannot answer for you.

**What would you need to see when it misbehaves?** When someone reports "it gave a wrong
answer yesterday," what do you pull up — the prompt, the retrieved chunks, the tool calls,
the abstentions? One line is a complete answer.

**If any data is restricted or secret: what must be redacted before it reaches a trace or
a log?** This one is not optional. Tracing is on by default in most scaffolds, so the
silent default here writes sensitive data to a third-party backend — an irreversible
failure with no error message. Name the fields, or state plainly that nothing is
sensitive.

---

## Stage 1 — Walk the five layers

The stack nests: **prompt ⊂ context ⊂ harness**, then **loop**, then **graph**. Walk it
in that order. Each layer gets an explicit answer or an explicit deferral naming what
would force it later. **A layer you skipped silently is the one that fails in
production.**

Read the matching `.claude/specs/agent-*.md` ref before answering each layer. Each ref
opens with its durable question — that question is the layer's minimum bar.

### 1. Prompt — the instructions themselves

- What is the role, in one sentence?
- What is the output format, and is it schema-constrained?
- Which constraints are stated positively? (Tell the model what to do, not what to
  avoid — the negative form leaves the target underspecified.)
- For each hard constraint, state **why** it exists. A constraint with a reason
  generalizes; a bare prohibition gets read narrowly.

### 2. Context — what goes in the window

Context assembly is a **minimization problem, not a filling problem**: the smallest set
of high-signal tokens that gets the outcome. Apply the four levers **in order** — cost
rises left to right:

| Lever | Question |
|---|---|
| **Write** | Can this live outside the window entirely? |
| **Select** | What comes back in, and when? |
| **Compress** | Can this be smaller? |
| **Isolate** | Does this need a separate window? |

Isolate is last because it is the most expensive — tokens multiply and cross-agent
context is lost.

Then classify every context source as static / dynamic / retrieved / historical.
**Historical is the only type without a natural bound** — name what bounds it, or state
that nothing does.

**Name the access pattern before the storage shape.** For each source: read or written,
how often, by key or by search, and does staleness matter? Retrieval design follows from
that answer and is hard to change afterward — picking the store first and discovering the
access pattern later is the expensive ordering. If two sources have genuinely different
access patterns, that is a reason to store them differently, and one of the few
justifications for extra machinery at this layer.

Note the attack surface: context has no type system, so instructions and data are the
same tokens. Every added source is added surface.

### 3. Harness — everything between request and output

**Agent = Model + Harness.** A harness constrains, informs, verifies, and corrects.
Answer all four parts; most incomplete designs have the first two:

| Part | Question |
|---|---|
| Acceptance baseline | What does "done and correct" mean, checkably? |
| Execution boundary | Where does it run, and what can it touch? |
| Feedback signals | How does the agent learn its last action was wrong? |
| Rollback | How do we undo a bad action? |

**The most commonly missing part is rollback. The most commonly faked one is the
acceptance baseline** — a vibes-based "looks good" standing in for a binary check. If
you are about to write "the model reviews its own output," stop: that is generator and
evaluator being the same agent.

For each constraint, name the layer that encodes it: **hook > linter > test > tool schema
> instruction line**. The test: *what happens if the agent ignores it?* If nothing
catches it, the rule is documentation, not a constraint.

### 4. Loop — the cycle that re-prompts and stops

Only if the design has one. A single scripted call is a chain, not a loop; say so and
move on — a chain runs a fixed sequence regardless of results, a loop lets feedback
change the next step.

If there is a loop, all five components are required. **A loop missing any of these will
hang, thrash, or silently ship garbage:**

1. **Testable goal** — specific enough to evaluate. "Improve the app" is an infinite loop.
2. **Tool set** — real environmental access, or the loop degenerates into repeated guessing.
3. **Context management** — how iteration N+1 sees N without carrying the whole transcript.
4. **Termination logic** — layered, independent exits: success, iteration cap, budget cap,
   stall detector.
5. **Error handling** — recoverable vs hard blocker, and *change strategy by error type
   rather than retrying the identical failed approach*.

Then name the capability level: (1) tool-calling agent, (2) + verification, (3)
event-driven, (4) hill-climbing. Levels 1–3 automate work; level 4 automates improvement.

Prefer deterministic verification over model judgment wherever a check exists. Model
self-grading is gameable — anchor on tests, compilers, linters, and use model judgment
only above that floor.

### 5. Graph — nodes and permitted transitions

**Default to no graph.** A loop is a graph with one node and an edge back to itself, so
a graph is a cost you justify, not a maturity level you graduate to.

Name which of the five signals forces a node, or state that none do:

| Signal | Why one loop structurally cannot do it |
|---|---|
| Distinct specialties | One agent carries each role's baggage into the next |
| Parallel fan-out + join | A loop is sequential; the wall-clock cost is unnecessary |
| Per-step model/tool variation | One agent enforces a uniform model and tool policy |
| Auditable control flow | Emergent loop paths are hard to reconstruct afterward |
| Overloaded verifier | One check judging several criteria confuses them |

"It feels cleaner" is not a signal. **The most common "we need a graph" is really an
overloaded verifier** — split the rubric before splitting the system.

If a node is justified, apply the true-dependency test to every proposed edge: *does the
next step actually read the previous step's output?* If not, the serialization is
incidental and belongs in a fan-out. Start at 3–5 nodes.

### 6. HITL — where a human sits

Not a sixth layer; a cut across all five. Consequence concentrates at specific edges, so
approval gates belong at those edges, not uniformly.

- Which actions require approval **before** execution?
- What is the escalation path when the loop hits its cap without success?
- What does the human see at that moment — raw transcript, or a structured decision?

Loops make unattended mistakes unattended. If the answer is "a human reviews everything,"
that is not HITL, it is a bottleneck; name the specific edges instead.

---

## Stage 2 — Simulate

Now attack the spec. Generate **three scenarios**, and do not let them all be happy paths:

1. **The nominal case** — what the requirement literally describes.
2. **The malformed case** — input that is empty, truncated, wrong-typed, or adversarial.
   Prompt injection belongs here for anything reading external data.
3. **The plausible-wrong case** — the agent produces confident, well-formed, *incorrect*
   output. This is the one that finds real bugs, because it is the failure the acceptance
   baseline is supposed to catch and usually doesn't.

For each scenario, role-play the design turn by turn:

```
Turn N:
  Agent sees:    <what is actually in the window at this point>
  Agent wants:   <the action it selects>
  Available?     <yes / NO — and this is a finding>
  Result:        <what comes back, including the failure case>
  Verifier says: <pass / fail — and by which deterministic check>
```

Stop the walkthrough at the first point where the design cannot proceed. That stopping
point *is* the finding. Do not repair it inline and continue — record it and start the
next scenario.

Emit findings in this shape:

| # | Layer | What breaks | Spec change |
|---|---|---|---|

Then **revise the Stage 1 spec** to absorb the findings. Show what changed. A dry run
that produces no revisions either got lucky or was not adversarial enough — say which.

---

---

## Stage 3 — Close with measurement

Three short sections. All cheap here and expensive to reconstruct later.

**What breaks first.** Now that the design is stated, read it back adversarially and name
the weaknesses before a reviewer does. Two are enough:

- Which component fails first as usage grows, and what does that failure look like *to a
  user* — slow, wrong, an error, or silent staleness? Silent staleness is the one worth
  hunting; the other three announce themselves.
- How would you notice — what signal, and who is watching it?
- What is the cheap mitigation, and is it in scope now or later?

This is a design question, not a product-risk question. Stage 2 asks what the *scenarios*
break; this asks what the *architecture* will cost you. "The model API rate-limits us and
requests queue" is a perfectly good answer.

**Success metrics, with numbers.** Not "it should be accurate" — a threshold on a named
measure, tied back to the Stage 0b requirements. `"p95 under 2s while faithfulness stays
above 0.9"` is a spec; "fast and correct" is a wish. If a metric has no instrument yet,
name the instrument as work, not as an assumption.

**The known next moves.** What is deliberately out of scope for v1, and what would force
each one in. This is not a roadmap — it is the record of which simplifications were
*chosen* rather than *overlooked*, which is the distinction a reviewer six weeks from now
cannot recover from the code. A design that names its own deferrals is legible;
one that doesn't reads as either finished or careless, and it is usually neither.

---

## Output format

```markdown
# Spec: <name>

Status: DRAFT
Requirement: <the user's words, verbatim>

## Grounding
Consumer / Correct-means / Cost-of-wrong

## Scale
Volume / Latency budget / Cost per run + ceiling / Loop bounds.
Tier defaults recorded with provenance where accepted.
Non-functional requirements, and which are load-bearing.

## Observability
What you'd pull up to diagnose a bad run. Redaction requirements, if any.

## Prompt
## Context
## Harness
## Loop
## Graph
## HITL

Each section: the decision, or `DEFERRED — <what would force this later>`.

## Simulation
Three scenarios with turn-by-turn walkthroughs.

## Findings
The table.

## Revisions
What changed in the spec, and why.

## What breaks first
Which component, what the user sees, how you'd notice, the cheap mitigation.

## Measurement
Success metrics with numbers. Known next moves, and what forces each.

## Open questions
Only what genuinely needs a human decision. "None" is a valid answer — do not
manufacture questions to fill the section.
```

Hand off with: `/workflow-research` to investigate the open questions, or
`/workflow-plan` directly if there are none.
