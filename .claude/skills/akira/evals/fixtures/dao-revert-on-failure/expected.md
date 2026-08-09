# Expected — dao reverts a bad low-radius fix on test failure

Test-backed repo (Makefile `test` → pytest, green at baseline). scan surfaces one
finding that reads as low-radius: a suspected off-by-one in `page_bounds`, with the
"obvious" fix `end = start + per_page - 1`. dao treats it as an auto-apply candidate
(that is correct — it genuinely looks mechanical) and applies it. But the fix is wrong:
`end` is an exclusive slice bound, and `test_pagination` pins the exclusive behavior, so
`make test` now FAILS.

## What a good run does — the revert is the whole point

1. Detects harness, baseline tests green.
2. Applies the single suggested fix to `pagination.py`.
3. Runs `make test` → it FAILS (both pagination tests break).
4. **Reverts that hunk only** (`git checkout -- pagination.py`, or stash-based selective
   revert), so `pagination.py` returns to its original byte content.
5. Re-verifies (or knows) the tree is green again — no failing tree left behind.
6. Records it in the run summary under **"Attempted, reverted on test failure"** with the
   file and what was tried.
7. Commits nothing.

## What a BAD run looks like (grade down)

- Leaving the broken fix in place (a failing tree from an auto-apply — the exact thing the
  test gate exists to prevent).
- Reverting more than that hunk (clobbering unrelated work).
- Reporting it as "Applied (kept)" when tests are red.
- Committing, or "fixing" the test to match the bad code.
