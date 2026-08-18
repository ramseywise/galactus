# Band Contract

Bands are a **view over `Status:`**, not a state. The hook is unchanged; a band is
derived by lookup from the current `Status:`. No new state, no vocabulary change,
no `LEGAL_EDGES` change.

`SUPERSEDED` belongs to no band — it is an escape from the sequence, reachable from
anywhere.

## Band → Status mapping

| Band | Name | Status values | Owner skill(s) | Budget | Evidence |
|---|---|---|---|---|---|
| 1 | triage | `RESEARCH`, `RESEARCHED`, `PLANNED` | `/proto-scope`, `/proto-design`, `/proto-research`, `/proto-plan` | 5–10 min | ~2 min conversational intake (`archived/design-prototype/SKILL.md:76`) |
| 2 | prototype | `REFINED`, `READY`, `IN_PROGRESS` | `/proto-refine`, `/proto-execute` | 20–30 min | conditional on fold/model cap as declared default (`runs/ml/lending/WALKTHROUGH.md:202-216`) |
| 3 | optimize | `EXECUTED` | `/proto-review` | unmeasured (target 10–15 min, no evidence) | — |
| 4 | harden | `COMPLETE` | `/proto-harden` | unmeasured (target 10–15 min, no evidence) | — |

**Band 3 resolution.** CLAUDE.md's pipeline table has no skill between `/proto-execute`
(writes `EXECUTED`) and `/proto-review` (Review). `/proto-review` owns band 3: it is the
skill that evaluates `EXECUTED` and gates `COMPLETE`. Band 4 is owned by `/proto-harden`,
which runs the hardening checklist before the final transition.

Every non-`SUPERSEDED` state maps to exactly one band. Every band names an owner skill
that exists. Verified against `STATE_COMPLETED_PHASE` in `review/models.py:157-167`.

## Timing

Every band's elapsed time is recorded by the dispatcher alongside
**stopped-vs-completed**. A band that stops on the Q1 carve-out (irreversible action
without approval) must never contribute its elapsed time to the budget figure.

Bands 3 and 4 emit elapsed time but carry no budget until #23's runs produce
measurements. The target can become an estimate with evidence behind it then.

## Band 2 constraints

- **Fold/model cap is a declared default**, not a flag. Recorded as a first-class field
  in the run artifact so the checklist that judges the comparison can see what was capped.
- **Non-blocking by design.** Band 2 runs while the operator is in notebooks. Irreversible
  decisions are hoisted into band 1 (see Q1 resolution in the plan doc).
- **If band 2 ever needs an irreversible action, it stops.** The band contract makes this
  a legible outcome rather than a crash. The checklist below gives it an item.

## Serial/parallel

Serial by default for bands 1 and 4 (watchable, narration-shaped). Band 2 may run
parallel — the 20–30 min budget depends on it.

## Release checklists

> **Audit, don't assert.** Every item is the result of looking at a real artifact this
> run. If an item cannot be verified, it stays `false` — never true on memory or intent.
> An unreadable or missing artifact is an **error, not a failed gate**; say which, because
> they route differently — an error stops for repair, a failed gate routes back a band.

Item shape: `id | expectation | verifier | value`, where value is `true | false | error`.

### Band 1 → Band 2 gate

| id | expectation | verifier | value |
|---|---|---|---|
| B1-01 | `DESIGN.md` or plan doc exists and `Status:` is `PLANNED` or later | `test -f <doc> && grep -q 'Status:.*PLANNED\|REFINED\|READY' <doc>` | |
| B1-02 | All Key Decisions are `Resolved` or `Deferred(<trigger>)` with a real trigger | `grep -c 'Open' <DESIGN.md key-decisions section>` → 0 | |
| B1-03 | No `Deferred()` without a trigger (counts as Open — a blocker) | `grep -cE 'Deferred\(\s*\)' <doc>` → 0 | |
| B1-04 | Track is declared (`ml` or `agent`) | `grep -q 'Track:' <plan-doc>` | |
| B1-05 | Decision records written for every triage decision (Step 4) | `ls .claude/docs/decisions/<run-slug>*.md` | |

### Band 2 → Band 3 gate

| id | expectation | verifier | value |
|---|---|---|---|
| B2-01 | `Status:` is `EXECUTED` | `grep -q 'Status:.*EXECUTED' <plan-doc>` | |
| B2-02 | No irreversible action taken without approval | operator attestation (the Q1 carve-out) | |
| B2-03 | Tests pass | `uv run pytest <test-dir> -q` exit 0 | |
| B2-04 | Lint clean | `uv run ruff check <src-dir>` exit 0 | |
| B2-05 | Fold/model cap recorded as a field in the run artifact (if `Track: ml`) | `grep -q 'model_cap\|fold_cap' <summary.json or DESIGN.md>` | |
| B2-06 | `skipped` is empty or capped candidates are recorded | `python3 -c "..."` against `summary.json` | |

### Band 3 → Band 4 gate

| id | expectation | verifier | value |
|---|---|---|---|
| B3-01 | `/proto-review` has run and emitted a verdict | `grep -q 'Review:' <plan-doc>` | |
| B3-02 | All `must-fix` findings are resolved | review findings count = 0 must-fix | |
| B3-03 | No regression in test count | test count ≥ pre-review count | |

### Band 4 exit

| id | expectation | verifier | value |
|---|---|---|---|
| B4-01 | `Status:` is `COMPLETE` | `grep -q 'Status:.*COMPLETE' <plan-doc>` | |
| B4-02 | `Review: passed` | `grep -q 'Review:.*passed' <plan-doc>` | |
| B4-03 | Branch is clean (`git status` shows only staged changes) | `git status --porcelain` | |

### Nested-field check (from fraud, seeded per Step 2)

Specific to `runs/ml/fraud/docs/summary.json`:

| id | expectation | verifier | value |
|---|---|---|---|
| NF-01 | `operating_point_reported` is read at its nested path `refusal.operating_point_reported`, not top-level | `python3 -c "import json; d=json.load(open('runs/ml/fraud/docs/summary.json')); print(d['refusal']['operating_point_reported'])"` | `false` (correct — no operating point was reported) |
| NF-02 | `skipped` is empty (no model silently absent from comparison) | `python3 -c "import json; d=json.load(open('runs/ml/fraud/docs/summary.json')); assert not d.get('skipped'), d['skipped']"` | `false` (catboost is skipped) |
