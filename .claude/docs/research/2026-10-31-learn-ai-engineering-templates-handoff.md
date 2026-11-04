# Handoff: templates removed from learn-ai-engineering

On 2026-10-31 the `templates/` folders in `learn-ai-engineering/ai-engineering/<pillar>/` were
deleted. The course notes now carry the essential parts inline. The files below are candidates for
this repo's Copier template. All of them are still in learn-ai-engineering history at commit
`6ee939f`. To recover one:

```bash
git -C ~/workspace/learn-ai-engineering show 6ee939f:<path> > <dest>
```

**Port?** means: **yes** = worth adding; **maybe** = overlaps something already here, so check first; **no** = left out on purpose.
The suggested destinations are relative to `template/`.

## 02 Context engineering (`ai-engineering/02-context-engineering/templates/`)

| File | What it is | Port? | Suggested home |
|---|---|---|---|
| `control_loop.py` | ContextManager plus evaluators: a context-assembly loop with scoring | yes (as a small lab or example) | `llm_kit/` example or `_scaffold/` |
| `scoring_functions.py` | context-quality scoring helpers used by the control loop | yes, together with `control_loop.py` | same |
| `prompts/*.md` (chain_of_thought, expert_guides, few_shot_learning, minimal_context, verification_loop) | prompt templates | maybe | `.claude/skills/` reference |
| `prompt_program_template.py`, `minimal_context.yaml`, `schema_template.{json,yaml}` | generic scaffolds | no (low value) | — |

## 03 Harness engineering (`ai-engineering/03-harness-engineering/templates/`)

| File | What it is | Port? | Suggested home |
|---|---|---|---|
| `init.sh` | 29-line startup-and-verify script | yes | a harness skill's `references/` (for example under `new-agent`) |
| `feature_list.json` + `feature_list.schema.json` | feature list (behaviour, verification, state) and its draft-07 schema | yes | same skill |
| `progress.md` | progress log: current state on top, append-only log below | yes | same skill |
| `session-handoff.md` | session handoff: verified / changed / broken / next / commands | yes | same skill |
| `AGENTS.md` | 69-line root file for a long-running coding agent | maybe (overlaps `CLAUDE.md.jinja`) | skill reference |
| `clean-state-checklist.md` | 8-line clean-state checklist | maybe | fold into `session-handoff.md` |
| `evaluator-rubric.md` | rubric: 6 categories, each scored 0–2 | maybe | reviewer agent or eval docs |
| `quality-document.md` | quality grades per area | no | — |
| `openai-repo-template/**` | OpenAI repo-docs scaffold (AGENTS, ARCHITECTURE, docs/*) | no | — |

## 04 Loop engineering (`ai-engineering/04-loop-engineering/templates/`)

| File | What it is | Port? | Suggested home |
|---|---|---|---|
| `checker-prompt.md` | strict checker sub-agent prompt (PASS / FAIL / PASS WITH NOTES) | yes | `.claude/agents/checker.md` |
| `maker-prompt.md` | maker prompt: one change per pass, write scope, handoff format | yes | `.claude/agents/maker.md` |
| `loop-contract.md` | loop contract: goal, scorekeeper, write scope, exits, caps, escalation | yes | a loop skill's reference |
| `loop-state.md` | five-field loop memory file, run stats and an archive section | yes | same |
| `ralph.sh` | bash Ralph loop with a ratchet, caps and stall detection | maybe (overlaps stop hooks) | `.claude/scripts/` |

## 05 Graph engineering (`ai-engineering/05-graph-engineering/templates/`)

| File | What it is | Port? | Suggested home |
|---|---|---|---|
| `generate-then-verify.py` | runnable LangGraph generate → validate → review graph (attempt bound, feedback reducer, InMemorySaver) | yes | `new-agent` skill LangGraph reference |
| `fan-out-merge.py` | `Send` fan-out with a MAX_FANOUT cap and a reducer merge | maybe | same |
| `graph-update.schema.json` | JSON Schema for agent writes to a shared KG (provenance, confidence, run and agent ids) | maybe | schemas reference |

## 06 Eval (`ai-engineering/06-eval/templates/`)

| File | What it is | Port? | Suggested home |
|---|---|---|---|
| `judge-prompt.md` | single-criterion judge prompt (PASS / FAIL / CANNOT_GRADE), few-shot slots, critique before verdict | yes | an eval skill, or `docs/evals/` in generated projects |
| `failure-taxonomy.md` | failure labels ordered by stage, priority = count × cost, change log | yes | same |
| `judge-calibration.md` | calibration worksheet: splits, confusion matrix, TPR/TNR/κ, sign-off | yes | same |
| `gate-contract.md` | per-gate contract: pool, graders, fail rules, budget | yes | same, or `evals/gates.yaml` |
| `evalset.schema.json` | JSON Schema for one eval row | yes | `evals/schema/` |
| `eval.yml` | GitHub Actions workflow: smoke, regression and nightly evals | maybe | `.github/workflows/` |

01 Prompt engineering had no templates.
