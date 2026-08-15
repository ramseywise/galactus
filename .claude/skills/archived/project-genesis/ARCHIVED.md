# project-genesis — archived 2026-08-14

Nothing moved. No live skill inherits this content.

## Why

The skill describes itself as a *"thin orchestrator around this repo's own
`copier.yaml`"* (SKILL.md line 12). **Galactus has no `copier.yaml`.** It was written for
`ai-project-template`, where that file lives, and vendored here without its central
dependency.

The mismatch is structural, not a broken path. Galactus's POCs are subdirectories under
`pocs/ai/` and `pocs/ml/` — they are not copier-scaffolded repos, and scaffolding a new
repo is not something this repo does. The skill's whole job (translate a scoping
conversation into ~20 copier answers, run it non-interactively, handle the
`.copier-answers.yml` re-entry case) has no target here.

## Where it still belongs

`~/workspace/ai-project-template/`, which owns `copier.yaml` and the scaffolding stage.
Per the config-layering rule, the repo that owns the stage is canonical — so if this skill
should exist anywhere, it is there, not vendored into a prototyping showcase.

## Consequence for the FRAME band

The old chain was `/project-discovery` → `/scope-poc` → `/project-genesis` → copier. With
genesis archived and discovery folded, FRAME is now:

`/proto-scope discovery` → `/proto-scope` → `/proto-design` → `/proto-research`

Scaffolding, where it is needed, is a manual step or a call into the template repo — not a
band in this pipeline.
