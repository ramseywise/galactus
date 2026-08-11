# Agent Tools — Conventions

**Durable question:** What makes a tool call gateable, auditable, and parallel-safe? When should a capability become an MCP server rather than an in-process tool?

*Tooling-agnostic. For LangGraph tool patterns see `langgraph.md`. For MCP server scaffolding see `cap-mcp.md` (payload).*

---

## 0. Tools consume context twice

*"Tools consume context **twice**: their **definitions** sit in the window permanently, and their **results** enter it per call."*

Both halves are budget. A definition is resident cost paid on every turn whether or not the tool is called; a result is transient cost paid per call. The two are optimized differently — definitions by terseness and by not loading them at all, results by filtering at the tool boundary.

Loading every tool and MCP server at startup *"degrades performance before the agent starts working."* Progressive disclosure is the counter-move: a short name and description (~10 tokens) stay resident, and the full body loads on demand — *"a capability library of dozens of skills costs a few hundred tokens at rest."* *(Source: `mcp/tool-design-as-context-engineering.md`, `harness/tool-design-as-harness-surface.md`)*

---

## 1. Tool design principles

Every tool should answer "yes" to all four questions before shipping:

1. **Reversible?** Can this action be undone, or does it need a confirmation gate?
2. **Idempotent?** If called twice with the same inputs, is the second call a no-op?
3. **Observable?** Does the tool return enough structured data to audit what it did?
4. **Parallel-safe?** If two agent turns call this tool concurrently, are there no race conditions?

Tools that fail #1 need a confirmation step in the agent loop before execution. Tools that fail #4 need explicit serialization or a locking strategy noted in their documentation.

### A fifth question, in a duplex design: fast enough?

Schema, naming, and error contracts transfer to voice unchanged — everything in §3 through §7 applies as written. What text guidance never has to ask is how long a tool takes, because in chat the answer is invisible: a spinner sits there for two seconds and nobody minds.

On a phone call the same two seconds is dead air, and a caller reads dead air as the line dropping. **A tool call inside a voice turn draws on the turn's latency budget — the caller's silence budget — and that budget is under a second** — it competes with the LLM's own time-to-first-token, which is already the dominant hop (`agent-voice.md §2`). A 2s availability lookup is not a slow tool in this setting; it is a failed turn.

So a fifth question, for duplex designs only:

5. **Fast enough?** Does this tool return inside the turn's silence budget — and if it cannot, what does the caller hear while it runs?

The second half is the real requirement, because plenty of necessary tools are honestly slow. The mitigation is to **fill the silence**: speak first, then call. "Let me check that for you" is not filler — it converts an unexplained gap into an expected wait, and it buys most of a second at no cost to the turn. Emit the acknowledgement to TTS *before* dispatching the call, not after it returns.

Where a tool is slow enough that even that fails, the design decision moves up a layer: prefetch it before the turn needs it, cache it across the session, or tell the caller you will follow up rather than holding them on a silent line.

---

## 2. Promote-from-bash heuristic

Start with a bash/shell tool. Promote to a dedicated tool when you need any of:

| Need | Promote because |
|---|---|
| **Gate** (confirm before execute) | The loop needs a structured hook; raw bash has none |
| **Render** (display in UI) | Structured output schema enables client rendering |
| **Audit** (log inputs/outputs) | Dedicated tool can emit typed spans; bash output is a string |
| **Parallelize** (safe concurrent calls) | Tool can be designed idempotent; bash scripts often aren't |
| **Retry with backoff** | Tool wrapper can implement retry policy cleanly |

Do not promote just to "clean up the loop". The bash/shell tool is the right default for read-only, non-parallelized, non-gated operations.

---

## 3. Tool schema rules

```
name:        snake_case, verb_noun pattern (e.g., search_documents, create_ticket)
description: one sentence — what it does, not how. Include side-effects.
parameters:  required fields first. Validate ranges/enums in the schema, not in the tool body.
return:      typed structure always. Never return raw strings to the model — wrap in {result, metadata}.
errors:      return {is_error: true, code: string, message: string} — never raise to the model.
```

The model reads the description and parameter schemas to decide whether to call the tool. A vague description produces incorrect calls. A missing side-effect note in the description bypasses safety review.

### The clarity test

*"If a human engineer can't definitively say which tool should be used in a given situation, an AI agent can't be expected to do better."* Stated as a check: given this task, is there exactly one obviously correct tool? *(Source: `harness/tool-design-as-harness-surface.md`, `mcp/tool-design-as-context-engineering.md`)*

### Terse beats verbose

Description length is resident cost (§0), so the wiki measures it: a bloated description runs ~45 tokens against ~9 for a good one, on the same tool. Parameter names carry the same load — `query: str` tells the model nothing that `search_query: natural-language description of the code you're looking for` doesn't tell it better. *(Source: `mcp/tool-design-as-context-engineering.md`)*

> **Conflict — flagged, not resolved.** The one-sentence rule above is not the only shape the wiki recommends. `harness/tool-design-as-harness-surface.md` gives a **five-section contract** — *What it does / WHEN TO USE / WHEN NOT TO USE / DO NOT USE FOR / EXAMPLES* — and asserts *"the two negative sections do the heavy lifting."* It also constrains how those sections are written: each `DO NOT USE FOR` entry should be **ratchet output**, *"traceable to an actual observed misuse"* rather than speculated. A five-section contract is not one sentence. The reconciling read is that the negative sections are what disambiguation costs once a registry has overlapping tools — but the specs disagree on the default, and this one has not been reconciled against the ~9-token target above.

### Return the answer, not the dump

*"A tool returning 50k tokens of raw output defeats just-in-time retrieval."* Offload the dump to disk and return a path reference. **Filter at the tool boundary**, *"where filtering is cheap and deterministic — not in the model."* *(Source: `harness/tool-design-as-harness-surface.md`, `mcp/tool-design-as-context-engineering.md`)*

### Separate the contract from the execution

Keep schema + description separate from execution logic — a factory pattern does this. *"Coupling them means every wording change touches executable code."* Since descriptions are tuned iteratively against observed misuse, that coupling makes the ratchet expensive. *(Source: `harness/tool-design-as-harness-surface.md`)*

> **Naming divergence.** The error shape above (`{is_error, code, message}`) does not match the wiki, which specifies *"structured errors with a stable `error_code`, plus `is_fatal` and `retry_after` where relevant"* — the rationale being that *"an error the agent can classify is an error it can recover from."* Three field sets are in play across this spec and two wiki pages. `is_fatal` and `retry_after` in particular carry information this spec's shape cannot express, and `agent-reliability.md §2` needs both to select a retry class. *(Source: `harness/tool-design-as-harness-surface.md`, `mcp/tool-design-as-context-engineering.md`)*

---

## 4. Tool registry conventions

When a system has more than five tools:

- **Group by domain**, not by implementation layer. The model needs to find the right tool, not understand your codebase.
- **Version tools** when their schema changes. Old callers break on silent schema changes.
- **Disable, don't delete** tools that are no longer needed in a given loop — keep their schema available for audit.

For dynamic tool sets (tools loaded at runtime from an external registry), document which tools are available at session start vs. loaded mid-turn. The model cannot call a tool it was not offered.

### Subtraction is a legitimate optimization

*"The dominant failure mode is bloated tool sets with overlapping functionality."* The rule above — disable, don't delete — preserves audit history, but it is not a reason to keep a tool *offered*. When two tools overlap, removing one from the offered set is the fix, and it is a real optimization rather than a concession. *(Source: `harness/tool-design-as-harness-surface.md`)*

---

## 5. MCP vs. in-process decision

| Criterion | In-process tool | MCP server |
|---|---|---|
| Latency tolerance | < 50ms path | > 100ms tolerable |
| Caller diversity | Single agent | Multiple agents / external callers |
| Security boundary | Same trust zone | Cross-trust-boundary isolation needed |
| State | Stateless | Can be stateful (server manages it) |
| Discovery | Agent-specific | Needs standardized discovery |
| Deployment independence | Coupled to agent | Independent deployable |

**Lean toward in-process** for agent-internal tools (search, format, validate). Promote to MCP when:
- Multiple agents (possibly in different runtimes) need the same capability.
- The capability has state that should not live in any single agent.
- You need to version and deploy the capability independently.
- A non-agent caller (IDE, CI, external service) also needs the capability.

The two-layer stack (MCP for vertical tool access + A2A for horizontal agent-to-agent) is the settled 2026 enterprise default. MCP governs tools; A2A governs agents calling agents.

> **Conflict — flagged, not resolved.** The wiki does not describe a two-layer stack. It describes a **five-protocol** one — MCP, A2A, **A2UI**, **AP2**, **UCP** — and grades them by maturity rather than presenting the mature two as the whole picture: *"MCP and A2A have real adoption... A2UI appears in working systems... AP2 and UCP are the newest and least proven; treat them as direction rather than as available infrastructure."* Read against that, the sentence above is right about what is *settled* and wrong about what *exists*. *(Source: `mcp/agent-interoperability-protocol-stack.md`)*

### MCP is three primitives, not one

| Primitive | What it is |
|---|---|
| **Resources** | Read-only data |
| **Tools** | Actions with side effects |
| **Prompts** | Reusable templates |

Everything above in this spec addresses Tools only. A capability that is read-only data is a Resource, and modelling it as a tool gives the model a call to make where it could have had context. *(Source: `mcp/mcp-protocol.md`)*

**Transport:** SSE is the legacy two-endpoint transport; Streamable HTTP (released March 2025) is its single-endpoint successor. **Production auth is *"under active development in the MCP spec"*** — treat cross-boundary credential handling as unsettled and see `agent-safety.md §4`. *(Source: `mcp/mcp-protocol.md`)*

### Exposure is the first security question

| Deployment | Risk |
|---|---|
| localhost | Low |
| Docker, no external port | Low |
| Cloud, public port | **High** — *"treat as a public API; add auth"* |
| Tunnel / Codespaces | **High** |

Two rules follow. **Access criteria are load-bearing:** *"an MCP server's access criteria define the blast radius of every tool call the agent subsequently makes."* And **secrets never traverse the boundary** — *"never return them in tool responses — even in error messages"*; prefer to *"make the MCP server stateless and secret-free by design."* For untrusted third-party servers, a mediation layer (Google's Model Armor is the named example) sits between the agent and the server. *(Source: `mcp/mcp-server-security-patterns.md`, `mcp/agent-interoperability-protocol-stack.md`)*

### Enforce read-only at the tool-definition layer

For a knowledge-serving server, the invariant is not a confirmation gate — it is that the write tool **does not exist**. Such a server *"must never expose write tools"*, and *"the invariant is enforced at the tool-definition layer, not by a prompt instruction — a prompt instruction is soft (BY-4 in SANYI terms)."* The Librarian MCP server is the worked example: five read-only tools, *"no write, append, or delete tool is exposed."*

This is strictly stronger than §6's confirm gate, and where it applies it should be preferred. A gate can be argued past; an absent tool cannot be called. *(Source: `mcp/mcp-server-security-patterns.md`)*

### A2A: the agent card and the task lifecycle

An A2A agent publishes `/.well-known/agent.json` declaring `capabilities`, `skills[]`, and `authentication.schemes` (e.g. `["Bearer"]`). Tasks move through `submitted → working → (input-required ↔ working) → completed | failed | cancelled` — note that `input-required` is a *cycle back into* `working`, not a terminal state, so a caller that treats it as failure will abandon recoverable work. *(Source: `mcp/a2a-agent-protocol.md`)*

> **Harness guarantees do not cross a protocol boundary.** *"A sandboxed, hook-guarded, rollback-capable agent that delegates a task over A2A to a remote agent has just handed work to something with an unknown harness."* `agent-safety.md §2`'s threat model has no zone for a delegated remote agent; until it does, treat an A2A callee as an untrusted external service rather than as an extension of your own harness. *(Source: `mcp/agent-interoperability-protocol-stack.md`)*

---

## 6. Write-operation safety

Tools that write, mutate, or delete require:

1. **Description declares the side-effect** — callers (human and model) see it in the schema.
2. **Confirmation step in the loop** before irreversible execution (see `agent-safety.md §3`).
3. **Structured result returned** — not just success/failure; what was created/changed/deleted.
4. **Idempotency key** when the write could be retried — the key prevents duplicate execution.

Never allow a tool to make irreversible writes on first call without a confirmation step. The agent-side confirm gate is the harness responsibility; the tool itself should still be defensively idempotent.

**Ship read-only first.** *"Start read-only; add write tools behind confirmation"* — the sequencing matters because a write tool added later is reviewed as a change, whereas one present at launch is reviewed as part of a larger surface.

---

## 7. Observability hooks

Each tool call should emit a span. At minimum:

- Tool name and version.
- Input hash (not raw input if PII is possible).
- Duration.
- Return code / error code.
- Parent trace ID.

See `agent-observability.md` for the full span schema.

---

## Sources

- Topics 5.2, 7.1 from `2026-07-19-research-B-topic-canon.md`
- `new-agent/references/framework-adk.md` (tool patterns)
- MCP two-layer stack notes, Research B emerging/settled table
- `mcp/tool-design-as-context-engineering.md` — tools consume context twice; the clarity test; token cost of descriptions and parameter names; filter at the boundary
- `harness/tool-design-as-harness-surface.md` — five-section contract; subtraction; contract/execution separation; structured error fields; progressive disclosure
- `mcp/agent-interoperability-protocol-stack.md` — the five-protocol stack and its maturity grading; access criteria as blast radius; mediation layers; harness guarantees at a protocol boundary
- `mcp/mcp-protocol.md` — Resources / Tools / Prompts; SSE vs Streamable HTTP; auth maturity
- `mcp/mcp-server-security-patterns.md` — exposure risk table; secret-free servers; read-only enforced at the tool-definition layer
- `mcp/a2a-agent-protocol.md` — agent card schema; task lifecycle
