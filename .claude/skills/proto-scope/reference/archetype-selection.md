# AI Project Archetypes

Four patterns that cover the vast majority of nonprofit AI projects. Each archetype
maps to specific copier choices — pick the one that best fits where the hard problem
lives, not where the most code goes.

---

## Quick Comparison

| Archetype | The AI's job | Typical demo | Complexity floor |
|-----------|-------------|--------------|-----------------|
| Information Retrieval | Find and surface existing knowledge | "Ask a question, get the right answer from our docs" | Multi-sprint |
| Document Generation | Draft artifacts from templates + context | "Click generate, get an editable first draft" | Weekend sprint |
| Workflow Automation | Orchestrate multi-step processes | "Event triggers a chain: extract → route → notify" | Multi-sprint |
| Conversational Interface | Natural-language access to complex systems | "Chat with your data / schedule / case history" | Semester |

---

## Information Retrieval

### What it is
The AI searches through a corpus of documents (PDFs, policies, regulations, case
notes, knowledge bases) and returns relevant answers with source citations. The
core value is: "stop digging through files manually."

### When to use it
- Staff/volunteers spend significant time looking things up
- The answers already exist somewhere — they're just hard to find
- Accuracy and source-tracing matter (legal, compliance, policy)
- The corpus is relatively stable (not changing every hour)

### When NOT to use it
- The information doesn't exist yet (need generation, not retrieval)
- The corpus is tiny (< 20 documents) — a simple search/FAQ page suffices
- Real-time data is needed (live inventory, today's schedule)

### Complexity rating
**Multi-sprint** — needs: document ingestion pipeline, embedding model selection,
vector store, retrieval quality evaluation (golden QA set), basic UI or API.

### Example nonprofit scenarios
- Legal aid org: "Volunteers look up tenant rights in a 500-page housing regulation PDF"
- Education nonprofit: "Staff search across 3 years of program evaluation reports"
- Health clinic: "Case managers find relevant benefit programs for specific client situations"

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `project_type` | `rag` | Directly maps — RAG is retrieval-augmented generation |
| `primary_chat_agent` | `lg_agent` | LangGraph agent with BM25 + embedding retrieval |
| `vector_backend` | `duckdb` (small), `postgres` (production) | DuckDB for < 10k docs, Postgres/pgvector for scale |
| `agent_memory` | `conversation` | Remember context within a session |
| `agent_tools` | `[mcp]` | Expose retrieval as an MCP tool |
| `optional_features` | (default) | Eval suite with hit_rate/MRR grading ships automatically |

### Trade-offs
- **Pro:** High-value for knowledge-heavy orgs; measurable quality (hit_rate); template ships a working example
- **Con:** Requires a real document corpus to be useful; embedding quality depends on content structure; needs ongoing ingestion as docs change
- **Key risk:** Retrieval quality — if the golden QA set shows < 0.7 hit_rate, the system isn't useful yet

---

## Document Generation

### What it is
The AI drafts documents, reports, summaries, or communications from templates,
context, and prior examples. The core value is: "stop writing the same thing from
scratch every time."

### When to use it
- The org produces repetitive documents (grant reports, case summaries, newsletters)
- 50-80% of content is reusable across instances (boilerplate, org info, standard sections)
- Human review before sending is acceptable (AI drafts, human edits)
- Output format matters (specific structure, tone, length requirements)

### When NOT to use it
- Every document is genuinely unique (creative writing, novel research)
- Zero tolerance for errors (contracts, legal filings) — unless paired with mandatory human review
- The bottleneck is data gathering, not writing (need retrieval first)

### Complexity rating
**Weekend sprint** (basic) to **multi-sprint** (with templates + context injection).
A prompt-only version (paste context, get draft) works in a day. Adding structured
templates, org-specific tone, and context injection from prior docs takes 2-4 weeks.

### Example nonprofit scenarios
- Arts nonprofit: "We apply for 15 grants/year, each report is 8 pages, 60% is the same info"
- Social services: "Monthly progress summaries for 40 active cases — same format, different details"
- Community org: "Weekly newsletter recapping events from 3 different calendars"

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `project_type` | `agent` | Agent with generation tools, not pure retrieval |
| `primary_chat_agent` | `lg_agent` or `none` | LangGraph if multi-step; none if single-prompt generation |
| `deployment_target` | `local` (weekend) or `docker` (production) | Local for prototype; containerize for team use |
| `agent_memory` | `none` or `conversation` | Stateless if each generation is independent |
| `optional_features` | `[promptfoo]` | Prompt eval for output quality scoring |

### Trade-offs
- **Pro:** Fastest to demo; volunteers immediately see value; low infrastructure needs
- **Con:** Quality is subjective (hard to evaluate automatically); needs good examples/templates to work well; humans still review everything
- **Key risk:** Template drift — if the org's format changes, templates need updating

---

## Workflow Automation

### What it is
The AI orchestrates multi-step processes: extract information, make routing decisions,
trigger actions, notify people. The core value is: "things that require 5 manual steps
now happen automatically when an event occurs."

### When to use it
- A process has clear sequential steps (event → extract → decide → act → notify)
- Multiple systems need to be coordinated (calendar + email + database + Slack)
- The bottleneck is handoff friction between steps, not any single step
- Rules are expressible (even if complex) — not purely judgment-based

### When NOT to use it
- Every case requires unique human judgment (can't express rules)
- The process isn't stable yet (still figuring out what the steps should be)
- Only one system is involved (just use that system's built-in automation)
- Volume is very low (< 5 cases/week) — manual is fine

### Complexity rating
**Multi-sprint** — needs: event trigger mechanism (webhook or scheduled), extraction
logic, routing rules, at least one integration (email, Slack, calendar), error handling
for when steps fail.

### Example nonprofit scenarios
- Education nonprofit: "After each tutoring session, extract notes → create follow-up tasks → notify coordinator"
- Housing org: "New intake form submitted → check eligibility → assign case worker → send confirmation"
- Volunteer coordination: "Meeting happens → transcript processed → action items extracted → assigned to owners"

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `project_type` | `workflow` | Workflow automation is the direct match |
| `primary_chat_agent` | `lg_agent` | LangGraph's graph control flow fits multi-step orchestration |
| `external_systems` | `[slack, calendar, email, ...]` | Workflows connect systems — select what's relevant |
| `agent_tools` | `[mcp, custom]` | Custom tools for each integration step |
| `human_approval` | `sometimes` | Approve irreversible actions (sending emails, creating records) |
| `optional_features` | `[n8n_webhook, composio]` | n8n for no-code trigger/glue; Composio for pre-built connectors |

### Trade-offs
- **Pro:** High operational impact (saves hours/week of coordination); measurable (count automated vs manual steps); composable with other archetypes
- **Con:** Requires stable process (can't automate what's still being figured out); integration maintenance (APIs change); error handling is complex
- **Key risk:** Reliability — a workflow that fails silently is worse than manual. Build notifications for failures from day one.

---

## Conversational Interface

### What it is
A natural-language interface that lets users interact with complex systems without
learning those systems' native UI. The core value is: "ask questions in plain
language, get answers and actions — no training needed."

### When to use it
- Users are non-technical (clients, community members, frontline staff)
- The underlying system is powerful but has a steep learning curve
- Users need different slices of the same data (each sees their own context)
- Support/FAQ load is high and repetitive

### When NOT to use it
- Users are already comfortable with the existing system
- The interaction is purely transactional (just needs a better form, not AI)
- Privacy/security requirements make a general chat interface risky
- The data to answer from doesn't exist yet

### Complexity rating
**Semester** — needs: auth/identity (who is this user?), per-user data scoping
(what can they see?), conversation history, tool-calling (to actually DO things,
not just answer), deployment (accessible to external users), evaluation (is it
actually helpful?).

### Example nonprofit scenarios
- Legal aid: "Tenants ask about their rights in plain language — bot answers from verified legal docs"
- Social services: "Clients check their case status, upcoming appointments, required documents via chat"
- Education: "Parents ask about their child's program schedule, volunteer assignments, progress"

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `project_type` | `chat_app` | Chat application is the direct match |
| `primary_chat_agent` | `both` or `lg_agent` | Full agent capabilities for tool-calling + retrieval |
| `primary_users` | `customers` or `public_api` | External users need auth, scoping, multi-tenancy |
| `primary_backend_language` | `both` | TS frontend + Python agent backend |
| `frontend_backend_topology` | `split_service` | Separate frontend (Vercel) + backend (Railway) for external access |
| `agent_memory` | `long_term` | Cross-session memory so users don't repeat themselves |
| `human_approval` | `sometimes` | Approve actions that modify records |
| `deployment_target` | `cloud` or `serverless` | Must be accessible to external users |

### Trade-offs
- **Pro:** Highest impact for external users; eliminates support bottleneck; available 24/7; multilingual potential
- **Con:** Highest complexity; requires auth, multi-tenancy, deployment; hardest to evaluate (conversation quality is subjective); longest to build
- **Key risk:** Scope — a "chatbot for everything" fails. Constrain to 3-5 specific tasks the bot handles, with clear handoff to humans for everything else.

---

## Choosing Between Archetypes

If the user is unsure, ask these disambiguating questions:

1. **"Does the answer already exist somewhere, or does it need to be created?"**
   - Exists → Information Retrieval
   - Needs creating → Document Generation

2. **"Is the main value finding information, or taking action?"**
   - Finding → Information Retrieval
   - Acting → Workflow Automation

3. **"Who uses this — your internal team, or the nonprofit's clients/community?"**
   - Internal → any archetype (simpler auth)
   - External → Conversational Interface (needs auth + scoping)

4. **"Is this one step or many steps?"**
   - One step (ask → answer, or input → output) → Retrieval or Generation
   - Many steps (trigger → extract → decide → act) → Workflow Automation

---

## Complexity Budget Reference

| Tier | Time | Team | What's achievable |
|------|------|------|------------------|
| **Weekend sprint** | 1-2 focused days | 1-2 people | Working prototype demonstrating core value. One happy path. No auth, no deploy, no eval suite. Uses `project_type=prototype` or simplest archetype config. |
| **Multi-sprint** | 2-6 weeks | 2-4 people | Production-ready core feature. Basic eval (golden QA or prompt scoring). Deployed to Docker or cloud. Handles the primary use case reliably. |
| **Semester** | 8-12 weeks | 3-6 people | Full system: auth, multi-tenancy, multiple integrations, eval suite with automated gates, deployment with monitoring, handoff documentation, operator training. |

When capacity doesn't match ambition: **reduce scope, not quality.** A weekend sprint
that delivers one working feature well is more valuable than a semester plan that ships
nothing because the team ran out of hours.
