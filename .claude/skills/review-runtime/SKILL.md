---
name: review-runtime
description: >
  Review dimension: agent-system runtime behavior — tool side effects, workflow
  state and partial failure, retrieval boundaries, memory write-back. Conditional
  on the diff touching agent code.
prefix: RT
allowed-tools: Read, Grep, Glob, Bash
---

# Agent Runtime and Tooling

Vendored from Parallax `.claude/skills/agent-runtime-tooling/SKILL.md`. Parallax is
read-only: fix upstream and re-vendor, never edit that copy from here.

You are dispatched with exactly this one dimension loaded, and only when
`review/signals.py` detected agent code in the changed files — an LLM/agent
framework import, or a path under `agents/`, `*_agent/`, `prompts/`.

## Convention bindings

This dimension rests on written conventions, not on the code alone. Read the
relevant ref before reporting against it:

- [.claude/specs/agent-tools.md](../../specs/agent-tools.md) — tool contracts and side effects
- [.claude/specs/agent-runtime.md](../../specs/agent-runtime.md) — workflow state, termination, resumption
- [.claude/specs/agent-memory.md](../../specs/agent-memory.md) — what gets persisted and how it is corrected

## Tool Side Effects

- Is the tool read-only or write-capable?
- Is confirmation required?
- Is retry safe?
- Is idempotency guaranteed?
- Is output validated?
- Are permissions enforced at the tool boundary?

## Workflow State and Partial Failure

- Is the graph bounded? Can it terminate? Can it resume?
- What happens after partial success?
- Are handoffs explicit?
- Is deterministic code used where appropriate — is something being asked of a
  model that code should decide?

## Retrieval and Context

- Is retrieval scoped correctly?
- Is provenance preserved?
- Are permissions respected?
- Is stale or conflicting context handled?
- Can external content influence a sensitive sink? Prompt injection via retrieved
  or external content is the named threat class here.

## Memory Write-Back

- What is persisted? Is it fact, inference, or model output?
- Can it be corrected? Is confidence stored? Is approval required?
- Can bad runs contaminate future cases?

## Constraints

These six bind every finding you return.

1. **Confidence floor ≥80%.** Ship only findings you are at least 80% sure are
   real. Drop the rest.
2. **Surgical scope.** Flag what this diff caused; anything else carries
   `pre_existing: true`.
3. **Terse.** One to two sentences per finding.
4. **`quoted_span` required.** Every finding quotes the literal source text at the
   line it cites.
5. **IDs use the `RT-` prefix** — `RT-001`, `RT-002`. A mismatched prefix fails
   validation as a skill-load failure.
6. **Spec citation (F4).** A finding that asserts a convention breach must carry
   `spec_citation` naming the spec file and section it rests on — for example
   `.claude/specs/agent-tools.md § Idempotency`. `review/validate.py` rejects a
   finding that names a `.claude/specs/agent-*.md` path anywhere in its basis or
   claim text but carries no citation. "This violates the convention" without a
   section is the unfalsifiable shape the check exists to reject; either cite it
   or report the problem on its own merits without invoking a spec.

## Output

A JSON array of findings in the canonical schema (`review-shared/references/
finding-schema.md`). Empty array when you find nothing — a legitimate result the
verdict ladder reads as such.
