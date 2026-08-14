# design-sprint — archived 2026-08-14

Nothing moved. No live skill inherits this content.

## Why

50 lines, of which ~13 were the shared repo-targeting preamble. What remained was a
six-phase IDEO/HMW pass:

1. Deconstruct → 2. HMW statements → 3. Technical solutions → 4. Workstream clustering →
5. Initiative definition → 6. Dependency mapping (HTML artifact)

Phases 1–5 are a thinner version of the problem framing `/scope-poc` already does at 460
lines, against the same blank-page situation. Phase 6 emitted an HTML dependency artifact
that nothing in this repo consumes.

The deeper reason is the lens. `design-sprint` speaks to a **PM running a roadmap** —
5–7 named initiatives, workstream clusters by role (WHERE-BE, WHERE-AI, WHERE-data,
WHERE-Ops), cross-initiative dependency maps. Galactus is a prototyping showcase and has
no such role. That work belongs on guacamayo's board.

## Worth keeping if this is ever revived

- The **WHERE-voice clustering rule**: a realtime/duplex interaction gets its own
  workstream rather than folding into WHERE-AI, because the audio loop and the reasoning
  graph have different owners and different failure modes, and merging them produces an
  initiative nobody can scope. That reasoning is preserved in `.claude/specs/agent-voice.md`
  independent of this skill.
- The quality constraint *"no generic outputs that could apply to anything"* — a good
  test, and one this skill's own phases 1–5 arguably failed.
