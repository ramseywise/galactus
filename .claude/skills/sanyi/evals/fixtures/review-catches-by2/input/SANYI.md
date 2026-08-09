# SANYI.md — test-fixture

Last audit: 2026-07-20

## 不易 Buyi (invariants)

### PII Masking

- **What**: All user-provided text is masked for PII before logging or external API calls
- **Where**: `masking.py` — `mask_pii()` function
- **Contract**: PII masking is always on; never bypassable via config, env, or flag
- **Evidence**: `test_masking.py::test_pii_always_masked`, `test_masking.py::test_no_bypass_flag`
- **Paths**: `masking.py`

## 简易 Jianyi (simple)

_No entries for this fixture._

## 变易 Bianyi (ever-changing)

_No entries for this fixture._

## Migrations

_None._

## Pending

_None._

## Debt

_None._
