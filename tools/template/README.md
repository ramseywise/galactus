# scripts/ — template-maintainer utilities

Tools for working on the template itself. Nothing here ships into rendered
projects (only `template/` is rendered).

| Script | What it does |
|---|---|
| `preview_defaults.py` | Evaluates `copier.yaml`'s Jinja default expressions for a given set of answers without rendering — quick way to check what a config would derive (`scaffold_full_project`, `include_*` toggles, directory names) before running a real render. |
| `sync-global-skills.sh` | **RETIRED 2026-08-11 — refuses to run.** Global is no longer the skill reservoir; skills are owned by the repo that owns the stage (galactus = prototyping, guacamayo = production workflow, this template = scaffolding). The template payload and guacamayo have since diverged in *both* directions, so syncing either way would destroy real content. Re-source deliberately, per skill, by hand. Full rationale in the script's header. |
| `sync-agent-references.sh` | Copies agent framework references into `template/.agents/`. Source repointed 2026-08-11 to `guacamayo/.claude/skills/new-agent/references/` (was `~/.claude/`, which no longer holds `new-agent`). Still one-way, source→template. |
