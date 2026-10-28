# Deployment Topology

Where your AI system runs and how it's structured. This determines cost, complexity,
who can access it, and how you operate it after the POC.

---

## Quick Comparison

| Topology | Who can access | Infra cost | Ops complexity | Best for |
|----------|---------------|-----------|----------------|----------|
| Local only | Just the developer | $0 | None | Weekend sprints, prototypes |
| Single service (Docker) | Team on same network / VPN | $5-20/mo | Low | Internal tools, multi-sprint POCs |
| Cloud service | Anyone with the URL | $20-100/mo | Medium | Production internal tools |
| Split service | External users + internal backend | $40-150/mo | High | Client-facing applications |
| Serverless | Anyone with the URL | Pay-per-use | Medium | Low-traffic, bursty workloads |

---

## Local Only

### What it is
The AI runs on a developer's machine. No deployment, no hosting, no external access.
Start the server, use it, stop it when done.

### When to use it
- Weekend sprint / prototype — proving the concept works
- The only user is the developer (or someone sitting next to them)
- You want zero infrastructure cost and zero ops burden
- You're iterating rapidly and don't want deploy cycles

### When NOT to use it
- Anyone besides the developer needs to use it
- You need it running when the developer's laptop is closed
- You're past the prototype phase

### Complexity rating
**Weekend sprint** — `make lg-up` or `make adk-up` and you're running.

### Example scenario
A volunteer wants to prove that RAG over housing regulations works before committing
the team to a multi-week build. They ingest 5 sample PDFs, run queries locally, show
the results at the next team meeting. No deploy needed.

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `deployment_target` | `local` | Design record: this is local-only for now |
| `project_type` | `prototype` or any | Prototype skips some scaffolding overhead |
| `frontend_backend_topology` | `single` | No frontend/backend split needed |

### Trade-offs
- **Pro:** Zero cost; zero ops; instant iteration; no security concerns (nothing exposed)
- **Con:** Only one user; dies when laptop closes; can't demo remotely; no persistence beyond local disk
- **Upgrade path:** When ready for more users, containerize (Docker) → push to Railway/Render

---

## Single Service (Docker)

### What it is
One container running your AI backend (FastAPI + agent). Accessible to anyone who
can reach the host — your team on the same network, or via a simple cloud host
(Railway, Render, a VPS).

### When to use it
- A small team (2-6 people) needs access
- All users are internal (staff, volunteers) — no external/public access needed
- You want simple deployment without frontend/backend split complexity
- The AI is an API or a simple web interface, not a full application

### When NOT to use it
- External users (nonprofit clients, community members) need access — they need auth
- You need a polished frontend (not just API calls or a basic chat UI)
- Multiple services need to scale independently

### Complexity rating
**Multi-sprint** — needs: Dockerfile, environment variables managed, a host
(Railway is the easiest for DSSG — free tier, auto-deploy from GitHub).

### Example scenario
A DSSG volunteer team builds a meeting-transcript-to-action-items pipeline. The 4
team members and 2 nonprofit staff need to upload transcripts and see results. One
Docker container on Railway, accessed via a shared URL, protected by a simple API
key in a header.

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `deployment_target` | `docker` | Container-based deployment |
| `primary_backend_language` | `python` | Single Python service, no TS frontend needed |
| `frontend_backend_topology` | `single` | One deployable unit |
| `primary_users` | `internal` | Team/staff access only |
| `data_sensitivity` | `internal` | No external user data flowing through |

### What the template gives you
- `infrastructure/containers/docker-compose.yml` — local multi-container dev
- `infrastructure/containers/lg_agent/Dockerfile` — production container image
- `.github/workflows/ci.yml` — CI that builds and tests the container
- `Makefile` targets: `make lg-up`, `make adk-up` (local dev), `make docker-build` (production)

### Trade-offs
- **Pro:** Simple mental model (one thing to deploy); cheap (Railway/Render free tier); team can share
- **Con:** No frontend (API only, or very basic); scaling is "make the one container bigger"; no user-level auth (shared API key at best)
- **Upgrade path:** Add a frontend → split_service topology. Add auth → Supabase integration.

---

## Cloud Service (Long-Running)

### What it is
A deployed service running 24/7 on a cloud platform (Railway, Render, AWS ECS, GCP
Cloud Run). Same as Docker but with proper hosting, monitoring, and optionally a
custom domain.

### When to use it
- The system needs to be available when nobody's actively running it
- Multiple users access it throughout the day
- You need reliability (auto-restart, health checks, logging)
- Still internal users — but distributed (remote team, multiple offices)

### When NOT to use it
- Traffic is very bursty with long idle periods (serverless is cheaper)
- You need sub-100ms cold starts (serverless has cold starts; long-running doesn't)
- Budget is $0 (Railway free tier has limits; Render free tier sleeps on inactivity)

### Complexity rating
**Multi-sprint** — same as Docker plus: environment variable management, health
checks, logging, maybe a CI/CD pipeline for auto-deploy on merge.

### Example scenario
A workforce development nonprofit uses the AI daily for job-matching. Five case
managers across 3 boroughs access it throughout the day. Needs to be up during
business hours without anyone "starting" it. Railway with a custom domain, auto-deploy
from the main branch.

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `deployment_target` | `cloud` | Long-running cloud service |
| `primary_backend_language` | `python` | Python backend (add TS if frontend needed) |
| `frontend_backend_topology` | `single` | One backend service (add frontend later if needed) |
| `primary_users` | `internal` | Distributed internal team |
| `data_sensitivity` | `internal` or `restricted` | Depending on client data flowing through |

### Trade-offs
- **Pro:** Always available; professional-grade reliability; team doesn't need to "start" anything
- **Con:** Monthly cost even when idle; needs monitoring (what if it crashes at 2am?); environment management
- **Key consideration for DSSG:** Railway's free tier ($5/mo credit) handles most DSSG workloads. Don't over-engineer hosting for a system that serves 5-20 users.

---

## Split Service (Frontend + Backend)

### What it is
Two separately deployed services: a frontend (typically Next.js on Vercel) and a
backend (typically FastAPI on Railway). They share identity via a common auth
provider (Supabase Auth) and communicate over HTTPS. Each scales independently.

### When to use it
- External users (nonprofit clients, community members) need a polished web interface
- Multi-tenancy required (each org sees only their own data)
- Frontend and backend have different deployment/scaling needs
- The team has both frontend and backend expertise

### When NOT to use it
- All users are internal (a single-service API with a simple UI suffices)
- The team is 1-2 people (split-service doubles operational burden)
- Weekend sprint (too much infrastructure for a prototype)
- No frontend expertise on the team

### Complexity rating
**Semester** — needs: two deployments, shared auth (Supabase), CORS configuration,
environment management for both services, JWT validation, frontend routing + middleware.

### Example scenario
A legal aid org wants tenants to check their case status. Tenants (external users)
log in via a web app, see their own cases, chat with an AI about their rights. The
Next.js frontend runs on Vercel (fast, global CDN). The FastAPI backend runs on
Railway (handles the LLM calls, database queries). Supabase Auth provides login +
RLS for tenant data isolation.

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `primary_backend_language` | `both` | Python backend + TypeScript frontend |
| `frontend_backend_topology` | `split_service` | The whole point of this topology |
| `primary_users` | `customers` | External users need auth + data scoping |
| `deployment_target` | `cloud` or `serverless` | Vercel (frontend) + Railway (backend) |
| `data_sensitivity` | `restricted` | External user data requires protection |
| `agent_memory` | `long_term` | Users expect continuity across sessions |
| `vector_backend` | `postgres` | Supabase Postgres for both vectors + app data |
| `ts_agent_framework` | `vercel_ai_sdk` | TS-native agent for frontend API routes (optional) |

### What the template gives you
- Next.js 15 frontend with App Router + Supabase Auth
- `src/middleware/auth.py` — FastAPI middleware validating Supabase JWTs
- `vercel.json` — Vercel deployment config
- `railway.toml` — Railway deployment config
- Edge middleware for protected routes on the frontend
- Supabase client initialization (`src/lib/supabase.ts`)

### Trade-offs
- **Pro:** Professional-grade UX; proper security; each piece scales independently; Vercel's global CDN for frontend
- **Con:** Highest complexity; two deployments to manage; CORS + auth configuration; more expensive; needs full-stack team
- **Key consideration for DSSG:** This is the "real product" topology. Only choose it if the nonprofit's clients/community will use it directly. Internal tools should use single-service.

---

## Serverless

### What it is
Functions that spin up on demand and shut down after execution. No persistent server.
You pay per invocation, not per hour. Best for low-traffic, bursty workloads.

### When to use it
- Traffic is unpredictable (mostly quiet, occasional bursts)
- Budget is tight (pay only for actual usage)
- The AI tasks are stateless and complete quickly (< 30 seconds per call)
- You're already using Vercel for a frontend (serverless functions are native)

### When NOT to use it
- Responses take > 30 seconds (function timeouts)
- You need persistent connections (WebSockets, streaming)
- High sustained traffic (serverless gets expensive at scale)
- You need in-memory state between requests

### Complexity rating
**Multi-sprint** — simpler deployment than long-running (no container management),
but cold starts and timeouts require careful design.

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `deployment_target` | `serverless` | Functions-as-a-service model |
| `ts_agent_framework` | `vercel_ai_sdk` | Vercel AI SDK designed for serverless |
| `primary_backend_language` | `typescript` | Most serverless platforms prefer TS/Node |

### Trade-offs
- **Pro:** Zero cost when idle; auto-scales; no server management; deploys instantly via Vercel/AWS
- **Con:** Cold starts (1-3s on first request); timeout limits; no persistent state; debugging is harder
- **Key consideration for DSSG:** Good fit for low-traffic tools (< 100 requests/day) that don't need streaming. Not ideal for chat applications that need persistent connections.

---

## Decision Shortcut

| Question | Answer → Topology |
|----------|-------------------|
| "Who uses this?" | Just me → Local. My team → Single/Docker. External users → Split service. |
| "What's the budget?" | $0 → Local or serverless free tier. $5-20/mo → Single service. $40+ → Split. |
| "Do external users log in?" | No → Single service. Yes → Split service (needs auth). |
| "How many hours does the team have?" | Weekend → Local. Multi-sprint → Single/Docker. Semester → Split service. |
| "Does it need to be up 24/7?" | No → Local. Business hours → Cloud. Always → Cloud or serverless. |
