# akira — the mode family

akira is not one subagent; it is a family with two temperaments and a path that walks
between them. The name is a family label, not a single scanner.

## The two temperaments

| | **Kaneda (yang)** | **Kiyoko (yin)** |
|--|--|--|
| Mode | `scan` | `wander` |
| Agent | `akira-scan` | `akira-wander` |
| Asks | "What is broken here?" | "What did this change leave unanswered?" |
| Returns | ranked findings (`file:line — issue — severity`) | 3–5 pointed questions |
| Mutates | no | no |
| Shape | parallel fan-out over file batches | one pass over the diff |

They are complements. scan finds the defect; wander finds the *decision the author walked
past*. Run wander before scan when you want to interrogate intent before hunting bugs;
run scan alone when you just want a defect list.

## The path

`dao` (道) is the path from findings to a fixed, tested working tree. It is **not** a
subagent — it runs inline in the session because it mutates the tree and drives an
apply→test→revert loop that a subagent can't safely hand back clean. dao consumes scan's
findings, triages them by blast radius, applies only the safe ones behind a test gate,
and syncs docs. See `dao.md` for the full contract.

## Full flow

**Bare `/akira`** = full flow: wander → scan → sanyi → dao. Scope is automatic: if a diff
exists (uncommitted + branch changes), scope = diff. If clean, scope = whole repo (scan
fans out over all tracked files, wander skips, sanyi runs audit).

## Why one skill, not three

The primitives share scope detection, repo resolution, and the report format. Splitting
them into three skills would duplicate that shared setup and hide the family relationship.
One `/akira` skill, 3 primitive tokens + full flow.

## Relationship to the other review tools

- **`/workflow-review`** — the pre-commit orchestrator. It dispatches akira-scan,
  akira-wander, and sanyi-review as concurrent subagent reporters, then adds plan
  fidelity, DoD, and a merge verdict. akira is its *interactive, actuating sibling*:
  the same findings, but standalone `/akira` also has `wander` and `dao` — question and
  fix modes workflow-review's reporters don't run on their own.
- **`/sanyi`** — contract enforcement: did this change move a boundary? akira asks a
  broader "is this any good?" (structure, patterns, decisions, quality); sanyi is one of
  akira's own reporters in the full flow.
