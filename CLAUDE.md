# galactus

Contract-bounded LLM generation. `ai-marketing-comms/` holds the reference implementation: a FastAPI
service that generates length-constrained marketing copy grounded in uploaded PDFs.

**Thesis:** counting characters is a job for code; the model's job is content.

## Stack

Python 3.12, `uv` (never `pip` — a hook blocks it), FastAPI, Pydantic v2, Anthropic SDK,
structlog. Tests live at `ai-marketing-comms/tests/`, evals at `ai-marketing-comms/evals/`.

```bash
uv sync                              # install
uv run pytest ai-marketing-comms/tests -q           # tests
uv run python ai-marketing-comms/evals/run.py --dry-run   # evals, no API spend
```

## Specs

`.claude/specs/agent-*.md` are the convention refs — read the relevant ones **before**
writing agent code, not after. Each opens with a durable question it answers. Start with
`agent-architecture.md`; it indexes the rest against the five-layer stack.

`agent-uncertainty.md` cuts across all of them: what the system does when it does not
know. Read it alongside the layer ref, not instead of one — it owns abstention,
asymmetric cost, and reversibility, which no single layer does.

`agent-voice.md` applies only to duplex/streaming designs — audio flowing both directions
at once. Where it applies, read it *instead of* the §4 Loop guidance, not alongside: a
duplex loop has no turn boundary, so the loop rules are not stricter there, they are
inapplicable. Where the design is request → response → done, ignore it entirely.

`langgraph.md`, `python.md`, `typescript.md` are stack bindings — read after the
`agent-*` refs, never instead of them.

## The pipeline

Design → build → review, with the plan doc as the bus between phases:

| Phase | Skill | Writes |
|---|---|---|
| Design | `/design-system` | A spec: the five layers answered or explicitly deferred |
| Research | `/workflow-research` | `## Research` in `.claude/docs/plans/YYYY-MM-DD-<slug>.md` |
| Plan | `/workflow-plan` | `## Plan` in the same doc |
| Refine | `/workflow-refine` | A readiness verdict; the only writer of `REFINED` / `READY` |
| Execute | `/workflow-execute` | Code; flips `Status:` |
| Review | `/workflow-review` | Verdict against `## Plan` |

`Status:` is a state machine, not a label — a hook rejects values outside
`RESEARCH → RESEARCHED → PLANNED → REFINED → READY → IN_PROGRESS → EXECUTED → COMPLETE`
(plus `SUPERSEDED`). One work item per plan doc.

## Rules

- **`uv add`, never `pip install`.** Enforced by `pip_guard.sh`.
- **Never commit on `main`.** Work happens on `{PREFIX}-{NUM}-{slug}`, `bug/{slug}`, or
  `spike/{slug}`.
- **Leave `ai-marketing-comms/` alone** unless the task is explicitly about it. It is the case study,
  not scratch space.
- **A rule you rely on belongs in a hook, not here.** This file is a table of contents.
  If an agent can ignore a line here with no consequence, that line is documentation —
  encode it at the strongest available layer instead (hook > linter > test > tool schema
  > instruction).

## Vendoring exception

`.claude/skills/` and `.claude/specs/` deliberately duplicate names from the operator's
global `~/.claude/`. Normally that is a double-load blocker. Here it is intentional:
galactus is a self-contained showcase — anyone who clones it gets a working setup with no
access to a private home directory. **Canon remains `~/.claude/`;** the copies here are
rendered payload. Fix generic skills upstream, then re-vendor.
