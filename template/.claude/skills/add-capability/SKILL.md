---
name: add-capability
description: >
  Add a capability to a scaffolded project after genesis — wraps `copier update
  -d include_<x>=true` so a deferred component (rag_agent, an MCP adapter, a
  second agent framework, an eval metric, an integration, a vector-backend
  upgrade, split_service) enters the repo through copier, never by hand-copying
  template files. Use when a parked open question's trigger fires or a milestone
  needs scaffolding that genesis deliberately left out. Triggers on: "add a
  capability", "add rag", "add an MCP server", "add an integration", "add an
  eval metric", "upgrade the vector backend", "scaffold X now", "/add-capability".
---

# /add-capability

The re-entry front door for a **rendered** project. Genesis scaffolds the base
and one shape example; everything deferred lands here, over time, when its
trigger fires. This skill is the capability-focused wrapper around
`/new`'s §Re-entry mechanism — same engine (`copier update`), same
clean-tree gate, but you name a *capability* instead of raw copier answers.

**One rule above all:** `.copier-answers.yml` is the scaffold state, and
`copier update` is the *only* way a component enters a repo after genesis.
Never hand-copy files out of the template. If you're tempted to `cp` a
`template/...` file in, stop — that's the drift this skill exists to prevent.

## Usage

```
/add-capability <capability> [key=value ...]
```

Aliases (thin front doors to the same flow, pre-filling the capability):

| Alias | Pre-fills | Notes |
|---|---|---|
| `/add-rag` | `include_rag_agent=true` | + prompts for `vector_backend` if not already set |
| `/add-eval-metric <name>` | adds `<name>` to `eval_metrics` | `escalation`/`friction`/`intent`/`language` |
| `/add-integration <name>` | adds `<name>` to `optional_features` | `composio`/`n8n_webhook`/`web_research`/`marketing`/`meeting_intelligence` |
| `/adk-scaffold`, `/langgraph-scaffold` | (framework skills) | prefer these for agent scaffolding; they handle framework-specific setup |

## Capability → copier answer

Map the request to the copier variable(s) it flips. These are the deferrable
capabilities — the base and the genesis shape example are already on disk.

| Capability | `-d` answer | Adds |
|---|---|---|
| RAG retrieval backend | `include_rag_agent=true` (+ `vector_backend=<x>`) | `rag_agent`, corpus index, retrieval eval |
| MCP adapter | add `mcp` to `agent_tools` (seeds `include_mcp_server`) | MCP server scaffold — thin REST client, no business logic |
| Second agent framework | `primary_chat_agent=both` (from `lg_agent`/`adk_agent`) | the other framework's agent + Makefile targets |
| Vector-backend upgrade | `vector_backend=postgres` (or `opensearch`) | pgvector/OpenSearch deps + config; runtime default unchanged |
| Interaction eval metric | add `<name>` to `eval_metrics` | heuristic grader + LLM judge + report section |
| Integration | add `<name>` to `optional_features` | the integration's client(s) / receiver |
| ML/stats | add `ml` to `optional_features` | classical ML/stats toolkit |
| Split frontend/backend | `frontend_backend_topology=split_service` | Next.js frontend + JWT-auth FastAPI backend |

Multiselect variables (`agent_tools`, `eval_metrics`, `optional_features`) are
**additive** — read the current value from `.copier-answers.yml` and pass the
full new list, existing entries included, or copier will drop the ones you omit.

## Steps

### Step 1 — Confirm this is a rendered project, in re-entry

- `.copier-answers.yml` present → yes. Absent → this isn't a scaffolded project;
  the user wants `/new` (first render), not this. Say so and stop.
- Read `.copier-answers.yml`: `_src_path` (template source), `_commit` (the
  version this project tracks), and every answered variable — that's the
  baseline you're mutating one capability at a time.

### Step 2 — Clean git tree, or hard-stop

```bash
git status --porcelain
```

**Any output → refuse and stop.** Ask the user to commit or stash first. This is
a hard gate, not a warning: `copier update` merges the template diff on top of
the working tree, and running it over uncommitted work produces conflicts that
git cannot recover (the pre-diff state is gone). Same rule `/template-update`
and `/new` §Re-entry enforce — a capability add is exactly the case
they're guarding. Do not offer a `--force`; there isn't one.

### Step 3 — Resolve the capability to concrete answers

From Step 1's baseline + the request, build the `-d` list:
- Look up the capability in the table above.
- For a multiselect, merge into the existing list (Step "Capability → copier
  answer" note) — don't clobber.
- If the capability needs a companion answer the baseline doesn't have (e.g.
  `include_rag_agent=true` with no `vector_backend`), ask for it now, in the
  design's terms ("production scale, or just getting started?" → `opensearch`/
  `postgres` vs `duckdb`). "I don't know" → take copier's derived default; note
  it in the report.
- Confirm the derived `-d` list back to the user before running anything — same
  "don't silently default" discipline as `/new`.

### Step 4 — Run copier update

```bash
copier update --trust --defaults -d "<capability>=<value>" [-d ...]
```

`copier update` re-renders from `_src_path` at (or past) `_commit`, carrying all
other answers from `.copier-answers.yml` automatically — you pass only the
changed capability. If the project was rendered from a **moving working tree**
rather than a tagged ref (no usable `_commit`, or `_src_path` points at a local
checkout you're iterating on), fall back to genesis's re-entry form:

```bash
copier copy --overwrite --vcs-ref HEAD --trust --defaults \
  -d "<capability>=<value>" [-d ...] "<template_path>" .
```

carrying the other answers from `.copier-answers.yml`.

**Conflicts** (`.rej` files or merge markers) → hand off to `/template-update`,
which owns conflict walkthroughs. Don't resolve them ad hoc here; a capability
add that touches user-edited files is exactly its Step 3/4 job.

### Step 5 — Verify the capability actually landed

Render-clean is not enough — exercise it (the roadmap's own lesson: A1 required
the full runtime loop, not a render check):

- New files for the capability are present, with no leftover unrendered Jinja
  (double-brace placeholders that copier should have substituted).
- `make setup` / `uv sync` if the capability pulled new deps.
- `make test` passes; if the capability ships an eval, `make eval-heuristic`
  (or its metric-specific target) runs.
- For a service capability (MCP, rag, split_service), the thing starts —
  `make <slug>-up` / `make rag-up` / the frontend `make ts-dev`.

Report what failed with output; don't call it done on a green render alone.

### Step 6 — Close the loop

- If this capability resolved a parked question, flip its DESIGN.md Open
  Question / Key Decision from `Deferred(<trigger>)` (or `Open`) to `Resolved`.
- Re-run `/gate-check` so LIFECYCLE.md reflects the new surface (gate-check is
  its sole writer — don't hand-edit it).
- Report: capability added, `-d` used, files that appeared, verification result,
  and the DESIGN.md/LIFECYCLE.md updates.

## Notes

- **Additive by design.** This skill adds capabilities; it doesn't remove them.
  Turning a toggle back off is a `copier recopy` / manual-delete operation —
  route that to `/template-update`'s "feature I don't want" scenario.
- **REST stays the boundary.** Adding an MCP adapter never adds business logic —
  each MCP tool is a thin client of a `/api/v1/*` endpoint (Part 3c). If a
  request wants logic *in* the MCP server, that's a design smell — surface it.
- **Don't invent capabilities.** If the request maps to no copier variable, say
  the template can't scaffold it and stop — same reporting discipline as
  the framework scaffold skills. The fix is a new template toggle, not a hand-copied file.
- **Where genesis vs add-capability applies:** genesis = first render (no
  `.copier-answers.yml`); add-capability = every render after. Same engine, two
  front doors.
