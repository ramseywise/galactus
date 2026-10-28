# Agent Orchestration Patterns

How the AI's logic is structured and executed. This choice determines how much
control you have over the AI's reasoning, how complex the implementation is, and
which framework dependencies you take on.

---

## Quick Comparison

| Pattern | Control level | Complexity | Best for |
|---------|--------------|-----------|----------|
| Single prompt (no agent) | None (one LLM call) | Minimal | Simple generation, classification |
| Single agent + tools | Medium (LLM decides) | Low-Medium | Straightforward tool-calling tasks |
| Multi-step graph | High (you define flow) | Medium-High | Complex workflows with branching |
| Multi-agent (crews/teams) | Variable (agents delegate) | High | Large systems with specialized roles |

---

## Single Prompt (No Agent Framework)

### What it is
One LLM call: input → prompt → output. No tools, no state, no framework. The
simplest possible AI system.

### When to use it
- The task is classification, extraction, or summarization (input → structured output)
- No external tools needed (no database queries, no API calls, no file access)
- Each request is independent (no conversation history needed)
- Weekend sprint / prototype — get something working in hours

### When NOT to use it
- The AI needs to take actions (call APIs, update databases)
- Multiple steps are required (look up → reason → act)
- Conversation history matters
- You need streaming or real-time interaction

### Complexity rating
**Weekend sprint** — literally one API call with a well-crafted prompt.

### Example scenario
An arts nonprofit needs grant reports reformatted from their internal template to
each funder's required format. Input: raw report + funder requirements. Output:
reformatted text. One LLM call, no tools needed.

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `project_type` | `prototype` or `ai_backend` | No full agent framework needed |
| `primary_chat_agent` | `none` | Build on rag_agent's infra without a chat agent |

### Trade-offs
- **Pro:** Simplest implementation; cheapest to run; easiest to evaluate; fastest to build
- **Con:** No tools, no memory, no complex reasoning; limited to what one LLM call can do
- **Upgrade path:** When you hit limits, add tool-calling → becomes "single agent + tools"

---

## Single Agent + Tools

### What it is
One agent with access to tools (search, database, calendar, APIs). The LLM decides
which tools to call, in what order, and when it has enough information to respond.
The framework handles the tool-calling loop.

### When to use it
- The AI needs to look things up or take actions to answer
- Tool selection is straightforward (the right tool is usually obvious from the question)
- One "personality" or role is sufficient (not multiple specialized agents)
- The happy path is: understand question → call 1-3 tools → synthesize answer

### When NOT to use it
- Complex branching logic (if X, do A; if Y, do B; if both, do C)
- Multiple specialized roles needed (researcher + writer + reviewer)
- You need human approval gates at specific points in the flow
- The process has loops (retry until quality threshold met)

### Complexity rating
**Multi-sprint** — needs: agent framework setup, tool definitions with schemas,
error handling, evaluation of tool selection quality.

### Example scenario
A workforce development org's case managers ask: "What programs is this client
eligible for?" The agent searches the eligibility database, checks the client's
profile, cross-references with program requirements, and returns a ranked list.
One agent, three tools (client lookup, program search, eligibility check).

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `project_type` | `agent` or `chat_app` | Agent-shaped project with tool-calling |
| `primary_chat_agent` | `lg_agent` (Python) or use `ts_agent_framework: vercel_ai_sdk` (TypeScript) | Single agent loop |
| `agent_tools` | `[mcp, custom]` | MCP for standard tools; custom for project-specific |
| `agent_memory` | `conversation` | Remember context within a session |

### Framework choice for single agent

| Framework | Runtime | Best when |
|-----------|---------|-----------|
| **LangGraph** | Python | You want explicit state management; already using LangChain tools |
| **Google ADK** | Python | Deploying to GCP; want managed session service; Gemini-first |
| **Vercel AI SDK** | TypeScript | Agent lives in a TS/Node backend; deploying to Vercel |

### Trade-offs
- **Pro:** Handles most real-world tasks; frameworks provide structure; good evaluation story (grade tool selection + final answer)
- **Con:** LLM decides tool order (sometimes wrong); needs good tool descriptions; framework lock-in
- **Key insight:** Most DSSG projects need this level and no more. Resist the urge to build multi-agent systems when one agent with good tools would work.

---

## Multi-Step Graph (LangGraph)

### What it is
You define a directed graph of processing steps (nodes) with explicit transitions
(edges). The LLM executes within nodes but YOU control the flow between them.
Supports branching, loops, parallel execution, and human-in-the-loop gates.

### When to use it
- The process has clear phases (extract → validate → enrich → decide → act)
- Branching logic: different paths based on intermediate results
- Human approval needed at specific checkpoints (not just "sometimes")
- Retry/reflection loops: "grade your own output, retry if below threshold"
- Parallel processing: fan-out to multiple tools/LLMs, fan-in results

### When NOT to use it
- Simple tool-calling suffices (over-engineering)
- The team is small and can't maintain graph complexity
- You're still figuring out what the steps should be (prototype first, graph later)

### Complexity rating
**Multi-sprint to semester** — needs: state schema design, node implementation,
edge logic, error handling per node, checkpointing for resumability.

### Example scenario
A housing org's intake pipeline: New client submits form → extract structured data
(node 1) → validate against known database (node 2) → if match found, merge records
(node 3a); if no match, create new record (node 3b) → assign case worker based on
caseload (node 4) → human review gate (node 5: case manager confirms assignment) →
send confirmation to client (node 6).

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `project_type` | `workflow` or `agent` | Graph-based orchestration |
| `primary_chat_agent` | `lg_agent` | LangGraph provides the graph primitives |
| `human_approval` | `sometimes` or `always` | Graph nodes can be interrupt points |
| `agent_memory` | `long_term` | Graph state persists across interrupts |
| `vector_backend` | `postgres` | Postgres checkpointer for durable graph state |

### What the template gives you
- `agents/lg_agent/graph/` — StateGraph definition (nodes, edges, state schema)
- `agents/lg_agent/nodes/` — individual node implementations
- `.agents/skills/langgraph-fundamentals/` — reference for StateGraph, nodes, edges, streaming
- `.agents/skills/langgraph-persistence/` — checkpointers, thread IDs, Store
- `.agents/skills/langgraph-human-in-the-loop/` — interrupt(), resume, approval gates

### Trade-offs
- **Pro:** Full control over flow; explicit error handling per step; human gates at precise points; resumable (checkpointed state)
- **Con:** More code to write and maintain; graph design is a skill; harder to modify once built; overkill for simple tasks
- **Key insight:** Start with a single agent. If you find yourself writing "if the tool result shows X, then call tool Y" — that's a graph wanting to exist. Refactor into LangGraph then, not before.

---

## Multi-Agent (Specialized Roles)

### What it is
Multiple agents, each with a specific role (researcher, writer, reviewer, coordinator),
working together on a task. One orchestrator agent delegates to specialists. Each agent
has its own tools, system prompt, and expertise.

### When to use it
- The task genuinely requires different "modes" of thinking (research vs. writing vs. critique)
- A single prompt/agent can't maintain quality across all subtasks
- The system is large enough to warrant specialization (5+ distinct responsibilities)
- You want to scale by adding specialists without changing the core agent

### When NOT to use it
- One agent with good tools can handle it (most cases)
- Team is small (< 4 engineers) — maintaining multiple agents is expensive
- The "roles" are just different prompts for the same task
- Weekend or multi-sprint timeline (this is semester-scope work)

### Complexity rating
**Semester** — needs: agent-to-agent communication protocol, shared state management,
orchestration logic, per-agent evaluation, failure handling when one agent fails.

### Example scenario
A research nonprofit producing policy briefs: Orchestrator agent receives a topic →
delegates to Researcher agent (searches academic databases, government sites, news) →
passes findings to Analyst agent (identifies key themes, contradictions, gaps) →
passes analysis to Writer agent (drafts the brief in house style) → passes draft to
Editor agent (checks citations, tone, factual claims) → returns polished brief.

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `project_type` | `agent` | Multi-agent system |
| `primary_chat_agent` | `lg_agent` or `both` | LangGraph for orchestration graph |
| `agent_tools` | `[search, mcp, custom]` | Each specialist gets different tools |
| `deployment_target` | `cloud` | Always-on for complex orchestration |

### Trade-offs
- **Pro:** Highest quality for complex tasks; modular (add/remove specialists); each agent can be evaluated independently
- **Con:** Highest complexity; expensive (multiple LLM calls per task); hardest to debug (which agent caused the error?); slowest (sequential agent calls)
- **Recommendation for DSSG:** Almost certainly overkill for a POC. Start with a single agent. If quality suffers because one agent can't handle all roles, add one specialist at a time. Never start with multi-agent.

---

## Decision Shortcut

| Question | Answer → Pattern |
|----------|------------------|
| "Does the AI need tools (search, APIs, databases)?" | No → Single prompt. Yes → continue below. |
| "How many tools, and is selection obvious?" | 1-5 tools, obvious selection → Single agent. |
| "Does the process have explicit phases with different logic?" | Yes → Multi-step graph (LangGraph). |
| "Do you need human approval at specific checkpoints?" | Yes → Multi-step graph with interrupt nodes. |
| "Does quality require genuinely different thinking modes?" | Yes → Multi-agent. No → Single agent with better prompts. |
| "How long do you have?" | Weekend → Single prompt. Multi-sprint → Single agent or graph. Semester → Graph or multi-agent. |

---

## Framework Decision Matrix

Once you've chosen a pattern, pick the framework:

| Decision | → Framework |
|----------|-------------|
| Runtime is TypeScript, deploying to Vercel | **Vercel AI SDK** |
| GCP deployment, managed sessions, Gemini-first | **Google ADK** |
| Need graph control flow (branching, loops, HITL) | **LangGraph** |
| Multi-provider LLM support needed | **LangGraph** (via LangChain integrations) |
| Simple single agent, no preference | **ADK** (less boilerplate than LangGraph for simple cases) |

See `.agents/skills/framework-selection/SKILL.md` for the complete decision guide
with detailed comparison table.
