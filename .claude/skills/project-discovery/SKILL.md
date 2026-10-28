---
name: project-discovery
description: >
  Guided discovery conversation for new AI project ideas — meets volunteers where
  they are ("what pain does this nonprofit have?") and produces a lightweight Project
  Profile before handing off to /scope-poc. Triggers on: "new project idea",
  "nonprofit has a problem", "I want to build something", "project discovery",
  "help me figure out what to build", "/project-discovery", "DSSG project",
  "what should we build for [org]", "I have an idea". Use this BEFORE /scope-poc
  when the user hasn't yet articulated actors, system boundaries, or technical
  approach — especially for DSSG volunteers starting from a pain point rather than
  a design. Does NOT scaffold infrastructure — that's /project-genesis downstream.
---

# /project-discovery

Upstream discovery conversation that runs **before** `/scope-poc`. Produces a
Project Profile — lighter than DESIGN.md, focused on what's painful and what
would demonstrate value. Designed for volunteers who may not have system design
vocabulary yet.

**Pipeline:** `/project-discovery` → `/scope-poc` → `/project-genesis` → copier

This skill answers: **What's worth building?**
`/scope-poc` answers: **What exactly is it?**
`/project-genesis` answers: **How do we scaffold it?**

## Usage

```
/project-discovery [--output path/to/PROJECT-PROFILE.md]
```

| Arg | Default | Description |
|-----|---------|-------------|
| `--output` | `.claude/docs/PROJECT-PROFILE.md` | Where to write the profile artifact |

---

## Tone

This is a conversation, not a form. The user may be a first-time volunteer who's
never built an AI system. Meet them where they are:

- Use plain language. Say "the AI finds answers in documents" not "RAG pipeline."
- Offer concrete examples from nonprofit contexts.
- Present choices as cards with trade-offs, not open questions that require expertise.
- If they're unsure, narrow it down by asking what the demo should SHOW.
- Never make them feel like they need to know the "right answer" — there isn't one.

---

## Steps

### Step 0 — Intake: who's in the room

Before the project, the people. Two minutes, conversational — not a form:

- **Who are you?** Role and background (engineer, data scientist, designer,
  domain expert, first-time volunteer). Calibrates every later explanation.
- **What's your setup?** OS, editor, languages they're comfortable in, tools
  they already use daily (Google Workspace, Notion, Slack, ...).
- **Team working rules?** Anything the team has already agreed on: review
  requirements, branch conventions, meeting cadence, "never touch X".

Record the answers in the profile's Intake section. Downstream: tooling
preferences and team rules become the rendered project's `CLAUDE.md`
conventions and hard rules at `/project-genesis` time; the people named here
seed DESIGN.md's actor table in `/scope-poc`.

On re-entry (a profile already exists), skip what's answered and fill only
what's blank — same as every other step.

### Step 1 — Pain point elicitation

Open with: **"Tell me about the nonprofit you're working with. What's painful for
them today — what takes too long, falls through cracks, or frustrates people?"**

Follow-up prompts (use whichever fits):
- "Can you give me a specific example — like, last week, what happened?"
- "Who does this work today? How much time does it take them?"
- "What happens when it goes wrong — what's the cost?"

**Goal:** Get a concrete, specific problem statement with a named actor and a
real-world consequence. Not "they need better data management" but "their intake
coordinator spends 3 hours per new client looking up which programs they qualify for."

### Step 2 — Archetype matching

Based on the pain point, read `reference/archetype-selection.md` and present the
1-2 archetypes that best match. Show each as a brief card:

> **[Archetype Name]**
> [One sentence: what it does]
> [One sentence: why it fits their situation]
> Example: [concrete similar project]

Ask: "Does either of these sound like what you're imagining? Or is it something
different?" If they're unsure, ask what the 5-minute demo would show — the answer
usually maps to exactly one archetype.

If the pain point spans archetypes (e.g., "find regulations AND draft a summary
letter"), name the primary (where the hard problem lives) and note the secondary
as a phase-2 add-on.

### Step 3 — Complexity budget

Ask: **"How much time and people do you have?"**

Present three tiers (read from `reference/archetype-selection.md`'s complexity section):

| Tier | Time | Team | What's realistic |
|------|------|------|-----------------|
| **Weekend sprint** | 1-2 days focused | 1-2 people | Working prototype, one happy path, no auth/deploy |
| **Multi-sprint** | 2-6 weeks | 2-4 people | Production-ready core feature, basic eval, deployed somewhere |
| **Semester** | 8-12 weeks | 3-6 people | Full system with auth, multi-tenancy, eval suite, handoff docs |

Follow up: "Are there hard deadlines — a demo day, a board presentation, a cohort end date?"

### Step 4 — Must-demonstrate items

Ask: **"Imagine you're showing this to the nonprofit in 5 minutes. What do they
need to see working to say 'yes, this is useful'?"**

Push for 3-5 concrete items. Reframe vague answers into demonstrable features:
- "Better data access" → "A volunteer types a question and gets the right regulation back in 3 seconds"
- "Streamlined intake" → "A new client fills out a form and the system auto-suggests 3 matching programs"
- "Reporting" → "A staff member clicks 'generate report' and gets a draft they can edit and send"

### Step 5 — Constraints and capacity

Ask about:
- **Team composition:** "How many people? What's their background — engineering, data science, design, domain expert?" (Maps to: which archetype they can realistically build.)
- **Hours:** "How many hours per week can the team dedicate?"
- **Tech constraints:** "Does the org already use specific tools — Google Workspace, Salesforce, a specific database? Anything we must integrate with?"
- **Non-goals:** "What's explicitly NOT your problem to solve — even if someone suggests it later?"

### Step 6 — Confirm and write Project Profile

Summarize what you've learned in the Project Profile format (see below). Present
it to the user and get explicit confirmation before writing.

Derive the "Copier Hints" section by mapping:
- Archetype → `project_type` (see `reference/archetype-selection.md` mapping table)
- Complexity → `deployment_target` (weekend=local, multi-sprint=docker/cloud, semester=cloud/serverless)
- External systems mentioned → `external_systems` values
- Team has TS expertise + frontend need → `primary_backend_language`

Write to `--output` path. Tell the user: **"Run `/scope-poc` next — it'll read
this profile and skip the questions you've already answered. It will ask about
actors, evaluation, and data classification to produce a full DESIGN.md."**

---

## Project Profile format

```markdown
# Project Profile — [project_name]

**Date:** YYYY-MM-DD
**Status:** Discovery / Ready-for-scoping

---

## Intake

- **Volunteer(s):** [name / role / background — who's building this]
- **Dev setup & tooling preferences:** [OS, editor, languages, daily tools]
- **Team rules:** [agreed conventions — reviews, branches, comms — or "none yet"]

## The Pain Point

[2-3 sentences: who has this problem, what they do today, why it's painful.
Use the user's own words where possible.]

## Nonprofit / Organization

- **Name:** [org name]
- **Domain:** [education / legal aid / arts / health / housing / workforce / civic tech / other]
- **Existing tech:** [what they use today — Google Sheets, Salesforce, paper forms, nothing]

## Archetype

**[Information Retrieval | Document Generation | Workflow Automation | Conversational Interface]**

[1 sentence: why this archetype fits this pain point]

## Must-Demonstrate (5-min demo)

1. [concrete item — what the user sees]
2. [concrete item]
3. [concrete item]
4. [optional]
5. [optional]

## Capacity Constraints

- **Team:** [N people, M hours/week, key skills]
- **Timeline:** [weekend sprint | multi-sprint (N weeks) | semester]
- **Hard deadlines:** [date + event, or "none"]
- **Integrations needed:** [named systems from Step 5]

## Explicitly Out of Scope

- [item — named explicitly to prevent scope creep]
- [item]

## Copier Hints (derived from discovery)

| Parameter | Suggested value | Rationale |
|-----------|----------------|-----------|
| `project_type` | [value] | [from archetype mapping] |
| `deployment_target` | [value] | [from complexity budget] |
| `primary_backend_language` | [value] | [from team skills] |
| `external_systems` | [values] | [from integrations needed] |
| `primary_users` | [value] | [from actors in pain point] |

[Additional hints if clearly determinable from the conversation — leave blank
rather than guess. /scope-poc will ask about anything not listed here.]
```

---

## Quality constraints

- **Concrete over abstract:** Every field in the profile must reference something
  the user actually said, not a generalization. "They track 200 cases in a
  spreadsheet" not "they have data management challenges."
- **One archetype:** Don't hedge with "a mix of retrieval and generation." Pick the
  primary. Note the secondary as a phase-2 consideration.
- **Honest complexity:** If the team has 2 people and 4 hours/week, don't suggest a
  semester-scope system. Match ambition to capacity.
- **No premature tech choices:** The profile should NOT name LangGraph, ADK, Vercel,
  or any framework. Those are `/scope-poc` and `/project-genesis` decisions. The
  profile speaks in outcomes and constraints.
- **Copier hints are suggestions:** Mark them as "suggested" not "decided." /scope-poc
  may override based on deeper analysis.
- **"I don't know" is a valid answer everywhere.** Write `unknown` in the profile
  rather than guessing — `/scope-poc` parks unknowns in DESIGN.md's Open Questions
  with a revisit trigger and offers the research path to close them. Re-running this
  skill later fills the gaps; the profile is updated in place, never started over.

---

## Notes

- If the user already has a clear design (actors, system boundaries, tech choices),
  skip this skill and go directly to `/scope-poc`. This skill is for the "I have an
  idea but don't know where to start" case.
- DSSG context: if the user mentions DSSG, nonprofit-success-ai, project-mgmt-ai, or
  the engagement lifecycle, note it in the profile. `/scope-poc` has specific DSSG
  handling that will activate downstream.
- The profile is a living document. Update it if the design conversation (later skills)
  reveals the initial archetype was wrong.

---

**Upstream:** None — this is the entry point for new project ideas.

**Next step:** `/scope-poc` — reads this profile and produces a full DESIGN.md.
