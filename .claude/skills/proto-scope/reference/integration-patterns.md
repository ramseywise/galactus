# Integration Patterns

How your AI system connects to external services (Slack, email, calendars, databases,
other APIs). The choice here determines what pre-built connectors you get, how much
you have to write yourself, and how maintainable the integrations are.

---

## Quick Comparison

| Pattern | Setup effort | Maintenance | Best for |
|---------|-------------|-------------|----------|
| MCP Tools | Low (expose/consume standard protocol) | Low (protocol-based) | AI-to-AI tool sharing, Claude Code integration |
| Composio Connectors | Low (pre-built, config-driven) | Low (managed by Composio) | Slack, Gmail, GitHub, 100+ SaaS apps |
| Direct API Clients | Medium (write httpx client per service) | Medium (APIs change) | Custom/niche services, fine-grained control |
| Webhook Receivers | Medium (endpoint + HMAC verification) | Low (event-driven) | Receiving events from external systems |
| n8n Workflow Glue | Low-Medium (config + HTTP calls) | Low (visual workflow editor) | Non-engineers connecting multiple services |

---

## MCP Tools (Model Context Protocol)

### What it is
A standardized protocol for exposing tools (functions with typed inputs/outputs) that
any MCP-compatible client (Claude Code, other agents) can discover and call. Your
project exposes tools via an MCP server; other agents consume them as capabilities.

### When to use it
- Your project's capabilities should be accessible to other AI agents
- You want Claude Code to directly call your project's functions
- You're building a tool that multiple agents in different projects will use
- You want typed, self-describing tool interfaces (schemas, descriptions)

### When NOT to use it
- The integration is purely human-to-human (no AI in the loop)
- You only need a simple REST API (MCP adds protocol overhead for non-AI consumers)
- The consuming side doesn't support MCP

### Complexity rating
**Multi-sprint** — the template scaffolds a working MCP server; you add tool definitions.

### Example scenario
A DSSG platform builds a "knowledge base query" MCP tool that searches across all
nonprofit documentation. Any Claude Code session in any DSSG project can add this
MCP server to their config and instantly query the KB without implementing retrieval.

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `include_mcp_server` | `true` | Scaffold an MCP server |
| `mcp_server_language` | `python` or `typescript` | Follows primary_backend_language |
| `agent_tools` | include `mcp` | Agent consumes MCP tools |
| `external_systems` | (as needed) | MCP tools can wrap any external service |

### What the template gives you
- `mcp_servers/<slug>/` — FastMCP (Python) or @modelcontextprotocol/sdk (TypeScript) server
- Pre-wired `search_articles` example tool (calls rag_agent's retrieval API)
- `.claude/skills/mcp-builder/` — comprehensive guide for building MCP tools
- Reference docs: `mcp_best_practices.md`, `python_mcp_server.md`, `node_mcp_server.md`
- Agent-side MCP integration: `lg_agent/clients/mcp.py` (LangChain MCP adapters), `adk_agent/mcp_tools.py`

### Trade-offs
- **Pro:** Standard protocol (works with any MCP client); typed schemas; self-describing; composable across projects
- **Con:** Protocol overhead for simple use cases; ecosystem still maturing; debugging requires understanding MCP transport (stdio)
- **Key insight:** If other AI agents will call your function, use MCP. If only humans or one specific system calls it, a REST endpoint is simpler.

---

## Composio Connectors (Pre-Built SaaS Integrations)

### What it is
Composio provides pre-built, managed connectors for 100+ SaaS applications (Slack,
Gmail, GitHub, Google Workspace, Salesforce, etc.). You configure which actions you
need; Composio handles auth, API changes, and rate limits.

### When to use it
- You need to interact with common SaaS tools (Slack, email, calendars, task managers)
- You don't want to build and maintain OAuth flows for each service
- The actions you need are standard (send message, create event, list issues)
- Speed matters — get integrations working in hours, not days

### When NOT to use it
- The service is custom/internal (Composio doesn't have a connector for it)
- You need highly customized behavior (Composio's actions may be too generic)
- You want zero external dependencies (Composio is a managed service)
- Budget is strictly $0 (Composio has a free tier but limits apply)

### Complexity rating
**Multi-sprint** — setup is fast (config-driven), but testing integrations with real
accounts and handling edge cases takes time.

### Example scenario
A volunteer coordination nonprofit needs their AI to: send Slack notifications when
tasks are assigned, create Google Calendar events for meetings, and update GitHub
issues when work is completed. Rather than building 3 OAuth flows + 3 API clients,
Composio provides all three as configured actions.

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `external_systems` | `[slack, github, google_workspace, email]` | Name the systems Composio will connect |
| `optional_features` | include `composio` | Scaffold the Composio integration |

### What the template gives you
- `integrations/composio.py` — Composio action wrapper (execute any registered action)
- Auto-seeded when `external_systems` includes Slack, GitHub, Email, or Google Workspace
- Works alongside (not instead of) direct API clients for the same services

### Trade-offs
- **Pro:** Fast to set up; auth handled; API changes managed; 100+ services available; reduces code you maintain
- **Con:** External dependency; free tier limits; may not cover niche services; less control over exact API behavior
- **When to use direct API instead:** When you need fine-grained control over the API call (custom headers, specific pagination, non-standard endpoints). Use Composio for standard actions, direct API for custom needs.

---

## Direct API Clients (httpx)

### What it is
Hand-written Python (or TypeScript) clients that call external APIs directly. Full
control over request/response handling, error management, and retry logic. One class
per service, following the template's established connector pattern.

### When to use it
- The service is custom or niche (no Composio connector exists)
- You need fine-grained control (specific headers, custom pagination, non-standard auth)
- The integration has complex business logic beyond "call this endpoint"
- You want zero external service dependencies

### When NOT to use it
- A Composio connector exists and does what you need (why reinvent?)
- The service has an official SDK that's well-maintained (use the SDK)
- The team doesn't have the API expertise to build and maintain a client

### Complexity rating
**Multi-sprint** — per service: understand their API docs, handle auth (API key,
OAuth, JWT), implement error handling, write tests.

### Example scenario
A nonprofit uses Eventbrite for events. They need: create event (specific venue,
custom fields), publish event (requires draft→live two-step), and attendee sync.
Composio's Eventbrite connector doesn't support their custom fields. Direct client
with their specific flows.

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `external_systems` | `[database, calendar, ...]` | Name the systems you're integrating with |
| `optional_features` | `[marketing]` for Eventbrite/LinkedIn/Canva | Pre-built marketing API clients |
| `optional_features` | `[meeting_intelligence]` for transcript processing | Pre-built extraction pipeline |

### What the template gives you
- `integrations/google_calendar.py` — Google Calendar OAuth2 client (list/create events, find availability)
- `integrations/eventbrite.py` — Eventbrite REST client (create/publish events)
- `integrations/linkedin.py` — LinkedIn UGC Posts API client
- `integrations/canva.py` — Canva Autofill API client
- `integrations/meeting_intelligence.py` — Transcript extraction (action items, decisions, owners)
- `integrations/settings.py` — Centralized integration config (env vars, shared secrets)
- Pattern: Pydantic models at boundaries, `RuntimeError` on missing credentials, httpx async client

### Trade-offs
- **Pro:** Full control; no external dependencies; works with any API; testable in isolation
- **Con:** More code to write and maintain; you handle auth/retries/rate-limits; API changes break your client
- **Key pattern:** One client class per service. Pydantic models for request/response types. Raise `RuntimeError` with clear message on missing credentials (never silently fail).

---

## Webhook Receivers (Inbound Events)

### What it is
Your system exposes HTTP endpoints that external services call when events happen.
The external service pushes data to you (rather than you polling it). Secured with
HMAC signature verification.

### When to use it
- External systems send notifications (n8n workflows, CI/CD, form submissions, Slack events)
- You need to react to events as they happen (not poll for changes)
- The external system supports webhooks (most modern services do)
- You want event-driven architecture (loose coupling between systems)

### When NOT to use it
- You're the one calling external APIs (that's a client, not a webhook)
- The external system doesn't support webhooks (you'll need to poll)
- Security requirements prevent exposing endpoints (air-gapped systems)

### Complexity rating
**Multi-sprint** — needs: publicly accessible endpoint (deployed service), HMAC
verification, event type routing, idempotent handlers, error recovery.

### Example scenario
A nonprofit uses n8n for their internal workflows. When a new client is onboarded in
n8n (form → Airtable → notification), n8n sends a webhook to the AI system with the
client details. The AI processes the intake, runs eligibility checks, and posts
results back.

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `optional_features` | include `n8n_webhook` | Scaffold the HMAC-verified webhook receiver |
| `deployment_target` | `docker` or `cloud` | Must be reachable by external services |

### What the template gives you
- `integrations/n8n_webhook.py` — HMAC-verified `POST /webhooks/n8n` endpoint
- Pluggable `EVENT_HANDLERS` dispatch (register handlers per event type)
- Mounted into all agent FastAPI apps via try/except ImportError (present only when toggled on)
- Signature verification: shared secret in env var, timing-safe comparison

### Trade-offs
- **Pro:** Real-time event processing; loose coupling; no polling overhead; works with any webhook-capable service
- **Con:** Needs deployed endpoint; security considerations (HMAC verification required); debugging is harder (events are async); idempotency is your responsibility
- **Key concern:** Every webhook handler must be idempotent — the same event may be delivered more than once.

---

## n8n Workflow Glue (No-Code Orchestration)

### What it is
n8n is a visual workflow automation tool (self-hosted or cloud). It connects services
via a drag-and-drop interface. Your AI system participates as one node in an n8n
workflow — either as a callable HTTP endpoint or as the trigger for further actions.

### When to use it
- Non-engineers need to modify the integration logic (program managers, coordinators)
- The workflow connects many services with simple logic between them
- You want to iterate on routing/filtering without code changes
- The AI is one step in a larger process (not the whole process)

### When NOT to use it
- All integration logic lives in the AI system itself (no need for external orchestration)
- The team is all engineers comfortable with code (n8n adds indirection)
- Complex AI-specific logic between steps (n8n's node model isn't ideal for this)
- Budget: n8n cloud costs; self-hosted requires maintenance

### Complexity rating
**Multi-sprint** — n8n setup is fast, but wiring it to your AI endpoints and handling
the bidirectional flow (n8n → your system, your system → n8n) takes iteration.

### Example scenario
A DSSG cohort coordination workflow: Google Form submission (trigger) → n8n extracts
fields → calls AI system's `/webhooks/n8n` endpoint with structured data → AI runs
matching algorithm → returns results → n8n sends Slack notification + creates Airtable
record + emails the coordinator. Non-engineers can modify the Slack message or add
an email step without touching code.

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `optional_features` | include `n8n_webhook` | Your system receives calls from n8n |
| `external_systems` | (as needed) | n8n handles the external service connections; you handle the AI |

### Trade-offs
- **Pro:** Non-engineers can modify workflows; visual debugging; connects 400+ services natively; rapid iteration on routing logic
- **Con:** External dependency; another system to operate; adds latency (HTTP hops); debugging spans two systems
- **Recommendation for DSSG:** Excellent fit for cohort projects where volunteers rotate. The n8n workflow survives team turnover better than custom code. AI does the hard part (extraction, matching, generation); n8n handles the plumbing.

---

## Decision Shortcut

| Question | Answer → Pattern |
|----------|------------------|
| "Will other AI agents call this function?" | Yes → MCP Tools |
| "Are you connecting to Slack/Gmail/GitHub/common SaaS?" | Yes → Composio (fast) or Direct API (control) |
| "Is the service custom or niche?" | Yes → Direct API Client |
| "Do external services need to push events to you?" | Yes → Webhook Receiver |
| "Do non-engineers need to modify the integration logic?" | Yes → n8n Workflow Glue |
| "Multiple of the above?" | Common pattern: MCP for AI consumers + Composio for SaaS + webhooks for inbound events |

---

## Combining Patterns (Common Setups)

**Internal team tool (most DSSG projects):**
- Composio for Slack/email notifications + Direct API for org-specific systems + MCP for cross-project tool sharing

**Client-facing application:**
- Direct API clients for the org's data systems + Webhook receivers for real-time events + No MCP (end users aren't AI agents)

**Workflow-heavy project:**
- n8n for orchestration glue + Webhook receiver for n8n callbacks + Composio for the services n8n doesn't cover + Direct API for custom logic
