---
name: assumption-audit
description: "Find the load-bearing guesses in a plan, spec, or design before they are built on. Names each assumption, rates it by confidence and decision impact, and gives the cheapest check that would settle it. Callable at any point — before research, after planning, mid-execute when something feels wrong. Triggers on: 'what are we assuming', 'audit the assumptions', 'what could make this wrong', 'stress the premises', '/assumption-audit'."
job: frame
allowed-tools: Read Grep Glob Bash Write
---

You are auditing assumptions. The output is a ranked list of the guesses a plan rests on,
each with the cheapest check that would settle it.

**Read `decide-shared/references/claim-schema.md` before emitting anything.** Claims use
its two orthogonal axes; collapsing them is the failure mode this skill exists to avoid.

**Report only. Never edit code, never edit the plan.** This skill finds the guesses; a
human decides what to do about them. It does not advance `Status:`.

## Input

`$ARGUMENTS` is a plan doc path, a spec path, a slug, or a description in the user's
words. If it names a file, read it. If it names nothing, audit the current session's
working plan — and if there isn't one, ask what to audit rather than inventing a target.

An empty or unreadable target is an **error, not an empty audit**. Say so and stop. Zero
assumptions found reads as "this plan is solid," which is the most dangerous possible
false negative from this skill in particular.

---

## Stage 1 — Extract, don't evaluate

Read the target and list every proposition it treats as settled. Extract first, judge
later: mixing the two makes you skip the assumptions that feel obviously true, and those
are the load-bearing ones.

Four places assumptions hide, in rough order of how often they turn out to be wrong:

| Source | Looks like | Example |
|---|---|---|
| **Stated as fact** | A declarative with no citation | "The API is idempotent" |
| **Implied by design** | Only makes sense if X holds | A retry loop implies idempotency |
| **Inherited** | Carried from an earlier doc unexamined | "As established in the spec…" |
| **Absent** | A question the plan never asks | No mention of what happens at scale |

The fourth is the hardest and the most valuable. A plan that never mentions concurrency
is asserting that concurrency does not matter — silently. **Silence is an assumption with
no author.**

For each, quote the line or name the file:line that generated it. An assumption you
cannot trace back is one you invented; drop it.

## Stage 2 — Find the load-bearing ones

Most assumptions do not matter. The audit is worthless if it returns forty items of equal
weight — that is a list, not an analysis.

For each extracted assumption, ask the counterfactual directly: **if this is false, what
in the plan stops working?**

- Nothing stops → not load-bearing. Drop it from the report entirely.
- One step needs rework → `recoverable`
- Several steps need rework, or a rewrite of one component → `costly`
- The approach itself is wrong → `fatal`

Answer with the *specific step*, not "problems." "Step 4's caching layer returns stale
reads" is an answer; "reliability issues" is not.

Then rate `confidence` independently — how sure are we the assumption *holds*, not how
sure we are it matters. Keep the axes separate. Read the grid in `claim-schema.md`; the
`speculative` / `fatal` cell is the highest-value output of this skill and the one most
likely to be rationalised away.

## Stage 3 — Name the cheapest check

For every surviving assumption, name what would settle it and what it would cost.

The bar is the acceptance-baseline rule: **a check vague enough that it cannot fail is
not a check.** "Confirm the API behaves correctly" fails. "POST twice with the same
idempotency key, assert one charge" passes.

Prefer, in order:

1. **Read something** — the vendor docs, the source, an existing test. Minutes.
2. **Grep the codebase** — does this pattern already exist here, and does it work?
3. **Run something small** — one script, one API call against a sandbox.
4. **Build the risky part first** — reorder the plan so the assumption is tested by step
   one instead of step nine.

Option 4 is the one people forget, and it is often free: the same work in a different
order, where failure surfaces on day one instead of day nine.

Where nothing settles it before building, say `unknowable-before-building` and recommend
`mitigate` or `escalate`. **Never invent a check to fill the field** — a fake check is
worse than an admitted gap, because it gets ticked off.

## Stage 4 — Report

Rank by `decision_impact` first, `confidence` second, cheapest check as the tiebreak.
Emit claims per the schema.

Write to `.claude/docs/decisions/YYYY-MM-DD-<slug>-assumptions.md` if the target was a
plan or spec file; return in chat if the target was a verbal description. Never write
into the plan doc itself — the plan is the pipeline's bus, and this is not a phase.

Close with two things, both required:

**The one to check first.** A single named assumption with its check. If a report ends
with fifteen equal items, nobody checks any of them.

**What you could not see.** Files not read, systems with no local source, domains outside
your knowledge. A clean audit that does not state its blind spots is indistinguishable
from an audit that failed to run.

---

## Failure modes of this skill

- **Auditing wording instead of substance.** "The plan says 'should' not 'must'" is not
  an assumption. If rewording it changes nothing about what gets built, it does not go in
  the report.
- **Listing risks and calling them assumptions.** "The vendor might go down" is a risk —
  that is `/war-game`'s job. An assumption is something the plan currently treats as
  *settled* that is not. The test: could you write it as "we are assuming X"?
- **Padding to look thorough.** Six real load-bearing assumptions beat thirty items of
  which six are real, because the thirty-item version gets skimmed.
