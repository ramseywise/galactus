# .claude/specs — the canonical convention refs

**The point.** Conventions that are true across repos, loaded *on demand* rather than
always. A repo `CLAUDE.md` cites one by bare filename (`Refs: typescript.md, logging.md,
verification.md`) and the session reads it when the work touches that ground. One copy is
what stops five copies of the same rule drifting apart.

**This directory is that copy.** `~/.claude/refs/` is a directory of symlinks into it, so
a bare filename in any repo's `CLAUDE.md` still resolves through `~/.claude/refs/`. Edit
here, never through the symlink's target elsewhere.

**A pointer that resolves to nothing says nothing.** It does not error. A ref cited from a
`CLAUDE.md` or a skill must exist here, or under its owning repo and be linked into
`~/.claude/refs/`. guacamayo owns the review specs (`finding-schema.md`,
`review-dimensions.md`, `review-dod.md`, `evidence-model.md`, `insights-analysis.md`);
they are linked in the same way.

## Contents

| Ref | Scope |
|---|---|
| `typescript.md` | TS/Next.js conventions — strict mode, ESM, no secrets client-side |
| `python.md` | Python conventions — uv, pydantic v2, polars, ruff |
| `logging.md` | Structured logging — **two sections, one per language**. Read the one for the repo you are in |
| `verification.md` | What counts as evidence that a change landed. Language-agnostic |
| `models.md` | Model pairing — which tier for which kind of work |
| `agent-architecture.md` | Agent conventions: the five-layer stack; indexes the other `agent-*` refs |
| `agent-context.md` | Agent conventions: what enters the context window, ordering, eviction |
| `agent-memory.md` | Agent conventions: what survives a turn, a session, a restart |
| `agent-tools.md` | Agent conventions: gateable, auditable, parallel-safe tools |
| `agent-runtime.md` | Agent conventions: stateless function vs long-lived process vs managed runtime |
| `agent-reliability.md` | Agent conventions: tool errors, rate limits, refusals, timeouts |
| `agent-safety.md` | Agent conventions: what the agent can't do and where that's enforced |
| `agent-eval.md` | Agent conventions: proving a change made it better |
| `agent-observability.md` | Agent conventions: what a trace must contain |
| `agent-uncertainty.md` | Agent conventions: behavior when the system doesn't know |
| `agent-voice.md` | Agent conventions: full-duplex audio |
| `langgraph.md`, `google-adk.md`, `adk-vercel.md` | Framework bindings for the agent conventions |

`~/.claude/refs/agent-skills/` (vendored LangChain/ADK cheatsheets) stays a local
directory, not a link here: it is third-party text with no license file, and this repo is
public.

## Rules

- **Never language-split a filename.** `logging.md` carries a Python section and a
  TypeScript section rather than becoming `logging-py.md` + `logging-ts.md`, because the
  repos citing it cite the bare name. Splitting the file silently breaks both pointers.
- **A ref is a convention, not a decision record.** If a rule is only true of one repo, it
  belongs in that repo's `CLAUDE.md`. A ref that is right for one repo and wrong for the
  next is worse than no ref, because it is read with the same authority in both.
- **Provenance lives in git history, not in the file.** No "Restored from" lines.
- **The mobile mirror is downstream.** `guacamayo/.sounding/refs/` copies from here (for
  sandboxes that clone guacamayo but not galactus). It is a shadow; this is the original.
