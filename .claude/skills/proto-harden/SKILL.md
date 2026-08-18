---
name: proto-harden
description: "Hardening pass for a prototype before demo or review — walks the defect classes distilled from the marketing-comms hardening (seam conformance, runnable demo, service-surface safety, eval falsifiability, doc parity, recurring patterns) against a run directory and fixes the gaps in-session, with tests. Triggers: 'harden the prototype', 'harden this run', 'pre-demo hardening', 'make it demo-ready', '/proto-harden <run-dir>'."
allowed-tools: Read Grep Glob Bash Edit Write
---

# Prototype hardening

A tool, not a phase. Called after `/proto-execute` and before `/proto-review` —
or standalone on any run that is about to be demoed, handed to review, or held
up as a reference. It never touches `Status:`; the plan-doc state machine does
not know it ran. `/proto-review` still judges the result afterwards — hardening
is not a substitute for the verdict.

**Evidence base:** `bug/marketing-comms-review-fixes` in this repo — ~1,900
lines of fixes to `runs/ai/marketing-comms/` found by reviewing a prototype
whose 300 tests were green. Every item below is a defect class that diff closed;
`git diff main...bug/marketing-comms-review-fixes` is the worked example when an
item's intent is unclear.

`$ARGUMENTS` — a run directory (`runs/ai/<slug>` or `runs/ml/<slug>`), or empty
to infer from the session's recent work. Ask rather than guess if ambiguous.

## Ground rules

1. **Fix, don't just list.** This skill exists because the checklist was learned
   by fixing; a gap you find, you close in-session — with a test that fails
   without the fix. Stop and report instead only when the fix needs a design
   decision (a contract change, a dropped guarantee) that is the operator's call.
2. **Never commit** — staged changes are the output. Never touch `Status:`.
3. **Run the suite before and after.** A hardening pass that breaks tests has
   made the prototype worse.

## The checklist

Work the classes in order — each is cheap to check and expensive to skip.

### 1. Seams — fakes vs. the real adapter

The founding defect: a port too narrow for its consumer (`LLM` had no `images`
param), a caller routing around the seam, and per-module fakes conforming to the
broken port — so the payload was built, thrown away, and no test could see it.

- One shared fake per port (`tests/fakes.py`), recording the **full** signature
  including optional channels. Delete per-module duplicates.
- A contract test on the **real adapter's wire shape**: decode what it sends and
  assert identity with the input (bytes, ordering, media type).
- Caller-side identity assertions at unit and end-to-end level: what crosses the
  seam equals the real artifact.
- Fakes raise the real error types, imported from production code.
- Full rule: `review-testing` § Seam conformance.

### 2. Runnable demo

Start the real process (`uv run uvicorn ...` or the stack equivalent) and drive
the demo path with real requests. `TestClient` green proves none of:

- **Config knobs exist** — persistence path, API key, budgets readable from env,
  validated at load (a negative budget must fail startup, not silently skip a
  loop).
- **Clients are process-global**, not constructed per request.
- **Startup reconciles orphaned state** — jobs left `running` by a dead process
  are failed loudly at boot, not left for clients to poll forever.
- **Concurrent access works** — file-backed SQLite needs WAL + busy timeout the
  moment a second client exists.
- **The demo transcript in docs/slides is re-run**, not assumed — response
  bodies drift.

### 3. Service surface (safety)

Run the full checklist in `review-safety` § Service-surface checklist:
client-string→path gating, read-time upload caps, magic-byte validation,
blocking work off the event loop, TOCTOU single-handle rule, tenant+id mutation
scope, metadata-only listings, fenced document content at prompt sinks,
whitelisted response models.

### 4. Eval falsifiability

Run the checklist in `review-safeguards` § Eval falsifiability: every headline
metric tested in **both** directions (the negative case is the load-bearing
one), scripted providers deriving output from their inputs rather than
fixture-matched constants, config parity with production (shared constants,
threaded budgets), fixture tables validated at load against the shipped
fixtures, eval fakes conforming to the port.

### 5. Doc parity

Read `docs/DESIGN.md` (and any presentation) against the code, not against
memory:

- Every linked path resolves.
- Every described behavior matches what the code does — a reversed design
  decision must reverse its rationale in the doc, not leave the old argument
  standing.
- No overclaimed guarantee: "cannot fail" must state its precondition and its
  backstop.
- The limitations list is current in both directions — it neither disclaims
  capabilities that now exist nor omits gaps that remain.
- Stale figures (test counts, metrics) match a fresh run.

### 6. Recurring patterns

Cheap greps with high yield; each was found live in the evidence diff:

- **Re-validate the backstop.** A "cannot fail" fallback's output is still
  re-checked before success is recorded; if it ever fires, fail loudly rather
  than ship an invalid result labelled degraded.
- **Load-time over request-time validation.** An unsatisfiable template, a
  negative budget — a designer typo should fail the deploy, not the one request
  that hit the edge.
- **Coerce at trust boundaries into the recovery path.** Malformed-but-adjacent
  input (an int where a string belongs) becomes input the existing repair
  machinery handles, not a crash deep in a validator.
- **Error paths that can themselves fail.** The write that records a failure is
  guarded; the first state write lives inside the try block.
- **Single definition for anything compared across modules** — a normalizer
  duplicated on both sides of an equality check is a latent silent mismatch.
  Same for shared constants (default budgets, template ids) between app and
  eval.
- **Degradation carries granularity** — *which* fields degraded, not a boolean.
- **Green for the wrong reason** — when adding a check, find the tests that were
  passing only because it was missing.

## Output

Close with a gap table — one row per finding, fixed or escalated:

| # | Class | Site | Fix | Test |
|---|-------|------|-----|------|
| 1 | seams | `src/model/gateway.py:62` | `images=` added to port + adapter | `test_anthropic_adapter.py::test_images_travel_...` |

Then the suite result (before/after counts), and anything escalated as an
operator decision. **Next step:** `/proto-review` — the hardened diff still gets
its verdict.
