---
name: design-prototype
description: "Designer role — spike/explore before committing. Use when the question is feasibility, not implementation: 'does this work?'. Fast validation mode: state the question, write minimum code, observe, decide (adopt/adapt/discard). Triggers on: 'prototype this', 'spike on X', 'try this approach', 'explore this API', 'validate this idea', 'feasibility check'."
disable-model-invocation: true
allowed-tools: Read Bash Grep Glob Write WebSearch WebFetch
---

Prototype or explore $ARGUMENTS. Apply all rules below strictly.

## Purpose
- Goal is fast learning and validation, not production-ready code
- Answer a specific question: "Does this work?", "How does this API behave?", "Is this approach feasible?"
- State the question being answered before writing code

## Rules
- No TDD — tests are optional during prototyping
- BCE layering and strict architecture rules are relaxed
- Shortcuts are allowed (hardcoded values, minimal error handling, skipped validation)
- Do not refactor or clean up existing production code as part of prototyping
- Keep prototype code clearly separated — use a `prototype/` directory or clearly mark files as experimental

## Workflow
1. Clarify the question or hypothesis being tested
2. Write the minimum code needed to answer it
3. Run it and observe the result
4. Document findings: what worked, what didn't, what was surprising
5. Decide together with the user: adopt (rewrite properly), adapt (refactor into production), or discard

## Output
- After prototyping, summarize findings as a comment in ROADMAP.md or as an ADR if the finding influences architecture
- If the prototype is adopted, promote it with `/workflow-plan` — write the plan against
  the working spike, then `/workflow-execute`. Do not rewrite from scratch; the spike is
  the specification.
- Never merge prototype code directly into production paths

## Routing
- First word `quick-start` → **Quick-start mode** (below): time-boxed spike loop for
  take-homes and live exercises. Serial by default.
- Otherwise → default prototyping mode (rules above).

## Quick-start mode

Time-boxed spike. Narrate every stage aloud — this mode is designed to be watched.

| Stage | Output | Checkpoint |
|---|---|---|
| 1. Frame | The one question, plus the stage-1 intake below | Two roots answered, derivations read back and corrected |
| 2. Scout | What's known / what must be decided | **Fan out only here**, only if multi-angle |
| 3. Decide | The no-list before the yes-list | Explicit human sign-off — do not proceed on silence |
| 4. Contract | The failing test(s) that define "done" — count set by the dial below | **Red.** Name the input that makes it fail, then show it failing |
| 5. Skeleton | Thinnest end-to-end slice that passes it | Green, or the stage failed |
| 6. Thicken | Real components replacing fakes, one at a time | After each swap, still green |
| 7. Review | What worked, what's missing, what you'd do next | Say the omissions out loud |

### Stage 1 intake — ask two, show the rest

Tiered per `patterns/asked-vs-derived-scaffold-variables`. Do **not** run Copier; that
was measured at ~12 min against ~2 min for this. Total budget: 2 minutes.

**Ask out loud (high blast radius):**

1. **Which archetype, and what are you building?** — Information Retrieval · Document
   Generation · Workflow Automation · Conversational Interface. Pick where the *hard
   problem* lives, not where the most code goes. This is the derivation root; everything
   below keys off it.
2. **Who uses it?** — internal team · customers · developers · public API. Seeds both
   deployment target and data sensitivity.
3. **Any decision whose silent default fails irreversibly.** Always includes human
   approval before acting ("independent of every other answer," so it cannot be derived
   even in principle). If the answer to (2) implies customer data, probe once: *anything
   regulated — health, financial, minors?*

**Show, don't ask (cheap to reverse — correct in one word):**

> "Document generation for internal review, so I'm setting: pipeline not agent-shaped,
> no retrieval, stateless, local-only deploy, notional cloud. Correct anything wrong."

Derived this way: agent-shaped y/n, tools, memory, external systems, deployment target.
A wrong guess here costs one line of a design doc — which is exactly why it is shown
rather than asked.

**Two rules from the source pattern:**

- *"'I don't know' never blocks the render."* An unknown is recorded with the trigger that
  would resolve it, and the spike proceeds. Unknowns are not blockers; unexamined
  assumptions are.
- Never present a non-decision as a choice. If something ships regardless, say that it
  ships — do not offer it as an option.

**Rules**
- Serial by default. Parallel agents are faster and unwatchable; on a recorded exercise
  the narration IS the deliverable.
- The no-list is a first-class artifact. What you declined to build, and why, is the
  strongest evidence of judgment available in a time-boxed exercise.
- **Test first, and show the red.** Stage 4 writes the assertion that defines done, run
  before the implementation exists. Never write the implementation first, and never
  "fix" a failing test by loosening it without saying why out loud — a test you wrote
  and then had to defend is the strongest judgment signal in the whole exercise.
- **Scale the contract to the window — it is a dial, not a constant.** Under ~1 h: 2–3
  tests, happy path + one boundary + one failure mode. 1–3 h: add malformed-input and
  error paths. Past ~3 h, or uncapped: a real suite, named so the intent reads without
  the implementation. Writing a full suite in a 60-minute exercise fails the exercise;
  writing three tests in an uncapped one under-delivers.
- **Say what would make it fail, before you make it pass.** One sentence naming the input
  that breaks the assertion. This is the guardrail against the failure mode of writing
  both test and implementation: a test asserting what the code already does cannot answer
  that question, so asking it out loud catches the tautology while it is still cheap.
  Corollary: do not edit the test and the implementation in the same unreviewed step.
- Every stage announces its time budget before it starts, and reports the overrun if any.
- Never skip stage 3 or stage 4. A spike without a decision point is just typing; a spike
  without a contract is just a demo. Stage 4 may shrink to a single test; it may not
  shrink to zero.

### Observed — galactus, 2026-08-08

First full run of this loop (ML6 take-home, ~2,350 source lines / 2,810 test lines,
uncapped across four sessions). Recorded here because the rules above were written
*before* the run, and two of them were bets.

**Derivation corrections: 0 of 5.** Archetype (Document Generation), agent-shaped (no),
retrieval (none), state (stateless), deploy (local + notional cloud) were all shown
rather than asked, and none was corrected. Per the tier rule's own test, that is evidence
the boundary was drawn correctly — those five had low blast radius and belonged in the
shown tier. **Do not shrink the block to a single sentence yet.** Zero corrections across
one run is consistent with a well-drawn boundary and equally consistent with an agreeable
reviewer; the count is the signal, and one sample does not establish it. Record the count
again next run and shrink only if it stays at zero on a second, differently-shaped case.

The asked tier is a different story. Of the three asked roots, **two changed a decision
and one was ceremony**: archetype drove the whole build shape, and the
irreversible-default question surfaced the API-key handling that kept the repo private
and unpushed until DoD. "Who uses it" changed nothing — the answer was implied by the
case document before it was asked. Keep it anyway: it costs one sentence, and it is only
redundant when the brief is unusually explicit about its audience.

**Contract stage under a time cap: not yet tested.** This run was uncapped, so the
red-test-first ordering held under the easiest possible conditions. The honest reading is
that the ordering is *validated as useful* and *unvalidated under pressure* — the
discipline's whole claim is that it survives when the clock bites, and that claim still
has no evidence. Treat the stage as unproven at 60–90 min until a capped run says
otherwise.

What the uncapped run does establish: **the test-first ordering paid for itself twice.**
The validator was green against its full test set before any LLM existed, and two genuine
defects surfaced from tests written first — both fixed in the source, not the test. A
third arrived late and is the sharper lesson: a role-separation bug survived a 259-test
green suite because every test covered the store layer, where the filter worked, and none
covered the API layer, where the filter was never passed. **A green suite is evidence
about the paths you tested and silent about the rest** — which is an argument for naming
the failing input out loud (the guardrail above), since that question is what exposes an
untested seam.

Also confirmed under the "same uninspected step" corollary: after fixing that bug, the
new regression test was re-run against the *reverted* fix to check it actually failed.
It did. Writing both test and implementation makes that check cheap and non-optional —
without it, a test that passes for the wrong reason is indistinguishable from one that
passes for the right one.

**Dial calibration: unchanged, with one clarification.** The uncapped run produced 160
test functions (262 cases with parametrization) — comfortably the "real suite" end, and
the thresholds above predicted that correctly. The 60–90 min end remains untested, so the
2–3 test threshold stands as written rather than being adjusted on no evidence.

The clarification the run *did* earn: at the uncapped end, **pick the tests by
architectural seam, not by count.** The suite that mattered was not large, it was
positioned — validator, fallback, and repair loop carry the contract, so they carry the
tests. The role bug is the counter-example that proves the point: 259 tests weighted
toward layers that already worked, and none at the seam that didn't.

### What to build first

The non-obvious call from the galactus run, and it generalizes past this one case.

**When the output must satisfy a constraint, build the checker before the generator.**

The instinct is to get something generating and then bolt validation on. Inverting it
pays three times over:

1. **The validator is a pure function** — no model, no network, no cost. It can be fully
   tested in seconds while the generator is still notional, so the expensive component is
   the last thing you build and the only thing you debug.
2. **It defines "done" precisely** before anything can rationalize a weaker definition.
   You cannot quietly relax a contract you wrote first and watched fail.
3. **It converts a vague failure into a repair instruction.** A validator that returns
   *"shorten 'headline' from 14 to at most 9 words"* hands the generator a mechanical fix.
   A generator built first tends to produce *"that didn't fit, try again"* — which is a
   retry, not a repair, and retries do not converge.

The general shape: **whatever decides whether the output is acceptable should exist,
and should be red, before whatever produces the output.** It applies to any
constrained-output problem — schema conformance, length limits, format compliance,
tool-call validity — and it is the reason the deterministic layer, not the model, is
what makes the guarantee.
