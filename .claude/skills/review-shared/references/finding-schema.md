# Canonical Finding Schema

Every review reporter (akira-scan, SANYI review, future reporters) outputs findings
in this format. The shared schema enables merge/dedup across reporters and a unified
report for orchestrators (`/code-review`, `/workflow-review`).

## Schema

```yaml
id: <source>-<NNN>              # AK-001, SY-001, AW-001
source: akira-scan | sanyi | akira-wander
location:
  file: path/to/file.py
  lines: 42-48                  # start-end or single line
  symbols: [function_name]      # optional — changed symbols involved

claim:
  title: one-line summary
  observation: what was found (factual, not interpretive)
  failure_scenario: how it breaks in practice
  impact: blast radius (who/what is affected)

evidence:
  state: verified | supported | hypothesis | question   # see evidence-model.md
  basis: [code grep, test result, contract entry, trace, caller inspection]

severity:
  source_native: <reporter's own taxonomy>
    # akira: Blocking | Non-blocking | Nit
    # SANYI: blocker | warning | info | notice (from violation code)
  merge_impact: blocker | important | question | suggestion | nit

recommendation:
  action: fix | accept | investigate | defer
  description: what to do
  tradeoffs: cost of fixing vs not (optional)

communication:
  comment_type: request_change | question | suggestion | nit
```

## Field rules

- **`id`**: unique within a single review run. Prefix encodes source: `AK` = akira-scan,
  `SY` = SANYI, `AW` = akira-wander. Numbering restarts each run.
- **`evidence.state`**: see `evidence-model.md`. Orthogonal to severity — a `hypothesis`
  can be `merge_impact: blocker`; a `verified` finding can be `merge_impact: nit`.
- **`severity.source_native`**: the reporter's own severity, preserved verbatim. Never
  invent or rewrite another system's codes.
- **`severity.merge_impact`**: PR-level impact. Reporters propose this; orchestrators may
  adjust during merge.
- **`communication.comment_type`**: maps to GitHub review comment types. Hypotheses and
  questions use `question`, not `request_change`.

## Merge-impact derivation (defaults)

Reporters propose `merge_impact` using these defaults. Orchestrators may override
during the merge step when cross-reporter context changes the picture.

| Source | Code/Tier | Default merge_impact |
|--------|-----------|---------------------|
| SANYI | BY-1, BY-2, BY-3, BY-4 | blocker |
| SANYI | JY-1, JY-2, JY-3 | important |
| SANYI | BN-1 | suggestion |
| SANYI | MG-1, UN-1, UN-2 | nit |
| akira | [Blocking] | blocker |
| akira | [Non-blocking] | important or suggestion (reporter judges) |
| akira | [Nit] | nit |
| akira-wander | all questions | question |

## Compact output format

For ranked-list readability (agents output this, not raw YAML):

```markdown
- **[merge_impact:evidence_state]** `ID` `file:line` — claim title
  Evidence: basis summary
  Merge impact: merge_impact
```

## Worked examples

### akira-scan finding

```markdown
- **[blocker:verified]** `AK-001` `api/handlers.py:42` — Unvalidated external input reaches SQL query
  Evidence: grep confirmed no validation between request handler (api/handlers.py:18) and
  query builder (db/queries.py:33). Input flows through `process_request()` → `build_query()`
  with no sanitization step.
  Merge impact: blocker
```

Schema:

```yaml
id: AK-001
source: akira-scan
location: { file: api/handlers.py, lines: 42, symbols: [build_query] }
claim:
  title: Unvalidated external input reaches SQL query
  observation: User input from request handler flows to query builder with no sanitization
  failure_scenario: SQL injection via crafted request parameters
  impact: Database compromise, data exfiltration
evidence: { state: verified, basis: [code grep of call chain] }
severity: { source_native: Blocking, merge_impact: blocker }
recommendation: { action: fix, description: Add input validation at handler boundary }
communication: { comment_type: request_change }
```

### SANYI BY-2 finding

```markdown
- **[blocker:verified]** `SY-001` `backend/security/masking.py:8` — PII masking made bypassable via env var
  Evidence: grep confirmed `os.getenv('DISABLE_MASKING')` gates `mask_pii()` (masking.py:8).
  Contract entry: 不易 Buyi / PII Masking. Invariant demoted to config option.
  Merge impact: blocker
```

Schema:

```yaml
id: SY-001
source: sanyi
location: { file: backend/security/masking.py, lines: 8, symbols: [mask_pii] }
claim:
  title: PII masking made bypassable via env var
  observation: New DISABLE_MASKING env switch can disable mask_pii() entirely
  failure_scenario: PII leaks to logs/responses when env var set
  impact: Privacy violation, regulatory exposure
evidence: { state: verified, basis: [code grep, contract entry] }
severity: { source_native: blocker, merge_impact: blocker }
recommendation: { action: fix, description: "Revert | redesign | amend contract via architecture review" }
communication: { comment_type: request_change }
```

## Persistence format (JSONL)

After producing findings, `/workflow-review` appends one JSON line per finding to the
review-findings file. It is an append-only log — a later review never rewrites an
earlier row.

```json
{"id":"AK-001","source":"akira-scan","date":"2026-07-23","repo":"guacamayo","file":"src/foo.py","lines":"42-48","symbols":["load_config"],"title":"Unchecked None return","merge_impact":"blocker","evidence_state":"verified","category":"bugs","session_id":"a1b2c3d4-e5f6-7890-abcd-ef1234567890"}
```

Required fields: id, source, date, repo, file, title, merge_impact, evidence_state,
category, session_id.
Optional: lines, symbols.

Reduced rows (severity conflated into one field, missing id/source) break trending and
cross-review dedup — write the full row or none.

File path: `.claude/docs/review-findings.jsonl`, relative to the repo root (create if
missing).
