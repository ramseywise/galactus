# Dryrun Scenarios — Full Detail

Each scenario provides: the volunteer's actual words (simulate as input), expected
outputs at each stage, and the reasoning behind expected values.

---

## Scenario A: Meeting Transcript Pipeline

### Volunteer input (simulate as if they said this)

> "I'm working with this after-school tutoring nonprofit — Tutors for Tomorrow.
> They have about 20 volunteer tutors who meet weekly in small groups. The problem
> is nobody tracks what was decided or what follow-ups are needed. The coordinator,
> Maria, spends her Friday afternoons going through her notes trying to reconstruct
> what each group committed to. She misses things, tutors forget their action items,
> and kids fall through the cracks because nobody followed up on 'let's check in
> with Jordan's teacher next week.'
>
> The team is me and one other volunteer, we have maybe 8-10 hours a week between us
> for the next 6 weeks. Maria's willing to test things and give feedback. They use
> Google Meet for sessions and Slack for coordination. No hard deadline but there's a
> cohort demo day in 5 weeks."

### Expected Project Profile

```markdown
# Project Profile — Tutors for Tomorrow Action Tracker

**Date:** [today]
**Status:** Discovery

## The Pain Point
Maria (coordinator) spends Friday afternoons reconstructing decisions and follow-ups
from weekly tutor group meetings. Action items get lost, tutors forget commitments,
and students fall through the cracks when follow-ups don't happen.

## Nonprofit / Organization
- **Name:** Tutors for Tomorrow
- **Domain:** Education
- **Existing tech:** Google Meet (sessions), Slack (coordination), no project tracker

## Archetype
**Workflow Automation**
The core problem is a multi-step process (meeting → extract decisions → assign actions → notify)
that's currently done manually and unreliably.

## Must-Demonstrate (5-min demo)
1. Meeting recording/transcript is processed automatically after the session ends
2. Action items are extracted with owners and deadlines
3. Each tutor gets a Slack message with their specific follow-ups
4. Maria sees a dashboard/summary of all outstanding action items
5. Missed follow-ups are flagged the following week

## Capacity Constraints
- **Team:** 2 volunteers, 8-10 hours/week combined
- **Timeline:** multi-sprint (6 weeks)
- **Hard deadlines:** Cohort demo day in ~5 weeks
- **Integrations needed:** Google Meet (transcription source), Slack (notifications)

## Explicitly Out of Scope
- Building a full project management tool (use existing tools for tracking)
- Handling non-meeting communication (email threads, DMs)
- Tutor scheduling or matching

## Copier Hints (derived from discovery)
| Parameter | Suggested value | Rationale |
|-----------|----------------|-----------|
| `project_type` | `workflow` | Multi-step event-driven processing |
| `deployment_target` | `docker` | Team needs access; demo day requires a running service |
| `primary_backend_language` | `python` | Team's skill set |
| `external_systems` | `[slack, calendar]` | Slack for notifications, calendar for meeting events |
| `primary_users` | `internal` | Maria and tutors (staff/volunteers) |
```

### Expected scope-poc behavior

**Pre-filled (confirm-only):**
- Tier 1 Q1: "Maria reconstructs meeting decisions manually" ← pain point
- Tier 3 Q7: Workflow automation (extract → route → notify) ← archetype
- Tier 5 Q12: 5 must-demonstrate items listed above
- Tier 4 Q11: 2 people, 8-10h/week, 6 weeks, demo day week 5
- Tier 5 Q14: Not building PM tool, not handling email/DMs, not scheduling

**Asked normally:**
- Who are the specific actors? (Maria=coordinator, 20 tutors=users, kids=indirect beneficiaries)
- System boundaries: How does transcript get in? (Google Meet recording → transcript API? Manual upload? Granola/Fireflies?)
- Data classification: Transcript content may contain student names/situations → `restricted`
- Evaluation: How do we measure "good extraction"? (% of action items caught vs. Maria's manual notes)
- Naive baseline: Maria's current Friday afternoon process (compare: time spent, items captured)
- Top risks: Transcript quality (background noise), action item ambiguity ("let's follow up" — who? when?)

### Key validation points

- `project_type` MUST be `workflow` (not `agent` — the core value is the multi-step pipeline, not open-ended conversation)
- `optional_features` should include `meeting_intelligence` (transcript extraction) and `n8n_webhook` (event trigger)
- `primary_chat_agent` is NOT the important choice here — the pipeline, not a chat agent, is the product

---

## Scenario B: Tenant Rights FAQ

### Volunteer input

> "I'm with NYC Legal Aid Partners — we help tenants in housing court. Our intake
> volunteers are mostly law students who rotate every semester. When a tenant calls
> in, the volunteer needs to figure out which protections apply to their situation.
> That means digging through the NYC Admin Code, state Real Property Law, HPD
> regulations, and our internal case precedent memos. A single intake can take
> 2-3 hours just on the lookup part because the volunteer doesn't know where to look.
>
> We have about 500 pages of primary source material (statutes + regulations) plus
> ~200 pages of our own memos analyzing specific situations. Our experienced
> attorneys know where to look instantly, but they can't be on every call.
>
> I'm leading this with 3 other volunteers (2 engineers, 1 law student). We have
> about 15 hours/week total, 8 weeks before the next semester starts. The law
> student can help curate the 'is this answer right' test cases."

### Expected Project Profile

```markdown
# Project Profile — NYC Legal Aid Tenant Rights Lookup

**Date:** [today]
**Status:** Discovery

## The Pain Point
Intake volunteers (rotating law students) spend 2-3 hours per tenant call looking
up which housing protections apply. The knowledge exists in 700 pages of statutes,
regulations, and internal memos — experienced attorneys know where to look instantly,
but can't be on every call.

## Nonprofit / Organization
- **Name:** NYC Legal Aid Partners
- **Domain:** Legal aid
- **Existing tech:** PDFs of statutes/regulations, internal memo documents (likely Word/Google Docs)

## Archetype
**Information Retrieval**
The answer already exists in their document corpus. The problem is finding it quickly.
An experienced attorney does this mentally; the AI replicates that lookup capability.

## Must-Demonstrate (5-min demo)
1. Volunteer types a tenant's situation ("my landlord hasn't fixed the heat in 3 weeks")
2. System returns the applicable statutes/regulations with citations
3. System shows relevant sections from internal case memos
4. Answers include source citations (which document, which section)
5. A law student can verify the answer is correct using the cited source

## Capacity Constraints
- **Team:** 4 volunteers (2 engineers, 1 law student, 1 lead), 15 hours/week total
- **Timeline:** multi-sprint (8 weeks)
- **Hard deadlines:** Next semester start (new volunteer cohort needs this tool)
- **Integrations needed:** None external — all documents are local/uploaded

## Explicitly Out of Scope
- Legal advice (the AI finds relevant law; attorneys advise clients)
- Case management or tracking
- Drafting legal documents
- Serving tenants directly (internal tool for volunteers only)

## Copier Hints (derived from discovery)
| Parameter | Suggested value | Rationale |
|-----------|----------------|-----------|
| `project_type` | `rag` | Classic retrieval-augmented generation over documents |
| `deployment_target` | `docker` | Team access; semester start is the deadline |
| `primary_backend_language` | `python` | Team has Python engineers |
| `external_systems` | `[]` | No external systems; all docs are local |
| `primary_users` | `internal` | Intake volunteers (law students) |
| `primary_chat_agent` | `lg_agent` | LangGraph agent with retrieval |
| `vector_backend` | `duckdb` | 700 pages is well within DuckDB's capacity |
```

### Expected scope-poc behavior

**Pre-filled (confirm-only):**
- Tier 1 Q1: Volunteer lookup bottleneck (2-3 hours per intake)
- Tier 3 Q7: Information Retrieval / RAG
- Tier 5 Q12: 5 must-demonstrate items
- Tier 4 Q11: 4 people, 15h/week, 8 weeks, semester boundary
- Tier 5 Q14: Not legal advice, not case management, not client-facing

**Asked normally:**
- Actors: Intake volunteers (law students, rotating), attorneys (subject matter experts, not daily users), tenants (indirect beneficiaries, never see the tool)
- System boundaries: Document ingestion (how are 700 pages provided? PDFs? A shared drive? One-time upload?)
- Data classification: `restricted` — statutes are public but internal memos may reference specific cases
- Multi-tenancy: Not needed (one org, shared tool)
- Evaluation: Hit rate against a golden QA set (the law student curates this!)
- Naive baseline: Experienced attorney's knowledge (they take 5 minutes vs. volunteer's 2 hours)
- Risks: Retrieval precision (wrong statute is worse than no answer in legal context), document formatting (OCR quality of old PDFs)

### Key validation points

- `project_type` MUST be `rag` (not `chat_app` — this is search, not conversation)
- `vector_backend` should be `duckdb` (700 pages = ~3500 chunks, well within single-file DB capacity)
- The law student curating test cases maps directly to golden-set evaluation
- `primary_users: internal` is critical — this is NOT client-facing (no auth/multi-tenancy needed)

---

## Scenario C: Grant Report Drafting

### Volunteer input

> "I'm helping Art Space Brooklyn — they're a tiny arts nonprofit, just 5 staff.
> They apply for about 15 grants a year and each final report is 6-8 pages. The
> thing is, like 60% of every report is the same information — org description,
> mission statement, program statistics, demographic data — just reformatted to
> match each funder's template. Their ED, Sarah, spends a full day on each report
> just copying and reformatting the same info.
>
> It's just me on this — I have a free weekend coming up and wanted to see if I
> could build something that helps. Sarah has all the previous reports in Google Docs
> and can give me the funder templates. No deadline, just a side project to see if
> it's useful."

### Expected Project Profile

```markdown
# Project Profile — Art Space Brooklyn Grant Report Assistant

**Date:** [today]
**Status:** Discovery

## The Pain Point
Sarah (ED) spends a full day per grant report (15 reports/year) copying and
reformatting the same organizational information (mission, stats, demographics)
into each funder's required template format.

## Nonprofit / Organization
- **Name:** Art Space Brooklyn
- **Domain:** Arts
- **Existing tech:** Google Docs (previous reports, funder templates)

## Archetype
**Document Generation**
The content largely exists already (org info, program data). The AI's job is to
assemble and reformat it into each funder's required structure.

## Must-Demonstrate (5-min demo)
1. Sarah provides a funder's report template (structure/sections required)
2. System pulls relevant content from previous reports and org data
3. System generates a first draft matching the funder's structure
4. Output is in a format Sarah can edit (not a black box)
5. Sections that need fresh writing are clearly marked vs. auto-filled sections

## Capacity Constraints
- **Team:** 1 person (me)
- **Timeline:** weekend sprint (1-2 days)
- **Hard deadlines:** None (exploratory side project)
- **Integrations needed:** Google Docs (source material, output)

## Explicitly Out of Scope
- Automating the grant application process itself (just the final report)
- Financial reporting or budget documents
- Multi-user system (just Sarah uses this)
- Deployment or hosting (local tool is fine)

## Copier Hints (derived from discovery)
| Parameter | Suggested value | Rationale |
|-----------|----------------|-----------|
| `project_type` | `agent` | Generation agent with document context |
| `deployment_target` | `local` | Weekend sprint, one user, no hosting needed |
| `primary_backend_language` | `python` | Solo developer, Python expertise |
| `external_systems` | `[google_workspace]` | Source docs in Google Docs |
| `primary_users` | `internal` | Just Sarah |
| `primary_chat_agent` | `none` | Simple generation, not a chat agent |
```

### Expected scope-poc behavior

**Pre-filled (confirm-only):**
- Tier 1 Q1: Report reformatting bottleneck (full day per report, 15x/year)
- Tier 3 Q7: Document generation
- Tier 5 Q12: 5 must-demonstrate items
- Tier 4 Q11: 1 person, weekend, no deadline
- Tier 5 Q14: Not applications, not budgets, not multi-user, not deployed

**Asked normally:**
- Actors: Sarah (ED, sole user), funders (indirect — receive the reports but don't use the tool)
- System boundaries: How does content get in? (Google Docs API? Copy-paste? Upload previous reports?)
- Data classification: `internal` (org info is not sensitive; grant reports are public once submitted)
- Evaluation: Manual review (Sarah reads the draft and says "this saves me time or it doesn't")
- Naive baseline: Sarah's current process (copy-paste + reformat manually, ~8 hours per report)
- Risks: Format compliance (funders are strict about structure); hallucinated statistics (must use real numbers from prior reports, never fabricate)

### Key validation points

- `project_type` should be `agent` (not `rag` — this is generation, not search)
- `deployment_target` MUST be `local` (weekend sprint, one person, exploratory)
- `primary_chat_agent: none` is correct — a simple prompt-based generator, not a conversational agent
- The weekend complexity budget should steer away from heavy infrastructure (no Docker, no eval suite, no CI)
- `optional_features: [promptfoo]` makes sense (evaluate output quality of generated reports)
