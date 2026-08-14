# design-prototype — archived 2026-08-14

Partially folded into `proto-research`. This is the only archived skill whose content
still runs anywhere.

## What moved

Both went into `.claude/skills/proto-research/SKILL.md` under `## Track routing`:

- **The ML-vs-agentic routing rule**, including the asymmetric-cost argument: an ML
  problem routed to the agent track yields a confident metric nobody checked, because the
  agent track has no stage that catches a leak; an agent problem routed to the ML track
  merely runs a profiling stage that finds nothing. Plus *"fitting a model is the tell —
  calling a model is not"* and the instruction to ask rather than default when ambiguous.
- **The ML quick-start contract** — profile before framing (`/ml-transform`), settle
  `(family, output)` (`/ml-select`), and the stage-4 pair: a baseline metric named before
  it is computed, and a passing leakage check. Plus *show the red first* and *an
  implausibly good first score is a finding, not a result*.

`proto-research` is now the only writer of `Track: {ml, agent}`, which
`plan_status_validate.sh` already validated but nothing set.

## What did not move, and why

- **Default prototyping mode** — "clarify the question, write minimum code, observe,
  decide adopt/adapt/discard" is what `/proto-research` → `/proto-plan` already do. Its
  own Output section handed off to `/proto-plan` → `/proto-execute`.
- **The seven-stage quick-start loop** — the stage table, the stage-1 intake tiering
  (asked vs shown), and the contract dial. Not carried over because no live skill runs a
  time-boxed watched spike. If galactus ever needs a take-home/live-exercise mode, this is
  the prose to start from — it is the most specific thing in the archive.
- **The 2026-08-08 observed run** — the ML6 take-home retrospective: 0 of 5 derivation
  corrections, the role-separation bug that survived a 259-test green suite, and the
  "pick tests by architectural seam, not by count" clarification. Kept as evidence; those
  numbers cannot be regenerated.
- **"Build the checker before the generator"** — the constrained-output inversion. Still
  true, still unhomed; it belongs in a spec rather than a skill.
