# design-initiative — archived 2026-08-14

Nothing moved. No live skill inherits this content.

## Why

The skill is well-written — the milestone rules below are the best statement of that idea
in the repo — but it targets tooling galactus does not use. Its Phase 2 Section 6 is a
**Linear hierarchy** (Initiative → Project → Milestone → Issue), and its exit hands off to
`/doc-to-linear-tickets`, **a skill that does not exist in this repo**. Galactus tracks
work in GitHub Issues.

Like `design-sprint`, it is the PM/EM lens: an initiative already named and agreed, broken
into milestones and a t-shirt-sized backlog with owners and a critical path. Galactus has
no roadmap to decompose. That work belongs on guacamayo's board.

## Worth keeping if this is ever revived

The milestone discipline is the salvageable part, and it is tool-independent:

- **A milestone is a verifiable system state, not a bundle of work.** Done-conditions are
  observations (*"a service key returns real rows from `GET /kb/search`"*), never activity
  (*"API built"*). If it names ongoing activity it is an initiative or a project, not a
  milestone.
- **One verifiable done-condition per milestone.** Two unrelated ones means split it.
- **Only externally-driven milestones get calendar dates**; the rest get sequence
  positions. Fake dates on gated work hide the real critical path, which is the gate.
- **Defer rather than stretch** — fewer verifiable milestones beat many vague ones.
- **Every task traces to at least one failure mode**, and a task that fits no milestone
  means either backlog scope creep or a missing checkpoint — resolve, do not orphan.

If milestone decomposition is ever needed here, fold these five rules into `/proto-plan`
rather than reviving the skill; the Linear-specific two-thirds is what made it unusable.
