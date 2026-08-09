---
name: review-architecture
description: >
  Review dimension: architecture and maintainability (boundaries, coupling,
  abstraction, dependency direction, long-term contracts, dead code) plus
  documentation accuracy — docs-vs-code drift, stale paths and capability claims.
prefix: AR
allowed-tools: Read, Grep, Glob, Bash
---

# Architecture and Documentation

Vendored from Parallax `.claude/skills/architecture-docs/SKILL.md`, both sections.
Parallax is read-only: fix upstream and re-vendor, never edit that copy from here.

You are dispatched with exactly this one dimension loaded.

## Architecture and Maintainability

- **Boundaries**: Are module/service boundaries respected, or does the diff reach
  across a layer it should not?
- **Dependency direction**: Does the dependency direction stay consistent — does a
  lower-level module now import from a higher-level one?
- **Coupling**: Is coupling increased in a way that makes future changes harder?
- **Abstraction**: Is the abstraction at the right level — not over-engineered for
  a one-off, not leaking implementation details it should not?
- **Duplication**: Is logic duplicated that already exists elsewhere in the
  codebase?
- **Evolution**: Does this change make future evolution easier or harder?
- **Rollback**: Can this change be rolled back cleanly?
- **Long-term contract**: Does this diff commit the codebase to a long-term
  contract (public API, schema, interface) it may come to regret?
- **Magic numbers**: Are unexplained numeric or string literals used directly in
  logic instead of named constants that convey intent?
- **Dead code**: Is there code, branches, or exports left in the diff that are no
  longer reachable or used?

## Documentation Accuracy

- Do existing docs (`CLAUDE.md`, `README.md`, architecture docs, any
  capability/status tables the project maintains) still describe the code
  accurately after this diff?
- Do file paths, module references, or capability claims in project docs still
  resolve to something real?
- This is distinct from a Definition-of-Done check ("did this diff update its own
  docs"). It catches pre-existing or diff-introduced drift between docs and code,
  not just missing updates for the current change.

Documentation drift is the one place `pre_existing: true` findings are routinely
worth reporting: a doc that lies was already lying before the diff, and the review
is when someone reads it.

## Constraints

These five bind every finding you return.

1. **Confidence floor ≥80%.** Ship only findings you are at least 80% sure are
   real. Architectural taste is not a finding; a broken dependency direction is.
2. **Surgical scope.** Flag what this diff caused, with the documentation-drift
   exception above. Anything the diff did not cause carries `pre_existing: true`.
3. **Terse.** One to two sentences per finding. Do not propose a redesign.
4. **`quoted_span` required.** Every finding quotes the literal source text at the
   line it cites — for a stale doc, quote the sentence in the doc that is now
   false, and cite the doc's path and line.
5. **IDs use the `AR-` prefix** — `AR-001`, `AR-002`. A mismatched prefix fails
   validation as a skill-load failure.

## Output

A JSON array of findings in the canonical schema (`review-shared/references/
finding-schema.md`). Empty array when you find nothing — a legitimate result the
verdict ladder reads as such.
