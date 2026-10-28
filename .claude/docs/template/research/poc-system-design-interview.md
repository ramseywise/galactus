# Research: POC system design interview — what must be answered before scaffolding

Date: 2026-07-15
Context: `ai-project-template` already has `/project-genesis` (copier infrastructure questions)
and a full set of capability toggles. What it doesn't have is the *upstream* conversation that
makes those choices well-informed rather than arbitrary. This doc captures what that conversation
should cover and how it maps to the template's output.

**Specific driver:** DSSG platform work (`nonprofit-success-ai` client portal + `project-mgmt-ai`
lifecycle backend) needs a demo-ready POC scaffold, but the design decisions that determine the
right copier answers (auth model, data model, actor surface, MVP scope) precede the copier
questions entirely. See `dssg/roadmap.md` for the reference system design this is calibrated on.

---

## The gap

`/project-genesis` answers **HOW to build it** — which agent framework, vector store, TypeScript,
MCP server, etc. These are infrastructure choices. They can't be answered well until you know:

- Who the actors are and what they do
- What the AI is actually doing for them
- What the MVP looks like (demo target)
- What constraints apply (data classification, multi-tenancy, operator model)

Without that upstream conversation, copier choices become guesses. The right agent framework
depends on whether you're doing retrieval, orchestration, or automation. The right vector backend
depends on whether you need a managed cluster or are just prototyping. The right integration
toggles depend on what external systems the project must connect to.

The missing layer is a **system design interview** that produces a `DESIGN.md` artifact, then
hands off to `/project-genesis` with those answers already in hand.

---

## Interview structure — five tiers

### Tier 1 — Problem and actors (C4 Level 1)

| Question | Purpose |
|----------|---------|
| What problem are you solving, and what's the current workaround? | Scopes "success"; surfaces if there's a simpler path |
| Who are the actors? (internal users, external users, other systems) | Determines auth model, multi-tenancy, API surface |
| What does the actor do TODAY vs what will the AI do for them? | Names what the AI is replacing/augmenting; prevents scope creep |
| What does POC success look like — what would a demo show? | Forces concreteness; names the demo target directly |

### Tier 2 — System boundaries (C4 Level 2)

| Question | Copier mapping |
|----------|----------------|
| What existing systems does this need to integrate with? | `include_mcp_server`, integration toggles |
| What data flows IN to the AI? (documents, DB records, live API calls) | `vector_backend`, `include_meeting_intelligence`, etc. |
| What does the AI produce? (text, structured output, triggered actions) | `primary_chat_agent` choice |
| Fresh project or layering onto an existing repo? | `scaffold_full_project` |

### Tier 3 — AI design

| Question | Copier mapping |
|----------|----------------|
| Is this retrieval (RAG), generation (drafts/summaries), automation (actions), or orchestration (multi-step)? | `primary_chat_agent` (lg_agent/adk_agent/none) |
| How will you evaluate "good"? Is there a golden set of expected answers? | `enable_structure_guard`, evals setup |
| What's the evaluation loop during POC — manual review, automated graders, user feedback? | `include_ragas_grader`, `include_promptfoo` |

### Tier 4 — Constraints (non-functional)

| Question | Copier mapping |
|----------|----------------|
| Data classification: public / internal / restricted / secret? | `data_sensitivity` |
| Multi-tenant requirement? (clients must never see each other's data) | Architectural flag — no direct copier equivalent; surfaces in DESIGN.md |
| Who operates this? Budget? (volunteer team vs. dedicated engineers) | `aws_region`, `vector_backend` complexity |
| Volunteer/rotating team or dedicated engineers? | Affects complexity threshold for what to scaffold |

### Tier 5 — MVP scope

| Question | Purpose |
|----------|---------|
| What's the thinnest slice that demonstrates value? | Prevents gold-plating; names the actual demo |
| What are the top 2–3 risks this POC should validate? | Structures what evals should grade |
| What's explicitly OUT of scope for POC? | Prevents scope creep during build |

---

## DSSG platform projects — specific context

Both current targets are **platform-level** (not cohort deliverables). They share:
- Supabase Postgres as the declared canonical data layer
- A single `Engagement` lifecycle: `initial_meeting → budgeting → engagement_tracking → hackathon → membership_close`
- Three actor roles: NPO Client (external), Data Diplomat (cohort volunteer), DSSG core volunteer (staff/leads)

**nonprofit-success-ai** — customer portal
- Actor: NPO Client (external, sees their own engagement status)
- Stage ownership: `initial_meeting → budgeting → engagement_tracking → membership_close`
- Current stack: React 19 + Firebase Auth + Firestore (no backend server)
- Open decision: Firebase vs. Supabase migration (highest-leverage decision per roadmap §1)
- AI scope: not yet defined; candidates include engagement summaries, stage-transition suggestions, client chat
- Key constraint: multi-tenancy is non-negotiable (one nonprofit must never see another's data)

**project-mgmt-ai** — lifecycle backend / coordination service
- Actor: DSSG core volunteers, Data Diplomats (internal/volunteer-facing)
- Stage ownership: `hackathon` stage (takes the handoff from the portal at `Engagement.stage === 'hackathon'`)
- Current stack: README only — nothing built yet
- Scope risk: 8-sprint proposal covers too much; needs explicit MVP narrowing before sprint 1
- Key handoff: receives `Engagement.hackathon_project` from nonprofit-success-ai's stage transition
- Auth: must reuse whatever nonprofit-success-ai lands on (single identity system)

**Shared infrastructure** (neither project owns these alone):
- Shared Supabase DB with `Business`/`Engagement`/`User` tables + RLS
- Platform API (auth check + engagement read/write + KB query stub)
- Comms sender (triggered by `Engagement.stage` writes, plain transactional email — not n8n)

---

## Output artifact: DESIGN.md

Every project scaffolded from this template should ship with a `DESIGN.md` stub covering:
1. Problem + success criteria (what does the demo show?)
2. Actors (who uses this, what do they do today, what does the AI do instead?)
3. System context (C4 L1 — one paragraph or lightweight mermaid)
4. MVP scope (in / out / open)
5. Key decisions (resolved and open)
6. Non-functional constraints (data classification, multi-tenancy, operator model)

The `/scope-poc` skill populates this before handing off to `/project-genesis`. If `/project-genesis`
is run without `/scope-poc`, the stub ships blank with clear placeholders — better than nothing, since
it forces the conversation to happen explicitly rather than implicitly.

---

## Design decision: sequential, not integrated

`/scope-poc` is a standalone skill that runs **before** `/project-genesis`, not a wrapper around it.
Rationale:
- Each skill stays focused: one conversation about design, one about infrastructure
- `/scope-poc` can be used for planning without immediately running copier
- The handoff is explicit: "run `/project-genesis` next, here's what to answer"
- For DSSG platform projects specifically, `/scope-poc` may produce a DESIGN.md months before the
  copier scaffold is run — design and build are different phases

The alternative (extending `/project-genesis` with design questions prepended) blurs those phases
and makes the skill unwieldy for users who've already done the design work.
