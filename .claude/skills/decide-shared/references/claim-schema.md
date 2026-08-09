# Claim schema

Every capability skill in the frame/decide family emits claims in this format. It is the
`finding-schema.md` of the decide family — same purpose, different unit. A review reporter
emits findings about code that exists; a capability emits claims about a decision that has
not been made yet.

## Schema

```yaml
id: <source>-<NNN>                # AA-001 (assumption-audit), WG-001 (war-game)
source: assumption-audit | war-game
job: frame | size | decide | design | derisk | report

claim:
  title: one-line summary
  statement: the assumption or threat, stated as a falsifiable proposition
  basis: what in the plan/spec/code led here (quote or file:line)
  if_wrong: what breaks, concretely — not "problems" but which step fails and how

confidence: certain | likely | speculative | unknown
  # how sure we are the claim holds

decision_impact: fatal | costly | recoverable | cosmetic
  # what it means for the decision if the claim holds

check:
  method: the cheapest thing that would settle it
  cost: minutes | hours | days | unknowable-before-building
  settles: what result would falsify it   # required — see below

recommendation:
  action: test | mitigate | accept | descope | escalate
  description: what to do
```

## The two axes are orthogonal

`confidence` is how sure you are. `decision_impact` is how much it matters. They are
independent, and collapsing them into one severity is the same bug `review-shared` warns
about, failing in the same direction: **speculative-but-fatal claims get downgraded**
because nobody could confirm them.

A `speculative` / `fatal` claim is the most valuable output either of these skills
produces. "We are assuming the vendor API is idempotent, we have not checked, and if it
is not, the whole retry design is wrong" is exactly the claim that should stop work —
*because* it is unresolved, not despite it.

| | `fatal` | `costly` | `recoverable` | `cosmetic` |
|---|---|---|---|---|
| `certain` | Stop. Redesign. | Budget for it now | Note it | Ignore |
| `likely` | Check before building | Check before building | Note it | Ignore |
| `speculative` | **Check first — highest value** | Timebox a check | Accept | Ignore |
| `unknown` | Name it as an open question | Name it | Accept | Ignore |

The diagonal is the trap: teams work the `certain` column because it is legible, and the
`speculative`/`fatal` cell — the one that kills projects — reads as "we're not sure, let's
move on."

## `settles` is required

Every claim must name what result would falsify it. A claim that cannot be falsified is
not a claim; it is a worry, and worries accumulate without ever resolving.

This is the acceptance-baseline rule from the harness layer, applied to analysis rather
than code: **a criterion vague enough that it cannot fail is not a criterion.** "Validate
the assumption" fails this. "Send two identical POSTs with the same idempotency key and
confirm one charge" passes.

If a claim genuinely cannot be settled before building, `check.cost` is
`unknowable-before-building` and the recommendation is `mitigate` or `escalate` — never
`test`. Saying so is honest; inventing a fake check is worse than admitting the gap.

## Ranking

Claims are ranked by `decision_impact` first, `confidence` second — impact-major,
confidence-minor. Ranking by confidence first buries the speculative/fatal cell, which
defeats the purpose of running the skill at all.

Within equal impact and confidence, cheaper checks rank higher: a five-minute check that
could invalidate the design should be run before a two-day one.
