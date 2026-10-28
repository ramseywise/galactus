# AI-Project-Template Pillar Gap Analysis

Status: COMPLETE
Date: 2026-07-29
Framework: learn-ai-engineering/.claude/docs/research/ai-eng-assessment-framework.md
Portfolio: guacamayo/.claude/docs/research/ai-eng-portfolio-assessment.md

---

## Purpose

Compare what AIT scaffolds against the 6-pillar assessment framework's Template Requirements table, cross-referenced with the portfolio assessment's universal gaps. The goal: identify what the template should add so that new projects start above the weaknesses found across the existing portfolio.

---

## Pillar 1: Prompt Engineering — 67% coverage

### Scaffolded

| Requirement | Tier | Evidence |
|-------------|------|----------|
| System prompt with role + constraints | Must | `agent.ts.jinja:15` — "You are a helpful assistant for {{ project_name }}" |
| Output format spec | Must | `core.md:86-142` — Pydantic `AssistantResponse` model |
| Template separation | Must | `core.md:326-370` — separate prompt files (answer.txt, clarify.txt, escalate.txt) |
| XML/structured instructions | Should | `framework-adk.md:48-50` — file-based prompt loading with structured sections |
| Prompt version tracking | Should | `core.md:22` — `PROMPT_VERSION = "{AGENT_NAME}-v1"` constant |

### Gaps

| Requirement | Tier | Impact | Portfolio evidence |
|-------------|------|--------|-------------------|
| **Few-shot example structure** | Must | No repo in portfolio has consistent few-shot patterns | All repos score 2 on prompt |
| **{{PLACEHOLDER}} pattern** | Must | Present but inconsistent (`{DOMAIN}`, `{AGENT_NAME}` — no standard) | — |
| **Prompt injection defense** | Nice | Regex detection in `framework-adk.md:59-65` but no structured template | 0/5 repos have injection defense |
| **Instruction hierarchy template** | Nice | No meta-prompt / base / context / task layering | — |

### Recommendation

- Add a `prompts/` directory scaffold with `system.md`, `examples.md`, `constraints.md` — one file per section, loaded at runtime. This enforces the few-shot + placeholder pattern by structure.
- Add a `PROMPT_VERSION` constant to the Vercel AI SDK scaffold (already in Python `core.md`, missing in TS `agent.ts.jinja`).
- Add an `untrusted-input-delimiter` pattern to the guardrails capability ref.

---

## Pillar 2: Context Engineering — 60% coverage

### Scaffolded

| Requirement | Tier | Evidence |
|-------------|------|----------|
| Retrieval tool integration point | Must | `core.md:250-277` — memory.py with append/get_history/clear |
| Static vs. dynamic context separation | Must | `core.md:281-322` — config.py shared observability + agent-specific vars |
| Progressive disclosure via skills | Should | `.agents/skills/` — add-on capabilities loaded on demand |
| LangSmith tracing (observability) | Should | `core.md:154-246` — observability.py with configure_runtime() |

### Gaps

| Requirement | Tier | Impact | Portfolio evidence |
|-------------|------|--------|-------------------|
| **Compaction trigger skeleton** | Should | No repo has compaction strategy | 0/5 repos manage token budgets |
| **Cache prefix optimization** | Should | No repo uses prompt caching | 0/5 repos optimize cache hits |
| **Token budget tracking** | Nice | No repo counts tokens | Universal gap across portfolio |
| **Context failure mode handling** | Nice | No scaffold for rot/poisoning/distraction diagnosis | — |

### Recommendation

- Add a `context-budget.ts` / `context_budget.py` skeleton that wraps model calls with token counting and logs per-category usage (system, history, tools, scratch). Even a logging-only version would surface the data needed to optimize.
- Add a `compaction-trigger` utility that summarizes conversation history when it exceeds a configurable threshold (e.g., 80% of model's context window). Pattern exists in `cap-compaction.md` reference but isn't wired into the scaffold.
- Add prompt caching annotations to the system prompt section (Anthropic-specific: mark stable sections as cache-eligible).

---

## Pillar 3: Harness Engineering — 67% coverage

### Scaffolded

| Requirement | Tier | Evidence |
|-------------|------|----------|
| CLAUDE.md with conventions | Must | `_scaffold/{{ ts_project_root }}/CLAUDE.md` |
| Tool definition with schema | Must | `tools/getTime.ts:9-24` — Zod schema with `tool()` |
| Error handling skeleton | Must | `eval/run.ts.jinja:105-107` — try/catch with error reporting |
| Settings pattern (env-driven) | Must | `settings.ts.jinja` — centralized settings object |
| Hook/middleware integration | Should | `.claude/hooks/README.md` — 13 enforcement hooks |
| Guardrail patterns | Should | `framework-adk.md:59-86` — injection + escalation regex detection |

### Gaps

| Requirement | Tier | Impact | Portfolio evidence |
|-------------|------|--------|-------------------|
| **Sandboxed execution** | Should | No scaffold for isolating tool execution | — |
| **Cost envelope management** | Nice | No budget/quota tracking per run | 0/5 repos track costs |
| **Five-component harness checklist** | Nice | No explicit checklist (context + tools + verification + cost + observability) | — |
| **Convergent-design primitives** | Nice | No filesystem/bash/sandbox/hooks/subagents primitives doc | — |

### Recommendation

- Add a `cost-envelope` utility that wraps API calls and tracks cumulative spend per run, with a configurable ceiling that triggers graceful termination. This is the #1 production risk gap.
- Add a `HARNESS_CHECKLIST.md` to the scaffold root — a 5-item checklist (context, tools, verification, cost, observability) that new projects can audit against. Lightweight, high signal.

---

## Pillar 4: Loop Engineering — 50% coverage (weakest)

### Scaffolded

| Requirement | Tier | Evidence |
|-------------|------|----------|
| Agent loop with iteration cap | Must | `agent.ts.jinja:24` — `stopWhen: stepCountIs(settings.maxSteps)` |
| Termination condition template | Must | `framework-lg.md:38-41` — State with max_cycles, cycle_count, terminate |
| Max cycles enforcement test | Must | `test.md:5-16` — smoke test for max_cycles_respected |

### Gaps

| Requirement | Tier | Impact | Portfolio evidence |
|-------------|------|--------|-------------------|
| **Verification loop wrapper** | Should | Only playground has partial maker/checker | 4/5 repos lack verification loops |
| **Maker/checker separation** | Should | Only atlas has planner/learner | Universal gap |
| **Durable state pattern** | Should | Checkpointer exists as optional skill, not default | — |
| **Event-driven triggers** | Nice | No cron/webhook scaffold | 0/5 repos have event-driven loops |
| **Stall detection** | Nice | No repeated-failure detection | — |
| **Hill-climbing trace analysis** | Nice | No trace→config feedback loop | — |

### Recommendation

- **Highest-impact gap in the template.** Add a `verification-loop` wrapper that:
  1. Runs the agent loop
  2. Passes the output to a grader (reuse eval grader interface)
  3. Feeds failures back as context for retry
  4. Caps retries independently of the inner loop cap
- Make the LangGraph checkpointer a default scaffold (not opt-in skill) — durable state is foundational for any loop beyond toy.
- Add a `stall-detection` utility that detects repeated identical tool calls or outputs and triggers escalation/termination.

---

## Pillar 5: Graph Engineering — 63% coverage

### Scaffolded

| Requirement | Tier | Evidence |
|-------------|------|----------|
| Multi-agent decomposition guidance | Must | `langgraph-scaffold/SKILL.md:20-35` — "What are the discrete steps?" |
| State schema template | Must | `framework-lg.md:8-42` — complete State TypedDict |
| Conditional routing pattern | Should | `framework-lg.md:50-95` — planner → {retrieve, clarify, escalate} |
| HITL interrupt pattern | Should | `langgraph-human-in-the-loop/SKILL.md:27-70` — interrupt/resume with Command |
| Checkpointer wiring | Should | `langgraph-persistence/SKILL.md:30-65` — Sqlite/Postgres setup |
| ADK callback architecture | Should | `framework-adk.md:16-19` — before/after agent/model callbacks |

### Gaps

| Requirement | Tier | Impact | Portfolio evidence |
|-------------|------|--------|-------------------|
| **Fan-out/fan-in template** | Should | No repo has parallel agent execution | 0/5 repos use fan-out |
| **Hierarchical subgraph composition** | Nice | Referenced but not scaffolded | 0/5 repos use subgraphs |
| **Knowledge-graph integration** | Nice | Not found | Only librarian has graph-like retrieval (backlinks) |

### Recommendation

- Add a `fan-out-fan-in` scaffold pattern using LangGraph's `Send` API — the most common multi-agent pattern missing across the portfolio. Include a synthesizer node that aggregates parallel results.
- The HITL and persistence skills are strong but opt-in; consider making persistence default (same recommendation as Loop pillar).

---

## Pillar 6: Evaluation Engineering — 76% coverage (strongest)

### Scaffolded

| Requirement | Tier | Evidence |
|-------------|------|----------|
| Unit test structure | Must | `agent.test.ts.jinja` — deterministic request/response tests |
| CI pipeline | Must | Makefile with 13+ eval/test targets |
| Pre-commit hooks | Must | `.claude/hooks/` — secrets_scan, code_quality, sdk_lint, test_coverage |
| Eval suite with task/trial/grader | Should | `eval.md:48-291` — EvalRunner with dataset loading, grading, aggregation |
| Grader interface contract | Should | `eval.md:176-223` — evaluate method with intent match, sources grounding |
| Golden dataset structure | Should | `eval/pipelines/run.py.jinja:38-49` — golden_qa.jsonl template |
| Heuristic grading | Should | BM25 + token overlap metrics (no LLM required) |
| RAGAS grader option | Should | Optional faithfulness/relevancy/context precision |
| Metric targets / gates | Should | `eval/targets.yaml.jinja` — hit_rate, MRR, answer_overlap thresholds |

### Gaps

| Requirement | Tier | Impact | Portfolio evidence |
|-------------|------|--------|-------------------|
| **Observability spans** | Nice | No structured tracing for eval runs | 0/5 repos have observability spans |
| **Drift monitoring** | Nice | DriftGrader mentioned in eval.md but not scaffolded | 0/5 repos monitor drift |
| **Gate ladder (multi-tier)** | Nice | `make eval-gate` exists but single tier | — |
| **Two-layer eval** | Nice | Unit/integration separated but no human-calibrated LLM evaluator | — |

### Recommendation

- Add OTel span instrumentation to the eval runner — each eval item gets a span with query, response, score, latency, and token count. This feeds both observability and drift monitoring.
- Add a `baseline-compare` mode to the eval runner that loads previous run results and flags regressions (score dropped >5% from baseline). Lightweight drift monitoring without online eval.

---

## Cross-Portfolio ↔ Template Gap Matrix

The portfolio assessment found 5 universal gaps. How does the template address each?

| Universal portfolio gap | Template scaffolds it? | Priority |
|------------------------|----------------------|----------|
| **No prompt versioning** | Partial — Python `core.md` has `PROMPT_VERSION`; TS scaffold does not | P1 — add to TS scaffold |
| **No observability spans** | Partial — LangSmith tracing for agents, no OTel spans | P1 — add OTel scaffold |
| **No token budget management** | No | P1 — add context-budget utility |
| **No prompt injection defense** | Minimal — regex only | P2 — add structured delimiter pattern |
| **No continuous eval** | No — point-in-time only | P2 — add baseline-compare mode |

---

## Prioritized Backlog

Issues to create for AIT, ranked by (portfolio impact × template effort):

| # | Item | Pillar | Tier | Effort | Impact |
|---|------|--------|------|--------|--------|
| 1 | **Verification loop wrapper scaffold** | Loop | Should | M | High — 4/5 repos lack this; template can set the pattern |
| 2 | **Token budget / context-budget utility** | Context | Nice | M | High — universal gap, template can enforce counting from day 1 |
| 3 | **OTel observability span scaffold** | Eval | Nice | M | High — 0/5 repos have spans; template wiring removes the activation energy |
| 4 | **Prompt versioning in TS scaffold** | Prompt | Should | S | Med — constant + convention, already in Python |
| 5 | **Baseline-compare eval mode** | Eval | Nice | M | Med — turns point-in-time evals into continuous regression detection |
| 6 | **Fan-out/fan-in graph template** | Graph | Should | M | Med — most common multi-agent pattern, no repo has it |
| 7 | **Make checkpointer default** | Loop+Graph | Should | S | Med — currently opt-in skill; should be wired by default |
| 8 | **Prompt injection delimiter pattern** | Prompt | Nice | S | Med — universal gap, low effort to add as convention |
| 9 | **Cost envelope wrapper** | Harness | Nice | M | Med — production risk mitigation |
| 10 | **Few-shot example directory** | Prompt | Must | S | Low — structural, but all repos skip few-shot anyway |

---

## Summary

| Pillar | Must | Should | Nice | Coverage | Portfolio priority |
|--------|------|--------|------|----------|-------------------|
| Prompt | 3/3 | 1/2 | 0/2 | 67% | P2 — versioning + injection |
| Context | 2/2 | 1/3 | 0/1 | 60% | P1 — token budgets |
| Harness | 4/4 | 2/3 | 0/2 | 67% | P2 — cost envelope |
| Loop | 3/3 | 0/3 | 0/3 | **50%** | **P1 — verification loop** |
| Graph | 5/5 | 0/2 | 0/1 | 63% | P2 — fan-out |
| Eval | 8/8 | 1/4 | 2/2 | **76%** | P2 — observability + drift |
| **Overall** | **25/25** | **5/17** | **2/11** | **65%** | |

**Key finding**: AIT hits 100% of Must-tier requirements — the foundation is solid. The gaps are in Should (29%) and Nice (18%) tiers, which map exactly to the intermediate→advanced maturity jump the portfolio needs. The top 3 additions (verification loop, token budget, OTel spans) would address the three most common portfolio weaknesses and move new projects from "developing" to "mature" at scaffold time.
