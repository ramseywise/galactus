# Handoff: templates removed from learn-ai-engineering

On 2026-10-31 the `templates/` folders in `learn-ai-engineering/ai-engineering/<pillar>/` were
deleted. The course notes now carry the essential parts inline. The files below are candidates for
this repo's Copier template. All of them are still in learn-ai-engineering history at commit
`e837ad89^`, on main. (`6ee939f` is on no branch and can be pruned.) To recover one:

```bash
git -C ~/workspace/learn-ai-engineering show e837ad89^:<path> > <dest>
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

## Ported 2026-11-04

Homes above were checked against the repo. `new-agent` no longer ships in the template, and no loop or eval skill exists, so nothing here reaches rendered projects.

- **Ported to `.claude/skills/new-agent/references/`:** `harness/` (`init.sh`, `feature_list.json`, `feature_list.schema.json`, `progress.md`, `session-handoff.md`), `loop/` (`maker-prompt.md`, `checker-prompt.md`, `loop-contract.md`, `loop-state.md`) and `generate-then-verify.py`. Notices are in `references/THIRD_PARTY.md`. Maker and checker went in as references, not `.claude/agents/`, so they are not offered as subagents.
- **Dropped:** `control_loop.py` and `scoring_functions.py`: 3,389 lines copied from davidkimai/Context-Engineering, not a small lab.
- **Held, no home:** `judge-prompt.md`, `failure-taxonomy.md`, `judge-calibration.md`, `gate-contract.md`, `evalset.schema.json`. No eval skill exists to hold them.
- **Maybe rows:** not ported. `prompts/*.md`: skip, generic. `AGENTS.md`: skip, overlaps `CLAUDE.md.jinja`. `clean-state-checklist.md`: fold into `session-handoff.md` if wanted. `evaluator-rubric.md`: revisit with the eval templates. `ralph.sh`: skip, overlaps stop hooks. `fan-out-merge.py`: revisit if a fan-out agent needs it. `graph-update.schema.json`: skip until a shared KG exists. `eval.yml`: revisit with the eval templates.
