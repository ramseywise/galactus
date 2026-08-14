# Archived skills

Skills that are no longer part of a band in `CLAUDE.md`'s routing table. They are kept
because their prose is worth reading before anyone writes a replacement, not because they
are expected to come back.

**Nothing here is invocable.** `.claude/skills/archived/**` is one level below where the
skill loader looks, so these do not appear in the skill list and cannot be reached by
`/name` or by model invocation.

Each directory carries an `ARCHIVED.md` naming the date, the reason, and where its live
substance went. Read that before reviving anything: in every case here the content either
moved into a live skill or targeted a tool this repo does not use.

| Skill | Archived | Reason | Substance now lives in |
|---|---|---|---|
| `design-prototype` | 2026-08-14 | Default mode duplicated `/proto-research` → `/proto-plan` | `proto-research` (track routing + ML contract) |
| `design-sprint` | 2026-08-14 | Thinner overlap of `proto-scope`'s problem framing; PM lens galactus has no role for | — |
| `design-initiative` | 2026-08-14 | Terminates in `/doc-to-linear-tickets`, which does not exist here; galactus tracks work in GitHub Issues | — |
| `project-discovery` | 2026-08-14 | Same intake conversation as `proto-scope`, one vocabulary level down | `proto-scope discovery` mode + its `reference/` |
| `project-genesis` | 2026-08-14 | Orchestrates "this repo's own `copier.yaml`" — galactus has none | `ai-project-template` owns the scaffolding stage |
| `docs-check` | 2026-08-14 | `review-architecture` already covers docs-vs-code drift, and reports it on every review | `review-architecture` |
