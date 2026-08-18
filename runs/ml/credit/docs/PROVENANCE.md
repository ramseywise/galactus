# Credit default — data provenance

## Outgoing frame (lebanese-blonde sample)

| Field | Value |
|---|---|
| File | `data/credit_default.csv` |
| Rows | 801 (incl. header) = 800 data rows |
| SHA-256 | `ef4c290e21f37c4bb6aacd9462c1f024aec61b6bcf752b9f76090a6cf355342a` |
| Origin | `~/workspace/lebanese-blonde/src/data/dataset.csv` (unverified copy) |
| Status | Untracked (`.gitignore:50` — bare `*.csv`); no git history |

Recorded 2026-08-18 before the UCI frame was added. This file has no git history
and `git revert` cannot restore it — this hash is its only identity.

## UCI frame (active)

| Field | Value |
|---|---|
| File | `data/uci_default_of_credit_card_clients.csv` |
| Source | UCI Machine Learning Repository |
| URL | `https://archive.ics.uci.edu/static/public/350/data.csv` |
| License | CC BY 4.0 |
| Citation | Yeh, I-C. (2009). Default of credit card clients. DOI: `10.24432/C55S3H` |
| Rows | 30,001 (incl. header) = 30,000 data rows |
| Prevalence | 22.12% (6,636 / 30,000) — download-verified, not source-stated |
| Label horizon | **One month** — cited from the UCI variables table (`default payment next month`), not from the prose description block |
| Target column | `Y` (renamed to `default` by the loader) |

### Known quirks (from research, verified at download)

- `PAY_0` through `PAY_6`: undocumented codes -2 (n=2,759) and 0 (n=14,737) — ~58% of rows
- No `PAY_1` column — sequence is PAY_0, PAY_2..PAY_6 (off-by-one trap)
- EDUCATION: codes 0, 5, 6 (345 rows) not in the data dictionary
- MARRIAGE: code 0 (54 rows) not in the data dictionary
- 35 duplicate rows when excluding `ID`
- Header: `ID, X1..X23, Y` (cryptic; real column names in the variables table)
