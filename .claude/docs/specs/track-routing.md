# Spec: Track routing for the prototyping pipeline

Status: DRAFT
Scope: router + phase protocol split. Execute repair loop and eval harness are out.

## Problem

The pipeline has one deterministic router and five prose phases.

`review/signals.py` classifies a changed-file set into `is_agent_code` / `is_ml_code` and
computes which dimensions run, with a `skipped` map carrying reasons. That is a typed
router feeding a fan-out of single-purpose nodes, joined by a computed verdict. It works.

Every other phase infers its own behaviour from an unstructured prompt. Consequences:

1. **`/ml-select` and `/ml-transform` are orphans.** 650 lines of real ML protocol —
   including `ml-select`'s refusal to run before profiling, which is a genuine
   precondition edge — reachable only by the operator remembering to type them. Grepping
   `proto-research`, `proto-plan`, and `proto-execute` for `ml-select|ml-transform|leakage|ML`
   returns zero hits.
2. **Track discipline is enforced only at the last phase.** `leakage` activates in review,
   after the code is built. Leakage is a planning-time decision — target definition, split
   strategy, and fold boundaries are chosen in the plan, not discovered in the diff.
3. **`proto-plan` is an overloaded verifier.** Goal elicitation, argument routing, and
   step authoring in one context, for both tracks implicitly.

## Decisions

| Decision | Value | Why |
|---|---|---|
| Track cardinality | Two: `ml`, `agent` | Matches what this repo prototypes. A third `general` track was considered and rejected — see Rejected below. |
| Track determination | Inferred from the plan doc, written to a `Track:` line | One router for the whole pipeline; inference happens once, at the earliest phase, and later phases read a cheap line. |
| Router location | `review/signals.py`, extended | It already owns the ML/agent vocabulary. A second router would be a second definition of "ML code". |
| Scope | Router + protocol split | The execute repair loop and the eval harness are separable and independently valuable. Doing them here would destabilise a pipeline in daily use. |

### Rejected: a third `general` track

`detect_signals` returns independent booleans, so "neither" is reachable today and repo
tooling work (the `review/` package itself, `.claude/` changes) genuinely is neither. The
two-way split means such work routes to `agent` by the tie-break below.

This is a real cost and it is accepted deliberately: a third protocol body per phase is
three new files whose content would be "today's prompt with the track-specific parts
removed" — the status quo, given a name. If tooling work routed to `agent` proves
actively wrong in practice, revisit; the router's return type does not need to change to
add a track, only `_TRACKS` and the protocol table.

## The router

### Contract

```python
def detect_track(
    doc_text: str | None = None,
    files: list[str] | None = None,
    repo_root: str = ".",
) -> dict:
    """Classify a work item as the `ml` or `agent` track.

    Returns:
        track:      "ml" | "agent"
        source:     "declared" | "doc" | "files" | "default"
        confidence: "high" | "low"
        reason:     human-readable string naming the evidence
    """
```

Returning `source` and `reason` alongside `track` is the same rule that made
`active_dimensions` return its `skipped` map: **a classification that does not say what it
rested on cannot be audited.** A `Track: ml` line whose `source` is `default` is a
different fact from one whose `source` is `doc`, and the phases treat them differently
(see Low confidence below).

### Precedence

1. **`declared`** — a `Track:` line in the doc. Human override always wins.
2. **`doc`** — keyword scan of the doc text.
3. **`files`** — existing `detect_signals` on referenced/changed paths.
4. **`default`** — `agent`, `confidence: low`.

### Tie-break

Both signals true → **`ml` wins**. Asymmetric cost: an ML work item planned as an agent
item skips target definition, split strategy, and leakage-by-construction — defects that
survive to production and are expensive to unwind. An agent item planned as ML gets asked
some irrelevant questions in an interview. The costlier miss decides the tie, and
`agent-uncertainty.md` §asymmetric cost is the reference.

### Doc-text patterns

Reuse `_ML_IMPORT_PATTERNS` / `_AGENT_IMPORT_PATTERNS` against fenced code blocks. Add
prose patterns, deliberately narrow:

```
_ML_DOC_PATTERNS:     train/test split, target leakage, feature engineering,
                      class imbalance, cross-validation, baseline metric,
                      AUC/precision/recall/RMSE, tabular, dataframe
_AGENT_DOC_PATTERNS:  tool call, system prompt, context window, agent loop,
                      retrieval, eval harness, MCP, LangGraph, ADK, subagent
```

**These are matched against a plan doc, not source.** A doc that discusses both tracks in
prose is the expected case, not the exception — which is why the tie-break above is a
rule and not an error path.

### Low confidence

`confidence: low` (source `default`, or doc-scan with fewer than two distinct pattern
hits) means **the phase asks the operator instead of proceeding.** The router never
silently picks a track on thin evidence; the phases treat a low-confidence result as a
question, not an answer. This is the `agent-uncertainty.md` abstention rule applied to the
router itself.

### CLI

```bash
echo '{"doc": "...", "files": ["a.py"]}' | uv run python -m review.cli detect-track
```

Same shape as `detect-signals`: JSON in, JSON out, exit 0.

## The `Track:` line

Written next to `Status:` by `/proto-research` (the earliest phase), read by every later
phase.

```
Status: PLANNED
Track: ml
```

`plan_status_validate.sh` gains a `Track:` check with the same shape as the `Status:`
check — enum `{ml, agent}`, one token, no suffix. The hook already parses the doc for
`Status:` with a tolerant regex and a `has_field` helper; this is an additional block in
the same `python3` heredoc, not a new hook.

**The hook validates the value; it does not require the line.** Docs predating this change
have no `Track:` line and must not become unwritable. A missing line means later phases
call `detect_track` and write the result back. Blocking on absence would make the 6
existing plan docs in `.claude/docs/plans/` immediately invalid.

## Phase restructuring

Each phase becomes a thin orchestrator over track-specific protocol modules. The pattern
is the one `proto-review` already uses: a generic dispatcher, one protocol loaded per
dispatch, named explicitly.

```
proto-plan  (orchestrator: goal elicitation, doc I/O, Status transitions)
  └─ track = Track: line, else detect_track
      ├─ ml    → plan-ml
      └─ agent → plan-agent
```

### What lives where

**Orchestrator (stays in `proto-*/SKILL.md`)** — goal elicitation, `$ARGUMENTS` routing
(`review`/`refine`/`argue`), target-repo resolution, plan-doc read/write, `Status:`
transitions, the spawn-prompt block. All track-independent.

**Protocol (new `.claude/skills/<phase>-<track>/SKILL.md`)** — only what differs by track.

| Phase | `-ml` protocol | `-agent` protocol |
|---|---|---|
| research | data availability, provenance, target feasibility, prior baselines | framework survey, tool inventory, prior-art loops, context budget |
| plan | target definition, split strategy, leakage-by-construction, baseline metric, `/ml-transform` → `/ml-select` as steps | five layers, loop termination, tool contracts, eval hooks |
| execute | fit-order discipline, split before transform, metric recorded per step | contract-first, harness before prompt |

Research and execute protocols are thinner than plan's — much of research and execute is
genuinely track-independent, and a protocol module that only restates the orchestrator is
worse than no module. **Write the plan protocols first; add research/execute protocols
only where a real difference exists.** Step 4 below is explicitly allowed to conclude that
`execute-ml` is not worth writing.

### `/ml-transform` and `/ml-select` stop being orphans

`plan-ml` names them as its own steps, in order, with `ml-transform` first — which is what
`ml-select`'s existing precondition already demands ("Refuses to select before the data
has been profiled"). That precondition becomes a routed edge instead of a line of prose
hoping to be read.

Their outputs (`.claude/docs/ml-config.md`, the `ColumnPlan`) are referenced from the plan
doc's `## Plan` section, so `/proto-execute` and `/proto-review` can find them.

**Neither skill is modified.** They are invoked, not rewritten.

## Non-goals

- **No fan-out in plan/execute.** The true-dependency test says planning is sequential:
  each step reads the previous step's output. Fan-out stays in review, where it earns its
  keep. Applying the review *pattern* is not the same as applying its *topology*.
- **No new state-machine edges.** `REFINED → PLANNED` and the rest of the failure edges
  are the next increment, not this one.
- **No execute repair loop.**
- **No changes to vendored skills.** `mcp-builder`, `skill-creator`, and `docs-check` are
  upstream copies per `CLAUDE.md`'s vendoring exception. `proto-*`, `ml-*`, and `review/`
  are galactus-canon and editable here.

## Verification

| Claim | Instrument |
|---|---|
| Router classifies correctly | Unit tests over the 6 existing plan docs in `.claude/docs/plans/`, hand-labelled. Both tie-break directions covered. |
| Router is honest about thin evidence | A doc with no track signal returns `confidence: low`, not a guess. |
| `Track:` hook accepts valid, rejects invalid | Hook tests alongside the existing ones in `.claude/hooks/tests/`. |
| Legacy docs stay writable | Write to a `Track:`-less doc succeeds. |
| ML protocol is reachable | An ML plan doc routes to `plan-ml` and names `/ml-transform` before `/ml-select`. |
| No regression | `uv run pytest -q` green; `detect-signals` output unchanged for the same input. |

The last row is load-bearing: `detect_track` adds to `signals.py` and must not perturb
`detect_signals`, which `/proto-review` depends on daily.

## Open questions

1. **Does `Track:` belong in the plan doc or a sidecar?** Spec says the doc — it is the
   bus, and a sidecar is a second source of truth. Flagged because it touches the hook.
2. **Should `/proto-review` consume `Track:`?** It has its own file-based detection that
   works. Reading `Track:` as a cross-check — declared `ml` but no ML signal in the diff —
   is a plausible finding, but it is scope creep here.
