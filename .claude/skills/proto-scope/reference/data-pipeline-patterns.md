# Data Pipeline Patterns

How data gets into and moves through your AI system. The choice here determines
how fresh your AI's knowledge is, how complex your infrastructure needs to be,
and which copier toggles to set.

---

## Quick Comparison

| Pattern | Data freshness | Infrastructure | Best for |
|---------|---------------|----------------|----------|
| Batch Ingest | Hours to days | Simple (run once, query many) | Stable document corpora |
| Event-Driven | Minutes | Medium (webhooks + queue) | System integrations |
| Streaming | Seconds | Complex (persistent connections) | Real-time monitoring |
| Hybrid | Varies by source | Medium-High | Multiple data sources |

---

## Batch Ingest + Vector Search

### What it is
Documents are loaded, chunked, embedded, and stored in a vector database as a
one-time (or scheduled) operation. Queries hit the pre-built index. The data
pipeline runs separately from the query path.

### When to use it
- Your corpus is documents (PDFs, policies, knowledge base articles, reports)
- Content changes slowly (weekly/monthly, not hourly)
- A delay of hours between content updates and availability is acceptable
- You want the simplest possible infrastructure

### When NOT to use it
- Data changes in real-time (live inventory, active conversations)
- You need the AI to know about something that happened 5 minutes ago
- The data source is an API, not documents

### Complexity rating
**Multi-sprint** — needs ingestion script, embedding model, vector store, but no
live infrastructure beyond the query endpoint.

### Example scenario
A legal aid org has 200 housing regulation PDFs. They update quarterly when new
rules are published. Volunteers need answers NOW but the corpus itself is stable.
Batch ingest the PDFs once, re-run when new versions are published.

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `project_type` | `rag` | RAG projects use batch ingest by default |
| `vector_backend` | `duckdb` (dev/small), `postgres` (production) | DuckDB for < 10k chunks; Postgres for scale + Supabase |
| `external_systems` | `[database]` if Postgres target | Seeds vector_backend default to postgres |
| `optional_features` | (defaults) | Eval suite with hit_rate grading ships automatically |

### What the template gives you
- `core/ingestion.py` — document loading + chunking pipeline
- `core/index.py` — vector index interface
- `agents/rag_agent/vectorstore.py` — backend-specific implementation (DuckDB/memory/OpenSearch/Postgres)
- `data/corpus/` — where source documents live
- `make corpus-ingest` / `make rag-corpus-ingest` — one-command ingestion

### Trade-offs
- **Pro:** Simplest architecture; debuggable (inspect the index); repeatable (re-ingest anytime)
- **Con:** Stale data between ingestion runs; large corpora = slow ingest + large index; embedding model choice matters for quality

---

## Event-Driven Processing

### What it is
External events (webhook callbacks, form submissions, scheduled triggers) kick off
processing pipelines. Each event is handled independently: extract → transform →
act. No persistent corpus — data flows through rather than being stored and searched.

### When to use it
- Multiple systems need to stay in sync (event in one → action in another)
- Processing is triggered by something happening (not by a user asking a question)
- Each event is relatively independent (not querying across all historical events)
- You need minutes-latency, not seconds

### When NOT to use it
- Users need to search across historical data (need retrieval, not event processing)
- Events are extremely high-volume (> 1000/hour) — need proper message queue infrastructure
- Processing requires context from many past events (need a database + retrieval)

### Complexity rating
**Multi-sprint** — needs: webhook/trigger infrastructure, at least one integration,
error handling for failed events, idempotency for retries.

### Example scenario
An education nonprofit uses Zoom for tutoring sessions. After each session ends,
Zoom sends a webhook → the system transcribes the recording → extracts action items
→ creates tasks in the project tracker → notifies the coordinator on Slack.

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `project_type` | `workflow` | Workflow = event-driven multi-step processing |
| `external_systems` | `[slack, calendar, email, ...]` | Name the systems that send/receive events |
| `optional_features` | `[n8n_webhook, composio]` | n8n for inbound webhooks; Composio for outbound actions |
| `human_approval` | `sometimes` | Approve before irreversible actions (sending, creating records) |
| `agent_tools` | `[mcp, custom]` | Custom tools for each processing step |

### What the template gives you
- `integrations/n8n_webhook.py` — HMAC-verified inbound webhook receiver
- `integrations/meeting_intelligence.py` — transcript → action items extraction
- `integrations/composio.py` — pre-built connectors for Slack, Gmail, GitHub, etc.
- Agents' FastAPI apps expose `POST /webhooks/n8n` when `include_n8n_webhook=true`

### Trade-offs
- **Pro:** Responsive (minutes, not hours); composable (add new event types independently); clear audit trail (each event logged)
- **Con:** More moving parts (triggers, handlers, retries); harder to test locally (need to simulate events); failure modes are complex (what if step 3 of 5 fails?)
- **Key concern:** Idempotency — events may be delivered more than once. Every handler must be safe to run twice.

---

## Streaming / Real-Time

### What it is
Persistent connections (WebSockets, SSE, polling) that process data as it arrives
with sub-second latency. The system maintains live state and reacts immediately.

### When to use it
- Users need immediate feedback (live chat, real-time collaboration)
- Monitoring/alerting scenarios (watch a feed, act on anomalies)
- The AI is participating in a live conversation (not answering stored questions)

### When NOT to use it
- Batch processing is acceptable (90% of nonprofit use cases)
- Your team doesn't have the infrastructure experience for persistent connections
- The data source doesn't actually change in real-time

### Complexity rating
**Semester** — needs: WebSocket/SSE infrastructure, connection management, state
synchronization, graceful reconnection, significantly more deployment complexity.

### Example scenario
A crisis hotline wants an AI co-pilot that listens to the conversation in real-time
and surfaces relevant resources to the counselor as topics come up — live suggestions,
not after-the-fact summaries.

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `project_type` | `chat_app` | Chat apps need real-time streaming |
| `primary_chat_agent` | `lg_agent` or `both` | LangGraph supports streaming natively |
| `ts_agent_framework` | `vercel_ai_sdk` | Vercel AI SDK streams via SSE out of the box |
| `deployment_target` | `cloud` | Persistent connections need long-lived servers |
| `frontend_backend_topology` | `split_service` | Separate frontend (WebSocket client) + backend (stream provider) |

### Trade-offs
- **Pro:** Best user experience for interactive applications; immediate feedback
- **Con:** Highest infrastructure complexity; hardest to test; deployment constraints (no serverless for WebSockets); requires frontend expertise
- **Recommendation for DSSG:** Unless the use case genuinely requires sub-second latency, start with event-driven and add streaming later. Most "real-time" needs are actually "within a few minutes" needs.

---

## Hybrid (Multiple Sources)

### What it is
Combines multiple patterns: a static corpus (batch-ingested) plus live data sources
(event-driven or API-fetched at query time). The AI can answer from both stored
knowledge and current state.

### When to use it
- The AI needs to reason over both historical documents AND current data
- Some data is stable (policies, guidelines) while other data changes (case status, schedules)
- The system is mature enough to handle multiple data paths

### When NOT to use it
- One pattern clearly dominates (don't over-engineer)
- First version / POC (start simple, add complexity later)
- Team is small and can't maintain multiple pipelines

### Complexity rating
**Semester** — needs everything batch ingest needs PLUS event/API integration.
This is almost always a phase-2 evolution, not a phase-1 choice.

### Example scenario
A social services org wants: (1) policy lookup from their procedures manual (batch,
stable) + (2) client case status from their Salesforce instance (API, live) + (3)
appointment availability from Google Calendar (API, real-time). The AI combines all
three to answer "what should this client do next?"

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `project_type` | `rag` or `agent` | RAG if retrieval-heavy; agent if action-heavy |
| `vector_backend` | `postgres` | Production-grade for the batch component |
| `external_systems` | `[database, calendar, ...]` | Name all live data sources |
| `agent_tools` | `[database, mcp, custom]` | Tools for each live data source |
| `optional_features` | `[composio]` | Pre-built connectors for live APIs |

### Trade-offs
- **Pro:** Most complete picture for the AI; handles complex real-world scenarios
- **Con:** Highest complexity; multiple failure modes; harder to evaluate (which source caused a wrong answer?)
- **Recommendation for DSSG:** Start with the dominant pattern. Add the second data path in phase 2 after the core is working. Name it explicitly in "Out of Scope" for the POC.

---

## Decision Shortcut

Ask: **"Where does the data the AI needs come from?"**

| Answer | Pattern |
|--------|---------|
| "Documents we already have (PDFs, docs, reports)" | Batch Ingest |
| "Things that happen (meetings, form submissions, events)" | Event-Driven |
| "Live systems (databases, calendars, APIs)" | Event-Driven or Hybrid |
| "A conversation happening right now" | Streaming |
| "A mix of the above" | Start with the dominant one; plan hybrid for phase 2 |
