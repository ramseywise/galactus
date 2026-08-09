---
name: review-contracts
description: >
  Review dimension: change-contract enforcement (SANYI). Checks the diff against
  the repo's SANYI.md — invariants modified or made bypassable, complexity budgets
  exceeded, tunables hardcoded, unrecorded layer migrations, unassigned files.
  Conditional on the repo having a SANYI.md.
prefix: CT
allowed-tools: Read, Grep, Glob, Bash
---

# Change Contracts

Vendored from Parallax `.claude/skills/sanyi/`. Parallax is read-only: fix upstream
and re-vendor, never edit that copy from here.

You are dispatched with exactly this one dimension loaded, and only when
`review/signals.py` found a `SANYI.md` in the repo. Without a contract there is
nothing to enforce and this dimension is skipped with a reason — do not
reconstruct a contract from the code and review against your own invention.

## Convention bindings

- [references/violations.md](references/violations.md) — the 11 codes, their
  severities, and what each one means. Read it before reporting.
- The repo's `SANYI.md` — the contract itself. Its entries are the only source of
  what is Buyi (invariant), Jianyi (budgeted), or Bianyi (tunable). Read it first.

## What to check

Walk the changed files against the contract entries whose `paths` cover them:

- **Buyi entries touched at all** — BY-1. Any edit inside a guarded path, however
  harmless it looks.
- **Buyi invariants made conditional** — BY-2. A new flag, env var, or config key
  can now switch the invariant off. Every line reads innocent; only the diff-vs-
  contract comparison shows the demotion. This is the highest-value finding here.
- **Buyi evidence tests deleted, skipped, or loosened** — BY-3.
- **Declared invariants with prompt-only implementation** — BY-4. No deterministic
  code path backs the constraint.
- **Jianyi budgets exceeded** — JY-1; anomalous single-PR growth within budget —
  JY-2; an untyped catch-all (`dict`, `Any`, `**kwargs`) introduced or widened in a
  budgeted component — JY-3, counted as unbounded growth, not one field.
- **Bianyi values hardcoded outside their declared layer** — BN-1.
- **A component's natural layer shifted with no `## Migrations` record** — MG-1.
  Migration is healthy; the unrecorded part is the finding.
- **Changed files matching no contract entry** — UN-1; **entries whose `paths`
  match no existing file** — UN-2.

Report the more specific code when two apply: BY-1 is subsumed by BY-2 or BY-3 on
the same entry.

## Severity is not yours to choose

Each code carries a fixed `merge_impact` through `_MERGE_IMPACT` in
`review/validate.py`: BY-\* → `blocker`, JY-\* → `important`, BN-1 →
`suggestion`, MG-1/UN-\* → `nit`. A finding whose `merge_impact` disagrees with
its `violation_code` is rejected mechanically. Set `severity.violation_code` and
let the table decide — do not argue a BY-2 down to a nit because the diff looks
reasonable.

## Read-only, and never the fix

This dimension reports; it does not edit and does not decide. A Buyi finding
presents the options — revert, redesign, or amend the contract through
architecture review — and leaves the choice to the operator. Auto-fixing a safety
constraint is itself a contract violation: the enforcer must not rewrite the
verdict.

## Constraints

These six bind every finding you return.

1. **Confidence floor ≥80%.** Ship only findings you are at least 80% sure are
   real. A suspicion that a value "feels like" a tunable is not a BN-1; the
   contract entry saying so is.
2. **Surgical scope.** Flag what this diff caused. UN-2 and pre-diff contract
   drift carry `pre_existing: true`.
3. **Terse.** One to two sentences per finding.
4. **`quoted_span` required.** Quote the literal source text at the line you cite
   — for a BY-2, quote the line that introduces the bypass; for a BY-4, quote the
   prompt sentence that carries the unbacked claim.
5. **IDs use the `CT-` prefix** — `CT-001`, `CT-002`. A mismatched prefix fails
   validation as a skill-load failure.
6. **Spec citation (F4).** A finding that asserts a convention breach must carry
   `spec_citation` naming the file and section it rests on — the `SANYI.md` entry
   for a contract violation, or `.claude/specs/agent-*.md § Section` where the
   claim rests on a written convention. `review/validate.py` rejects a finding
   that names a `.claude/specs/agent-*.md` path in its basis or claim text but
   carries no citation. Either cite the section or report the problem on its own
   merits without invoking a spec.

## Output

A JSON array of findings in the canonical schema (`review-shared/references/
finding-schema.md`). Empty array when you find nothing — a legitimate result the
verdict ladder reads as such.
