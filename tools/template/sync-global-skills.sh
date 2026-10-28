#!/usr/bin/env bash
# =============================================================================
# RETIRED 2026-08-11 — this script no longer reflects how skills are owned.
# =============================================================================
#
# What it used to do
# ------------------
# Mechanism A: `~/.claude/skills/` was the single canonical reservoir for every
# generic workflow skill. This script mirrored a pinned subset of that reservoir
# into `template/.claude/skills/` (destructively — `rm -rf` on each destination),
# so scaffolded projects, which cannot see `~/.claude/`, shipped with them.
#
# Why it is retired
# -----------------
# The ownership model inverted. Global is no longer the reservoir; it now holds
# only `code-*` + `inbox-clean`. Skills live in the repo that owns the stage of
# work they belong to:
#
#   galactus/.claude/skills/     prototyping: design, proto-* pipeline, review-*
#   guacamayo/.claude/skills/    production workflow, cross-repo persistence,
#                                contract review
#   ai-project-template/         copier scaffolding + framework library
#
# Running this script today would:
#   1. hard-fail — 20 of the 24 names in its old SKILLS[] array no longer exist
#      in the reservoir, and the missing-name check is a deliberate hard error;
#   2. if forced past that, destroy real content — the template's payload copies
#      and guacamayo's copies have BOTH diverged, in both directions. Neither is
#      a stale mirror of the other. `workflow-insights` alone has 86 lines the
#      other side lacks, and `workflow-research` has 31 going the other way.
#
# `akira` and `sanyi` were retired outright on 2026-08-11 and are no longer
# scaffolded; their replacement is galactus's `review-*` dimension family, which
# is still stabilising. Review capability will be re-added to the template once
# that family settles — see the galactus plan rather than reviving this script.
#
# What to do instead
# ------------------
# Nothing automatic, for now. The template's payload is a fork with independent
# value, not a mirror to be refreshed. When the template should pull a skill from
# a repo, do it deliberately and re-diff by hand: the source of truth is the repo
# that owns that stage, and a copy into the template is a product decision about
# what scaffolded projects receive — not a sync.
#
# If a replacement is written, it must:
#   - take its source per-skill (galactus OR guacamayo), not from one reservoir;
#   - merge rather than `rm -rf` + `cp`, or at minimum diff and prompt;
#   - never assume template == downstream copy.
# =============================================================================
set -euo pipefail

cat >&2 <<'EOF'
sync-global-skills.sh is RETIRED (2026-08-11) and will not run.

Global is no longer the skill reservoir. Skills are owned by the repo that owns
the stage of work: galactus (prototyping), guacamayo (production workflow),
ai-project-template (scaffolding + framework library).

The template payload and guacamayo have diverged in BOTH directions — syncing
either way destroys real content. Re-source deliberately, per skill, by hand.

See the comment block at the top of this file for the full rationale.
EOF
exit 1
