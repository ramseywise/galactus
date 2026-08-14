# project-discovery — archived 2026-08-14

Folded into `proto-scope` as **discovery mode**. Run it with `/proto-scope discovery`.

## What moved

All five steps, plus the tone contract, into `.claude/skills/proto-scope/SKILL.md` under
`## Discovery mode`:

- **The tone contract** — plain language over jargon ("the AI finds answers in documents",
  not "RAG pipeline"), concrete nonprofit examples, choices as cards with trade-offs,
  narrow-by-demo when they are unsure, and never make them feel there is a right answer
  they are missing. This is the reason the mode exists separately rather than being
  deleted: the design interview assumes vocabulary a first-time volunteer may not have.
- **Step 0 intake** (who is in the room, setup, team working rules), **step 1 pain-point
  elicitation** with the specificity test, **step 2 archetype matching** including the
  duplex-voice probe, **step 3 complexity tiers**, **step 4 must-demonstrate items** with
  the vague-to-demonstrable reframing.
- **`reference/`** — all six files (`archetype-selection.md`, `agent-orchestration.md`,
  `data-pipeline-patterns.md`, `deployment-topology.md`, `eval-approaches.md`,
  `integration-patterns.md`) now live at `.claude/skills/proto-scope/reference/`.
  `proto-scope` had no reference directory before this fold; these are load-bearing for
  archetype matching in both modes.

## Why fold rather than keep

Both skills ran the same intake conversation at different vocabulary levels, against the
same situation (a new project, nothing written down). Two skills meant the operator had to
know which one they needed *before* the conversation that establishes it — and the honest
answer is usually "start plain, get more precise", which is one skill run twice, not two
skills.

## What did not move

The `/project-discovery` → `/scope-poc` → `/project-genesis` → copier chain in its header.
`project-genesis` was archived the same day (galactus has no `copier.yaml`), and the first
two collapsed into one skill, so the chain is now `/proto-scope discovery` →
`/proto-scope` → `/proto-design`.
