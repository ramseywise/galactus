# Model Pairing — skills, agents, sessions

*The skill tables below predate the 2026-09 machine move and name skills that no longer
exist. Treat the principle as current and the tables as needing a pass.*

*Principle: pay for judgment, not for reading. Fan-out and extraction → haiku;
workhorse execution → sonnet; judgment-dense / error-expensive / irreversible →
opus-class. /fast = same Opus, faster output — a latency lever, not a cost lever.*

Skills run in the invoking session's model — the tables say **which session tier to invoke
them in** (and which model their sub-agents pin). Enforcement strength: agent-def
frontmatter > skill-text spawn instructions > this ref (session choice is Ramsey's).

## Current default

`~/.claude/settings.json` → `"model": "opus[1m]"`. There is no `~/.claude/CLAUDE.md` on this
machine, so nothing states this default in prose — the doc↔config check that `/meta-retro`
Check B runs has no doc side to compare against. That is a gap, not a pass.

## Live skills (2026-09-03)

| Tier | Skills | Why |
|------|--------|-----|
| **Opus-class** | `/workflow-triage`, `/workflow-review`, `/contract`, `/retro`, `/design-*`, `/create-skill` | Verdicts, architecture, contract judgment, changes to the tooling itself — errors compound |
| **Sonnet** | `/workflow-build` (execute stage), `/workflow-research`, `/git-pr`, `/git-issue`, `/git-board` | Plan is already made or the task is bounded; needs competence, not maximal judgment |

## Sub-agent spawns (pinned, not session-dependent)

| Agent / spawn | Model | Set where |
|---------------|-------|-----------|
| `research-scout` fan-out | haiku | Agent tool `model` param |
| `Explore` lookups | haiku | Agent tool `model` param |
| `review` dimension reporters | session model or fable | one per dimension, dispatched in parallel |
| `build-scout`, `plan-refine-scout` | fable or sonnet | reasoning depth without full opus judgment |
| Finding verification + report merge | session model | deliberate — cheap generate, narrow expensive verify |

**Corrected 2026-09-03:** the 2026-08-20 copy said fable "is not yet available as an Agent
enum value in Claude Code; use sonnet until `claude-sonnet-4-5-v2` appears". Both halves are
now false — `fable` is a selectable value in the Agent tool's `model` enum, and the id is
`claude-fable-5`. A workaround kept past its expiry costs more than the problem did.

## Rules of thumb

- Session about to run a plan, a retro, or a contract pass → start it opus.
- Routine build/execute day → a sonnet session is fine; the pinned haiku fan-outs don't care.
- Execution runs in a **fresh** session per item, with the plan doc as input — never as a
  continuation of the opus planning session. ~5k fresh context beats a compacted 150k.
- Never let a sub-agent's confident output skip main-model verification — model choice
  changes cost, not the verification duty (`verification.md` §1).
