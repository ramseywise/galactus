# Expected: init-valid-contract

A good run of `/sanyi init` against this fixture:

1. Auto-drafts Bianyi entries from `config.py` (MODEL_NAME, MAX_RETRIES, CONFIDENCE_THRESHOLD, CHUNK_SIZE) and `prompts.py` (SYSTEM_PROMPT)
2. Auto-drafts Jianyi entry for `states.py` AgentState with `current: 8 fields` measurement
3. Identifies `guards.py` as a Buyi candidate (safety guards: PII masking, escalation)
4. **Step 2 verification catches that guards.py has zero call sites** — `mask_pii` and `check_escalation_needed` are not imported by `router.py` or any other module
5. Presents the guards.py candidate **with the verification result** (gap noted), not silently placed in Buyi as if it were active
6. Creates SANYI.md with all 6 required sections: Buyi, Jianyi, Bianyi, Migrations, Pending, Debt
7. Closing audit runs and seeds Debt section (at minimum: the guards.py zero-callsite gap as BY-4)

The key judgment: step 2 verification must catch that guards.py is dead code from a
contract perspective. Placing it in Buyi without noting the gap would create a false
contract entry — exactly the failure mode init step 2 was designed to prevent.
