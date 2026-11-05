# runbook-search
Date: 2026-11-04
Status: RESEARCHED
Track: agent

Track reasoning: the system calls embedding, reranking and LLM models and fits none. Tuning one abstain threshold on labeled queries is calibration, not model fitting. If a later design trains a ranker on click logs, re-route that work to `ml`.

## Research

### Summary
Use hybrid retrieval with a deterministic identifier lookup in front of it, and put evidence gates around the LLM: `identifier lookup + BM25 + dense → fuse → rerank → gate → generate from whole sections → verify steps against source`. At this scale, cost and index performance do not decide anything (about $20 a month, about 10,000 chunks). The design has to be judged on two things: whether "nothing found" stays true, and whether an invented step can reach the screen. The template's `rag_agent` fails both as shipped, and its default full-text index cannot find `E4021` at all. I tested that directly.

### Scope
**Investigated:** retrieval shape for mixed exact-code and plain-language queries; abstention; citation and step verification; freshness under 50 changes a day; sizing and cost; the snapshot's specs and template assets.

**Out of scope:** implementation, UI, deployment and the plan. The real wiki and real query logs were not available, so nothing here has been measured on your corpus.

**Evidence tiers used below:**
- *Measured here:* in-memory tests on synthetic pages, described in F3 and F4.
- *Read:* primary pages I opened. For the arXiv papers that means the abstract only.
- *Search summary:* seen only through search results. Named as such wherever it is used.

Vendor-blog recall figures that turned up in search (for example 91% vs 78% recall@10) are deliberately not used.

Template paths: `$P` = `template/_scaffold/{{ py_project_root }}`; `$A` = `$P/{{ ai_source_root }}/agents`.

### Findings

**F1. The numbers rule out some designs and leave the choice of store open. Confidence: High for the arithmetic, Medium for the costs, which rest on the assumed sizes.**

| Quantity | Arithmetic | What the planner does with it |
|---|---|---|
| Mean page | 4M / 6,000 ≈ 667 tokens | Smaller than a typical 800-token chunk, so most pages may need no split. The mean hides the tail: get the distribution first |
| Prompt-stuffing | 4M is 20× Anthropic's 200k "skip RAG" line and 4× a 1M window | Retrieval is required |
| Chunks | About 10k at about 400 tokens each | Exact vector scan is plausible; an ANN index is not needed for scale |
| Churn | 50/6,000 ≈ 0.8% a day, about 33k tokens at mean size | Re-embedding costs about $0.002 a day. Freshness and deletes drive index updates, not cost |
| Traffic | 200/week ≈ one every 50 minutes on average; real traffic arrives in incident bursts | No throughput problem. Production data accumulates slowly (F9) |
| Full embed | 4M × $0.06/MTok (`voyage-4`) = $0.24 | Rebuilding is cheap, so changing the embedding model is cheap too |
| Rerank | About 21k tokens per query (50 × 400 + 50 × 20 for the query) × $0.05/MTok ≈ $0.001 | About $1 a month |
| Generation | 4k in, 300 out: Haiku 5.5 $0.0006, Sonnet 5.5 $0.011, Opus 5.5 $0.022 | At about 870 queries a month: $0.50, $10 or $19. Choose the model on error rate, not price |

Sources: [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing), [Voyage pricing](https://docs.voyageai.com/docs/pricing), both read 2026-11-04. Rerank token formula from [Voyage reranker docs](https://docs.voyageai.com/docs/reranker). The 50-candidate, 400-token and 4k/300 sizes are my assumptions. Free-token allowances would cover most embedding and rerank cost but are not counted.

**F2. The pipeline shape, as the evidence supports it. Confidence: Medium.** The overall shape is well supported; no stage has been measured on your corpus.

| Stage | Shape | Why |
|---|---|---|
| Parse | Keep heading path and code fences verbatim. Carry page ID, URL, last-modified, owner and page type | Steps live in lists and fences; F5 and F7 depend on this metadata |
| Chunk | Keep short pages whole; split long ones on headings | F1. Anthropic notes that boundaries and overlap affect results |
| Identifier table | Extract code-shaped tokens per page into an exact map, normalizing `E4021`, `e4021` and `E-4021` | F3 and F4 |
| Lexical | BM25 with an analyzer proven to keep digits | F3 |
| Dense | Embeddings for plain-language queries | Vocabulary mismatch is what BM25 cannot cover. Unmeasured here; see Disconfirming Evidence |
| Fuse | RRF, which uses ranks and so avoids mixing score scales. k=60 is the [conventional](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf) constant (paper title and metadata seen via search, not read in full) | No labeled data exists yet to justify tuned weights |
| Rerank | Retrieve wide, keep narrow | Anthropic: 150 → 20; `agent-context.md:74`. The reduction is measured for recall only (F6) |
| Evidence gate | Abstain before any generation | F4 and F5 |
| Expand | Send the whole section or page, not the matching fragment | A fragment can drop the precondition or rollback around a step. This is my reasoning, not a measured result |
| Generate | Short answer, citations required, steps quoted | F5 |
| Verify | Deterministic check that each command and step appears in a cited page | F5 |
| Return | Typed outcome (F5), with ranked links available even if generation fails | F8 |

**F3. Analyzer defaults can silently turn a real page into "not found". Confidence: High for the DuckDB behaviour (measured on duckdb 2.0.0), Medium for other engines.** The template's call at `$P/core/pipelines/corpus/index.py:45` uses DuckDB FTS defaults, which drop digits.

| Query against a small test corpus | DuckDB defaults | SQLite FTS5 defaults |
|---|---|---|
| `E4021`, page contains it | No results | Correct page |
| `E9999`, in no page | Not tested | No results |
| `ERR_CONN_4290`, page contains it | Match, on `err` and `conn` only | Correct page |
| `ERR_CONN_1111`, **in no page** | **Returns the 4290 page** | No results (quoted phrase query) |
| `E-4021`, page has `E-4021` | Not tested | Matches that page only; `E4021` does not match it |

Both DuckDB failures are dangerous here. The first makes a true "found" read as "nothing found". The second returns the wrong runbook with a positive score. Changing the `ignore` pattern to keep digits and underscores fixed `E4021`, `E4099` and `ERR_CONN_4290` in the same test.

For Postgres, the [default parser documents](https://www.postgresql.org/docs/current/textsearch-parsers.html) `numword` for letter-digit strings such as `beta1`. The page does not cover underscores, so that case needs testing. **The planner needs an analyzer test on real code shapes as an early gate, whichever store is chosen.**

**F4. Identifier presence is decidable, so the model and score thresholds should not be the ones to decide it. Confidence: High on the principle, Medium on the measurements (synthetic).** `agent-uncertainty.md:147` says deterministic checks win whenever they can answer the question.

The test used 400 templated synthetic pages, each with one unique code, queried by the bare code. Absent codes were codes in no page. Models: `all-MiniLM-L6-v2` (the template default, 60 present and 60 absent queries) and `ms-marco-MiniLM-L-6-v2` (25 each), reranking all 400 pages.

| Model | Correct page rank | Best score, code present (p5 / p50 / p95) | Best score, code absent (p5 / p50 / p95) |
|---|---|---|---|
| Dense MiniLM | Top-1 23%, top-5 43%, top-20 67% | 0.27 / 0.33 / 0.40 | 0.26 / 0.31 / 0.38 |
| Cross-encoder | Top-1 100% | 5.78 / 6.68 / 7.42 | 0.79 / 3.41 / 6.25 |

- Dense scores barely separate a real code from a nonexistent one. At least 95% of absent-code queries score above the template's `confidence_threshold` of 0.25 (`$A/rag_agent/settings.py.jinja:36`).
- The cross-encoder ranks codes well, but its score ranges overlap at the tails, so a threshold would still leak some absent codes.
- An exact map gives a true answer to "does any page contain this code?" Absence must become a `not_found` outcome. Near-matches may be listed as links labeled "not a code match", never used as the basis for steps.
- Presence alone is not sufficient. A code may appear only in a changelog or a postmortem, so the evidence gate still applies.
- This fits the published pattern: dense retrievers [do much worse than sparse methods on entity-rich questions](https://arxiv.org/abs/2109.08535) (EMNLP 2021, abstract only), and [Anthropic](https://www.anthropic.com/news/contextual-retrieval) gives the same reasoning with "Error code TS-999".

**F5. "Say when you found nothing" needs structure at four points, because a prompt instruction alone does not hold. Confidence: High on the need, Medium on the mix.**

Large models given insufficient context ["often output incorrect answers instead of abstaining"](https://arxiv.org/abs/2411.06037) (Joren et al., ICLR 2025, abstract). Selective generation using sufficiency signals raised correct answers among responses by 2-10%. Search summaries also report 35-62% correct answers on insufficient context, which implies models answer from their own knowledge; that is the behaviour to fear here. Commercial legal RAG tools were measured [hallucinating 17-33% of the time](https://arxiv.org/abs/2405.20362) despite vendor claims (2024, a different domain, abstract only). Retrieval does not remove the problem.

| Point | Check | Type | Catches |
|---|---|---|---|
| Before retrieval | Identifier absent from table | Code | Code in no page |
| Before generation | Rerank threshold plus lexical signal, calibrated on hard negatives | Code, calibrated | Weak or off-topic evidence (`agent-safety.md:20`) |
| Before generation | Does this passage actually answer the question? | LLM, optional | Relevant page that lacks the answer |
| After generation | Every command, flag, hostname and step is present in a cited page; every link is in the index | Code | Invented or altered steps (`agent-safety.md:21`) |

Facts the planner needs:
- **No vendor threshold exists to copy.** [Voyage's docs](https://docs.voyageai.com/docs/reranker) give no calibration or cutoff guidance. Practitioner sources found by search agree that thresholds must be calibrated per deployed model and redone on change.
- **Native citations do not prove support.** [Claude citations](https://platform.claude.com/docs/en/build-with-claude/citations) guarantee valid pointers to supplied documents. That is not the same as the claim being supported, and the docs tell you to check for missing citations in their field-parsing example. They also return a 400 if combined with structured outputs, so the typed outcome has to come from the harness, not from a JSON response format.
- **Spec tension, unresolved.** `agent-safety.md:43` quotes "Do NOT use LLM-as-judge for runtime grounding", while the sufficiency research uses an LLM rater. The verbatim step check satisfies the rule. An LLM sufficiency gate before generation arguably does not breach it, but it is a judgement call the planner should make explicitly. `agent-safety.md:31` also flags that gate latency conflicts with its own <5ms rule.
- **Outcomes must be typed, with four states** (`agent-uncertainty.md:72-79`): `answer`, `links_only` (thin or conflicting evidence, or the step check failed), `not_found`, `error`. `error` must never render as `not_found`. To an on-call engineer, "no runbook exists" and "search is broken" lead to different actions. Empty results and abstentions should be recorded as events (`agent-observability.md:261-262`).
- **Verbatim checking has a limit.** It shows that a step exists in a page. It does not show that the step applies here or that the page is correct (F7).

**F6. Published retrieval gains are a direction, not a target. Confidence: Medium.** [Anthropic](https://www.anthropic.com/news/contextual-retrieval) reports top-20 retrieval failure falling from 5.7% to 3.7% (contextual embeddings), 2.9% (adding contextual BM25) and 1.9% (adding reranking). The setup was codebases, fiction and academic papers, 150 → 20 rerank, with Gemini Text 004 as the best embedding. Three things limit the transfer:
- It has no runbooks and no unanswerable queries, so it says nothing about abstention.
- Its $1.02/MTok assumes 8k-token documents. With 667-token pages many chunks are the whole page, so contextualizing probably adds less. A heading-path prefix is the cheaper alternative to test first.
- "20 chunks performed best" is a recall result. Anthropic itself warns that too many chunks can distract the model, and `agent-context.md:74` calls fixed `k` a bug. A short answer probably wants far fewer than 20.

**F7. Correct retrieval of the wrong kind of page is a separate hazard. Confidence: Medium, by reasoning, with no measured rate.** A wiki of 6,000 pages is not 6,000 runbooks. A postmortem can describe a step that made things worse, and an old page can describe a retired system. Both pass a verbatim check. So page type, last-modified date and owner have to be shown with the answer, and conflicting pages surfaced side by side instead of blended.

Wiki edit access is also an attack surface. [PoisonedRAG](https://arxiv.org/abs/2402.07867) reports about 90% success with five injected texts per target question in a database of millions (abstract only; a targeted, optimized attack in a research setting). Existing defenses it tested fell short. Treat retrieved text as semi-trusted (`agent-context.md:334`) and show who last edited a page.

**F8. Failure-domain independence matters as much as retrieval quality. Confidence: Medium, by reasoning.** This tool gets used when the platform is unhealthy. If it shares a database, network path or identity provider with what is failing, it can disappear during the incident it exists for. The wiki itself may also be down, so stored page copies are needed for reading and linking. An LLM outage should degrade to ranked links, not to failure. Links before generation also protect latency: the snapshot's specs cite 500-1500ms for retrieval plus rerank and 800-2000ms for generation (`agent-safety.md:31`), both secondhand figures.

**F9. An evaluation set must exist first, and it must contain queries with no answer. Confidence: High.** Without negative cases the abstain decision cannot be measured at all. The template's eval has none (`$P/{{ eval_root }}/metrics/retrieval.py`, `graders/citation.py`).

The set needs three strata with separate metrics: exact codes, plain language, and unanswerable. The unanswerable stratum should include near-miss codes and topics adjacent to real pages.

Metrics: recall@k per stratum; false-answer and false-abstain rates; and unsupported-step rate as a hard limit.

Production will not supply this quickly. Zero failures in n trials bounds the true rate at about 3/n with 95% confidence, so 100 clean cases only shows ≤3%, which would still allow about 6 bad answers a week at this volume. 300 clean cases shows ≤1%, or about 2 a week. Offline cases have to carry most of the weight, and incident reviews are the natural source of real queries.

**F10. Freshness needs deletes and atomic swaps more than it needs speed. Confidence: High on template behaviour, Medium on the need.** At nightly rebuild, up to about 50 changed pages can be stale for a day, and a corrected runbook edited minutes ago may be the one that matters. Reindexing a changed page by ID and hash is cheap (F1). A deleted page must stop being retrievable: all the template's vector backends expose `upsert` and `similarity_search` but no delete (`$A/rag_agent/vectorstore.py.jinja:67,79`), so a retired runbook would keep being served. Index version and page timestamp should appear in the answer. Mixing embedding models in one index is a known trap (`agent-memory.md:172`); given F1, a full rebuild and swap avoids it.

**F11. The store is a cheap, reversible choice. Decide it on what you already run, and do not research it further. Confidence: Medium.**

| Option | Lexical | Fits if | Watch for |
|---|---|---|---|
| Embedded file (SQLite FTS5, DuckDB) plus exact vector scan | BM25-style | Few ops people; independence from the platform matters (F8) | Analyzer (F3); a filter inside the vector query if pages have ACLs |
| Postgres + pgvector | Built-in `ts_rank` [is not BM25](https://www.tigerdata.com/blog/introducing-pg_textsearch-true-bm25-ranking-hybrid-retrieval-postgres); extensions add it, some still preview (vendor and list sources, via search) | Postgres is already well run, outside the failure domain | Shared failure domain; extension maturity |
| OpenSearch | BM25; [RRF since 2.19](https://docs.opensearch.org/latest/search-plugins/search-pipelines/score-ranker-processor/), default constant 60 | A cluster already exists | Heavy for 200 searches a week if run only for this |

`agent-uncertainty.md:134` says not to deliberate over cheap-to-reverse choices. Because the source of truth is the wiki and rebuilds cost cents, this qualifies.

### Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `$A/rag_agent/graph.py`, `nodes/retrieve.py`, `nodes/generate.py`, `confidence.py` | SKIP as the pipeline shape | `Source` and `RetrievalResponse` in `schema.py`; the node layout as a place to add gates | `retrieve → generate` is the collapse shape (`agent-uncertainty.md:55`). Confidence is "informational only" (`confidence.py:1`), and empty results reach the model as "(no matching articles found)" (`generate.py:17`) |
| `$P/core/pipelines/corpus/index.py` | ADAPT | | BM25 structure is fine; the analyzer default breaks codes (F3); full rebuild only |
| `$P/core/pipelines/corpus/ingestion.py`, `preprocessing.py` | ADAPT | | Non-recursive `*.md` glob and filename-stem IDs (`ingestion.py:18,25`) will not suit a wiki tree. Whitespace collapse (`preprocessing.py:20`) destroys headings and code fences, which F2 depends on |
| `$A/rag_agent/vectorstore.py.jinja` | ADAPT | | One-factory backend swap is useful. Missing delete (F10) and metadata filter, which `agent-context.md:83` requires inside the query if ACLs apply. Lexical side is separate, so no hybrid |
| `$A/rag_agent/embeddings.py` with `all-MiniLM-L6-v2` | ADAPT | | Keep the local option if wiki text cannot leave the network. The default model is unproven for this; commercial models were not tested |
| `$P/{{ eval_root }}/metrics/retrieval.py` | REUSE | | `hit_rate` and MRR are correct and pure. Abstention metrics must be added beside them |
| `$P/{{ eval_root }}/graders/citation.py` | ADAPT | | `grade_retrieval` is usable. Token overlap is not evidence that a step is supported, and a single `expected_id` cannot express "no answer" |
| `$P/tests/unit/core/test_retrieval_quality.py` | SKIP | Test structure | Ten questions and `MIN_HIT_RATE = 0.6` are starter values, far too loose here |
| `$P/{{ eval_root }}/graders/ragas_grader.py` | SKIP | Not assessed beyond the catalog note; the `metrics_registry` seam may be reusable | `TEMPLATE.md:185` records a broken upstream import. The grader itself was not read |
| `$A/{{ lg_agent_dir }}/nodes/retrieve.py` | ADAPT | | The `filter_content` injection seam and `retrieve_span` are the right pattern. `guards.py` was not read, and it may rewrite text, which needs checking against verbatim steps |
| Copier `project_type=rag` (`TEMPLATE.md:110`) | ADAPT | | A sound entry point for a new project, given the verdicts above |
| `.claude/specs/agent-uncertainty.md`, `agent-safety.md` layers 3-4 | REUSE | | They directly govern this design; note the F5 tension |
| `.claude/specs/agent-context.md:79` pipeline order | ADAPT | | Written for vector search only. Metadata-first ordering holds; a lexical and identifier leg must be added |
| `.claude/specs/agent-runtime.md:157-159` semantic cache | SKIP | A query-embedding cache keyed by index version | A similarity-matched cached answer can serve a stale or adjacent runbook. Only the opening of that section was read |

### Assumptions
Nobody was available to answer questions, so these stand in for the answers.

- **Assumption:** the wiki can be exported or read programmatically, with stable page IDs and URLs. — **Evidence:** "markdown pages" in the request. — **If wrong:** ingestion becomes the main project. — **Confidence:** Medium
- **Assumption:** wiki text may be sent to external model APIs. — **Evidence:** none; `CLAUDE.md` names the Anthropic SDK as the stack. — **If wrong:** local embedding and reranking become required, and F1 costs change to hosting costs. Runbooks may contain internal hostnames or secrets. — **Confidence:** Low
- **Assumption:** all on-call engineers may read all 6,000 pages. — **Evidence:** none. — **If wrong:** permission filtering becomes a security control inside the query (`agent-context.md:83`), and caching gets harder. — **Confidence:** Low
- **Assumption:** the error codes have a recognizable shape. — **Evidence:** the single example `E4021`. — **If wrong:** the identifier leg needs broader extraction and F4's guarantee weakens. — **Confidence:** Medium
- **Assumption:** the budget is about 2 seconds to links and about 10 seconds to an answer. — **Evidence:** none stated; the figures are my guess for someone mid-incident. — **If wrong:** the optional LLM gate and model tier change. — **Confidence:** Low
- **Assumption:** the system only informs and a human executes every step. — **Evidence:** "someone could run it on production". — **If wrong:** this research does not cover automated execution, which needs approval gates (`agent-uncertainty.md:96`). — **Confidence:** High
- **Assumption:** false abstention is much cheaper than an invented step, so thresholds should lean toward abstaining. — **Evidence:** the request. — **If wrong:** too many abstentions could teach people to stop using it. Showing links on abstention limits this cost, but the balance needs measuring. — **Confidence:** Medium
- **Assumption:** page sizes are not extremely skewed. — **Evidence:** only the mean is known. — **If wrong:** chunking and costs change moderately; costs are still small. — **Confidence:** Medium

### Disconfirming Evidence

- **F2 hybrid:** would be contradicted by BM25 alone matching hybrid on real queries, if your runbook titles already use on-call vocabulary. I searched and found no study on technical documentation either way. Hybrid support is mostly general or vendor material, and one search result warns it is not an automatic gain. **Unresolved. An ablation (BM25 only, dense only, hybrid) on your gold set settles it, and dense could be dropped if it adds nothing.**
- **F2 fixed pipeline vs agent search:** a May 2026 preprint, ["Is Grep All You Need?"](https://arxiv.org/abs/2605.15184), reportedly finds grep beating vector retrieval in agent harnesses, on a 116-question conversational-memory sample, with results strongly dependent on the harness. I saw this through search summaries only; a practitioner report says the same for code. This counts against assuming embeddings are needed. It does not transfer directly: the domain differs, and agent loops add the latency and non-determinism that `agent-context.md` describes, at the worst moment for them. Worth keeping grep-like exact lookup, as F4 already does; an agent loop was not tested.
- **F4 exact path needed:** I expected cross-encoders to do poorly on bare codes. They ranked the right page first 25 of 25 times, which contradicts that expectation. The case for the exact path now rests on proving absence and on the score overlap, not on rank failure. The test also flatters the models and may misjudge them: templated pages make the code the main differentiator, and queries were bare codes. Modern commercial embeddings were not tested and may do better than MiniLM on rank. They could not make absence decidable.
- **F5 layered gates:** would be undercut if a strong model with citations almost never invents steps, leaving the gates as mere latency. Joren and Magesh point the other way but test other tasks and older models; I did not find runbook-specific data. The cheap verbatim check is worth having regardless. The LLM sufficiency gate is the part most likely to prove unnecessary.
- **F5 verbatim check:** could produce too many false rejects, since a good answer often rephrases. Requiring quotes for steps and commands only, leaving prose free, reduces this. Unmeasured.
- **F6 contextual retrieval skipped by default:** could be wrong if the page distribution has a heavy tail or short pages rely on context from their parents. Measurable through the same ablation.
- **F8 independence:** reasoned, not evidenced. If this organization's incidents rarely touch shared infrastructure, it matters less. I did not look for data, and it depends on your platform.

### Key Unknowns
Ordered by how much the answer could change the design.

1. The page-type mix: how many of the 6,000 are runbooks, and can type be determined from path or template?
2. Data policy: may wiki text leave the network, and do pages contain secrets? Is there per-page access control?
3. How often the plain-language queries have any answer in the wiki. This sets the expected abstain rate and whether abstain thresholds can be calibrated meaningfully.
4. Real identifier formats, and whether they are consistent across teams.
5. Hybrid's actual gain, the abstain threshold and false-abstain rate on this corpus. Only an eval set can answer these.
6. Latency budget and the surface used (Slack, web, pager). Neither was stated.
7. Where the wiki and candidate hosting sit relative to the platform's failure domains.
8. Wiki quality: stale-page rate, duplicate and conflicting runbooks, and who owns them. No retriever can fix a wrong page. Ownership of the eval set is also open.

### Recommendation
The research points to a deterministic identifier lookup plus BM25 and dense retrieval fused by rank and reranked, followed by a calibrated evidence gate before generation, whole-section context, and a deterministic check that every step and command in the answer exists in a cited page, with four typed outcomes where `not_found` and `error` stay distinct. Before anything else, the planner should treat three things as gates: an analyzer test on real code shapes, because the template's default fails it; a labeled eval set that includes unanswerable queries and near-miss codes; and an ablation that lets dense retrieval, contextualization and the LLM sufficiency gate each earn their place. Cost and index scale should not drive any decision here, and the store should follow what the team already runs, subject to keeping search available when the platform is not. The template's `rag_agent` is a usable starting scaffold but not a usable pipeline shape. This requirement also has no five-layer spec yet, so `/proto-design` should settle the policy unknowns above (data egress, permissions, latency) before or alongside `/proto-plan`.
