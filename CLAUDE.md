# galactus

Contract-bounded LLM generation. `runs/ai/marketing-comms/` holds the reference implementation: a FastAPI
service that generates length-constrained marketing copy grounded in uploaded PDFs.

**Thesis:** counting characters is a job for code; the model's job is content.

## Stack

Python 3.12, `uv` (never `pip` — a hook blocks it), FastAPI, Pydantic v2, Anthropic SDK,
structlog. Tests live at `runs/ai/marketing-comms/tests/`, evals at `runs/ai/marketing-comms/evals/`.

```bash
uv sync                              # install
uv run pytest runs/ai/marketing-comms/tests -q           # tests
uv run python runs/ai/marketing-comms/evals/run.py --dry-run   # evals, no API spend
uv run uvicorn api:app --app-dir runs/ai/marketing-comms/src --port 8000   # serve the demo
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

## Routing — pick the cheapest thing that answers

Decide what a request deserves before reaching for a phase. Most requests deserve no
pipeline at all. Full band, state-machine and tool reference:
[.claude/docs/pipeline.md](.claude/docs/pipeline.md) — read it only when entering BUILD.

| Request looks like | Do | Runs as |
|---|---|---|
| Clear bug with a repro, a rename, a one-file change, a question | Just do it. No plan doc | inline |
| Unfamiliar area, several plausible approaches, answer spread over many files | `research-scout` per angle, in parallel; keep the conclusion, not the dumps | haiku ×N |
| Work spanning sessions, or touching hooks, `template/`, or the reference run | `/proto-build` — routes research → plan → refine (→ execute → review once `READY`) | sonnet workers |
| A pain point or idea with no design yet | `/proto-scope` (`discovery` if no design vocabulary) | inline — it is a conversation |
| A plan or spec resting on a guess | `/assumption-audit` | CROSS |
| A plan about to ship | `/review-defense` | CROSS |
| A design that must handle not-knowing | `/fog` | CROSS |
| "Is this done?" before commit | `/proto-review` | haiku ×dims |
| An afternoon thesis, a library trial | `/spike` | inline |
| Where should new work live (run vs repo, AI vs ML) | `/new` (typed) | inline |

**Human seats are never routed around**, by `/proto-build` or anything else: the goal
question before a plan, the `Track:` question when ambiguous, the `READY` gate, and the
commit. Everything else between phases is bookkeeping and belongs in a subagent.

A small plan doc may use the light header (`Status:`, a one-paragraph `Done target:`,
steps) and go `RESEARCH → PLANNED` without a research phase. A new plan doc carries no
`From:`; the hook rejects it.

## Rules

- **`uv add`, never `pip install`.** Enforced by `pip_guard.sh`.
- **Never commit on `main`.** Work happens on `{PREFIX}-{NUM}-{slug}`, `bug/{slug}`, or
  `spike/{slug}`.
- **Runs under `runs/` are working code, not frozen exhibits.** Refactor, fix, and bring
  them to convention like anything else here. `runs/ai/marketing-comms/` is the reference
  implementation, so changes to it should be deliberate and keep its 318 tests green —
  but "it is the case study" is not a reason to leave drift in place.
- **A new test directory under `runs/` must be added to `testpaths` in `pyproject.toml`.**
  Omitting it does not fail; it collects zero tests, which reads exactly like passing.
- **A rule you rely on belongs in a hook, not here.** This file is a table of contents.
  If an agent can ignore a line here with no consequence, that line is documentation —
  encode it at the strongest available layer instead (hook > linter > test > tool schema
  > instruction).

## Canon lives here

`.claude/skills/`, `.claude/specs/` and `.claude/hooks/` in this repo are the canonical
copies. `~/.claude/` holds none of them and is not upstream of anything here. Links point
the other way: `~/.claude/skills/new` is a symlink into this repo, so `/new` works from any
directory, and the convention refs in `~/.claude/refs/` are symlinks into `.claude/specs/`, so a
bare `Refs: python.md` in any repo's CLAUDE.md reads the copy here. Edit specs here.

**The template ships from the same files.** Every shared skill or hook under
`template/.claude/` is a symlink into the root `.claude/` (copier follows symlinks, so a
rendered project gets real files). Edit the root copy; never replace a symlink with a
file. A `.jinja` hook exists only where the generated project needs a rendered path, and
it must stay line-for-line with its root twin apart from that path.

**Hooks only run when the session is rooted here.** `settings.json` registers them as
`$CLAUDE_PROJECT_DIR/.claude/hooks/<name>`. In this workspace `~/workspace/.claude` is a
symlink to `~/.claude`, so a session rooted at `~/workspace` resolves that path to
`~/.claude/hooks/`, which does not exist: none of these hooks fire there. Open the session
in `galactus/` when the guards matter.
