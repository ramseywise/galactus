---
name: scope-poc
description: >
  System design interview for a new AI project — produces DESIGN.md capturing problem,
  actors, MVP scope, and key decisions before handing off to /project-genesis.
  Triggers on: "scope a project", "design interview", "what should we build", "system design", "help me scope", "POC planning", "before genesis", "/scope-poc". Also triggered automatically when a user seems to be starting from scratch without a clear design.

  DSSG-aware: recognizes nonprofit-success-ai (customer portal) and project-mgmt-ai (lifecycle backend) and applies DSSG platform context automatically.
---

# /scope-poc

Upstream design conversation that runs **before** `/project-genesis`. Produces `DESIGN.md`. The two skills in sequence: `/scope-poc` → `/project-genesis` → `copier`.

`/project-genesis` answers HOW to build it (infrastructure). This skill answers WHAT to build. Don't conflate them — many design sessions happen weeks before the scaffold is run.

## Usage

```
/scope-poc [--output path/to/DESIGN.md]
```

| Arg | Default | Description |
|-----|---------|-------------|
| `--output` | `.claude/docs/DESIGN.md` (pre-scaffold) or `DESIGN.md` (in-project) | Where to write the design artifact |

---

## Interview conventions

**"I don't know" is a first-class answer.** Any question below can be answered
*unknown* — park it, don't force a guess:

- Record it in DESIGN.md's Open Questions with a concrete revisit trigger
  ("resolve before sprint 1", "revisit when the first external consumer appears").
- If it's a Key Decision, mark it `Deferred(<trigger>)` with the current default
  choice recorded. A Deferred with a real trigger blocks nothing — not genesis,
  not the G1 gate; a Deferred without one counts as Open (a blocker).
- Offer the research handoff: `/research` (one deep question) or
  `/parallel-research` (breadth-first) to close it, then re-run this skill.

**Re-running is cheap and expected.** This skill is idempotent over DESIGN.md — a
later run reads the existing file, ratifies what's resolved, and interviews only
the gaps. Never start a fresh DESIGN.md when one exists.

## Steps

### Step 0 — Discover what's already decided

**Scan for planning docs before asking anything** — not just DESIGN.md. Check the
workspace for `roadmap.md`, `.claude/docs/milestones/*.md`, `.claude/docs/plans/*.md`,
and any sequencing/exec-summary docs. Milestone files frequently contain the literal
scaffold parameters (a real dry-run found `vector_backend=postgres` and
`primary_chat_agent=lg_agent` written verbatim in a milestone's "done when"). Treat
these as pre-answered sources with the same authority as an existing DESIGN.md.

**Ratify inherited decisions — don't silently adopt them.** For every decision a doc
pre-answers, surface it as a one-line checkpoint: *"your roadmap resolved X on
\<date\> — confirm, or reopen?"* Skipping the re-interview is right; skipping the
user's consent is not. A user who never said "yes, LangGraph" out loud will not feel
ownership of the scaffold that assumes it — this exact failure was observed in a live
session.

### Step 0.5 — DSSG detection

Before starting the interview, check if the project is a known DSSG platform project.
Signals: the user mentions "DSSG", "nonprofit-success-ai", "project-mgmt-ai", "dssg/",
"customer portal", "hackathon coordination", or the engagement lifecycle stages.

If DSSG platform is detected:
- Skip generic auth/data questions — Supabase Postgres is already the declared stack
- Load the shared context block below (§DSSG context) before starting the interview
- Ask only what's specific to THIS project's slice (stage ownership, actor, AI scope, MVP)
- Acknowledge what's already decided rather than re-deciding it

### Step 0.6 — Consume Project Profile (from /project-discovery)

Scan for `.claude/docs/PROJECT-PROFILE.md` or `PROJECT-PROFILE.md` in the workspace.
If found, this project went through `/project-discovery` upstream — many questions are
already answered.

**Load and map the profile to interview tiers:**

| Profile field | Maps to | Interview tier |
|--------------|---------|----------------|
| "The Pain Point" | Problem statement + current workaround | Tier 1 Q1 (pre-filled) |
| "Nonprofit / Organization" | Actor context | Tier 1 Q2 (partially pre-filled) |
| "Archetype" | AI approach (retrieval/generation/automation/orchestration) | Tier 3 Q7 (pre-filled) |
| "Must-Demonstrate" | MVP scope — thinnest slice | Tier 5 Q12 (pre-filled) |
| "Capacity Constraints" | Operator model, budget, timeline | Tier 4 Q11 (pre-filled) |
| "Explicitly Out of Scope" | POC exclusions | Tier 5 Q14 (pre-filled) |
| "Copier Hints" | Design record — suggestions, not decisions | Informational (verify during interview) |

**For each pre-filled field:** present as a one-line ratification checkpoint:
*"Your discovery session determined [X] — confirm, or reopen?"*

Do NOT silently adopt profile values. The user must explicitly confirm each one,
same discipline as Step 0's ratification of planning docs.

**Questions still asked normally** (not covered by the profile):
- Specific actors and their roles (Tier 1 Q2-3 — profile names the org but not all actors)
- System boundaries and existing integrations (Tier 2 Q4-6)
- Data classification and multi-tenancy (Tier 4 Q9-10)
- Evaluation metrics and naive baseline (Tier 3 Q8, Q8b)
- Top risks (Tier 5 Q13)

The profile is a head start, not a shortcut — it pre-fills the "what" but the "how"
and "constraints" still need the full interview.

### Step 1 — Tier 1: Problem and actors

**If the project is agent-shaped, open with the three-axes disambiguation** — users
reliably collapse these into one anxiety ("should this be a Vercel agent, LangGraph,
or Supabase/Firebase?" — verbatim from a live session). State it plainly before any
technical question, and never bundle a governance gate (budget/approval pending) with
a technical choice in the same question:

| Axis | The question | Typical answers |
|------|--------------|-----------------|
| Agent framework | How the AI code is written | LangGraph / ADK (Python), Vercel AI SDK (TS) |
| Database / identity | Where data lives, who users are | Supabase / Postgres / Firebase |
| Deployment | Where it runs | Vercel (TS frontends), Railway/cloud (Python services), local |

These are independent decisions — say so explicitly.

Have a real conversation (not a rigid checklist read aloud). Cover:

1. **What problem are you solving?**
   - What does someone do today without this system?
   - What does success look like — what would a demo show someone in 5 minutes?

2. **Who are the actors?**
   - Who uses this directly (humans)?
   - What other systems does it interact with?
   - Is there a distinction between internal users (staff/volunteers) and external users (clients)?

3. **What does the AI specifically do?**
   - Is this retrieval (find and surface relevant info), generation (draft/summarize), automation
     (take actions on behalf of a user), or orchestration (coordinate multiple steps)?
   - What does the actor do TODAY for this task, that the AI would do instead or augment?

Skip a question if the answer is obvious from context already given. This is a conversation,
not a form. If they've already said "it's a client portal for nonprofits to track their
engagement status," you know the actor without asking.

### Step 2 — Tier 2: System boundaries

4. **What existing systems does this connect to?**
   - Auth (existing identity provider, or building new?)
   - Data sources (existing DB, documents, APIs)
   - Destinations (where does AI output go — DB write, email, Slack, another system?)
   - If the Actors table (Step 1) has an **external, non-DSSG-staff** row and this project needs its own
     backend (not just retrieval) — name FOIA-Fluent's split-service shape (Next.js on Vercel + FastAPI on
     Railway, Supabase JWT shared identity) as the candidate topology in the summary, the same way the
     DSSG-context block below pre-fills known answers for `nonprofit-success-ai`/`project-mgmt-ai`. This
     maps to `/project-genesis`'s `frontend_backend_topology` question (see §7 table).

5. **Is this a fresh project or layering onto something?**
   - If layering: what already exists and what's off-limits to touch?

6. **Does it need to expose tools to other agents or services?** (→ MCP server)

### Step 3 — Tier 3: AI design

7. **What data does the AI reason over?**
   - Structured records (DB rows)? Unstructured documents (PDFs, transcripts, notes)?
   - Live API data (calendar, email, web)?

7b. **Does the MVP itself need retrieval (RAG)?**
   - Retrieval belongs in THIS project only if the MVP's demo requires finding and
     surfacing stored content. Extraction pipelines, automation, and services that
     read via another system's API usually don't — don't let the scaffold's defaults
     answer this for the user. Record the answer in Key Decisions; it drives whether
     rag_agent and its heavy embedding dependencies belong in the render at all.

8. **How will you evaluate "good"?**
   - Is there a golden set of expected outputs to grade against?
   - Or is quality judged manually / by user feedback?
   - Does quality measurement need to be automated for CI?
   - Capture the answers as concrete metric targets in DESIGN.md's Evaluation table
     (metric, target, how measured) — they become `evals/targets.yaml` in the
     generated project, not just prose.

8b. **What's the naive baseline?**
   - What happens if you build nothing — or solve it with a lookup table, keyword
     search, or a human checklist?
   - What must the AI beat, and by how much, to justify itself? Most AI projects
     fail at planning, not modeling — a project that can't name its baseline
     can't demonstrate value over it.

### Step 4 — Tier 4: Constraints

9. **Data classification:** public / internal / restricted / secret?
   - Any PII or sensitive client data flowing through?

10. **Multi-tenancy:**
    - Must multiple clients/orgs be isolated from each other's data?
    - Is this enforced at the DB layer (RLS) or application layer?

11. **Operator model:**
    - Who runs this after the POC — rotating volunteers, a dedicated team, or the org itself?
    - Budget constraints (free tier only, or paid services acceptable)?

11b. **Load, latency, and spend — the trade-off axes:**
    - Roughly how many users/requests per day at POC, and at the realistic 6-month state?
    - Is there a response time anyone would actually notice — "under 5 seconds" is a
      real answer, so is "it's a batch job, minutes are fine"?
    - Is there a monthly ceiling on API/model spend that must not be crossed?

    **These have tier defaults — offer them rather than forcing a number.** Read the
    complexity tier from PROJECT-PROFILE.md's `Timeline` field if present, else ask:

    | Tier | Load | Latency | Spend ceiling |
    |------|------|---------|---------------|
    | Weekend sprint | demo-scale, <10 users | none — demo tolerance | free tier only |
    | Multi-sprint | tens of users, <1k req/day | name one target (e.g. p95 < 10s) | a real monthly number |
    | Semester | name a real projection | p95 target, stated | a real monthly number, with alerting |

    A volunteer accepting the tier default is a **resolved** answer, not an unknown —
    record it as `<value> (weekend-sprint tier default, unvalidated)` in DESIGN.md's
    Non-Functional Constraints. Do NOT park these as Open Questions; an accepted
    default is a decision, and Open Questions block G1 (§Interview conventions).
    Only park as Open when the user says the number matters *and* they don't know it.

11c. **Observability — what would you need to see when it misbehaves?**
    The scaffold ships tracing; this asks what it's *for*.
    - When someone reports "it gave a wrong answer yesterday," what do you need to
      pull up to diagnose it — the prompt? the retrieved chunks? the tool calls?
    - **If data classification (Q9) is `restricted` or `secret`:** what must be
      redacted before it reaches a trace or a log? This one is not optional —
      DESIGN.md already warns that restricted fields must never be traced raw, and
      a trace backend is scaffolded by default. Same discipline as `human_approval`:
      a silent default here has an irreversible failure mode.

    One or two lines into DESIGN.md's Non-Functional Constraints `Observability:`
    bullet. "Langfuse traces, redact client names and emails" is a complete answer.

### Step 5 — Tier 5: MVP scope

12. **What's the thinnest slice that demonstrates value?**
    - What must be working for someone to say "yes, this is useful"?

13. **What are the top 2–3 risks this POC should validate?**
    (These become the eval suite's primary grading targets.)

13b. **What breaks first?**
    Now that the design is stated, read it back adversarially — name the weaknesses
    before a reviewer does. Two are enough:
    - Which component fails first as usage grows, and what does the failure look
      like to a user (slow? wrong answer? error? silent staleness)?
    - How would you *notice* it — what signal, and who is watching it?
    - What's the cheap mitigation you'd reach for, and is it in POC scope or after?

    This is a design question, not a product-risk question — Q13 asks what the POC
    should *prove*, this asks what the architecture will *cost you*. Answers go to
    DESIGN.md's "What Breaks First" section, not the Evaluation table. "The LLM API
    rate-limits us and requests queue" is a perfectly good POC-tier answer.

14. **What's explicitly OUT of scope for the POC?**
    (Name it explicitly — prevents scope creep during build.)

### Step 6 — Confirm and write DESIGN.md

Summarize what you've learned back to the user in the DESIGN.md structure below. Get explicit
confirmation before writing. If anything feels like a guess rather than something they actually
said, ask directly.

Unknowns never block the write: park each one per §Interview conventions (Open
Questions entry with trigger, or `Deferred(<trigger>)` Key Decision) and write the
DESIGN.md anyway — a design with named gaps beats no design.

Write the DESIGN.md to `--output` (default: `.claude/docs/DESIGN.md` if pre-scaffold,
`DESIGN.md` in the project root if already inside a generated project).

### Step 7 — Hand off to /project-genesis

After writing DESIGN.md, surface the `/project-genesis` answers that are now determinable
from the design:

| DESIGN.md answer | /project-genesis question |
|-----------------|--------------------------|
| AI approach + system shape | `project_type` (drives most other defaults; `existing_repo` = layering-only) |
| Actors | `primary_users`, `primary_chat_agent` |
| External systems to integrate | `external_systems` (seeds integrations, Composio, web research, vector store), `agent_tools` |
| Agent behavior (tools/memory/approval) | `agent_tools`, `agent_memory`, `human_approval` |
| Data classification | `data_sensitivity` |
| Deployment / operator model (budget/scale) | `deployment_target`, `vector_backend` complexity |
| Vector/retrieval needs | `vector_backend` |
| System boundaries (external user + own backend) | `frontend_backend_topology` |
| Optional tooling implied by the design | `optional_features` |
| Evaluation table (metrics + targets) | transcribed into `evals/targets.yaml` after render (see /project-genesis Step 4) |

Tell the user: "Run `/project-genesis` next. Here's what to answer for the infrastructure
questions:" — and list the pre-determined values. Questions still open can be answered
interactively during `/project-genesis`.

---

## DESIGN.md structure

```markdown
# System Design — [project_name]

**Date:** YYYY-MM-DD
**Status:** Draft / Confirmed / In-build

---

## Problem + Success Criteria

[1–2 sentences: what problem, who has it, what's the current workaround]

**POC demo target:** [What does someone see in a 5-minute demo that makes them say yes?]

**Naive baseline:** [What's the non-AI alternative (do nothing / keyword search / manual
process), and what must the AI beat, by how much, to justify itself?]

---

## Actors

| Actor | Type | What they do today | What the AI does for them |
|-------|------|--------------------|--------------------------|
| [name] | [internal/external/system] | [current state] | [AI's role] |

---

## System Context (C4 Level 1)

[One paragraph or lightweight mermaid diagram: people + systems + connections.
Don't draw what doesn't exist yet. Containers and components come later, when you're building.]

---

## MVP Scope

**In:**
- [concrete deliverable]
- [concrete deliverable]

**Out (explicitly):**
- [what we're NOT building in POC]

**Open (decide before sprint 1):**
- [decision that's blocking build but not resolved yet]

---

## Key Decisions

| Decision | Status | Choice | Rationale (chose X over Y, gave up Z) |
|----------|--------|--------|---------------------------------------|
| Auth/identity | Resolved / Open / Deferred(<trigger>) | [choice] | [alternative considered] — chose this because [reason]; accepted cost: [what we gave up] |
| Data model ownership | Resolved / Open / Deferred(<trigger>) | [choice] | [same shape] |
| AI approach (retrieval/gen/automation) | Resolved / Open / Deferred(<trigger>) | [choice] | [same shape] |
| [other] | | | |

**Rationale authoring rule.** A rationale that only records *provenance* ("set at
scaffold time", "from design.yaml") is not a rationale — it says what happened, not
why. Every hand-authored row names at least one real alternative and the cost of not
taking it. If no alternative was genuinely considered, write "no alternative
considered" rather than inventing one; that is itself useful signal at review.
The generated rows between the `design-table` markers are exempt — they are a
rendered view of `design.yaml` and provenance is the correct content there.

Status semantics: `Deferred(<trigger>)` records the default choice now and names
the concrete event that reopens the decision. A Deferred without a real trigger
counts as Open. Open items block the G1 gate; Deferred items don't.

---

## Open Questions

- [question] — *revisit:* [trigger or date] — *close via:* [/research, /parallel-research, or a named person]

---

## Evaluation

| Metric | Target | How measured |
|--------|--------|--------------|
| [e.g. hit_rate] | [e.g. ≥ 0.8] | [e.g. `make eval-heuristic` vs golden set] |
| [risk-derived metric, from Tier 5 Q13] | | |

[These become `evals/targets.yaml` in the generated project — `make eval-gate`
fails when a metric drops below target. Derive at least one row from each of
the top risks named in Step 5, and one from the naive baseline (what margin
over the baseline justifies the AI).]

---

## Non-Functional Constraints

- **Data classification:** [public / internal / restricted / secret]
- **Multi-tenancy:** [required / not required — enforcement mechanism if required]
- **Operator model:** [who runs this, budget, volunteer vs. dedicated]
- **Scale:** [expected load, SLA if any]
```

---

## DSSG platform context (loaded when DSSG detected in Step 0)

These are already decided for DSSG platform projects — do not re-decide them in the interview:

**Shared infrastructure** (neither project owns alone):
- Supabase Postgres — shared DB, `Business` / `Engagement` / `User` tables, RLS from day one
- Engagement lifecycle: `initial_meeting → budgeting → engagement_tracking → hackathon → membership_close`
- Platform API: shared auth check + engagement read/write (API key per calling service)
- Comms sender: triggered by `Engagement.stage` writes, plain transactional email (not n8n)

**Three actor roles** (all projects share these):
- **NPO Client** (external) — nonprofit partner, sees their own engagement status
- **Data Diplomat** (internal) — cohort volunteer, does the grassroots work with NGOs
- **DSSG core volunteer** (internal) — staff/leads, builds and runs the platform

**Per-project scope:**

*nonprofit-success-ai* (customer portal):
- Actor: NPO Client (external-facing)
- Stage ownership: all stages EXCEPT `hackathon` (portal drives `initial_meeting` → `membership_close`)
- Handoff OUT: when `Engagement.stage` transitions to `hackathon`, project-mgmt-ai takes over
- Current state: React 19 + Firebase Auth + Firestore (no backend server)
- Open decision: Firebase vs. Supabase migration — resolve before adding AI features. If resolved toward
  Supabase, the concrete scaffold is `split_service` (Next.js + FastAPI + Supabase JWT, modeled on
  FOIA-Fluent).
- Multi-tenancy: non-negotiable (RLS required from day one)
- AI scope: to be defined — candidates: engagement summaries, stage suggestions, client chat

*project-mgmt-ai* (lifecycle backend / coordination service):
- Actor: DSSG core volunteers + Data Diplomats (internal/volunteer-facing)
- Stage ownership: `hackathon` stage (receives handoff from portal)
- Handoff IN: `Engagement.stage === 'hackathon'` from nonprofit-success-ai
- Current state: README only — nothing built
- Scope risk: existing 8-sprint proposal is too broad; first task is MVP narrowing
- Auth: must reuse whatever nonprofit-success-ai lands on (one identity system)
- Key open question: which single slice ships first (meeting transcription? task extraction? handoff capture only?)

**For DSSG interview, focus on:**
1. Which project? (portal vs. lifecycle backend)
2. What's the AI doing in this project specifically? (not named in either repo yet)
3. MVP: what's the thinnest demo? (for portal: client sees their engagement status + one AI-generated summary; for lifecycle backend: hackathon handoff captured + team assigned)
4. Firebase vs. Supabase decision (blocks both projects)

---

## Notes

- Don't conflate `/scope-poc` with `/project-genesis`. Design and infrastructure are different
  conversations at different times. Many `/scope-poc` sessions happen before any code exists.
- If the design reveals a need the template genuinely can't scaffold, name it explicitly
  rather than silently dropping it — same discipline as `/project-genesis` and `/new-agent`.
- DESIGN.md is a living doc. Update it when decisions resolve or scope changes. It's not a
  one-time artifact — it's the authoritative record of what this project is for.
