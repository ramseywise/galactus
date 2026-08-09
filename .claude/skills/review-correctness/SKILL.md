---
name: review-correctness
description: >
  Review dimension: correctness and contracts — input validation, output
  contracts, schema compatibility, state transitions, invariants, edge cases,
  ordering, concurrency, and cross-usage schema consistency.
prefix: CR
allowed-tools: Read, Grep, Glob, Bash
---

# Correctness and Contracts

Vendored from Parallax `.claude/skills/intent-correctness/SKILL.md`, § "Correctness
and Contracts", with guacamayo's correctness reporter folded in. Parallax is
read-only: fix upstream and re-vendor, never edit that copy from here.

You are dispatched with exactly this one dimension loaded. Report only correctness
problems — intent, testing, and silent failure each have their own dispatch.

## What to examine

- **Inputs**: Are inputs validated and handled for the full range of values they
  can actually take, not just the happy path?
- **Outputs**: Do outputs match the documented or implied contract (type, shape,
  units, nullability)?
- **Schemas**: If a schema changed, is it backward compatible, or is the
  migration/versioning handled explicitly?
- **State transitions**: Can the system land in an invalid or unreachable state?
- **Invariants**: Are the invariants the code relies on still upheld after this
  change?
- **Edge cases**: What edge cases (empty, null, zero, max, duplicate,
  out-of-range) are exercised, and which are missing?
- **Ordering**: Does ordering matter here, and is it guaranteed where the code
  assumes it?
- **Concurrency**: Is concurrent access to shared state safe (races, locks,
  atomicity)?
- **Compatibility**: Is this change compatible with existing callers, stored data,
  or in-flight requests during rollout?
- **Cross-usage consistency**: when the diff modifies a shared schema or type,
  check all of its usages across the repo, not only the diff's own callers.

## Constraints

These five bind every finding you return.

1. **Confidence floor ≥80%.** Ship only findings you are at least 80% sure are
   real. Drop the rest.
2. **Surgical scope.** Flag what this diff caused. Pre-existing problems are
   reportable only when the change makes them more likely to fire, carrying
   `pre_existing: true`.
3. **Terse.** One to two sentences per finding.
4. **`quoted_span` required.** Every finding quotes the literal source text at the
   line it cites. `review/validate.py` rejects a span the cited line does not
   contain.
5. **IDs use the `CR-` prefix** — `CR-001`, `CR-002`. A mismatched prefix fails
   validation as a skill-load failure.

Cross-usage checks are the one place you are expected to read outside the diff.
Grep for every usage of a changed shared type before claiming compatibility — a
correctness finding that rests on an unread caller is a hypothesis, and must carry
`evidence_state: hypothesis` if you ship it at all.

## Output

A JSON array of findings in the canonical schema (`review-shared/references/
finding-schema.md`). Empty array when you find nothing — a legitimate result the
verdict ladder reads as such.
