# docs-check — archived 2026-08-14

Superseded by the `review-architecture` dimension. Nothing moved; the coverage already
existed there.

## Why

`review-architecture` declares documentation accuracy in its own description — *"docs-vs-code
drift, stale paths and capability claims"* — and its body asks the same questions this
skill asked:

- Do existing docs (`CLAUDE.md`, `README.md`, architecture docs) still match the code?
- Do file paths, module references, or capability claims in project docs still resolve?

It does the job better in two ways this skill could not:

1. **It reports pre-existing drift.** `review-architecture` treats documentation as the one
   place `pre_existing: true` findings are routinely worth raising — *a doc that lies was
   already lying before the diff*. A standalone audit had no such convention.
2. **It emits findings against the shared schema**, so drift lands in the same merge
   ladder as every other dimension, with a quoted false sentence and a `path:line`
   citation, instead of a separate report nobody routes.

## What this means operationally

Doc drift is now checked on every `/proto-review` run rather than only when someone
remembers to type `/docs-check`. That is the actual upgrade: the standalone skill required
an operator to suspect drift before it could find any.

If you want a docs-only pass without a full review, run the `review-architecture`
dimension alone rather than reviving this.
