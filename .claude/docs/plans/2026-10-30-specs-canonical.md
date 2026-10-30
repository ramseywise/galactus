# Specs — one canonical copy in galactus

Status: PLANNED
Date: 2026-10-30
Issue: — (none yet)

Decided 2026-10-30 (Ramsey): galactus `.claude/specs/` is canonical. Everything else
points at it.

## Research

Direct inspection, 2026-10-30.

### Four copies today

| Location | Role it claims | Contents |
|----------|----------------|----------|
| `galactus/.claude/specs/` | canonical (galactus CLAUDE.md "Canon lives here") | 16 specs |
| `~/.claude/refs/` | "the global reference layer" (its own README) | the same 13 shared specs + `logging.md`, `models.md`, `verification.md`, `README.md`, `agent-skills/` |
| `guacamayo/.claude/specs/` | vendored, header says "Galactus is canonical" | `agent-safety.md`, `agent-uncertainty.md` (+ 5 guacamayo-owned review specs) |
| `guacamayo/.sounding/refs/` | mobile mirror, tracked so a clone has it | `logging`, `models`, `python`, `typescript`, `README` |

### How far the copies have drifted

| Spec | refs vs galactus |
|------|------------------|
| 11 `agent-*`, `langgraph`, `google-adk` | 3–7 lines: a "Restored 2026-10-xx" note, plus one path in `agent-memory.md` |
| `python.md` | galactus has 3 extra Don'ts (swallowed exceptions, network timeouts, unclosed resources); refs links `logging.md` |
| `typescript.md` | refs is generic ("the database", "Next.js API routes", "see logging.md"); galactus is diskoe-specific ("Supabase", "Vercel Functions") |
| `logging`, `models`, `verification` | refs only |

### Who reads them

- `Refs: verification.md` in guacamayo, sisyphus, and `dssg/nonprofit-success-ai`
  CLAUDE.md files resolve a bare filename to `~/.claude/refs/`.
- About 15 skills across galactus and guacamayo cite `~/.claude/refs/<file>` by path.
- So `~/.claude/refs/<name>.md` must keep resolving. Symlinks satisfy that.
- `galactus/template/.claude/` ships no specs, so the template is unaffected.

## Plan

Based on: direct codebase inspection (Research above).

**S1. Reconcile content into galactus.** One commit per file class, staged only.
- `python.md`: keep galactus's Don'ts, add refs's `logging.md` link.
- `typescript.md`: take refs's generic wording. galactus's Supabase and Vercel lines are
  diskoe-specific and belong in that repo's CLAUDE.md.
- `agent-memory.md`: keep galactus's path (`.claude/skills/langgraph-persistence/SKILL.md`),
  which exists. Drop the "Restored" notes everywhere; git history records that.
- Move `logging.md`, `models.md`, `verification.md` into `galactus/.claude/specs/`.
- Move the refs `README.md` to `galactus/.claude/specs/README.md`, rewritten: galactus is
  canon, `~/.claude/refs/` is symlinks.
- `agent-skills/` (vendored cheatsheets): move to `galactus/.claude/specs/agent-skills/`.

**S2. Turn `~/.claude/refs/` into symlinks.** Back up first:
`cp -R ~/.claude/refs ~/.claude/backups/refs-2026-10-30`. Then one symlink per file into
`~/workspace/galactus/.claude/specs/`, same pattern as `~/.claude/skills/`.

**S3. guacamayo vendored specs.** Replace `guacamayo/.claude/specs/agent-safety.md` and
`agent-uncertainty.md` with relative symlinks to `../../../galactus/.claude/specs/`.
Check first that `/review-defense` and `/fog` read them by path, not by copying into a
prompt. If a guacamayo clone without galactus must still work, keep copies and add a drift
test instead. Decide in refine.

**S4. guacamayo mobile mirror.** Keep `.sounding/refs/` as a copy, since a phone clone has
no galactus. Its source changes to galactus. Add a tiny `make refs-mirror` target in
guacamayo that copies from `../galactus/.claude/specs/`, and have `/meta-dream`'s refresh
step call it.

**S5. Update the docs that state the canon.** galactus CLAUDE.md "Canon lives here"
paragraph: `~/.claude/refs/` is symlinks into galactus specs. guacamayo CLAUDE.md
`.sounding/refs/` row: source is galactus.

### Verification

- `for f in ~/.claude/refs/*.md; do [ -L "$f" ] || echo "not a link: $f"; done` → no output.
- `for f in ~/.claude/refs/*.md; do [ -e "$f" ] || echo "dangling: $f"; done` → no output.
- `diff -r ~/.claude/backups/refs-2026-10-30 ~/.claude/refs` shows only the reconciled
  lines from S1.
- `grep -rn "Restored 20" galactus/.claude/specs` → none.
- galactus `uv run pytest -q` still green (nothing imports specs, but check).

### Open Questions

- Q1 (S3): symlink or copy-plus-drift-test for guacamayo's two vendored specs?
  Recommendation: symlink, because guacamayo already depends on a sibling clone of
  librarian for its sessions store.
