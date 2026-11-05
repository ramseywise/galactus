# Runbook search: retrieval pipeline
Date: 2026-11-04
Status: RESEARCHED
Track: agent

## Research

### Summary
The pipeline should be single-pass: exact identifier lookup and BM25 alongside dense retrieval over heading-based chunks, then fusion, reranking, an evidence gate in code before any generation, and a check in code afterwards that blocks any step not found in a cited page. At 6,000 pages and 200 searches a week, neither scale nor cost forces a choice, so the design should be judged on how reliably it says "not found". That is decidable for exact codes but only statistical for plain descriptions, and I found no evidence that a score threshold separates answerable from unanswerable descriptions, so this has to be measured before launch.

### Scope
**Investigated:** retrieval stages, chunking, abstention, invented-step defence, index freshness, store requirements, evaluation, and which repo assets can be reused.

**Sources:** the repo snapshot, public web sources, and the course wiki through Librarian. I read eight course notes in full (listed under Course grounding). I did not read the course notes on managed RAG or semantic caching, so statements on those topics rest on the notes I did read or on reasoning, and say so.

**Out of scope:** product and library selection, the UI, wiki-side content cleanup, and any automated execution of steps. No experiment was run, so every number below comes from a cited source or is my own arithmetic on the stated facts.

**What the stated facts imply (my arithmetic):**

| Fact | Derived | Why it matters |
|---|---|---|
| 4M tokens / 6,000 pages | about 667 tokens per page (mean; distribution unknown) | The mean page exceeds a 512-token embedder limit, and such embedders can truncate silently, so whole-page embedding is out. A whole page still fits in a prompt |
| Chunking at 300–500 tokens | about 8,000–13,000 chunks (estimate) | Well under the 100k-chunk line where the course comparison starts to need more than simple stores |
| 50 changed pages / day | 0.83% of pages, about 33k tokens a day | Re-embedding churn costs a negligible amount; deletes and lag are the real problems |
| 200 searches / week | about 29 a day, about 10,400 a year | Too little traffic to learn quickly from production, and a semantic cache would rarely pay off |

### Findings

#### F1. The pipeline is one pass through nine stages, with only one generative call. Confidence: High

| # | Stage | What it must guarantee | Main evidence |
|---|---|---|---|
| 1 | Query parse | Identifiers are extracted literally. The query is not rewritten by default | `course/generative-ai/02-rag-retrieval/notes/05-chunking-query-parsing-and-reranking.md` |
| 2 | Scope filter | Archived and restricted content is excluded inside each retrieval list, not after fusion | `.claude/specs/agent-context.md:85`; `course/generative-ai/02-rag-retrieval/notes/03-keyword-semantic-and-hybrid-search.md` |
| 3 | Parallel retrieval | Exact identifier lookup, BM25 and dense retrieval run separately, at 20–50 candidates per ranked list | `course/generative-ai/02-rag-retrieval/notes/03-keyword-semantic-and-hybrid-search.md` |
| 4 | Fusion | Rank-based fusion (RRF). The fused score is never used as evidence, because RRF discards magnitude | `course/generative-ai/02-rag-retrieval/notes/03-keyword-semantic-and-hybrid-search.md` |
| 5 | Rerank | A cross-encoder narrows to a variable 3–8 sections. An exact identifier hit cannot be ranked out | `.claude/specs/agent-context.md:76`; `course/generative-ai/02-rag-retrieval/notes/05-chunking-query-parsing-and-reranking.md` |
| 6 | Evidence gate | Code chooses the outcome. No model is called when evidence is absent | `.claude/specs/agent-uncertainty.md:63-66`; `.claude/specs/agent-safety.md:22` |
| 7 | Generation | Extracts from the passed sections, cites each claim, and runs at temperature near 0 | `course/generative-ai/02-rag-retrieval/notes/06-generation-for-rag.md` |
| 8 | Post-check | Code verifies that citations exist, claims are cited, and strict-tier spans resolve to the source. Failure blocks the answer | `.claude/specs/agent-safety.md:39-43`; `runs/ai/marketing-comms/src/ingest/facts.py:140-162` |
| 9 | Typed response | One of four outcomes (F3), plus links and the index timestamp | `.claude/specs/agent-uncertainty.md:79-83` |

This matches the repo's stated shape, "retrieve wide, rerank hard, send narrow" (`.claude/specs/agent-context.md:76-81`), and adds the gate and the post-check because of the production risk. A vector store is justified here even though the reference run avoided one: that run's own design calls the choice scale-dependent and says "it flips" (`runs/ai/marketing-comms/docs/DESIGN.md:399-403`), and 4M tokens cannot be preloaded on every query.

**Planner:** treat the guarantees as acceptance criteria for each stage. Any addition must beat this baseline in an ablation run.

#### F2. Exact codes are decidable, so a missing code must never fall through to semantic neighbours. Confidence: High

Whether E4021 appears in the corpus is a lookup, not a judgment. `.claude/specs/agent-uncertainty.md:149` requires an LLM call to justify itself against the deterministic alternative, and here the deterministic alternative is complete.

The hazard is the near-miss. A dense retriever can rank a page about E4022 highly for a query about E4021, and near-miss distractors reduce answer accuracy by up to 25% (Cuconasu, as reported in `course/generative-ai/02-rag-retrieval/notes/06-generation-for-rag.md`). The course's reassuring result, where bge-small found every code, came from 18 pages. The note itself calls that an "easy haystack" and says the advantage shrinks across thousands of near-identical error pages (`course/generative-ai/02-rag-retrieval/notes/03-keyword-semantic-and-hybrid-search.md`).

Three cases need explicit rules:

- **Code absent:** report "E4021 is not in the wiki as of T". Do not generate an answer.
- **Code mentioned but with no procedure,** such as a changelog entry: return `partial`, naming the page and saying that it has no procedure.
- **Code absent, description matches:** say first that the code was not found, then offer the description matches as pages that may not apply.

Exact hits also need protection from the reranker. On the course's Tallybook corpus a general reranker raised MRR from 0.742 to 0.84 but cut recall@3 from 0.95 to 0.90, because it "hasn't seen Tallybook's error codes" (`course/generative-ai/02-rag-retrieval/notes/05-chunking-query-parsing-and-reranking.md`).

Tokenisation can defeat all of this. A tokeniser that splits `HTTP-403` matches every HTTP page, while a whole-token one correctly finds nothing for an absent `HTTP-404` (`course/generative-ai/02-rag-retrieval/notes/03-keyword-semantic-and-hybrid-search.md`).

**Planner:** build an identifier inventory at index time, and test it against real variants (`E4021`, `e4021`, `E-4021`) and other identifier kinds before trusting a zero result.

#### F3. "Found nothing" must be a typed outcome chosen by code, kept separate from failure. Confidence: High

Prompting will not deliver abstention. Nine prompt variants made no salient difference in Zhao et al., who conclude that missing evidence should be caught upstream (`course/generative-ai/02-rag-retrieval/notes/06-generation-for-rag.md`). Google's work finds that adding retrieved context can reduce a model's ability to abstain ([Sufficient Context, ICLR 2025](https://arxiv.org/pdf/2411.06037.pdf)). The repo's specs already require the gate (`.claude/specs/agent-uncertainty.md:66`), and they rule out the generator grading itself (`.claude/specs/agent-uncertainty.md:112`).

| Outcome | Meaning | What the engineer sees |
|---|---|---|
| `answer` | Gate and post-check both passed | Short answer, cited links, page last-modified dates |
| `partial` | Some relevant evidence, but incomplete or conflicting | What was found, what was not, and any conflict stated |
| `no_evidence` | Retrieval worked and nothing passed the gate, or the post-check blocked the answer | An explicit "no verified runbook found as of T" |
| `retrieval_failed` | A component failed | An explicit error, plus a search of what is still reachable. Never phrased as "not found" |

The last row is where the repo's assets are weakest. `.claude/specs/agent-uncertainty.md:79` says a dispatch failure is "**Never** the same as abstention", yet the retrieval assets collapse uncertainty in several places:

| Asset | Collapse site |
|---|---|
| `.claude/skills/new-agent/references/cap-rag.md:86-88` | An AWS `ClientError` returns `[]`, so an outage reads as an empty result |
| `template/_scaffold/{{ py_project_root }}/{{ ai_source_root }}/agents/rag_agent/vectorstore.py.jinja:214-218,241-242` | A `doc_count` exception returns 0, and a count of 0 returns `[]`. Postgres does the same at `:298-307,333-334` |
| `.claude/skills/new-agent/references/cap-rag.md:113-115` | A grading parse failure becomes a neutral 0.5 |
| `.claude/skills/new-agent/references/cap-rag.md:212-213` | When CRAG attempts run out, it returns "best available passages" with no marker that they are below threshold |

**Planner:** make the four outcomes part of the response contract, with a failure-injection test for each collapse site that gets reused.

#### F4. Abstention on description queries is statistical and unproven. Confidence: Medium

"Payments queue backing up" has no lookup to settle it, so the gate needs a signal, and each candidate has a problem:

| Signal | Status | Problem |
|---|---|---|
| RRF score | Unusable | Discards magnitude, and a weak single keyword hit can reach the top (`course/generative-ai/02-rag-retrieval/notes/09-vector-database-comparison.md`) |
| Provider relevance score | Weak | A 0.7 gate passed most runs because Bedrock returned decent scores (`course/generative-ai/02-rag-retrieval/notes/11-retrieval-improvements.md`). Bedrock KB's raw score also reportedly returns 0.0 through the API (`course/generative-ai/02-rag-retrieval/notes/09-vector-database-comparison.md`) |
| Reranker score | Best candidate, unproven | I searched and found no study calibrating it for unanswerable detection |
| Agreement between lists | Supporting only | Multi-retrieved chunks are a positive signal (`.claude/specs/agent-context.md:86`), but agreement does not show the content answers the question |
| LLM sufficiency check | Option to test | One autorater reached about 93% accuracy on its authors' own data, and selective generation improved correctness among answered queries by 2–10% ([Google Research](https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/?hl=fr)). It adds a model call and latency |

A threshold is therefore an operating point on a labelled set, not a constant. Under the course's grader states, an uncalibrated threshold is "experimental" (`course/generative-ai/08-eval/notes/04-graders.md`). The 0.7 default in `.claude/skills/new-agent/references/cap-rag.md:118-122` has no calibration behind it.

**Planner:** make calibration a pre-launch step with a recorded operating point. Include a no-go path if no signal separates the classes: in that case, description queries return links only, with no generated answer.

#### F5. The invented-step defence is a hard block on strict claims, and the safety spec needs a project override. Confidence: High

Each claim that an engineer could act on (a command, step, parameter, path or threshold) must resolve to a near-verbatim span in a cited section, and a failed check must block it. The evidence for treating these claims strictly:

- Copied values were accurate 98.6–98.9% of the time against 71.9–76.4% for inferred ones in DataGemma (`course/generative-ai/02-rag-retrieval/notes/06-generation-for-rag.md`).
- A citation does not establish attribution: about half of ELI5 answers in ALCE were not fully supported (`course/generative-ai/02-rag-retrieval/notes/06-generation-for-rag.md`).
- The eval notes already define a strict tier for menu paths and numbers (`course/generative-ai/08-eval/notes/07-evaluating-rag-and-grounding.md`).
- The repo has a working precedent, where `verify_facts` drops facts whose span does not resolve (`runs/ai/marketing-comms/src/ingest/facts.py:140-162`), described as "a **block, not a warning**" (`runs/ai/marketing-comms/docs/DESIGN.md:230-232`).

**Conflict with the spec:** `.claude/specs/agent-safety.md:39-43` rates verbatim overlap as "Soft — log". That is too weak here, because a logged warning does not stop an engineer running the step. This project needs an explicit override for strict-tier claims.

**Limits of the check:** it catches fabricated strings. It does not catch a real command applied to the wrong situation, steps stitched from two pages, or a verbatim step from a stale page. `.claude/specs/agent-safety.md:45` also forbids an LLM judge for runtime grounding. An LLM sufficiency check before generation (F4) belongs to Layer 3 rather than runtime grounding, but that boundary should be recorded explicitly.

**Check the original text:** run spans against the unfiltered source. `filter_content` substitutes `[filtered]` (`template/_scaffold/{{ py_project_root }}/{{ ai_source_root }}/guardrails/guards.py.jinja:108-126`), so a filtered span would fail to match or misreport.

**Planner:** on failure, degrade to `no_evidence` plus links rather than repairing or regenerating. Define the strict claim categories before writing the check.

#### F6. Declining to answer should not mean declining to search. Confidence: Medium

During an incident, a bare "nothing found" leaves the engineer with nothing, while a generated guess is unsafe. The middle option is to state that no verified answer exists and list the nearest pages, labelled unverified, with no generated text. A real page is something the engineer can judge, whereas an invented step has no source to check. The remaining risk is that a near-miss page gets followed anyway, so a page matching a different code must name the mismatch. This is my reasoning rather than a tested result, and the labelling needs a usability check.

**Planner:** decide this explicitly. It changes what `no_evidence` displays, not what the gate decides. Candidate links should be withheld only when access or poisoning risk makes them unsafe.

#### F7. Chunk on markdown structure and keep procedures whole. Confidence: High

Structure-based chunking is the better default where documents have structure. In the course's example, the section chunk held the answer whole while a fixed 28-word split cut it. Element-based chunks scored 53.2% against 48.2% on FinanceBench, and semantic chunking showed no gain on real documents in Qu et al. (`course/generative-ai/02-rag-retrieval/notes/05-chunking-query-parsing-and-reranking.md`). A split procedure is especially dangerous here: step 4 retrieved without steps 1–3 is a correct citation of an unsafe instruction.

What chunking must provide:

- Split on headings, and keep numbered procedures and code blocks intact.
- Store the page title, heading path, URL and last-modified date with each chunk, so citations can link to a section.
- Retrieve on the chunk, and return the parent section for generation.
- Check chunk length against the embedder limit, since truncation is silent.

`fixed_chunker` in `.claude/skills/new-agent/references/cap-rag.md:242-282` ignores headings and code blocks, so it should not be used. The "hierarchical" chunker there has no parent link (`:380-385`).

Contextual Retrieval is the next thing to test, not part of the baseline. Anthropic reports top-20 failure falling from 5.7% to 3.7% with contextual embeddings, 2.9% with contextual BM25 and 1.9% with reranking ([Anthropic](https://www.anthropic.com/engineering/contextual-retrieval)). This is the vendor's own test, and [gains are reported to vary](https://gradientflow.com/contextual-retrieval-rag/) with chunk size, model, prompt and implicit context. Runbooks with descriptive heading paths may already carry much of that context.

**Planner:** prefix chunks with title and heading path first (deterministic and free), and test contextual retrieval as an ablation row.

#### F8. Scale forces no particular store, so choose on capabilities and what the team already runs. Confidence: High on scale, Medium on managed services

At about 13,000 chunks, exact scan is viable: the course measured 0.1 ms at 10k/384d and 2.0 ms at 50k/1024d (laptop, random vectors, single-query; concurrency is a stated caveat). Exact scan also has perfect recall and no parameters, which removes approximate-search misses as one reason for "not found". The course's decision flow under about 100k chunks points to pgvector where Postgres is already in use, and DuckDB or Chroma otherwise (`course/generative-ai/02-rag-retrieval/notes/09-vector-database-comparison.md`).

Requirements that do matter:

| Requirement | Why | Watch for |
|---|---|---|
| Real BM25 with control over tokenising | F2 depends on it | Native Postgres `tsvector` ranking lacks BM25 saturation and length normalisation, per a [vendor source](https://paradedb.com/blog/hybrid-search-in-postgresql-the-missing-manual), and pgvector has no BM25 without a plugin. I found no independent benchmark or source on identifier tokenising |
| Filters inside both lists | F1, stage 2 | `vectorstore.py.jinja` exposes no filter parameter |
| Atomic per-page chunk replacement with deletes | F9 | The repo's upserts never delete orphans |
| Exposed raw scores and chunk boundaries | F4 and F5 need them | Managed RAG can hide them (`course/generative-ai/02-rag-retrieval/notes/09-vector-database-comparison.md`) |

The score and chunk visibility requirement makes managed RAG a weak baseline, though that note warns its snapshot may be stale, and current behaviour should be checked.

**Planner:** select against this table rather than by product name. Also see F10 on where the store runs.

#### F9. Freshness volume is easy, but deletes and lag need design. Confidence: Medium

At 50 pages a day, either content-hash incremental updates or a rebuild with an atomic swap is feasible. I did not time a rebuild, though caching embeddings by content hash would limit its cost. The hazards lie elsewhere:

- **Orphans:** upserts never delete old chunks (`template/_scaffold/{{ py_project_root }}/{{ ai_source_root }}/agents/rag_agent/vectorstore.py.jinja:67-77,309-329`), so a removed step could still be retrieved and would pass the span check, because the span resolves against indexed text. Span checks should therefore resolve against the same current version as the citation.
- **Rebuild gaps:** `template/_scaffold/{{ py_project_root }}/core/pipelines/corpus/index.py:37-45` drops and rebuilds the table in place, so a live query could fall into the gap.
- **Missed events:** change events can be lost, so periodic reconciliation against the wiki is needed.
- **Unseen staleness:** faithful does not mean correct (`course/generative-ai/08-eval/notes/07-evaluating-rag-and-grounding.md`). A verbatim step from an outdated page passes every check, so show the last-modified date, version-pin retrieved documents (`.claude/specs/agent-context.md:319`), and report conflicting pages as conflicts instead of blending them.

"Not found" is only true as of the last sync, so the index timestamp belongs in the response. Librarian showed the same pattern in this research: one result carried a `DEGRADED RETRIEVAL` banner saying its index was behind the files on disk.

**Planner:** add tests for page edit, rename and delete, plus an alert on index lag.

#### F10. The tool will be needed during the outages it could share a dependency with. Confidence: Medium

This is my reasoning. I found no direct course coverage (see Course grounding). A runbook tool hosted on the platform it documents can fail during the incident it exists for. Three consequences follow:

- Keep a copy of page text with the index, because links to the wiki may be down and the answer's sources still need to be readable.
- When the LLM provider is down, fall back to retrieval-only results, using the `retrieval_failed` wording for the missing part.
- Identify which platform services the search depends on, and keep it out of their failure domain.

**Planner:** resolve the failure-domain question before choosing where the store runs. It may matter more than the choice of store.

#### F11. Leave out HyDE, the CRAG retry loop, agents, and default rewriting. Confidence: Medium

| Technique | Evidence | Verdict |
|---|---|---|
| CRAG retry loop | +0.005 MRR and +3.4 s, with 17 of 32 rank-1 hits identical; n=32 cannot resolve the difference, and abstention was not measured (`course/generative-ai/02-rag-retrieval/notes/11-retrieval-improvements.md`) | Keep the gate, drop the loop |
| HyDE | Latency rose from 1.5 s to 11.7 s, medical QA fell from 0.750 to 0.460 in Wang et al., and a bad guess misleads BM25 (`course/generative-ai/02-rag-retrieval/notes/05-chunking-query-parsing-and-reranking.md`). A generated document steering retrieval is also the wrong direction for this risk | Exclude |
| LLM query planner | Lost to regex by 0.031 MRR and added 4 s (`course/generative-ai/02-rag-retrieval/notes/11-retrieval-improvements.md`) | Exclude |
| Multi-query rewriting | BM25 went from 0.175 to 0.850 on a toy corpus, but with hand-written rewrites as a best case, not run in production (`course/generative-ai/02-rag-retrieval/notes/11-retrieval-improvements.md`) | Ablation only, for vocabulary mismatch on descriptions. Identifiers are never rewritten |
| Agentic search loop | More latency and less determinism, plus more paths to test, on a task where outcomes must be predictable (`.claude/specs/agent-architecture.md` §4) | Exclude from baseline |
| Semantic cache | About 29 queries a day, and a stale cached answer is hazardous. My reasoning only, since I did not read the course note on caching | Exclude |

**Planner:** if an excluded technique is proposed, require it to beat the baseline on the unanswerable stratum as well as on ranking metrics.

#### F12. Evaluate abstention as its own measure, with far more unanswerable cases than the repo's test has. Confidence: High

The retrieval gate comes before the generation gate, with stages scored separately (`.claude/specs/agent-eval.md:96-97`; `course/generative-ai/08-eval/notes/07-evaluating-rag-and-grounding.md`). `template/_scaffold/{{ py_project_root }}/tests/unit/core/test_retrieval_quality.py` is the wrong bar here: 10 rows, a 0.6 hit rate, no unanswerable rows, and no split by query type.

- **Strata:** exact code, description, mixed, and unanswerable. The unanswerable set must include near-miss codes (E4022 present, E4021 absent) and decommissioned services.
- **Seeding:** this is a new project with no traffic, so use postmortems and alert names (`.claude/specs/agent-eval.md:131-136`). Have on-call engineers write the description queries, without the pages in front of them, to avoid vocabulary leakage.
- **Failure labels:** use `source_missing`, `rank_miss`, `citation_hallucination`, `unsupported_claim` and `wrong_escalation` (`.claude/specs/agent-eval.md:113-120`). Keeping coverage gaps separate from ranking misses tells the team whether to fix the wiki or the retriever.
- **Scoring:** report abstention rate separately and apply a hallucination veto. Scoring abstention like a wrong answer rewards guessing. With a target confidence of t=0.9, a mistake costs 9 times what a correct answer gains (`course/generative-ai/08-eval/notes/04-graders.md`).
- **Controls and comparisons:** include no-context and random-context baselines (`course/generative-ai/08-eval/notes/07-evaluating-rag-and-grounding.md`), and use paired bootstrap for pipeline comparisons, given a worst-case SE of 0.088 at n=32 (`course/generative-ai/02-rag-retrieval/notes/11-retrieval-improvements.md`).

**Sizing the unanswerable set (rule of three):** with zero failures in n cases, the 95% upper bound is about 3/n.

| Unanswerable cases, zero false answers | Upper bound on false-answer rate | False answers per year if 10% of queries are unanswerable (illustrative) |
|---|---|---|
| 100 | 3% | up to about 31 |
| 300 | 1% | up to about 10 |

The team should choose the acceptable rate explicitly. Even a clean run on 100 cases leaves room for a false answer every couple of weeks. Over-abstention also has a cost, which must be measured on the answerable strata. The SPADE results show false failures rising when many checks must all pass, 88% and 53% in the two cases reported (`course/generative-ai/08-eval/notes/04-graders.md`), so the false-failure rate of the combined gate and post-check should be measured as a whole.

**Planner:** build the evaluation set before tuning anything, trace every stage from day one (`course/generative-ai/02-rag-retrieval/notes/07-rag-in-production.md`), and run a shadow period on real queries with a conservative threshold.

#### F13. Wiki edit rights become a path to production. Confidence: Medium

Someone who can edit a page can place a step that the tool will then quote, and the span check will pass, because the step really is in the source. `course/generative-ai/02-rag-retrieval/notes/07-rag-in-production.md` covers poisoning (PoisonedRAG), keeping ingestion separate from the application, and enforcing permissions at retrieval, and it opens with an internal-runbook leak. Showing the editor and the last-modified date helps engineers notice an unexpected change.

The repo's `_INJECTION_PATTERNS` (`template/_scaffold/{{ py_project_root }}/{{ ai_source_root }}/guardrails/guards.py.jinja:63-69`) are narrow and contain no shell commands, so they should not over-block runbooks in the way the regex criticised in that course note does (`sudo|apt-get|pip install`). They are not sufficient alone. Pages may also contain secrets, and those would be copied into the index and into prompts sent to the model provider.

**Planner:** add a threat model covering edit rights, secret scanning at ingestion, and permissions, treating page content as semi-trusted data rather than instructions.

#### F14. Cost is not a constraint, and latency is dominated by generation. Confidence: High on cost, Medium on latency

Prices below are aggregator-reported or assumed, unverified against primary sources, and useful for order of magnitude only.

| Item | Estimate | Basis |
|---|---|---|
| Embed the full corpus | $0.08–0.52 | $0.02–0.13/MTok, [aggregator-reported](https://www.costbench.com/software/embedding-apis/openai-embeddings/). The course's older comparison gives about $1.60 at ada-002 (`course/generative-ai/02-rag-retrieval/notes/07-rag-in-production.md`) |
| Daily re-embedding | Under 1 cent | 33k tokens at those rates |
| Contextual retrieval, full corpus | About $4 | $1.02/MTok from a secondary source; I could not confirm it in Anthropic's text |
| Generation | About $0.03 a query, about $340 a year | Assumed $5/$25 per MTok, 5k input, 300 output |

**Planner:** do not remove a safety stage to save money. The course's estimates put the reranker at about 50 ms, with generation dominating (`course/generative-ai/02-rag-retrieval/notes/07-rag-in-production.md`). The gate runs before generation, and a failed gate skips it, so abstaining should be faster than answering (`.claude/specs/agent-safety.md:33`). Links are available before generation finishes, so they could be shown first.

#### F15. Native citations may conflict with the response schema. Confidence: Medium

If Claude is the provider, its citations feature and Structured Outputs are incompatible and return a 400 error ([Claude citations docs](https://platform.claude.com/docs/en/build-with-claude/citations.md)), while `.claude/specs/agent-architecture.md` §4 expects a response schema. [Search-result blocks](https://platform.claude.com/docs/en/docs/build-with-claude/search-results) offer a citation path, but I could not confirm that `cited_text` is guaranteed valid. A schema guarantees only shape, not truth (`course/generative-ai/02-rag-retrieval/notes/06-generation-for-rag.md`).

**Planner:** the post-check in F5 stays regardless of provider. Whichever provider is chosen, check this interaction against current documentation before designing the output format.

### Course grounding

- query: `hybrid retrieval BM25 dense embeddings exact identifiers error codes reciprocal rank fusion` (domain=course) → 10 hits — result led with DEGRADED RETRIEVAL (search index behind the files on disk, so results may omit or misquote recent edits); I read the used notes in full
  - used: course/generative-ai/02-rag-retrieval/notes/03-keyword-semantic-and-hybrid-search.md
  - used: course/generative-ai/02-rag-retrieval/notes/09-vector-database-comparison.md
  - used: course/generative-ai/02-rag-retrieval/notes/11-retrieval-improvements.md
- query: `chunking strategy markdown documents contextual retrieval parent page` (domain=course) → 10 hits
  - used: course/generative-ai/02-rag-retrieval/notes/05-chunking-query-parsing-and-reranking.md
- query: `abstain when no evidence retrieval quality gate refuse to answer groundedness citations` (domain=course) → 10 hits
  - used: course/generative-ai/08-eval/notes/04-graders.md
  - used: course/generative-ai/08-eval/notes/07-evaluating-rag-and-grounding.md
  - used: course/generative-ai/02-rag-retrieval/notes/06-generation-for-rag.md
- query: `reranking cross-encoder retrieve wide send narrow` (domain=course) → 10 hits
  - used: course/generative-ai/02-rag-retrieval/notes/05-chunking-query-parsing-and-reranking.md
- query: `incremental index updates stale documents freshness content hash re-embedding` (domain=course) → 10 hits
  - used: course/generative-ai/02-rag-retrieval/notes/07-rag-in-production.md
  - used: course/generative-ai/02-rag-retrieval/notes/09-vector-database-comparison.md
- query: `RAG evaluation recall@k faithfulness golden set unanswerable queries` (domain=course) → 10 hits
  - used: course/generative-ai/08-eval/notes/07-evaluating-rag-and-grounding.md
  - used: course/generative-ai/02-rag-retrieval/notes/06-generation-for-rag.md
  - used: course/generative-ai/02-rag-retrieval/notes/11-retrieval-improvements.md
- query: `when not to use a vector database, agentic search grep versus RAG pipeline cost at low query volume` (domain=course) → 10 hits
  - used: course/generative-ai/02-rag-retrieval/notes/09-vector-database-comparison.md
- query: `on-call incident runbook search retrieval availability during outage` (domain=course) → 10 hits — no direct course coverage of availability during an incident
  - used: course/generative-ai/02-rag-retrieval/notes/07-rag-in-production.md

### Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `.claude/specs/agent-uncertainty.md` | REUSE | All of it | Already defines the gate and separates abstention from error |
| `.claude/specs/agent-context.md` | REUSE | All of it | Defines the retrieval shape, variable k and filtering |
| `.claude/specs/agent-eval.md` | REUSE | All of it | Provides staged gates and failure labels |
| `.claude/specs/agent-safety.md` | ADAPT | Layers and code-first grounding unchanged | Tier 3 "Soft — log" needs a hard-block override for strict claims (F5) |
| `.claude/skills/new-agent/references/cap-rag.md` | ADAPT | `PassageItem` and the `Retriever` protocol | The CRAG loop, 0.7 gate, chunkers and failure handling all conflict with this project's needs (F3, F4, F7, F11) |
| `template/_scaffold/{{ py_project_root }}/core/pipelines/corpus/index.py` | ADAPT | The DuckDB BM25 search path, whose `[]` on no match stays distinct from a raised connection error | The rebuild is not atomic, and identifier tokenising is unverified |
| `template/_scaffold/{{ py_project_root }}/{{ ai_source_root }}/agents/rag_agent/vectorstore.py.jinja` | ADAPT | Backend interface and exact-scan DuckDB path | Dense only, with no filters, orphaned chunks, and outages reported as empty results |
| `template/_scaffold/{{ py_project_root }}/{{ ai_source_root }}/agents/rag_agent/embeddings.py` | REUSE | Local model loading with a pinned revision | Model choice remains an eval question |
| `template/_scaffold/{{ py_project_root }}/{{ ai_source_root }}/agents/{{ lg_agent_dir }}/nodes/retrieve.py` | ADAPT | Source and score shape, and filtering snippets rather than dropping them | BM25 only, with no gate |
| `template/_scaffold/{{ py_project_root }}/{{ ai_source_root }}/guardrails/guards.py.jinja` | ADAPT | `filter_content` and its patterns, which do not over-block commands | Must not alter the text that span checks use |
| `template/_scaffold/{{ py_project_root }}/tests/unit/core/test_retrieval_quality.py` | ADAPT | Test structure | The bar is too low, and it lacks unanswerable rows and strata (F12) |
| `runs/ai/marketing-comms/src/ingest/facts.py` | ADAPT | `verify_facts` and `resolve_span` pattern | Built for facts at ingest; needs applying to generated claims at answer time |
| Managed RAG (Bedrock KB, Discovery Engine) | SKIP | Could still serve as a retrieval component if the team is already on that cloud, or be compared in an ablation, once score access is checked | Hidden scores and chunk boundaries undermine the gate (F8). Based on a possibly stale course snapshot |
| `.claude/specs/models.md` | SKIP | The tiering principle only, "pay for judgment, not for reading" | Its tables are stale by its own note, and it has little bearing on retrieval |

### Assumptions

- **Assumption:** Track is `agent`, not `ml`. — **Evidence:** the system calls models and trains none; the skill's test is that fitting a model is `ml` and calling one is not. Calibrating a gate threshold is evaluation work, not model fitting. — **If wrong:** if the team later trains a custom ranker or classifier, that work needs its own `ml` item with a baseline and leakage check. — **Confidence:** High
- **Assumption:** research can continue without a `/proto-design` spec. — **Evidence:** the skill stops for a FRAME gap, and the consumer and cost of being wrong are both stated, but no spec answers all five layers. Nobody is available to ask. — **If wrong:** a later spec may change these findings, especially F6 and F10. — **Confidence:** Medium
- **Assumption:** a person reads every answer, and nothing executes steps automatically. — **Evidence:** the request says "someone could run it". — **If wrong:** automated execution would need a much stricter design than this document covers. — **Confidence:** High
- **Assumption:** queries are single-shot, not conversational. — **Evidence:** the request describes searches and a short answer. — **If wrong:** query context handling is required, which adds rewriting risk. — **Confidence:** Medium
- **Assumption:** the wiki has an export or API that exposes changes and deletes. — **Evidence:** none; a platform wiki commonly would. — **If wrong:** full periodic rebuilds become the only option, which increases lag. — **Confidence:** Medium
- **Assumption:** all on-call engineers can read all pages. — **Evidence:** none stated. — **If wrong:** permission filtering becomes a required security control in stage 2 and in caching (`.claude/specs/agent-context.md:85`). — **Confidence:** Low
- **Assumption:** pages and queries are mostly English. — **Evidence:** both examples are English. — **If wrong:** the choice of embedder, reranker and BM25 analysis changes. — **Confidence:** Medium
- **Assumption:** identifiers follow predictable patterns beyond E4021. — **Evidence:** one example. — **If wrong:** the inventory in F2 misses identifiers, and a "not found" becomes false. — **Confidence:** Low
- **Assumption:** an answer within a few seconds is acceptable. — **Evidence:** no target was stated, and generation dominates. — **If wrong:** a tighter budget favours showing links first or removing the reranker, which must then be re-evaluated. — **Confidence:** Medium
- **Assumption:** no labelled queries or search logs exist. — **Evidence:** "New project." — **If wrong:** existing wiki search logs would make the best seed for the evaluation set. — **Confidence:** Medium
- **Assumption:** provider and hosting stack are open. — **Evidence:** none stated. — **If wrong:** an existing Postgres or cloud commitment narrows F8 and may settle F15. — **Confidence:** Medium

### Disconfirming Evidence

| Finding | What would contradict it | Did I look? | What I found |
|---|---|---|---|
| Hybrid retrieval is needed (F1) | Dense alone matching hybrid | Yes | Partial contradiction. RRF did not raise recall@3 and lowered MRR (0.91 to 0.84) on 18 pages (`course/generative-ai/02-rag-retrieval/notes/03-keyword-semantic-and-hybrid-search.md`), and dense minus hybrid was +0.133 with an interval crossing zero on 20 queries (`course/generative-ai/02-rag-retrieval/notes/11-retrieval-improvements.md`). These corpora are tiny, so neither settles 6,000 pages. BM25 stays because F2 needs exact matching and the note calls hybrid an "insurance policy". Pure dense should be an ablation row |
| Rerank is net-positive (F1) | A reranker losing correct documents | Yes | Found: recall@3 fell from 0.95 to 0.90 on unfamiliar error codes. This is why F2 protects exact hits, and description queries may lose recall too. Measure recall after reranking |
| A gate can abstain reliably (F3, F4) | Scores that fail to separate answerable from unanswerable | Yes | The strongest evidence against. The 0.7 gate passed most runs, and I found no study supporting reranker thresholds. F4 is Medium for this reason |
| Dropping CRAG (F11) | CRAG helping on another corpus, or a stricter gate helping | Partly | The measured result is n=32 on one corpus, with a lenient gate, and did not measure abstention. It supports not adding CRAG by default, not that it can never help |
| Hard span block (F5) | Verbatim checks rejecting good answers | Yes | Real risk. All-pass checks can produce high false failures (SPADE), and over-abstaining during an incident has its own cost. The block is limited to strict claims, and failures degrade to links |
| Generation adds value at all | Links-only search being enough | Not tested | No evidence either way. The request asks for a short answer, but links-only is a credible baseline and the fallback for F4. On-call preference should be tested in the shadow period |
| Baseline excludes contextual retrieval (F7) | Large gains on this corpus | Yes | Anthropic's reductions are large on its own tests. They could hold here, and the cost is low, so this is a matter of sequencing and is settled by an ablation |
| Heading-based chunks work (F7) | A wiki with poor heading structure | Could not check | I have no access to the corpus. A sample of pages would settle it (Key Unknowns) |
| RAG beats agentic search (F11) | Just-in-time grep-style search being safer | Yes | `.claude/specs/agent-context.md` treats just-in-time retrieval as a real pattern. Its costs here are latency, wandering and non-determinism, but a plain literal search is effectively what F2 already includes |

### Key Unknowns

1. **Does any signal separate answerable from unanswerable description queries?** This is the most important unknown, because F4 depends on it. I searched and found no literature on reranker score thresholds. It can only be measured on labelled queries from this corpus.
2. **How does the tokeniser treat the real identifiers?** It determines whether a zero-result code lookup can be trusted. Needs a test using real codes.
3. **What do the pages look like?** That covers length distribution, heading quality, how procedures are written, and the share of duplicate or stale pages. A sample of about 100 pages would answer most of it.
4. **Does hybrid beat dense at 6,000 pages?** The course results are from corpora too small to say.
5. **Do pages have restricted access?** This decides whether stage 2 is a security control.
6. **Where would the tool run relative to the platform it documents?** This decides F10.
7. **What are the latency budget and the index-lag budget?** Neither was given. An engineer editing a runbook during an incident may expect the change to be found straight away.
8. **What false-answer rate is acceptable, and what abstention rate would on-call engineers tolerate?** This is a product decision that the evaluation depends on.
9. **What share of real queries are unanswerable?** The 10% figure in F12 is illustrative only.
10. **External facts needing checks against current documentation:** the `cited_text` guarantee, current prices, and managed-service score behaviour.

### Recommendation

The research supports a deterministic, single-pass hybrid pipeline in which the model only writes from evidence that code has already accepted, and code then checks what the model wrote. Exact-code misses can be answered with certainty at low cost, and that should be treated as settled. The open risk is the description query with no runbook behind it, where the abstention signal is unproven, so the next phase should measure this early, on a labelled set with a large unanswerable stratum, before effort goes into store selection or optional retrieval improvements. If no signal separates the classes, the evidence supports returning links without generated answers for description queries rather than shipping an uncalibrated gate. The project should also record two decisions that the repo's defaults would otherwise get wrong here: strict claims are a hard block rather than the spec's logged warning, and a retrieval failure is never reported as "found nothing".
