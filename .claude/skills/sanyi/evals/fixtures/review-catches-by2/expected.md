# Expected: review-catches-by2

A good run of `/sanyi review` against this fixture:

1. Identifies the finding as **BY-2** (invariant made bypassable), not BY-1 (direct modification)
2. Names the `ENABLE_PII_MASKING` env var as the specific bypass vector
3. Reports severity as **blocker**
4. Does NOT report BY-3 (evidence test deleted) — test_masking.py is NOT modified in this diff
5. Presents decision options: revert | redesign | amend contract
6. Verdict affirms the diff changes the system's change-contract structure

The key judgment: BY-2 is the correct code because the invariant is not directly edited —
it's semantically undermined by wrapping it in a conditional. BY-1 would be wrong (that's
for direct edits to the invariant's implementation). BY-3 would be a false positive (the
evidence tests are still intact in this diff).
