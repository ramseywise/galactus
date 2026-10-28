#!/usr/bin/env bash
# Renders the agent-framework reference library from the global reservoir
# (~/.claude/skills/new-agent/references/) into this template's .agents/ tree.
#
# One-way: reservoir -> template, never the reverse. ~/.claude/skills/new-agent/
# references/ is canon (edit it there); run this script, then commit the result
# here, whenever the reservoir changes and the template should pick it up.
#
# Companion to sync-global-skills.sh, which syncs .claude/skills/ (Claude Code
# workflow commands). This one syncs .agents/ (tool-agnostic agent knowledge,
# readable by ADK tooling or any other harness). Two scripts because the two
# trees have different shapes and different render rules.
#
# WHY A RENDERER AND NOT `cp` (2026-07-19): template/.agents/skills/ was
# hand-copied once and covered by no script. The drift ran BACKWARDS — the
# template's framework-selection carried an entire third framework (Vercel AI
# SDK) that the reservoir lacked, and nobody noticed. It has since been promoted
# to canon. Two files still need a real transform (see RENDER RULES).
#
# --dry-run: print what would change (with per-file detail) without writing.
set -euo pipefail

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

# Source moved 2026-08-11: global is no longer the skill reservoir. `new-agent`
# is now owned by guacamayo (production workflow repo); its references/ tree is
# the canonical source for this template's .agents/ library. See the retired
# scripts/sync-global-skills.sh for the full ownership-model rationale.
RESERVOIR="$HOME/workspace/guacamayo/.claude/skills/new-agent/references"
TEMPLATE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/template/.agents"

# ---------------------------------------------------------------------------
# What goes where
# ---------------------------------------------------------------------------
#
# TWO DESTINATIONS, because these are two different kinds of document:
#
#   SKILLS[]     -> .agents/skills/<name>/SKILL.md
#     Framework and scaffold guides. Genuine skills: each already carries
#     authored frontmatter in the reservoir (name + description, plus Apache-2.0
#     attribution on the Google-derived ADK pair). An agent harness discovers
#     and loads these by description.
#
#   REFERENCES[] -> .agents/references/<name>.md
#     Code-generation payload — the cap-* capability specs plus core/eval/test/
#     infra/docs. These are emitted-code templates, not skills: they have no
#     frontmatter in the reservoir and no meaningful "use this when" trigger.
#     Rendering them as skills would mean inventing 23 descriptions and diluting
#     a directory whose README promises a curated framework reference library.
#     They ship so a scaffolded project can generate capability code offline,
#     with no access to ~/.claude.
#
# Deliberately NOT synced: nothing. This is a full mirror of the reservoir's
# references/ directory — 30 files, ~11k lines, shipped into every scaffolded
# project regardless of which capabilities it enables. Chosen (2026-07-19) for a
# simple script with no copier-answer coupling; the cost is dead weight in
# projects that use one capability. Revisit if template size becomes a problem.

SKILLS=(
  framework-selection
  adk-scaffold
  adk-dev-guide
  langgraph-scaffold
  langgraph-fundamentals
  langgraph-persistence
  langgraph-human-in-the-loop
)

REFERENCES=(
  core
  infra
  eval
  test
  docs
  framework-adk
  framework-lg
  cap-a2a
  cap-batch
  cap-cluster
  cap-finetune
  cap-forecast
  cap-genai
  cap-hitl
  cap-kg
  cap-langchain
  cap-rag
  cap-rlhf
  cap-search
  cap-streaming
  cap-vision
)

# ---------------------------------------------------------------------------
# Fail fast on drift in either direction
# ---------------------------------------------------------------------------
#
# Skipping with a warning lets a renamed file rot in the template indefinitely —
# the warning scrolls past, the exit code stays 0, and stale copies keep
# shipping. That is exactly how 13 pre-rename names sat unnoticed in
# sync-global-skills.sh; same hard-fail here.

missing=()
for name in "${SKILLS[@]}" "${REFERENCES[@]}"; do
  [ -f "$RESERVOIR/$name.md" ] || missing+=("$name")
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "error: ${#missing[@]} name(s) in SKILLS[]/REFERENCES[] are not in the reservoir ($RESERVOIR):" >&2
  printf '  %s\n' "${missing[@]}" >&2
  echo "Renamed? Update the array in this script. Retired? Remove it there and" >&2
  echo "git rm the stale template/.agents/ copy." >&2
  exit 1
fi

# The reverse check: a NEW reservoir file that no array mentions would silently
# never ship. Warn rather than fail — adding a reference upstream shouldn't break
# an unrelated sync — but make it loud enough to act on.
unlisted=()
while IFS= read -r path; do
  base="$(basename "$path" .md)"
  listed=0
  for name in "${SKILLS[@]}" "${REFERENCES[@]}"; do
    [ "$name" = "$base" ] && listed=1 && break
  done
  [ "$listed" -eq 0 ] && unlisted+=("$base")
done < <(find "$RESERVOIR" -maxdepth 1 -name '*.md' | sort)

if [ ${#unlisted[@]} -gt 0 ]; then
  echo "warning: ${#unlisted[@]} reservoir file(s) are in neither array and will NOT ship:" >&2
  printf '  %s\n' "${unlisted[@]}" >&2
  echo "Add each to SKILLS[] (has frontmatter, is a skill) or REFERENCES[] (code-gen payload)." >&2
fi

# ---------------------------------------------------------------------------
# RENDER RULES — why this is not `cp`
# ---------------------------------------------------------------------------
#
# 1. Link rewriting. The reservoir is a flat directory, so canon says
#    "read `adk-scaffold.md`". In the template those same docs are skill
#    directories, so the rendered copy must say
#    "`.agents/skills/adk-scaffold/SKILL.md`". Applies to SKILLS[] only —
#    REFERENCES[] stay flat in both trees, so their relative links already work.
#
# 2. Copier variables. langgraph-scaffold.md uses `source_root` as a generic
#    placeholder; a scaffolded project has the real copier variables
#    `py_project_root` and `ai_source_root` (copier.yaml:323,328). Verified as a
#    genuine substitution, not drift.
#
#    Canon writes it BOTH ways in adjacent lines — braced inside the example
#    path (`{source_root}/agents/...`) and bare in the prose that follows
#    ("if `source_root` isn't obvious"). Substituting only the braced form
#    leaves the sentence naming a variable its own example no longer uses, so
#    both forms are rewritten. Order matters: braced first, or the bare rule
#    corrupts the braced occurrence into `{py_project_root}/{ai_source_root}`
#    nested inside the outer braces.
#
# Frontmatter needs NO synthesis: all 7 SKILLS[] files already carry authored
# frontmatter in the reservoir, including the Apache-2.0 attribution block on
# the two Google-derived ADK skills. Do not generate it here — a hand-written
# description outperforms a guessed one, and the license block must survive
# verbatim.

render() {
  # $1 = source path, $2 = "skill" | "reference"
  if [ "$2" = "skill" ]; then
    sed -E \
      -e 's/`(framework-selection|adk-scaffold|adk-dev-guide|langgraph-scaffold|langgraph-fundamentals|langgraph-persistence|langgraph-human-in-the-loop)\.md`/`.agents\/skills\/\1\/SKILL.md`/g' \
      -e 's/\{source_root\}/{py_project_root}\/{ai_source_root}/g' \
      -e 's/`source_root`/`py_project_root\/ai_source_root`/g' \
      "$1"
  else
    cat "$1"
  fi
}

# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

changed=()
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

sync_one() {
  # $1 = name, $2 = "skill" | "reference"
  local name="$1" kind="$2" src dst label
  src="$RESERVOIR/$name.md"

  if [ "$kind" = "skill" ]; then
    dst="$TEMPLATE_ROOT/skills/$name/SKILL.md"
    label="skills/$name/SKILL.md"
  else
    dst="$TEMPLATE_ROOT/references/$name.md"
    label="references/$name.md"
  fi

  render "$src" "$kind" > "$tmp"

  if ! diff -q "$tmp" "$dst" >/dev/null 2>&1; then
    changed+=("$label")
    if [ ! -f "$dst" ]; then
      echo "$label: new ($(wc -l < "$tmp" | tr -d ' ') lines)"
    else
      echo "$label:"
      # what moves, before overwriting — direction is always reservoir -> template
      # (diff exits 1 on difference; don't let pipefail kill the run)
      { diff "$dst" "$tmp" 2>&1 || true; } | head -8 | sed 's/^/    /'
    fi
    if [ "$DRY_RUN" -eq 0 ]; then
      mkdir -p "$(dirname "$dst")"
      cp "$tmp" "$dst"
    fi
  fi
}

for name in "${SKILLS[@]}";     do sync_one "$name" skill;     done
for name in "${REFERENCES[@]}"; do sync_one "$name" reference; done

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

if [ ${#changed[@]} -eq 0 ]; then
  echo "No changes — .agents/ already matches the reservoir."
elif [ "$DRY_RUN" -eq 1 ]; then
  echo "[dry-run] ${#changed[@]} file(s) would sync:"
  printf '  %s\n' "${changed[@]}"
else
  echo "Synced ${#changed[@]} changed file(s):"
  printf '  %s\n' "${changed[@]}"
  template_repo="$(cd "$TEMPLATE_ROOT/../.." && pwd)"
  echo "Review with: git -C $template_repo diff"
fi
