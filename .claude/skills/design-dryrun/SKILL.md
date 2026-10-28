---
name: design-dryrun
description: >
  Simulate a volunteer walking the full project discovery pipeline with sample
  nonprofit scenarios. Validates artifact handoffs, checks that the right questions
  are asked/skipped, and logs friction. Use for: regression testing the skill
  pipeline after changes, onboarding new skill contributors, validating that
  /project-discovery → /scope-poc → /project-genesis produces coherent results.
  Triggers on: "/design-dryrun", "test the discovery pipeline", "smoke test skills",
  "validate the design flow", "run dryrun scenarios".
---

# /design-dryrun

Automated smoke test for the design skill pipeline. Simulates a volunteer walking
through `/project-discovery` → `/scope-poc` → (optionally) `/project-genesis` with
sample nonprofit scenarios. Validates that:
- The right archetype is selected for each pain point
- Project Profiles contain all required fields
- `/scope-poc` correctly consumes the profile (skips pre-answered, asks remaining)
- Copier hints map to valid parameter values
- The pipeline produces coherent, non-contradictory artifacts

## Usage

```
/design-dryrun [--scenario A|B|C|all] [--depth discovery|scope|full] [--output path]
```

| Arg | Default | Description |
|-----|---------|-------------|
| `--scenario` | `all` | Which scenario(s) to run |
| `--depth` | `scope` | How deep: discovery-only, through-scope, or full-pipeline |
| `--output` | `.claude/docs/dryrun-friction.md` | Where to write the friction log |

---

## Scenarios

Read full scenario details from `reference/scenarios.md`. Summary:

### Scenario A: Meeting Transcript Pipeline (Workflow Automation)

- **Nonprofit:** After-school tutoring program (education)
- **Pain:** "20 volunteer tutors meet weekly, nobody tracks decisions or follow-ups"
- **Expected archetype:** Workflow Automation
- **Expected project_type:** `workflow`
- **Expected complexity:** multi-sprint
- **Key copier hints:** `external_systems: [slack, calendar]`, `optional_features: [n8n_webhook, meeting_intelligence]`

### Scenario B: Tenant Rights FAQ (Information Retrieval)

- **Nonprofit:** Legal aid org serving NYC tenants
- **Pain:** "Volunteers spend 3 hours per intake looking up applicable housing regulations"
- **Expected archetype:** Information Retrieval
- **Expected project_type:** `rag`
- **Expected complexity:** multi-sprint
- **Key copier hints:** `vector_backend: duckdb`, `primary_chat_agent: lg_agent`

### Scenario C: Grant Report Drafting (Document Generation)

- **Nonprofit:** Small arts nonprofit (5 staff, no tech team)
- **Pain:** "Apply for 15 grants/year, each report is 8 pages, 60% is the same info"
- **Expected archetype:** Document Generation
- **Expected project_type:** `agent`
- **Expected complexity:** weekend sprint
- **Key copier hints:** `deployment_target: local`, `optional_features: [promptfoo]`

---

## Process

For each scenario, trace through the pipeline step by step:

### Stage 1: /project-discovery simulation

1. Present the scenario's pain point as if a volunteer said it
2. Trace through the discovery skill's 6 steps with the scenario's inputs
3. **Checkpoint 1.1:** Did the skill select the expected archetype? (PASS/FAIL)
4. **Checkpoint 1.2:** Does the produced Project Profile contain all required sections?
   - The Pain Point (non-empty, uses concrete language)
   - Nonprofit / Organization (name, domain, existing tech)
   - Archetype (matches expected)
   - Must-Demonstrate (3-5 concrete items)
   - Capacity Constraints (team, timeline, deadlines)
   - Explicitly Out of Scope (at least 1 item)
   - Copier Hints (all parameters are valid copier.yaml names, all values are valid choices)
5. **Checkpoint 1.3:** Are copier hints internally consistent?
   - If archetype is "Workflow Automation" → project_type should be `workflow`
   - If complexity is "weekend sprint" → deployment_target should be `local`
   - If external users → primary_users should be `customers` or `public_api`
6. Write the simulated Project Profile to a temp location

### Stage 2: /scope-poc simulation (if depth >= scope)

1. Feed the simulated profile to `/scope-poc`
2. **Checkpoint 2.1:** Does Step 0.6 fire? (finds and reads the profile)
3. **Checkpoint 2.2:** Are the right fields pre-filled (confirm-only, not re-asked)?
   - Pain point → Tier 1 Q1 (should be confirm-only)
   - Archetype → Tier 3 Q7 (should be confirm-only)
   - Must-demonstrate → Tier 5 Q12 (should be confirm-only)
   - Capacity → Tier 4 Q11 (should be confirm-only)
   - Out of scope → Tier 5 Q14 (should be confirm-only)
4. **Checkpoint 2.3:** Are the right questions still asked normally?
   - Actors and their specific roles (Tier 1 Q2-3)
   - System boundaries and integrations (Tier 2 Q4-6)
   - Data classification (Tier 4 Q9)
   - Evaluation metrics and naive baseline (Tier 3 Q8, Q8b)
   - Top risks (Tier 5 Q13)
5. **Checkpoint 2.4:** Does the resulting DESIGN.md structure contain all sections?

### Stage 3: Copier validation (if depth == full)

1. Check that all copier hints from the profile + decisions from scope-poc map to valid
   copier.yaml parameters and values
2. **Checkpoint 3.1:** No parameter references a non-existent copier.yaml question
3. **Checkpoint 3.2:** No value is outside the declared choices for its parameter
4. **Checkpoint 3.3:** No contradictions (e.g., `project_type=prototype` with `deployment_target=cloud`)

---

## Output: Friction Log

Write to `--output` path in this format:

```markdown
# Design Pipeline Dryrun — [date]

## Summary
- Scenarios run: [A, B, C]
- Pipeline depth: [discovery | scope | full]
- Result: [ALL PASS | N failures]

## Scenario A: Meeting Transcript Pipeline
| Checkpoint | Expected | Actual | Result |
|-----------|----------|--------|--------|
| 1.1 Archetype | Workflow Automation | [actual] | PASS/FAIL |
| 1.2 Profile completeness | All sections | [missing sections if any] | PASS/FAIL |
| 1.3 Hint consistency | Internally consistent | [contradictions if any] | PASS/FAIL |
| 2.1 Profile consumed | Step 0.6 fires | [yes/no] | PASS/FAIL |
| 2.2 Pre-filled correct | 5 fields confirm-only | [which failed] | PASS/FAIL |
| 2.3 Right questions asked | 5+ questions remain | [which wrongly skipped] | PASS/FAIL |
| 2.4 DESIGN.md complete | All sections | [missing] | PASS/FAIL |

### Friction entries
- [step]: [what happened] → [what should have happened] → [fix direction]

## Scenario B: ...
[same format]

## Scenario C: ...
[same format]

## Recommended fixes
1. [highest-severity friction entry + suggested fix]
2. ...
```

---

## Quality constraints

- **Expected values are assertions, not suggestions.** A scenario that produces the
  wrong archetype is a FAIL — not "close enough." The scenarios were chosen because
  they have clear, unambiguous correct answers.
- **Every friction entry names three things:** what happened, what should have happened,
  and which file/line to fix. Vague entries ("felt confusing") are not acceptable.
- **The dryrun must complete in a single session.** No multi-turn dependencies, no
  "come back tomorrow." If a checkpoint requires external input (API keys, real
  copier render), skip with a note rather than blocking.
- **Copier validation is syntactic, not semantic.** Check that parameter names and
  values are valid; don't actually render (that's what CI does).

---

**Upstream:** Run this after modifying any of: `/project-discovery`, `/scope-poc`,
`/project-genesis`, or the reference cards. Changes to those skills should not
introduce friction that wasn't there before.

**Next step:** If friction entries exist, fix them. Then re-run `/design-dryrun`
to confirm the fixes resolved the friction without introducing new issues.
