---
name: review-testing
description: >
  Review dimension: test coverage — unit, integration, contract, regression,
  end-to-end, negative paths, assertion usefulness, and failure-before-fix
  evidence.
prefix: TE
allowed-tools: Read, Grep, Glob, Bash
---

# Testing

Vendored from Parallax `.claude/skills/intent-correctness/SKILL.md`, § "Testing".
Parallax is read-only: fix upstream and re-vendor, never edit that copy from here.

You are dispatched with exactly this one dimension loaded. Report only testing
gaps — the bug itself belongs to correctness or silent failure; you own whether
anything would catch it.

## What to examine

- **Unit**: Do unit tests cover the new/changed logic in isolation?
- **Integration**: Do integration tests cover how this interacts with the
  components it depends on?
- **Contract**: If a contract (API, schema, interface) changed, is there a
  contract test guarding it?
- **Regression**: For a bug fix, does a regression test exist for that specific
  bug?
- **End-to-end**: Is there end-to-end coverage exercising this change through a
  realistic path?
- **Negative paths**: Are failure paths tested, not just the success case?
- **Useful assertions**: Do the assertions verify the behavior that matters, or
  only that the code ran without throwing?
- **Failure-before-fix evidence**: For bug fixes, is there evidence the test
  failed before the fix and passes after?

A test that cannot fail is worse than a missing test: it reports coverage it does
not provide. Assertions that only check "no exception" are the common shape.

## Constraints

These five bind every finding you return.

1. **Confidence floor ≥80%.** Ship only findings you are at least 80% sure are
   real. Drop the rest.
2. **Surgical scope.** Flag coverage gaps this diff created. A module that was
   already untested is reportable only when the change extends it, carrying
   `pre_existing: true`.
3. **Terse.** One to two sentences per finding.
4. **`quoted_span` required.** Every finding quotes the literal source text at the
   line it cites — for a missing test, cite and quote the untested code, not an
   absent test file. A finding whose only location is a file that does not exist
   cannot be validated and will be rejected.
5. **IDs use the `TE-` prefix** — `TE-001`, `TE-002`. A mismatched prefix fails
   validation as a skill-load failure.

## Output

A JSON array of findings in the canonical schema (`review-shared/references/
finding-schema.md`). Empty array when you find nothing — a legitimate result the
verdict ladder reads as such.
