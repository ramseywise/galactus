---
name: new
description: >
  Front door for starting something new. Routes AI-shaped from ML-shaped work, picks
  where it lands (a run under galactus's runs/, or a standalone repo rendered from
  this repo's copier template, Python or TypeScript), then walks only that path.
  Triggers on: "new project", "new prototype", "new poc", "start something new",
  "scaffold a project", "back at it again", "/new".
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, AskUserQuestion
---

# /new

Three questions decide everything downstream, so they come first and in this order:
**what shape** (AI or ML), **where it lands** (a run here, or its own repo), and for a
repo, **which language**. Ask the first, commit to it, then the next. Do not walk two
paths in one session.

Ask real questions, confirm before acting, never silently default. This is a
scoping-to-scaffold translator, not an onboarding ritual: no phases, growth logs or
reflection steps.

## Usage

```
/new [--branch ai|ml] [--land run|repo] [--output path] [--execute]
```

| Arg | Default | Description |
|-----|---------|-------------|
| `--branch` | ask at gate 0 | Skip the shape question when you already know |
| `--land` | ask at gate 1 | `run` → `runs/<branch>/<slug>/` here; `repo` → copier render |
| `--output` | derived from the name | Run directory, or the repo path to render into |
| `--execute` | off (**dry-run**) | Without it, every step names the write and stops |

**Dry-run is the default and it is not a formality.** Without `--execute`, write nothing:
name the file you would write and the command you would run, then wait.

## Gate 0: shape

> "Is this **AI-shaped** (an agent, RAG, a generation service, an LLM in the loop) or
> **ML-shaped** (tabular data, a target column, a model that predicts)?"

When it is unclear, ask: **is there a labelled outcome column in a frame you already
have?** If yes, it is ML, however much an LLM might appear later. A fraud model with an
LLM narrative layer is an ML project with an AI consumer: pick the branch that owns the
*risk* and note the other as downstream.

| | AI branch | ML branch |
|---|---|---|
| Specs loaded | `.claude/specs/agent-*.md` (start `agent-architecture`) + `agent-uncertainty` | `python.md` only; **no `agent-*` spec** |
| Reference run | `runs/ai/marketing-comms/` | `runs/ml/credit/` |
| Dominant risk | ungrounded generation, silent contract breach | leakage, imbalance, uncalibrated scores |

**Say which specs you are skipping and why.** Silent routing is indistinguishable from
no routing.

**ML branch:** read `reference/ml-branch.md` and walk its gates 1–7. It lands as a run
(`runs/ml/<slug>/` on the root `ml/` toolkit). The template's `ml` add-on renders ML on
top of an agent scaffold, so it is not a clean ML project yet. Gate 7 findings are the
spec for one.

## Gate 1: landing (AI branch)

| | Run (`--land run`) | Repo (`--land repo`) |
|---|---|---|
| Lands in | `runs/ai/<slug>/` in galactus | its own directory, rendered by copier |
| Good for | a spike, a demo, a thesis to test in an afternoon | something that will be deployed, shared or kept |
| Next | `/proto-scope` → `/proto-design` → BUILD band | Steps 0–6 below, then the project's own skills |

Default to **run** when the operator says spike, demo, or try. A run can graduate to a
repo later; a repo that should have been a spike is weight carried for nothing.

For a run: create `runs/ai/<slug>/{src,tests}/`, add `runs/ai/<slug>/tests` to
`testpaths` in `pyproject.toml` (a missing entry collects zero tests and reads as
passing), then hand off to `/proto-scope`. Stop here.

## Gate 2: language (repo only)

Ask it out loud. Do not let it fall through to the default:

> "Python, TypeScript, or both?"

- **python**: ships the working example agents, evals and `llm_kit`.
- **typescript**: a real Node/TS backend with its own lint, typecheck and test tooling.
  Pick it when the operator lives in TS or the thing is a Next.js / Vercel AI SDK app.
- **both**: only when there is a concrete reason for two runtimes.

Record it as `primary_backend_language` in Step 2, then continue at Step 0.

## Repo steps

### Step 0 — Check for existing DESIGN.md and planning docs

If a `DESIGN.md` or `.claude/docs/DESIGN.md` exists (produced by `/proto-scope`), read it first.
Also scan for planning docs that pre-answer infrastructure questions: `roadmap.md`,
`.claude/docs/milestones/*.md`, `.claude/docs/plans/*.md` — milestone files sometimes contain
the literal copier arguments (a live dry-run found `vector_backend=postgres` and
`primary_chat_agent=lg_agent` verbatim in a milestone's "done when"). Don't re-ask what's
already answered — but ratify inherited decisions out loud ("your milestone pins X — confirm?")
rather than silently adopting them. Surface only the questions that remain open.

If no DESIGN.md exists, consider suggesting `/proto-scope` before continuing — especially if the
user hasn't yet defined actors, MVP scope, or key architectural decisions. `/new`
works without it, but infrastructure choices made without a design are guesses.

If the target directory already contains a `.copier-answers.yml`, this is a
**re-entry**, not a first render — skip the interview except for what's changing
and follow §Re-entry below.

### Step 1 — Ask, don't hand over a form

Have a short real conversation (not a rigid checklist read verbatim). The
interview is six open questions plus confirmations of derived values — scope
first, implementation only where Phase 1 makes it relevant.

**The six asked variables (always cover these):**

1. **What are you building?** → `project_name` (free text), `project_description`
   (free text, one sentence).
2. **What type of project?** → `project_type` (`chat_app`/`agent`/`workflow`/`rag`/
   `mcp_server`/`ai_backend`/`eval_suite`/`prototype`/`existing_repo` — the last
   one is layering-only mode: `.claude/` + `mcp_servers/` if
   they want, nothing else touched). This is the derivation root — 54 vars key off it.
3. **Who uses it?** → `primary_users` (`internal`/`customers`/`developers`/`public_api`).
   Seeds data sensitivity and deployment target.
4. **What external systems does it touch?** → `external_systems` (multiselect:
   `slack`/`github`/`google_workspace`/`calendar`/`email`/`database`/`web`) —
   copier seeds integrations, `agent_tools`, and `vector_backend` from this,
   so get it right rather than skipping it.
5. **Does the agent need human approval before acting?** → `human_approval`
   (`none`/`sometimes`/`always`). A governance posture — independent of every
   other answer, and the one variable where a silent default has an irreversible
   failure mode. Always ask it out loud. (Copier's `sometimes` default is a
   reasonable seed; the human must confirm it, not accept it blindly.)

**Confirm derived values (don't re-ask — propose and let the user correct):**

After the five open questions above, surface the derived values as explicit
confirmations. Present: "Given your answers, I'm setting these — correct anything
wrong:"

- `project_slug` → `{{ project_name.lower().replace(' ', '-') }}`
- `primary_backend_language` → already asked at gate 2. Always write it to the
  answers file, even when it is `python`, so the choice is on record.
- `deployment_target` → derived from `primary_users`: `internal` → `docker`;
  `customers`/`public_api` → `cloud`; `developers` → `local`. (Cheap wrong
  guess — one CD workflow + DESIGN.md row. Surface the derivation, not a blank prompt.)
- `data_sensitivity` → derived from `primary_users`: `customers`/`public_api`
  → `restricted`; else `internal`. **Critical:** don't let this default silently
  — it drives a hard rule in the generated `CLAUDE.md` and a Terraform tag. If
  the project touches health, financial, or children's data, it must be `secret`.
  Ask explicitly: "You said customers — I'm setting data sensitivity to
  `restricted`. Anything regulated (health, financial, minors) that should make
  this `secret`?"
- `agent_tools` → seeded from `external_systems` (github/database entries carry
  over automatically). Confirm the derived list.
- `agent_memory` → `conversation` (default). Only ask if the design requires
  durable cross-session memory; `long_term` seeds the postgres checkpointer,
  which `database` in `external_systems` already implies.

The eight derived variables (`project_slug`, `primary_backend_language`,
`deployment_target`, `data_sensitivity`, `agent_tools`, `agent_memory`,
`ticket_prefix`, `enable_macos_notifications`) are all `when: false` in
`copier.yaml` — they resolve from defaults. This skill's job is to
confirm them in conversation, not to leave them as invisible guesses.

**Phase 2/3 — only when the conversation raises them (otherwise the seeded
defaults are right):**

7. **Which chat agent(s)** — LangGraph (`lg_agent`), Google ADK (`adk_agent`),
   both, or neither (build on `rag_agent` alone)? → `primary_chat_agent`.
   Copier derives a sensible default from `project_type`; only ask if the
   design names a framework. `akira` ships independently as a .claude
   skill + vendored scan agent — not product source, not "the framework".
7b. **What is the agent called?** → `agent_slug` — ALWAYS propose this from
   the project's domain (an intake assistant → `intake_triage`, a grants
   helpdesk → `grants_qa`), never leave the generic `assistant` default
   without offering a better name. It names `{{ source_root }}/agents/<slug>/`
   and the Makefile targets (`<slug>-up`/`-chat`); with `both`, ADK gets
   `<slug>_adk`. Must be a lowercase Python identifier; `rag_agent`,
   `lg_agent`, `adk_agent`, `akira` are reserved.
7c. **Prebuilt retrieval backend, or custom RAG?** → `include_rag_agent`
   (default on). Only surface this when the design describes its own
   retrieval/RAG architecture — turning it off drops `rag_agent` and the
   project points `RAG_AGENT_URL` at the custom service instead. Flag the
   conflict if `promptfoo` is selected with `include_rag_agent=false` (its
   config targets rag_agent's /chat), and note that the golden-QA retrieval
   eval then needs the LangGraph chat agent (BM25) or a custom backend
   registered in `evals/pipelines/run.py`.
8. **Vector store at production scale, or just getting started?** →
   `vector_backend` (`duckdb` default / `memory` zero-setup / `opensearch`
   cluster / `postgres` pgvector — auto-defaulted to `postgres` when `database`
   is in `external_systems`).
9. **Optional add-ons** → `optional_features` (multiselect: `akira` +
   `dev_companion` default on; `promptfoo`/`ragas`/`web_research`/
   `meeting_intelligence`/`marketing`/`n8n_webhook`/`composio`/`ml`).
   Mention only the ones the design implies — e.g. classical ML/stats work
   (baselines, forecasting, A/B) → add `ml`.
10. **Which interaction metrics matter?** → `eval_metrics` (multiselect:
    `escalation`/`friction`/`intent`/`language` — each ships a heuristic
    grader + LLM judge + report section; agent-shaped projects seed
    escalation + friction). Ask in the design's terms, not copier's: "when
    should this assistant hand off to a human?" → escalation; "does it route
    queries to the right place?" → intent; multilingual users → language.
    Retrieval eval ships regardless — don't offer it as a choice.

Skip questions whose answer is obvious from context already given (e.g. if
they've already said "no existing repo, brand new thing", `project_type` can't
be `existing_repo`). Everything not covered keeps copier's own derived default
— don't invent additional questions, and don't ask about anything in
copier.yaml's "inferred, never asked" tier (`source_root`, `eval_root`,
`python_version`, `aws_region`, ...) unless the user brings it up.

**"I don't know" never blocks the render.** An unknown answer means: leave the
variable unset (the seeded default fills it), park the question in DESIGN.md's
Open Questions with a revisit trigger — or, for a Key Decision, record it as
`Deferred(<trigger>)` with the default noted — and offer `/research` /
`/parallel-research` to close it. Scaffold the base now; the capability lands
later via re-entry (§Re-entry) when the trigger fires. Genesis never blocks on
a deferred decision.

### Step 2 — Map to copier variables

Build the `-d key=value` list from Step 1's answers. The six asked variables
always go in. The eight derived vars (`project_slug`, `primary_backend_language`,
`deployment_target`, `data_sensitivity`, `agent_tools`, `agent_memory`,
`ticket_prefix`, `enable_macos_notifications`) are all `when: false` in
copier.yaml — include them in the answers file only if the user overrode the
derived value in Step 1's confirmations. Leave anything else not explicitly
discussed unset — it'll fall through to `copier.yaml`'s own default via
`--defaults` in Step 4.

### Step 3 — Confirm before acting

Show the derived answer table back to the user (variable → value → why) before
running anything. If an answer feels like a guess rather than something they
actually said, ask directly instead of assuming — same discipline as
`new-agent/SKILL.md`'s "don't silently default."

### Step 4 — Write the answers file

Write the answers from Step 2 to `/tmp/new-answers.yml`. Do not run copier
here — the file is the deliverable of this step, and it is reviewable before
anything hits disk.

```yaml
# /tmp/new-answers.yml  — generated by /new
# Review, then run: make -C ~/workspace/galactus project ANSWERS=/tmp/new-answers.yml output_dir=<path>
project_name_input: <name>
project_slug: <slug>
project_description: <description>
project_type: <chat_app|agent|workflow|rag|mcp_server|ai_backend|eval_suite|prototype|existing_repo>
primary_users: <internal|customers|developers|public_api>
# ...one key per answer from Step 2's table; omit keys not covered (--defaults fills them)
```

Include only the variables explicitly covered in the conversation. Multiselects
use YAML list syntax (`[a, b]`). Hidden/derived variables (`scaffold_full_project`,
`include_*`, `vector_backend` when not asked, `source_root`, ...) may be pinned
here when the conversation explicitly named them — otherwise omit and let
`--defaults` derive them.

Show the user the written file path and contents, then present the render command
from Step 5. **Do not run it — the user runs it after review.**

### Step 5 — Review and render

Tell the user to review `/tmp/new-answers.yml`, then render:

```bash
make -C ~/workspace/galactus project ANSWERS=/tmp/new-answers.yml output_dir=<absolute_path>
```

Resolve `<output_dir>` to an absolute path first (e.g. `mkdir -p ~/workspace/my-project && cd ~/workspace/my-project && pwd`) — a relative path has previously caused a broken `mv` mid-render.

**Rendering into an existing repo** (files already present) needs a protocol, not
hope:
1. Before rendering: `git status` the target; snapshot any UNTRACKED files that the
   template will touch (`README.md`, `.claude/**`) to a backup dir — git cannot
   restore untracked files.
2. Add `OVERWRITE=1` to the make invocation (`make project ANSWERS=... output_dir=... OVERWRITE=1`).
3. After rendering: restore user-owned files the template clobbered — at minimum
   `git checkout -- README.md` if the repo had a real README — and report exactly
   which pre-existing files were overwritten vs preserved.

After a successful render: if Step 0 found a DESIGN.md, copy it over
`<output_dir>/DESIGN.md` (the rendered stub is blank — the real design wins), and
transcribe its Evaluation table into `<output_dir>/evals/targets.yaml` (uncomment/
add one `metric: target` line per table row whose metric the eval runner measures;
metrics it doesn't measure stay in DESIGN.md only — name them in the Step 6 report
as manual-grading targets). If the design's data classification disagrees with the
`data_sensitivity` answer just rendered, stop and ask — don't reconcile silently.

### Step 6 — Report

Summarize what was generated (directory tree, notable toggles that ended up
on/off), report whether a DESIGN.md was carried over and which Evaluation
targets landed in `evals/targets.yaml` (vs. manual-grading targets that stayed
in DESIGN.md only), and surface the template's own next steps (mirrors `_message_after_copy`
in `copier.yaml`: review `CLAUDE.md`'s Hard Rules, `chmod +x .claude/hooks/*.sh`
if needed, `make setup` then the chat agent's `make <agent_slug>-up` (or
`make rag-up` when only rag_agent ships) if `scaffold_full_project`, `uv sync` inside
`mcp_servers/<slug>` if `include_mcp_server`, and `/sanyi init` to define the
project's change-contract now that its shape is set).

## Re-entry — running genesis again

The render is not a one-shot commitment. `.copier-answers.yml` in the generated
project is the **scaffold state**: it records every answer, and changing an
answer through copier is the only way components enter a repo after genesis —
never hand-copy template files in.

1. **Detect:** `.copier-answers.yml` present in the target → re-entry mode
   (Step 0). Read it; the recorded answers are the baseline. Interview only
   what's changing — usually a parked open question whose trigger fired
   ("first external consumer appeared" → `include_mcp_server=true`).
2. **Clean tree first:** `git -C <target> status` must be clean before
   re-rendering — copier conflicts on top of uncommitted work are
   unrecoverable. Hard-stop and ask the user to commit/stash otherwise.
3. **Execute:** `copier update -d <changed>=<value>` when the project was
   rendered from a tagged version; from a moving working tree,
   `copier copy --overwrite --vcs-ref HEAD --defaults -d <changed>=<value> . <target>`
   with the other answers carried from `.copier-answers.yml`. Conflict
   walkthroughs are `/template-update`'s job — hand off there when the diff
   touches user-edited files.
4. **Close the loop:** mark the parked DESIGN.md question/decision `Resolved`,
   and re-run `/gate-check` in the target if it tracks LIFECYCLE.md.

Re-entry is idempotent gap-filling: unchanged answers re-render to identical
files; only the flipped toggle's files appear.

**Adding a single capability to an already-rendered project?** Run
`/add-capability <x>` *in that project* instead of driving copier by hand — it's
the capability-named front door over this same mechanism (clean-tree gate,
`copier update -d`, close-the-loop → gate-check), with aliases `/add-rag`,
`/add-eval-metric`, `/add-integration`. This §Re-entry path is for the
template-author's cross-repo view; `/add-capability` is what ships into and runs
inside the generated project.

## Notes

- **Tell the user the add-later story in Step 5's report — always.** Point them
  at §Re-entry: scaffold the MVP now, flip toggles later when actually needed.
  Users who don't know this over-scaffold "just in case" — say it explicitly.
- **Legacy toggle → new axis mapping** (planning docs written against the old flat
  interview stay actionable — both forms are honored by `-d`):

  | Old toggle | New interview source |
  |---|---|
  | `include_calendar_integration=true` | `calendar` in `external_systems` |
  | `include_meeting_intelligence=true` | `meeting_intelligence` in `optional_features` |
  | `include_ml=true` | `ml` in `optional_features` |
  | `include_promptfoo/ragas/web_research/composio/n8n_webhook` | same name in `optional_features` |
  | `scaffold_full_project=false` | `project_type=existing_repo` |

- The raw `make new_project` (interactive) / `make new_project_dev` (dirty
  working tree, no commit required) targets in this repo's `Makefile` remain
  the power-user/CI/scriptable path — this skill doesn't replace them, it's a
  friendlier front door for the common case.
- If the conversation reveals a need this template genuinely can't scaffold
  (a capability with no corresponding copier toggle), say so explicitly rather
  than silently dropping it — same reporting discipline as `new-agent`'s Step 4.
- **Recommended sequence:** `/proto-scope` (design interview → DESIGN.md) → `/new`
  (infrastructure interview → copier). Running `/new` alone is valid but means
  infrastructure choices are made without design context. The generated project includes a
  blank `DESIGN.md` stub as a reminder to fill it in.
