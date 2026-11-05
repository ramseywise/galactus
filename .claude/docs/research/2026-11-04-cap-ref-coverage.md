# Cap ref vs course example coverage map (2026-11-04)

**Examples actually run: 12** (cheap, offline, in scratch copies outside the repo; `uv run --offline` from cache). Everything else is marked "not run". Nothing was marked tested from its name.

Run list: context-budgeter-py `test.py`; tool-server-sandbox-py `test.py`; tool-server-sandbox (TS) `test.ts`; `tool_agent.py`; `injection_replay.py`; langgraph-graph `test.py`; note 05-04 interrupt block; `demo_07_lcel.py`; `demo_02_agentic.py` (completed with output; exit code not captured); observability `check_blocks.py 01-tracing` (11 blocks ok); note 09 PEFT block 1; note 05-RL/02 Bradley-Terry block 4.

Paths are under `~/workspace/learn-ai-engineering/`. Licence: no LICENSE file at the repo root and `THIRD_PARTY.md` does not list own-authored labs, so every lab below is "authored in this repo, licence not stated". Exceptions are named.

**Galactus side:** no test covers any ref template text. `runs/ai/marketing-comms/` holds adapted copies (observability, guardrails) with `tests/test_obs.py`; those test the copy, not the ref (not run). `template/_scaffold/.../observability/tracing.ts.jinja` is a TS tracing implementation (not run).

**Section classification, common to all 18 refs:** "Agnostic contract" + runtime table = CONTRACT. Spec/security/bug notes and "Design notes" = GUIDANCE. Each `## File:` block = TEMPLATE, untested by any test. Only deviations are listed per ref.

## Per-ref tables

### cap-compaction
| Item | Finding |
|---|---|
| Sections | CONTRACT; GUIDANCE (design notes); TEMPLATE `compaction.py` (summarise_history, LangGraph node, helpers), untested |
| Notes | `ai-engineering/02-context-engineering/notes/05-compression-compaction.md` (read; prose, no runnable compaction code) |
| Smallest example | `ai-engineering/02-context-engineering/practice/context-budgeter-py/` (Python; TS twin `context-budgeter/` has test.ts, not run). Check: test.py. Offline, stdlib. RAN, passed. Own, licence not stated |
| Move up when | the history no longer fits after eviction and you need an LLM summary of the dropped turns, or the LangGraph node wiring |
| Gaps | No LLM summarisation, no LangGraph node. Partial match only |

### cap-mcp
| Item | Finding |
|---|---|
| Sections | CONTRACT (runtime table); GUIDANCE; TEMPLATE `mcp_server.py` (FastMCP), `mcp_client.py`, untested |
| Notes | `ai-engineering/03-harness-engineering/notes/03-tool-design.md`, `04-execution-boundaries.md` (headings only), `02-context-engineering/notes/09-protocols.md` (not read) |
| Smallest example | `ai-engineering/03-harness-engineering/practice/tool-server-sandbox-py/` and `tool-server-sandbox/` (TS). Hand-rolled JSON-RPC stdio server, path jail, allowlist, approval gate, audit. Check: test.py / test.ts. Offline. RAN both, passed (Python needs the sibling dir layout). Own, licence not stated |
| Move up when | you need the official SDK or FastMCP transport, a client, or interop with a host you do not control |
| Gaps | No FastMCP or official SDK use, no client. Tested in both languages |

### cap-genai
| Item | Finding |
|---|---|
| Sections | CONTRACT; TEMPLATE `tool_registry.py`, `shared_tools.py`, untested |
| Notes | `generative-ai/03-agentic-foundations/notes/02-tool-use-and-react.md` |
| Smallest example | `generative-ai/03-agentic-foundations/practice/tool_agent.py` (Python). Registry with schemas, `check_args`, `dispatch`, parallel calls, 8 failure scenarios. No assertions (prints a table). Offline, stdlib. RAN. Own, licence not stated |
| Move up when | tools are shared across agents and need a schema builder and a common registry, not one agent's inline dispatch |
| Gaps | TS: only `generative-ai/01-llm-fundamentals/practice/01-typescript-sdk/03-function-calling.ts` (needs API key, no test, not run); `tool-server-sandbox` TS is the tested option. Python example has no assertions |

### cap-guardrails
| Item | Finding |
|---|---|
| Sections | CONTRACT; GUIDANCE; TEMPLATE `guardrails.py` (5 layers), untested |
| Notes | `ai-engineering/09-safety-and-security/notes/02-prompt-injection-and-jailbreaks.md`, `03-guardrail-models.md` (headings only), `generative-ai/03-agentic-foundations/notes/07-guardrails-and-autonomy.md` (not read) |
| Smallest example | `ai-engineering/09-safety-and-security/practice/injection_replay.py`. Input filter, egress allowlist, provenance policy, attack/utility rates. Offline, stdlib, no assertions. RAN. Own, licence not stated |
| Move up when | you need routing, grounding and escalation layers, not just input and egress filtering |
| Gaps | Covers roughly layers 1 and 4 only. No tested checker. Python only |

### cap-hitl
| Item | Finding |
|---|---|
| Sections | CONTRACT; TEMPLATE `interrupt.py` (about 90% LangGraph-specific), untested |
| Notes | `ai-engineering/05-graph-engineering/notes/04-durable-execution-and-interrupts.md` |
| Smallest example | The inline block at lines 100-149 of that note (about 40 lines): interrupt, MemorySaver, `Command(resume=)`, thread_id, fork. No test file; output matched the note's printed output. RAN. Larger: `practice/langgraph-graph/` test.py RAN, passed; `langgraph-graph-ts/` test.ts not run (needs npm install). Own, licence not stated |
| Move up when | you need env-gated approval, a resume handler for an HTTP endpoint, or a non-LangGraph runtime |
| Gaps | LangGraph only. ADK, Managed Agents, Vercel AI SDK not covered. TS test not run |

### cap-observability
| Item | Finding |
|---|---|
| Sections | CONTRACT; GUIDANCE (OTel semconv v0.4.x); TEMPLATE `observability.py` (`AgentSpan`, exporter, structlog), untested |
| Notes | `generative-ai/06-observability/notes/01-tracing` (note 01), `06-cost-and-latency-dashboards.md` |
| Smallest example | Note 01 block at lines 153-184: one span per generation with token and cache buckets. Checker: `generative-ai/06-observability/practice/check_blocks.py` (RAN, 11 blocks ok). Offline with a local fake. Own, licence not stated |
| Move up when | you need the GenAI semconv attributes, a real OTLP exporter or structured logs rather than Langfuse-on-OTel |
| Gaps | No `AgentSpan`, no semconv, no structlog. Python only |

### cap-langchain
| Item | Finding |
|---|---|
| Sections | CONTRACT ("none" plus LCEL equivalents table); GUIDANCE (deprecation); TEMPLATE `chains/*.py`, untested |
| Notes | `generative-ai/04-agentic-frameworks/notes/07-lcel-composition-in-practice.md`; `generative-ai/01-llm-fundamentals/notes/11-langchain-basics.md` (not read) |
| Smallest example | `generative-ai/04-agentic-frameworks/practice/01-research-agent/demo_07_lcel.py`. Chains, parsers, capped batches, structured output, map-reduce. Offline stub model. No assertions (note shows output). RAN. Own, licence not stated |
| Move up when | you must wrap an existing legacy chain interface rather than write LCEL directly |
| Gaps | Python only |

### cap-streaming
| Item | Finding |
|---|---|
| Sections | CONTRACT; TEMPLATE `app.py` (FastAPI SSE, sync endpoint, handlers), untested |
| Notes | `generative-ai/04-agentic-frameworks/notes/02-agentic-search-persistence-streaming.md` (L4 streaming section) |
| Smallest example | `.../01-research-agent/demo_02_agentic.py`: LangGraph stream modes (updates, messages). Offline. No assertions. RAN (completed, exit code not captured). Own, licence not stated |
| Move up when | the stream has to cross an HTTP boundary with SSE framing and error handling |
| Gaps | No SSE or FastAPI transport anywhere. Python only. Weak match |

### cap-finetune
| Item | Finding |
|---|---|
| Sections | CONTRACT; GUIDANCE (bf16 bug note); TEMPLATE `finetune/dataset.py`, `trainer.py`, untested |
| Notes | `generative-ai/01-llm-fundamentals/notes/09-peft-and-fine-tuning-in-practice.md`; `07-sft-and-instruction-tuning.md` (not read); `ai-engineering/08-multimodal-engineering/notes/02b-...` (not read in full) |
| Smallest example | Note 09 block 1: `LoraConfig` + `get_peft_model` on a tiny random Llama. Offline, no download. Prints trainable params 65,536 / 3,201,280 (2.0472%), matching the note. RAN. Own, licence not stated |
| Move up when | you have a real dataset to convert, split and train, and need eval and publishing around the adapter |
| Gaps | Dataset conversion, Trainer, eval not covered. `vlm_finetune_lab.py` is the full pipeline but needs a ~0.5 GB download and minutes to hours (not run) |

### cap-rlhf
| Item | Finding |
|---|---|
| Sections | CONTRACT; GUIDANCE (UNVERIFIED TRL PPO note); TEMPLATE `preference_collector.py`, `reward_trainer.py`, `ppo_trainer.py`, untested |
| Notes | `generative-ai/05-RL/notes/02-rlhf-pipeline.md`, `03-preference-optimization.md` |
| Smallest example | Note 02 block 4: Bradley-Terry reward model from 2000 pairs (numpy, ~20 lines). Printed "learned: [ 1.54 0.65 -0.52 -1.67]" and "0.71, true 0.73", matching the note. RAN. Own, licence not stated |
| Move up when | you collect real annotator preferences and train with TRL on a GPU |
| Gaps | No PreferenceCollector, no TRL reward or PPO example that runs (DPO block is illustrative, GPU). Q-learning lab (Apache-2.0, adapted from bojieli) rejected as not preference learning |

### cap-rag
| Item | Finding |
|---|---|
| Sections | CONTRACT; TEMPLATE `retrieval.py` (types, Bedrock KB, grading, rewriting, CRAG loop), `chunking.py`, untested |
| Notes | `generative-ai/02-rag-retrieval/notes/01`, `05` (chunking), `07`, `08`, `11`, `12` |
| Smallest example | `generative-ai/02-rag-retrieval/practice/ragkit.py`: BM25, toy embeddings, RRF, hybrid Retriever, recall/MRR/NDCG. Offline, numpy. Checker: `check_blocks.py` over the notes. NOT RUN. Own, licence not stated |
| Move up when | you need grade-and-rewrite (CRAG) or a managed knowledge base behind a Retriever protocol |
| Gaps | No runnable CRAG loop, no Bedrock. Python only. Not run, so unverified |

### cap-forecast
| Item | Finding |
|---|---|
| Sections | CONTRACT; GUIDANCE (interval clamping, naive guard); TEMPLATE `features.py` (features, SHAP), `pipeline.py`, untested |
| Notes | `data-science/05-time-series-and-recommenders/notes/01-time-series-ml.md`, `data-analytics/06-applied-analyses/notes/01-forecasting.md` (blocks counted, not run) |
| Smallest example | Candidate: `data-analytics/06-applied-analyses/practice/ch01_forecasting.py` (seeded synthetic data, statsmodels + Prophet, about a minute). Alternative `data-science/05-.../practice/customer-segments-lab/forecast.py` (synthetic; walk-forward, MASE; pinned deps, ~70 s lab). `01_forecast_lab.py` downloads UCI data, so not offline. None checked by a test. NOT RUN. Own, licence not stated (bike data is UCI) |
| Move up when | you need SHAP features and an interval-clamped pipeline instead of a baseline backtest |
| Gaps | Examples were read at header level only. No tested minimal forecast. Python only |

### cap-cluster
| Item | Finding |
|---|---|
| Sections | CONTRACT; GUIDANCE (all-noise HDBSCAN fallback, UMAP, dedupe); TEMPLATE `embeddings.py` (Bedrock Titan, UMAP), `cluster.py` (clustering, LLM labelling), untested |
| Notes | `data-science/01-classical-ml/notes/05-unsupervised-learning.md` (KMeans block at line 148), `05b-clustering-categorical-and-mixed-data.md` |
| Smallest example | `data-science/05-time-series-and-recommenders/practice/customer-segments-lab/segments.py` (k-means, HDBSCAN, atlas fallback rule, stability; synthetic; numpy pandas scikit-learn) |
| | `data-science/01-classical-ml/practice/mixed_clustering.py` is heavier (prince, kmodes, catboost). Neither has a test. NOT RUN. Own, licence not stated |
| Move up when | you must cluster text embeddings and label clusters with an LLM |
| Gaps | No LLM labelling, no embedding step, no Bedrock. HDBSCAN fallback appears in the lab (matches the ref note) but was not run |

### cap-batch
| Item | Finding |
|---|---|
| Sections | CONTRACT; GUIDANCE (Message Batches snippet); TEMPLATE `batch_runner.py` (semaphore, append-per-item, resume), untested |
| Notes | none that cover concurrency with resume |
| Smallest example | Partial only: `demo_07_lcel.py` capped batches (`max_concurrency` 1/2/6, input order kept). RAN. Eval harnesses (`generative-ai/08-eval/practice/eval-suite-ci*`, `ai-engineering/01-prompt-engineering/practice/prompt-eval-harness*`) write results jsonl but have no concurrency, isolation or resume |
| Move up when | n/a: no example |
| Gaps | GAP: no failure isolation, no resume, no Message Batches API example. `multi-tenant-agents` (uncommitted, another session) uses asyncio workers; not used |

### cap-kg
| Item | Finding |
|---|---|
| Sections | CONTRACT; GUIDANCE (Cypher injection, Neptune, score bug notes); TEMPLATE `kg_client.py`, `graph_schema.py` (`safe_identifier`, models), untested |
| Notes | `ai-engineering/05-graph-engineering/notes/09`, `10`, `10b`, `11`, `11b`, `12` |
| Smallest example | None runnable offline. Closest: `11-kg-rag-and-text-to-cypher.md` `Literal` whitelist block (same idea as `safe_identifier`, needs a live graph object); `10b` networkx metrics block (not run) |
| Move up when | n/a |
| Gaps | GAP: no graph-store example, no Neptune, no injection test |

### cap-a2a
| Item | Finding |
|---|---|
| Sections | CONTRACT; GUIDANCE (security-fix note); TEMPLATE `a2a_client.py`, `a2a_router.py`, untested |
| Notes | prose only: `generative-ai/03-agentic-foundations/notes/05-framework-survey.md` (protocols section), `06-google-adk-intensive.md`, `04-multi-agent-design-patterns.md`, `ai-engineering/05-graph-engineering/notes/05-topology-patterns.md` |
| Smallest example | None. A grep for agent card / A2A across code in generative-ai and ai-engineering found no `.py` or `.ts` hits |
| Move up when | n/a |
| Gaps | GAP: no code at all |

### cap-search
| Item | Finding |
|---|---|
| Sections | CONTRACT; TEMPLATE `search_tool.py` (Serper/Tavily, rate limit), untested |
| Notes | `generative-ai/04-agentic-frameworks/notes/02-agentic-search-persistence-streaming.md` (Tavily block, illustrative, needs `TAVILY_API_KEY`); `generative-ai/07-agentic-applications/notes/01-internet-search-agent.md` (legacy upstream, Bing retired; not read) |
| Smallest example | None offline or tested. Tavily block is marked illustrative. `deep_research_bench` is vendored and has its own LICENSE (type not checked) |
| Move up when | n/a |
| Gaps | GAP: no tested example, no Serper, no rate limiting |

### cap-vision
| Item | Finding |
|---|---|
| Sections | CONTRACT; GUIDANCE (stale-constant note); TEMPLATE `vision.py` (Pydantic, base64, message formatter, Pillow resize), untested |
| Notes | `ai-engineering/08-multimodal-engineering/notes/01-image-input.md` (token math, Pillow downscale, box validation) |
| Smallest example | Note 01 blocks only (offline, no checker file found, not run) |
| Move up when | n/a |
| Gaps | GAP or weak: no base64 or MIME-typed message part, no size validation. `invoice_pipeline.py` is OCR and heavy (not run) |

## Ranking by gain from a top-of-ref example

Ranked by the size of what the existing example already shows, plus how likely an agent is to over-build without it.

1. **cap-hitl** - tested LangGraph example exists and the ref is about 90% LangGraph; the minimum is about 40 lines against a long template.
2. **cap-genai** - `tool_agent.py` shows the whole registry/dispatch/failure loop in one stdlib file; agents easily over-build registries.
3. **cap-mcp** - tested in Python and TS; the ref's FastMCP template is much larger than what a first tool needs.
4. **cap-guardrails** - 5-layer template invites building all layers; example shows what two layers buy.
5. **cap-observability** - checked block shows a span with token and cache accounting; the AgentSpan/OTel/structlog stack is much larger.
6. **cap-langchain** - runs offline, and a runnable LCEL version shows the chains/ package is mostly unneeded.
7. **cap-compaction** - tested, but covers only eviction.
8. **cap-finetune, cap-rlhf** - small runnable fragments (LoRA config, Bradley-Terry) of much larger pipelines.
9. **cap-rag** - good retrieval example but not run, and the CRAG loop is uncovered.
10. **cap-forecast, cap-cluster** - examples exist but were not run and have no test.
11. **cap-streaming** - weak match (no SSE).
12. **None available:** cap-batch, cap-kg, cap-a2a, cap-search, cap-vision.

## Gap list

- **No example:** cap-a2a (no code), cap-search (illustrative only), cap-kg (needs a live graph store; no Neptune), cap-batch (no concurrency, isolation, resume or Batches API), cap-vision (no base64/MIME message).
- **Partial:** cap-compaction (no summarisation), cap-streaming (no SSE), cap-finetune (no dataset/Trainer), cap-rlhf (no collector, no TRL), cap-rag (no CRAG, no Bedrock), cap-observability (no AgentSpan/semconv/structlog), cap-guardrails (about 2 of 5 layers), cap-mcp (no FastMCP/official SDK, no client).
- **Python only:** genai (TS example needs a key and has no test), guardrails, observability, langchain, streaming, rag, finetune, rlhf, forecast, cluster. **TS example exists but not run:** hitl, compaction. **Tested in both:** mcp.
- **No tests in Galactus** for any ref template text.

## Could not be determined

- Whether `ragkit.py` and the RAG `check_blocks.py` pass (not run).
- Whether forecast and cluster examples run and what they print (not run; header level only; forecast needs a ~1 minute run with Prophet, the lab ~70 s).
- TS twins `langgraph-graph-ts`, `context-budgeter` (not run).
- Licence of vendored `deep_research_bench`, `deep-research-bot`, `nn-zero-to-hero` (types not checked). Own labs have no stated licence, so reuse terms for own code are not documented.
- Exit code of `demo_02_agentic.py`.
- Notes marked "not read" above were identified but not read.
