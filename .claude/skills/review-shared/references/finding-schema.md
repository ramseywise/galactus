# Canonical Finding Schema

Every review dimension outputs findings in this format. The shared schema is what lets
the orchestrator merge and dedupe across ten dimensions and write one unified report.

**`review/models.py` is authoritative.** This file documents it; where the two disagree,
the code wins and this file is the bug. `review/validate.py` enforces it mechanically —
a finding that does not validate is rejected, not repaired.

## Schema

```yaml
id: <PREFIX>-<NNN>              # CR-001, SF-002 — prefix set by the dimension
reporter: intent | correctness | silent_failure | testing | safety
        | architecture | runtime | safeguards | contracts
category: correctness | reliability | security | data | architecture
        | testing | operations | agent_behavior | evaluation | communication
evidence_state: verified | supported | hypothesis | question   # see evidence-model.md

location:
  files:
    - path: path/to/file.py
      start_line: 42            # optional
      end_line: 48              # optional; must be >= start_line
  symbols: [function_name]      # optional — changed symbols involved

claim:
  title: one-line summary
  observation: what was found (factual, not interpretive)
  failure_scenario: how it breaks in practice   # optional
  impact: blast radius (who/what is affected)   # optional

severity:
  source_native: blocker | warning | info | notice   # optional
  merge_impact: blocker | important | question | suggestion | nit
  violation_code: BY-2                              # contracts only

basis: [code grep, test result, contract entry, trace, caller inspection]
comment_type: request_change | question | suggestion | nit
plan_step: 3                    # optional — the plan step this relates to

quoted_span: "if user_input:"   # REQUIRED — literal source text at the cited line
spec_citation: ".claude/specs/agent-tools.md § Idempotency"   # optional
pre_existing: false             # true when the diff did not cause it
```

## Field rules

- **`id`**: unique within a run, matching `{PREFIX}-{NNN}`. The prefix is set by the
  dimension — see the table below. Numbering restarts each run.
- **`id` prefix is skill-load verification, not naming.** One `review` agent serves all
  ten dimensions, so the prefix is the only in-band evidence that a dispatch loaded the
  skill it was told to load. A `safety` dispatch returning `CR-001` is rejected as a
  skill-load failure, because that mismatch is what a wrong-skill dispatch looks like.
- **`quoted_span` is required.** The literal source text at the line cited. A finding
  that cannot quote the code it cites did not read the code. Matched
  whitespace-normalized against `start_line..end_line` with a ±1-line window.
- **`spec_citation`**: required when a finding asserts a convention breach. A finding
  naming a `.claude/specs/agent-*.md` path in its basis or claim text but carrying no
  citation is rejected — "this violates the convention" without a section is
  unfalsifiable. Enforced for `runtime`, `safeguards`, and `contracts`.
- **`pre_existing`**: `true` when the diff did not cause the problem. Surgical scope is
  the default; documentation drift is the routine exception.
- **`evidence_state`**: orthogonal to severity — a `hypothesis` can be
  `merge_impact: blocker`; a `verified` finding can be a `nit`. A `question` state
  constrains `merge_impact` (it cannot be a blocker).
- **`severity.source_native`**: a foreign system's own severity, preserved verbatim.
  Never invent or rewrite another system's codes.
- **`comment_type`**: maps to GitHub review comment types. Hypotheses and questions use
  `question`, not `request_change`.

## Dimension prefixes

Mirrors `REPORTER_ID_PREFIX` in `review/models.py`. `review/tests/test_prefix_map.py`
fails loudly if this table and the code drift apart.

| Dimension | Skill | Prefix |
|---|---|---|
| intent | `review-intent` | `IN` |
| correctness | `review-correctness` | `CR` |
| silent_failure | `review-silent-failure` | `SI` |
| testing | `review-testing` | `TE` |
| safety | `review-safety` | `SF` |
| architecture | `review-architecture` | `AR` |
| runtime | `review-runtime` | `RT` |
| safeguards | `review-safeguards` | `SG` |
| contracts | `review-contracts` | `CT` |
| leakage | `review-leakage` | `LK` |

The `wander` agent is not a dimension and emits questions, not findings — its output
does not use this schema.

## Merge-impact derivation

Dimensions propose `merge_impact`; the orchestrator may adjust during merge when
cross-reporter context changes the picture, and must say so when it does.

**The `contracts` dimension is the exception: its `merge_impact` is fixed by
`violation_code` and is not adjustable.** `_MERGE_IMPACT` in `review/validate.py`
rejects any mismatch.

| violation_code | merge_impact |
|---|---|
| BY-1, BY-2, BY-3, BY-4 | blocker |
| JY-1, JY-2, JY-3 | important |
| BN-1 | suggestion |
| MG-1, UN-1, UN-2 | nit |

For the other eight dimensions there is no code table — the reporter judges, subject to
the ≥80% confidence floor, and a `question` evidence state caps impact below blocker.

## Compact output format

For ranked-list readability (agents output this, not raw YAML):

```markdown
- **[merge_impact:evidence_state]** `ID` `file:line` — claim title
  Evidence: basis summary
  Merge impact: merge_impact
```

## Worked examples

### A `safety` finding

```markdown
- **[blocker:verified]** `SF-001` `api/handlers.py:42` — Unvalidated external input reaches SQL query
  Evidence: grep confirmed no validation between request handler (api/handlers.py:18) and
  query builder (db/queries.py:33). Input flows through `process_request()` → `build_query()`
  with no sanitization step.
  Merge impact: blocker
```

Schema:

```yaml
id: SF-001
reporter: safety
category: security
evidence_state: verified
location:
  files: [{ path: api/handlers.py, start_line: 42 }]
  symbols: [build_query]
claim:
  title: Unvalidated external input reaches SQL query
  observation: User input from request handler flows to query builder with no sanitization
  failure_scenario: SQL injection via crafted request parameters
  impact: Database compromise, data exfiltration
severity: { merge_impact: blocker }
basis: [code grep of call chain]
comment_type: request_change
quoted_span: "cursor.execute(f\"SELECT * FROM t WHERE id = {req.id}\")"
```

### A `contracts` BY-2 finding

```markdown
- **[blocker:verified]** `CT-001` `backend/security/masking.py:8` — PII masking made bypassable via env var
  Evidence: grep confirmed `os.getenv('DISABLE_MASKING')` gates `mask_pii()` (masking.py:8).
  Contract entry: Buyi / PII Masking. Invariant demoted to config option.
  Merge impact: blocker
```

Schema:

```yaml
id: CT-001
reporter: contracts
category: security
evidence_state: verified
location:
  files: [{ path: backend/security/masking.py, start_line: 8 }]
  symbols: [mask_pii]
claim:
  title: PII masking made bypassable via env var
  observation: New DISABLE_MASKING env switch can disable mask_pii() entirely
  failure_scenario: PII leaks to logs/responses when env var set
  impact: Privacy violation, regulatory exposure
severity: { source_native: blocker, merge_impact: blocker, violation_code: BY-2 }
basis: [code grep, contract entry]
comment_type: request_change
quoted_span: "if os.getenv('DISABLE_MASKING'):"
spec_citation: "SANYI.md § Buyi / PII Masking"
```

## No persistence

Findings are session state. Nothing is written to disk — the orchestrator's markdown
report is the output, and a later review never reads an earlier one's findings.

This is deliberate. A durable findings log implies trending, cross-review dedup, and a
schema that must stay back-compatible with every row ever written; this subsystem takes
none of that on. If a future work item wants persistence, it arrives as its own decision
with its own storage design — not by a reader assuming a JSONL append was meant to be
here.
