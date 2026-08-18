# Decision Record Shape

Each decision triage (`/proto-scope`) settles is recorded here as a markdown file.
One file per run, named `<run-slug>-decisions.md`.

## Record fields

| Field | Required | Description |
|---|---|---|
| `decision` | yes | What was decided |
| `proposed_default` | yes | The default the system proposed |
| `outcome` | yes | `confirmed` (operator accepted the default) or `overridden` (operator chose differently) |
| `operator_choice` | if overridden | What the operator chose instead |
| `reversibility` | yes | `trivial` / `costly` / `irreversible` — determines whether the question was proposed-and-confirmed or asked open |
| `source` | no | Where the proposed default came from (planning doc, convention, prior run) |

## Example

```markdown
# Decisions — fraud-parity

| # | Decision | Proposed | Outcome | Reversibility |
|---|---|---|---|---|
| D1 | Agent framework | LangGraph (from DESIGN.md) | confirmed | trivial |
| D2 | Track | ml (model fitting, not API calling) | confirmed | trivial |
| D3 | Human approval for external writes | — | asked-open | irreversible |
| D9 | Fold/model cap | 3-fold, exclude catboost | overridden → 5-fold, include all | costly |
```

## How it's used

- **Written by** `/proto-scope` at band 1 exit
- **Read by** the dispatcher at band 2 entry (Step 5 of the band contract)
- **Auditable**: the `reversibility` field makes the propose-vs-ask routing inspectable
  — a decision marked "silently defaulted" carries the claim that it was cheap to reverse,
  and a reviewer can dispute that claim
