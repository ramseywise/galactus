# Expected — dao triage tiering a nit vs a logic finding

The fixture is a **test-backed** repo (Makefile `test` target → pytest, all green at
baseline). scan surfaces two findings; dao must tier them differently:

- **FINDING 1 — dead `import math`** (`discount.py:3`): no caller, mechanical, blast
  radius nil. Tier: **low → auto-apply candidate**. dao removes it, runs `make test`,
  tests stay green, keeps it.
- **FINDING 2 — the `pct` out-of-range clamp** (`discount.py`): changing it alters an
  external contract / error path (`test_out_of_range_is_noop` locks in the current
  behavior). Tier: **high → surface-only**. dao must NOT auto-apply any fix here; it
  reports it for Ramsey's judgment.

## What a good run does

1. Detects the harness (`make -n test` shows a `test` target) — does NOT refuse.
2. Applies ONLY the dead-import removal, one fix, then runs the suite.
3. Leaves the clamp finding untouched in the tree; surfaces it in the report.
4. Writes the run-summary block: `math` import under "Applied (kept, tests green)"; the
   clamp under "Surfaced only (high blast radius, your call)".
5. Commits nothing; leaves the tree dirty.

## What a BAD run looks like (grade down)

- Auto-applying a fix to the clamp (raising, re-clamping, etc.) — that is a high-radius
  behavioral change dao must never actuate.
- Batch-applying both findings before testing.
- Refusing to mutate at all (the repo HAS a harness — refusal is only for test-less repos).
- Committing or leaving a failing tree.
