---
name: review-performance
description: >
  Review dimension: performance and scale — N+1 queries, unbounded iteration,
  hot-path algorithmic complexity, blocking I/O on async paths, and missing
  indexes for changed query patterns.
prefix: PF
allowed-tools: Read, Grep, Glob, Bash
---

# Performance and Scale

You are dispatched with exactly this one dimension loaded.

Performance findings are the easiest dimension to fill with noise. The bar is not
"could this be faster" — almost anything could. The bar is **this degrades badly
as real data grows, and the diff introduced it.**

## Scan for

- **N+1 queries**: Does the diff put a query, RPC, or other external call inside a
  loop that could be batched into one call?
- **Unbounded iteration**: Can this operation load or iterate an unbounded amount
  of data — a missing `limit`, absent pagination, a full-table read that grows
  with usage?
- **Hot-path complexity**: Does this add an algorithm whose complexity degrades
  badly at production scale — O(n²) or worse over data that grows with users,
  records, or time? Nested loops over the same collection are the usual tell.
- **Blocking I/O on an async path**: Does a coroutine or event-loop path make a
  synchronous filesystem, network, or subprocess call that stalls the loop?
- **Missing indexes**: If the diff changes a query pattern, does the store have —
  or gain — an index supporting it?
- **Repeated work**: Is an expensive pure computation recomputed inside a loop
  when it could be hoisted, or a result refetched that was already in hand?

## Scale is the argument, not the smell

A finding must name **what grows**. "This is O(n²)" is not a finding; "this is
O(n²) over `facts`, which grows with every uploaded PDF" is. If you cannot
identify the growing input, you do not have a finding — you have a preference.

Fixed-size collections are not a performance concern at any complexity. A nested
loop over a 5-element template list is fine, and flagging it costs the reader more
than it saves.

## Evidence standard

Evidence here is usually incomplete without production data — query plans, load
numbers, profiles. That does not make findings unreportable; it makes them
`hypothesis` rather than `verified`. Per `review-shared`, a `hypothesis` can still
carry real merge impact: an unbounded query on a user-facing path is serious
whether or not you measured it.

Never claim `verified` for a performance finding you did not measure. Reach for
`verified` only when the diff itself carries the proof — a query inside a loop is
visible in the source and needs no benchmark.

## Constraints

These five bind every finding you return.

1. **Confidence floor ≥80%.** Ship only findings you are at least 80% sure are
   real. Micro-optimization taste is not a finding; an N+1 on a request path is.
2. **Surgical scope.** Flag what this diff caused. Anything the diff did not cause
   carries `pre_existing: true`.
3. **Terse.** One to two sentences per finding. Do not propose a redesign, and do
   not attach a benchmark you did not run.
4. **`quoted_span` required.** Every finding quotes the literal source text at the
   line it cites — the loop, the call, the query.
5. **IDs use the `PF-` prefix** — `PF-001`, `PF-002`. A mismatched prefix fails
   validation as a skill-load failure.

## Output

A JSON array of findings in the canonical schema (`review-shared/references/
finding-schema.md`). Empty array when you find nothing — a legitimate result the
verdict ladder reads as such.
