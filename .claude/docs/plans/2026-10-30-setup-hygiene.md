# Setup hygiene — CI repoint, global settings, stale cruft

Status: PLANNED
Date: 2026-10-30
Issue: — (none yet)

Sibling plans from the same audit: `2026-10-30-specs-canonical.md`,
`2026-10-30-global-guard-hooks.md`, `2026-10-30-review-engine-consolidation.md`.

## Research

Direct inspection of galactus, guacamayo, the product repos and `~/.claude/`, 2026-10-30.
Each item is small, reversible, and independent of the others.

| # | Finding | Evidence |
|---|---------|----------|
| R1 | Four repos' CI still calls the retiring template's reusable workflow | `uses: ramseywise/ai-project-template/.github/workflows/python-ci.yml@main` in `ci.yml` (and `dependabot-auto-merge.yml`) of atlas, librarian, listen-wiseer, guacamayo |
| R2 | The repoint is already written, never landed | `preserve/repoint-ci-to-galactus` exists in all four: atlas `d4a6101`, librarian `106831a`, listen-wiseer `310e49c`, guacamayo `e1b6176`. 1–3 one-line changes each. `galactus/.github/workflows/python-ci.yml` exists |
| R3 | Global default model is a stale pin | `~/.claude/settings.json` `"model": "claude-haiku-4-5-20251001"` |
| R4 | Global auto-mode context describes a parked project | `autoMode.environment` and two `soft_deny` rules describe DISKOE (`~/workspace/diskoe`), which now lives in `old/` |
| R5 | 17 unused third-party commands load into every session | `~/.claude/commands/*.agent.md` + `README.md`, all dated 2026-07-25, "AgenticOS (Under Construction)" |
| R6 | guacamayo's venv predates the machine move | test traceback paths read `/Users/wiseer/workspace/guacamayo/...` |
| R7 | One guacamayo test is not hermetic | `tests/telemetry/test_recurrence.py::test_live_corpus_directions_discriminate` reads the live findings corpus; fails on today's data (1 failed, 1158 passed) |
| R8 | guacamayo `AGENTS.md` is stale and duplicates CLAUDE.md | describes `review/` and `telemetry/` at the root (now `src/`) and per-dimension agent files (collapsed in GUA-158) |

Out of scope by decision (2026-10-30): guacamayo's plan docs stay untracked.

## Plan

Based on: direct codebase inspection (Research above).

Every step is staged only. Pushing branches and opening PRs is Ramsey's.

**S1. Land the CI repoint (R1, R2).** In each of atlas, librarian, listen-wiseer,
guacamayo: rebase `preserve/repoint-ci-to-galactus` onto current `main` and rename it to a
proper work branch. guacamayo is on `feat/portfolio-sweep-skill-ownership` with staged
work — do not switch its checkout; use a worktree. Ramsey pushes and opens the four PRs.
Order: galactus `python-ci.yml` must be on `origin/main` first (check with
`gh api repos/ramseywise/galactus/contents/.github/workflows/python-ci.yml`).
Verify: each PR's CI run goes green and its log shows the galactus workflow ref.
Then, and only then, ai-project-template can be archived.

**S2. Global settings (R3, R4).** In `~/.claude/settings.json`:
- `model` → the alias `"opus"` (an alias does not go stale the way a dated ID does).
- Drop the DISKOE `soft_deny` rules and the DISKOE-specific `environment` lines. Keep
  `$defaults`. Rewrite the environment block for this workspace: org `ramseywise`,
  galactus/guacamayo public, `.sounding/` and `.env*` sensitive, never commit or push.
- Back up first: `cp ~/.claude/settings.json ~/.claude/backups/settings.json.2026-10-30`.
Verify: `jq . ~/.claude/settings.json` parses; a fresh session reports the new model.

**S3. Archive the AgenticOS commands (R5).** `mv ~/.claude/commands ~/.claude/backups/commands-agenticos-2026-07`.
Reversible by moving back. Verify: a fresh session's skill list has no `*.agent` entries.

**S4. guacamayo venv + hermetic tests (R6, R7).** `rm -rf .venv && uv sync` in guacamayo.
Mark the live-corpus test with a `live` marker, register it in `pyproject.toml`, and
exclude it by default (`addopts = "-m 'not live'"`). Verify: `uv run pytest -q` → 0
failed; `uv run pytest -m live` still runs it on demand.

**S5. guacamayo AGENTS.md (R8).** Replace with a short pointer: what the repo is, then
"conventions live in CLAUDE.md". Keeps the file for non-Claude tools without a second
description to drift. Verify: `grep -c "review/driver.py" AGENTS.md` → 0.

### Verification

- S1: four green PR runs on the galactus workflow.
- S2: `jq -r .model ~/.claude/settings.json` → `opus`; `grep -c diskoe ~/.claude/settings.json` → 0.
- S3: `ls ~/.claude/commands` → no such directory.
- S4: guacamayo `uv run pytest -q` → `0 failed`.
- S5: AGENTS.md under 20 lines.

### Open Questions

- Q1: Default model. Plan says `opus`. Say if you want something else.
- Q2: Branch names for S1. No issues exist yet. Plan uses `bug/repoint-ci-to-galactus`
  unless you file issues first.
