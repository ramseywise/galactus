---
name: design-sprint
description: "PM role — blank-page problem framing. Use when starting a feature or initiative from scratch: 'what should we build and why?'. Runs IDEO/HMW methodology: deconstruct problems → HMW statements → technical solutions → workstream clusters → initiative backlog. Triggers on: 'start a new feature', 'run a design sprint', 'define what to build for X', 'generate HMW statements', 'blank-page initiative'."
disable-model-invocation: true
allowed-tools: Read Bash Grep Glob WebSearch Write
---

## Target repo

Same convention as the phase protocols (research/plan/execute/code-review): a
`repo:<name-or-path>` token in `$ARGUMENTS` targets another workspace repo (bare name
resolves to `~/workspace/<name>`); all repo-relative paths and git/test commands resolve
against it, and artifacts land in the TARGET repo. No token → the cwd's repo; in a
meta/workspace-root session, ask rather than defaulting.

Run a full design sprint using IDEO / Stanford d.school HMW methodology for: `$ARGUMENTS`

## Inputs (ask if not provided)

1. **Use case** — product, feature, or problem space
2. **Known constraints** — market, language, tech stack, team roles
3. **Existing data** — research, ticket data, prototypes, production metrics
4. **Scope boundary** — what is explicitly out of scope

## Phases

1. **Deconstruct** — problems, pain points, insights, opportunities. Table: Area | Finding | Implication.
2. **HMW statements** — reframe each finding as a How Might We question. Outcome-oriented, not solution-prescribing.
3. **Technical solutions** — for each HMW: what's required + concrete named technical approach.
4. **Workstream clustering** — group by WHO (FE), WHERE-BE, WHERE-AI, WHERE-data, WHY (observability), WHERE-Ops. Note cross-cluster items.
5. **Initiative definition** — 5-7 named initiatives. Each: name, one-sentence goal, components, roles, cross-initiative dependencies. First initiative has zero external deps.
6. **Dependency mapping** — HTML artifact per initiative: cards with title, description, needs, enables, role badge. Color-coded by role.

If any HMW implies a realtime/duplex interaction — someone speaking to the system and
interrupting it — the clustering in Phase 4 gains a WHERE-voice workstream that owns
turn-taking, barge-in, and the latency budget. It is not part of WHERE-AI: the audio
loop and the reasoning graph have different owners and different failure modes, and
merging them produces an initiative nobody can scope. See `agent-voice.md`, and
`design-system` §4b for the layer model.

## Quality constraints

- Be specific to the use case — no generic outputs that could apply to anything
- Use real numbers, benchmarks, and named tools where they exist
- Cite analogous systems or prior art
- If multilingual requirements exist, call them out as day-one decisions

---

**Next step**: `/design-initiative <initiative-name>` for each named initiative once the workstream list is agreed. `design-sprint` answers *what* to build; `design-initiative` answers *how* — failure modes, backward mapping, task backlog.
