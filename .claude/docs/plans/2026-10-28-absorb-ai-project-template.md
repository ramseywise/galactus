# Absorb ai-project-template into galactus
Date: 2026-10-28
Status: PLANNED
Issue: TBD (open as GAL-<n>; branch `GAL-<n>-absorb-template`)

## Goal

galactus becomes the single home for the AI-engineering kit:

```
galactus/
├── copier.yaml              # from ai-project-template; `_subdirectory: template`
├── template/                # copier payload (what a new project gets)
│   └── .claude/skills/<x>   # symlinks into ../../.claude/skills/<x> for the shipped subset
├── .claude/                 # ONE canonical copy of skills, specs, hooks, agents
├── runs/                    # vibecoding examples (marketing-comms, lending, fraud, …)
├── ml/  experiments/        # shared toolkit — canonical here, template links to it
├── tools/template/          # template maintainer scripts (was ai-project-template/scripts)
├── versions.toml            # dependency + model pins for everything above
└── Makefile                 # template targets (lint-render, test_render) + galactus targets
```

`ai-project-template` is archived on GitHub with a pointer to galactus. It is not deleted.

**Why:** `~/.claude/` stopped being the source of truth after the 2026-09 machine move
(it has no hooks, specs or skills now), so three copies of the tooling became two copies
that drift. The shared hooks already differ (`lib.sh` by 314 lines). `galactus/experiments/` is
a byte-identical copy of the template's, and `galactus/ml/` is a 1,571-line-stale one.
One repo means one copy of each.

## Verified facts this plan rests on

- Copier follows symlinks and copies the target content; non-`.jinja` files are not
  rendered (tested 2026-10-28 with copier 9.x). So skills can live once at `.claude/skills/`
  and the template ships them through symlinks.
- Template renders are green today: Python 124 passed, TypeScript 48 passed (from `HEAD`,
  staged work excluded).
- galactus today: 617 passed, 7 failed (`review/tests/test_validate.py`, line anchors stale
  vs `gateway.py`), 4 collection errors (`ml` dep group not installed by default).
- Only `atlas/` was generated from the template (`_src_path` = local ai-project-template path).
- Template's only Jinja-templated skill file is `skills/README.md.jinja`.

## Steps

### 0. Preserve in-flight work (both repos)
Both `main`s have staged, uncommitted work: galactus 45 files (plans/research), template
138 files (93 skill changes + `copier.yaml`), and 4 stashes between them.
- Commit each repo's staged set to `preserve/2026-10-28-staged-main`, then land it via
  PR (preferred, since the template's 93 skill edits are the newest skill text) or leave it parked.
- Stashes → `preserve/stash-*` tags, per the preserve-refs convention.
- Done when: `git status` is clean on both `main`s and nothing is only in a stash.

### 1. Reshape ai-project-template for transplant (in that repo, branch `prep-absorb`)
`git mv` into the target layout so history and blame follow the files:
- `scripts/` → `tools/template/`; `ruff.toml` settings → noted for merge into galactus `pyproject.toml`
- `README.md` → `template/MAINTAINING.md`
- `.claude/docs/plans/*` → `.claude/docs/plans/template/` (no filename clashes; keeps the
  `Status:` validator's reach)
- `.claude/skills/*` (maintainer skills) → kept at `.claude/skills/` (they get de-duplicated in step 3)
- `copier.yaml`, `template/`, `versions.toml`, `Makefile`, `.github/workflows/test-render.yml` stay put
- Done when: `make test && make lint-render` pass on `prep-absorb`.

### 2. Merge with history (in galactus, branch `GAL-<n>-absorb-template`)
```bash
git remote add ait ../ai-project-template && git fetch ait
git merge --allow-unrelated-histories ait/prep-absorb
```
Expected conflicts: `.gitignore`, `.pre-commit-config.yaml`, `.claude/skills/` name
collisions (`project-genesis` vs `archived/project-genesis`). Resolve by union and keep both
skill copies for now; step 3 removes the duplicates.
- Fix `copier.yaml` / `Makefile` / `tools/template/validate_paths.py` path assumptions.
- Done when: `make test`, `make lint-render`, `make test_render` pass **from galactus**, and
  `copier copy ~/workspace/galactus /tmp/x --defaults` renders.

### 3. One copy of everything
| Area | Keep | Remove / fold |
|---|---|---|
| Scoping interview | `proto-scope` (superset: has `discovery` mode) | `scope-poc` |
| Front door | one `/new` skill: AI vs ML routing (from `prototype-genesis`) + language pick + copier run (from `project-genesis`) | both old genesis skills |
| Review | `review-*` + `review-shared`; template `code-review` kept as the light single-pass review for the `/spike` lane (D2) | nothing |
| Hooks | `.claude/hooks/` canonical; `template/.claude/hooks/*.jinja` source `lib.sh` from it | reconcile the 4 drifted hooks; delete `hook_parity_check.sh` |
| Specs | both of each pair — not duplicates: `specs/langgraph.md` / `google-adk.md` are convention→surface binding tables, `new-agent/references/framework-{lg,adk}.md` are the codegen file templates `/new-agent` writes from | nothing (re-checked 2026-10-28) |
| `experiments/` | root `experiments/` | template copy → symlink (identical today) |
| `ml/` | template's (newer superset), moved to root `ml/` | galactus's stale copy; template keeps only its `.jinja` docs and links the code |

- Shipped skill set: choose which root skills a generated project gets, symlink only those
  into `template/.claude/skills/`. galactus-only skills (`skill-creator`, `proto-harden`, …) are not shipped.
- Rewrite CLAUDE.md's "Vendoring exception" section: canon is now this repo; `~/.claude/` is
  not involved.
- Add a CI check that every `template/.claude/skills/*` is a symlink (no silent re-forks).
- Done when: no skill/hook/spec name exists twice; renders still pass; galactus tests pass.

### 4. Examples green + CI
- `[tool.uv] default-groups = ["dev", "ml"]` → clears the 4 collection errors.
- Re-anchor the 7 `review/tests/test_validate.py` fixtures to current `gateway.py`.
- CI: render matrix (from `test-render.yml`) + `pytest` over `runs/` in one workflow.
- Done when: CI green on the branch.

### 5. Vibecoding improvements (separate PRs after the merge lands)
1. **Hook diet.** After each edit: ruff format/fix only. Move pyright, test-coverage and public-API
   checks to `Stop` or pre-commit. Today a generated project runs ~12 hooks per edit.
2. **`/spike` lane.** On `spike/*` branches: no plan doc required, `Status:` validation off,
   one light review at the end.
3. **Models in one place.** `[models]` in `versions.toml`, bump to the 5.5 family; replace ~12
   hardcoded IDs (`llm_kit.py`, `.env.example`, agent settings, Terraform, judge base) and
   the stale `llm_kit` pricing table.
4. **TypeScript-only renders.** No `pyproject.toml` / `core/` / `evals/` / `llm_kit/` when
   `primary_backend_language=typescript`.
5. **Context diet.** Fold the 13 `review-*` into one skill with per-dimension refs; cap
   skill descriptions (several are 400–600 chars); slim `new-agent` (11k lines).
6. **Dangling refs.** `/grow-companion`, `/review-sweep` are referenced but don't exist.
7. **Start from anywhere.** Symlink `/new` into `~/.claude/skills/` so a session at `~/workspace` can scaffold.

### 6. Cutover
- `atlas/.copier-answers.yml`: `_src_path` → galactus; run `copier update` on a branch there.
- Archive `ramseywise/ai-project-template` on GitHub; README points to galactus. Keep the
  local clone until atlas updates cleanly.
- Open AIT issues: move the live ones to galactus, close the rest with a link.

## Progress (branch `GAL-43-absorb-template`, nothing pushed)

- Steps 0–4: done.
- 5.1 hook diet: done (d813531). Per edit: ruff format/fix, docs hygiene, memory guard.
  Checks run once at Stop via `stop_checks.sh`. Inline guards read stdin; they were dead
  (`$CLAUDE_TOOL_INPUT` is never set). The friction-log hook still reads env vars.
- 5.2 `/spike`: done (a3737fa).
- 5.3 models: done (13df64e). `[models]` in `versions.toml`; stale-ID scan in CI.
- 5.4 TS-only renders: done (cf9dddc). New derived `has_python`; TS render has its own CI job.
- 5.5 context diet: done (101e73a). 11 dimensions moved to `review-shared/dimensions/`;
  `proto-scope` description capped. `new-agent` left: 114-line SKILL.md, refs load on demand.
- 5.6 dangling refs: done (47e1949).
- 5.7 `/new` from anywhere: done. `~/.claude/skills/new` → this repo (local machine only).
- 6 cutover (2026-10-28): galactus made public so public consumers can call its reusable
  workflows. Rendered `ci.yml` now calls `ramseywise/galactus/.github/workflows/python-ci.yml@main`.
  librarian, listen-wiseer, guacamayo and atlas repointed on their own branches; atlas's
  `_src_path` → galactus. ai-project-template is deliberately **not archived** yet (owner's
  call, later); its issues have not been moved.

## Open decisions
- D1: Land the staged work via PR before merging (recommended) or park it on `preserve/`?
- D2: ~~Ship `code-review` as the `/spike` light review, or drop it?~~ Ship it (2026-10-28).
- D3: guacamayo's `.claude/skills/new-agent/` is a stale fork of galactus's (galactus adds the
  voice/duplex rows; nothing flows the other way). Delete it there, or symlink it to galactus?
