# Ledger flags — for `/workflow-retro`

Rows in `guacamayo/.sounding/tooling-ledger.md` that galactus work has invalidated or
resolved. **This file only flags; it never edits the ledger.** `/workflow-retro` is the
writer — it reads these and decides what lands.

---

## FLAG 2026-08-14 — void row: "R6 F6 design-* skills"

**Target row**: `guacamayo/.sounding/tooling-ledger.md` line 37, dated 2026-07-30, due
2026-08-17.

> R6 F6: design-* skills (sprint/initiative/milestones/prototype) — 0 invocations across
> 261 sessions / 3 retro windows; decision: retire (a), consolidate (b), or document (c)
> | workflow | `presence:design-skill-invoked within 3 design-heavy sessions OR
> documented-retirement in log` | hypothesis — pending Ramsey decision; due 2026-08-17

**Requested action: void the row.** Do not action (a)/(b)/(c) on its due date. The
decision it asks for has since been made on better evidence (below), but the row's own
evidence supports none of the three options, and a row whose measurement is invalid
should not be closed as though it measured something.

### Why the evidence is void

1. **Wrong population.** The 261 sessions were guacamayo and workspace sessions. `design-*`
   is not installed there; `workflow-*` is the correct pipeline in those repos. The count
   measures galactus skills against sessions that could not invoke them.

2. **Predates the repo by 10 days.** The row was written 2026-07-30. Galactus's first
   commit is 2026-08-09. All three retro windows closed before the skills had a home, and
   `~/.claude/projects/` had no galactus session directory at all — so the lifetime
   invocation count for *every* galactus skill was zero for reasons that have nothing to
   do with the skills.

3. **Unsatisfiable metric.** Every skill named carries `disable-model-invocation: true`.
   They cannot self-trigger; they run only when typed. `presence:design-skill-invoked`
   counts model invocation, which was structurally impossible for the whole window.

The three defects are independent — fixing any one still leaves the row unmeasurable.

### What was decided instead, and on what evidence

Resolved 2026-08-14 by reading the skills rather than counting them (issue #4, phase 3):

| Skill | Decision | Reason |
|---|---|---|
| `design-prototype` | **folded** into `proto-research`, rest archived | Default mode duplicated `/proto-research` → `/proto-plan`; the ML-vs-agentic routing rule and ML contract were unique and are now live |
| `design-sprint` | **archived** | Phases 1–5 are a thinner `scope-poc`; phase 6 emits an HTML artifact nothing consumes |
| `design-initiative` | **archived** | Terminates in `/doc-to-linear-tickets`, which does not exist here; galactus tracks work in GitHub Issues |
| `design-system` | **kept, wired** | The only requirement → five-layer agent spec path; feeds `/proto-research` |
| `design-milestones` | n/a | Not present in galactus; retired from global 2026-08-11 |

The row's real finding was not "these skills are unused" but "these skills have no entry
point." That is now fixed: `CLAUDE.md` carries a four-band routing table naming every live
skill and the condition that enters it.

### Replacement row

Measured in galactus sessions only, against skills that can actually be reached
(`disable-model-invocation` dropped from all three CROSS skills on the same date):

```
| 2026-08-14 | Galactus FRAME+CROSS bands wired into CLAUDE.md routing table;
design-prototype folded into proto-research; design-sprint + design-initiative archived |
workflow | `presence:frame-or-cross-skill-invoked within 3 galactus sessions` |
hypothesis — due 2026-09-14 |
```
