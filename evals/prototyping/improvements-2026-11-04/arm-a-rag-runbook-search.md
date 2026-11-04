# runbook-search
Date: 2026-11-04
Status: RESEARCHED
Track: agent

## Research

### Summary
Use a fixed pipeline with no agent loop: an exact-identifier path beside hybrid BM25 and dense search, then a reranker, a deterministic evidence gate that can stop before the model runs, and a code check on the answer. Scale does not drive this design: about 13,000 chunks fit an exact scan, and the model and retrieval APIs should cost roughly $100 a year. The hard problems are false "found nothing" results, near-miss runbooks such as E4012 for E4021, and steps that are invented or dropped. The template's RAG starter handles none of these out of the box; with its default tokenizer, a search for `E4021` returns nothing even when a page contains that code.

### Scope
**Investigated:** retrieval path, chunking, store, freshness, abstention, answer verification, evaluation and cost at the stated scale; repo specs; template RAG assets; course material; public sources; two throwaway probes.

**Out of scope:** UI, auth implementation, hosting, wiki connector details, step execution, multi-turn chat, and final vendor choice. This doc does not plan or implement any of them.

**Evidence limit:** nobody had access to the real wiki, queries or incident history. Probes used synthetic data, so no number here measures retrieval quality on this corpus.

**Path shorthand:** `T/` = `template/_scaffold/{{ py_project_root }}/`, and `RAG/` = `T/{{ ai_source_root }}/agents/rag_agent/`.

**Track:** `agent`. The system calls a model and fits none. Thresholds are tuned on data, so they need a held-out set (F9). Fine-tuning an embedder or reranker later would be a model fit and should be re-routed to `ml`.

### Findings

#### F1. The pipeline should be fixed, with stages that can stop it. Confidence: High
Every stage can be named in advance, so a loop adds risk without adding reach (`.claude/specs/agent-architecture.md` §0). The uncertainty spec requires `retrieve → evaluate evidence → answer OR abstain` as a gate (`.claude/specs/agent-uncertainty.md:63`), and the context spec sets the same retrieval order (`.claude/specs/agent-context.md:81`).

The shape the evidence supports:

```text
OFFLINE
wiki sync → content-hash diff → heading-aware chunks → identifier index + BM25 + embeddings
          → new index version → atomic swap

ONLINE
query → extract identifiers → permission filter
      ├─ error-code path: literal lookup; absent code stops answer generation
      └─ hybrid path: BM25 + dense, 20–50 each → RRF
      → rerank to 3–5 sections → EVIDENCE GATE → constrained generation → CODE CHECK
      → typed result: answer | partial | not_found | error
```

**Planner:** treat each arrow that can stop the run as a tested branch, and do not add a model call where code can decide.

#### F2. Error codes need their own literal path, and a missing code must stop generation. Confidence: High
Course material shows why. An embedder may return generic pages for an error code, and an early advantage on a small corpus "shrinks" when there are thousands of near-identical error pages (`course/generative-ai/02-rag-retrieval/notes/03-keyword-semantic-and-hybrid-search.md`). RRF also gives a weak one-hit match the same rank credit as a strong one (`course/generative-ai/02-rag-retrieval/notes/09-vector-database-comparison.md`).

The dangerous case is an absent code. Dense search can still rank E4012 highly for E4021, so hybrid search must not be allowed to rescue that query into an answer.

| Query | Required behaviour |
|---|---|
| Code present on a procedure page | Use those sections, even if the reranker dislikes them |
| Code present only in passing, such as a code list or postmortem | Say it was mentioned; return `partial`, not steps |
| Code absent | Return `not_found`: "no page contains E4021 as of <index time>" |
| Code absent, with description (`E4021 payments queue backing up`) | State the code is absent; show description matches, labelled as not code matches |
| Similar code exists | May show "similar code, not a match" as a link; never as steps |
| Identifier-like term such as `p99`, `S3`, `k8s` | Boost only; do not apply the absence rule |

**Planner:** a literal hit is necessary but not sufficient for an answer. Derive identifier patterns by mining the corpus; one example (`E4021`) cannot define the namespace.

#### F3. The default DuckDB tokenizer breaks the core requirement. Confidence: High for the behaviour; synthetic data
`T/core/pipelines/corpus/index.py:45` builds the index with default options. DuckDB's documented default ignore pattern removes non-letters ([DuckDB FTS docs](https://duckdb.org/docs/stable/core_extensions/full_text_search.html)). The probe (DuckDB 2.0.0, five documents) confirmed the result:

| Query | Default config | Digits and hyphen kept, no stemmer or stopwords |
|---|---|---|
| `E4021` (page exists) | **no result** | correct page |
| `E9999` (no page) | no result | no result |
| `HTTP-403` (page exists) | correct page | correct page |
| `HTTP-404` (no page) | **returns the HTTP-403 page, same score** | no result |
| `E-4021` (page says `E4021`) | no result | **no result** |
| `payments queue backing up` | right page first, plus 2 weak pages | right page only |

The default config produces both failure types: a false "nothing" and a false match. `E4021` tokenizes to `e`, and `HTTP-403` to `http`. The custom config fixes literal matching but still needs variant normalization, and turning off stemming can reduce recall for prose. Combined stemming with digit retention was not tested.

**Planner:** expect two lexical views, one for literal identifiers and one for stemmed prose. Add tokenizer regression tests before any quality measurement.

#### F4. Descriptive queries should use hybrid retrieval with a measured reranker. Confidence: Medium
BM25 alone is weak on paraphrase: recall@3 of 0.2 against 1.0 on codes and keywords in the course corpus (`notes/03`). That risk fits queries like "payments queue backing up" when the page says "consumer lag". The course also warns that hybrid is "an insurance policy": on one small corpus RRF did not beat dense recall and lowered MRR from 0.91 to 0.84.

Reranking helps in [Anthropic's Contextual Retrieval write-up](https://www.anthropic.com/engineering/contextual-retrieval), where top-20 failure fell from 5.7% to 2.9% with contextual embeddings and BM25, then 1.9% with reranking. But a web-trained cross-encoder pushed a correct document out of the top 3 because it had not seen the corpus's error codes (recall@3 0.95→0.90; `course/generative-ai/02-rag-retrieval/notes/05-chunking-query-parsing-and-reranking.md`). Answer quality also fell as more passages reached the prompt, even when the right one was present (Zhao et al., in `notes/05`).

| Stage | Starting point | Keep it if |
|---|---|---|
| BM25 + dense + RRF | 20–50 each | It beats either retriever on descriptive recall |
| Cross-encoder | Down to 3–5 sections | Recall after rerank does not fall, overall or by query class |
| Contextual chunk text | Off; use title and heading path first | It beats deterministic prefixes on the golden set |
| HyDE | Off | Unlikely: it invents vocabulary, and one study saw latency rise from 1.5 s to 11.7 s (`notes/05`) |
| LLM query planner or CRAG loop | Off | Unlikely: −0.031 MRR for +4 s, and +0.005 MRR for +3.4 s, on 32 queries (`course/generative-ai/02-rag-retrieval/notes/11-retrieval-improvements.md`) |

**Planner:** measure these stages as switches against a baseline. Do not ship them because they are common.

#### F5. Chunk by markdown structure and retrieve at section level. Confidence: Medium-High
The course's default is structure when a document has it, and semantic chunking showed no consistent gain on real documents (`notes/05`). Runbooks add one requirement: a split must not separate a precondition from its command. Sections should keep their page title, heading path, source URL, revision and position, with code blocks unbroken. Average page size is about 667 tokens, so many pages may need only light splitting, but the distribution is unknown.

The embedder can silently truncate long sections (bge-base at 512 tokens, `notes/03`). Generated contextual text, if adopted, must be searchable only. It must never count as evidence or appear in an answer.

**Planner:** index small, return the whole section, and test on real tables, nested lists and long code blocks.

#### F6. The evidence gate must run before generation, and its thresholds are not known yet. Confidence: High that it is required; Low on which signals are enough
A prompt instruction will not provide abstention. Models kept answering without the gold passage, and nine prompt variants made no salient difference (`course/generative-ai/02-rag-retrieval/notes/06-generation-for-rag.md`). [Joren et al. (ICLR 2025)](https://arxiv.org/abs/2411.06037) report that proprietary models often answer incorrectly rather than abstain when context is insufficient. High-scoring passages without the answer are the worst distractors, cutting accuracy by up to 25% (Cuconasu et al., in `notes/06`). The safety spec also places a retrieval gate before generation (`.claude/specs/agent-safety.md:22`).

RRF is rank-based and discards score magnitude (`notes/03`), so it cannot show that nothing relevant exists. Candidate signals are reranker score, literal-identifier match, coverage of query terms, agreement across retrievers, and page type. Scores can't reliably tell "right system" from "similar system", so a false answer may pass them all. An LLM sufficiency check is therefore worth testing, but not assuming: the course's CRAG numbers measure ranking rather than abstention, and a sufficiency check adds a judge that can be misled (`.claude/specs/agent-safety.md:342`).

**Planner:** make this a ratchet. Code can block generation; the model may downgrade to `not_found`, but cannot override a block. Choose thresholds on measured false-answer cost, as in F9.

#### F7. Make invented steps structurally hard, then check what remains. Confidence: High on checks; Medium on the render approach
Schemas only guarantee shape: a hallucinated `kb-99` citation passes (`notes/06`). In the course's citation lab, a 0.9 fuzzy match accepted 3 of 7 bad answers, one with an invented deadline (`course/generative-ai/02-rag-retrieval/notes/07-rag-in-production.md`). For commands, a one-character difference can matter, so the comparison must be exact after only minimal whitespace normalization.

Verbatim checks still miss three things that matter here: **dropped steps, reordered steps, and correct text from the wrong service's page**. "Short answer" pulls directly against that risk, because summarizing a runbook can drop "drain first".

| Answer design | Invented command | Dropped or reordered step | Fit |
|---|---|---|---|
| Free text, instruction only | Not controlled | Not controlled | Fails the requirement |
| Free text + verbatim check | Caught if the command is recognized | Not caught | Minimum acceptable |
| Model writes a summary and picks section IDs; code renders the steps from the source | Not possible in the rendered steps; prose still needs checking | Controlled within a section | Lead candidate |
| Extractive results only, no model | Not possible | Controlled | Strong baseline; may fail "short answer" |

The check should verify that every cited ID was retrieved, every code span and number appears verbatim in its cited section, and every claim has a citation (`notes/06`; `course/generative-ai/08-eval/notes/07-evaluating-rag-and-grounding.md`). Temperature is not a control: the course suggests about 0, while `RAG/model/gateway.py:30-34` notes that some models reject it.

**Planner:** a failed check should remove the answer text and fall back to labelled links, not trigger a confident retry. Links must show the sections actually cited, because appending every retrieved source only records what the model saw (`notes/06`).

#### F8. "Found nothing" must be a trustworthy, typed result. Confidence: High
The spec treats a failed component as an error, never an abstention (`.claude/specs/agent-uncertainty.md:79`). A collapsed state is dangerous in both directions: an outage that says "no runbook" sends an on-call engineer away from a page that exists.

| State | Meaning | User sees |
|---|---|---|
| `answer` | Gate and code check passed | Short answer, source sections, links, page age |
| `partial` | Relevant pages, but no verified procedure | Labelled links, no steps |
| `not_found` | Search ran on a healthy index and evidence failed the gate | Explicit "found nothing", index time, closest pages only if labelled |
| `error` | A required stage failed | "Search failed", not a finding about the wiki |
| Stale index flag | Sync is past its freshness limit | A warning on every state; a code absence is reported as uncertain |

A partial failure needs its own rule. If dense search is down, BM25 can still confirm a code that is present, but can't support a descriptive `not_found`. The template's content filter creates one such risk: on internal error it returns empty text with `blocked=True` (`T/{{ ai_source_root }}/guardrails/guards.py.jinja`, `filter_content`), which can look like empty evidence if a caller only reads `.text`.

**Planner:** record abstentions and low-confidence results as first-class events (`.claude/specs/agent-observability.md:263`), and put the state in the response type, not the prose.

#### F9. Evaluation must measure abstention separately, with enough no-answer cases. Confidence: High
A recall score says nothing about whether the system stays silent when it should. The eval spec already separates retrieval from generation and distinguishes `source_missing` from `rank_miss` (`.claude/specs/agent-eval.md:113-114`), and the course warns against scoring coverage gaps as ranking failures (`notes/11`). Results should be reported by query class:

| Gate | Measures | Hard-fail example |
|---|---|---|
| Tokenizer and literal lookup | Present codes found; absent codes not matched | Any false match on an error code |
| Retrieval | Recall@k after rerank, code and descriptive classes separately | Rerank demotes a literal match |
| Abstention | False-answer rate on no-answer cases; false-abstention rate on answerable cases | Steps returned for an absent code |
| Grounding | Citation, verbatim command and number checks | Command not in cited section |
| Completeness | Required steps and preconditions preserved, in order | Precondition dropped |
| Failure injection | Store, embedder, reranker, model and stale-sync failures | Outage reported as `not_found` |

**Sample size:** with zero false answers in *n* no-answer cases, the rule of three gives a 95% upper bound of about 3/n. So 60 cases can only support "under about 5%", and 300 are needed for "under about 1%". One error per class is enough to fail a release when the steps can touch production. A 32-query set had a worst-case standard error of 0.088 (`notes/11`), so paired bootstrap should be used for comparisons.

**Getting labels:** a new service has no logs. Seed from alerts, incident tickets and postmortems. Build no-answer cases cheaply by holding a page out of the index and reusing its real question, and by altering existing codes into absent ones. These produce realistic near-misses. At about 10,400 searches a year, traffic grows slowly, and labelling is the main cost.

**Planner:** keep threshold-tuning and report sets separate, and store the query-set version with each score (`notes/11`).

#### F10. Freshness is cheap to solve, but it affects whether "found nothing" is true. Confidence: Medium-High
About 50 pages a day is about 33,000 tokens, or 0.8% of the corpus. Full re-embedding is about $0.24 at the listed $0.06/M price, so cost does not justify complicated incremental machinery.

DuckDB's FTS index does not update when its table changes ([docs](https://duckdb.org/docs/stable/core_extensions/full_text_search.html)), and a probe confirmed a newly inserted page was not found without a rebuild. A rebuild over about 14,000 synthetic chunks took 0.75 s. Another process could not open the file read-only while a writer held it, which favours building a new version and swapping it atomically, or a server database if the deployment needs concurrent writes.

Deletes and renames need the same treatment as edits. A deleted dangerous page that stays searchable is a real failure, and `RAG/agents` vector upsert has no delete path (`RAG/vectorstore.py.jinja:67-77`). Recency should be displayed rather than used as a filter, because an untouched runbook may still be right. The answer should pin the page revision it used (`.claude/specs/agent-context.md` §7).

**Planner:** define a freshness limit and alert on it. Track last successful sync, page count changes and failed pages, and reconcile against the full page list periodically to catch missed events.

#### F11. A single-file or existing database is enough, provided it exposes scores. Confidence: Medium-High
At 4M tokens, 300–800 token chunks give about 5,000–13,000 items, below the course's rule-of-thumb 100,000 for exact scan (`notes/09`). A probe on 14,000 synthetic 1,024-dim vectors found:

| Method | Time |
|---|---|
| Template pattern: fetch all rows, score in a Python loop (`RAG/vectorstore.py.jinja:82-89`) | 1.19 s |
| DuckDB SQL exact scan | 0.021 s |
| BM25 query with no match (a floor, not typical) | 0.012 s |

| Store | Fit | Main concern |
|---|---|---|
| DuckDB | Fits this scale with BM25, vectors and filters in one file; template default | Writer lock; multi-instance serving |
| Postgres + pgvector | Good if already operated here | BM25 needs a plugin (`notes/09`) |
| OpenSearch | Good if a cluster already exists | Heavy to introduce for about 29 searches a day |
| Managed RAG (Bedrock KB, Vertex) | Poor | Score visibility is limited, which undermines the gate (`notes/09`) |

**Planner:** choose based on what the team already runs. The gate needs raw scores, and scale does not justify an ANN index, dedicated vector database or semantic cache.

#### F12. Quality and failure handling should decide the budget, not API cost. Confidence: Medium
Estimates assume 13,333 chunks, 40 candidates of 400 tokens per rerank, 2,000 input and 300 output tokens per answer, and 10,400 searches a year.

| Item | Listed price | Approx. cost |
|---|---|---|
| Full-corpus embedding | $0.06/M ([Voyage, via third party](https://www.developersdigest.tech/models/embeddings/voyage-3-5)) | $0.24 per rebuild |
| Daily changed pages | same | $0.002/day |
| Reranking | $0.05/M or about $2/1,000 searches ([third party](https://apicostcalc.com/cohere-vs-voyage-vs-jina-rerank-cost-calculator.html)) | $8–21/year |
| Answer generation | Sonnet 5.5, $2/$10 per M ([docs](https://platform.claude.com/docs/en/models/sonnet-5-5/overview)) | about $73/year |
| Contextual text, if adopted | Haiku 5.5, $0.10/$0.50 per M ([docs](https://platform.claude.com/docs/en/models/haiku-5-5/overview)), no caching, 75 output tokens per chunk | about $2 per corpus |

Latency matters more. The safety spec's rough budget is 500–1500 ms for retrieval plus rerank and 800–2000 ms for generation (`.claude/specs/agent-safety.md:33`). Retrieved links can therefore be available before generation finishes, which also means a slow model never blocks the page an engineer needs.

**Planner:** do not choose a weaker model or skip a safety stage to save money at this volume. Confirm prices before committing.

### Course grounding
Librarian returned a `DEGRADED RETRIEVAL` banner on all five queries because its index was behind the files on disk, so a thin result would not prove missing coverage.

- query: `hybrid retrieval BM25 and vector search for exact identifiers and error codes` (domain=course) → 10 hits, DEGRADED RETRIEVAL
  - used: course/generative-ai/02-rag-retrieval/notes/03-keyword-semantic-and-hybrid-search.md
  - used: course/generative-ai/02-rag-retrieval/notes/09-vector-database-comparison.md
- query: `RAG abstention refuse to answer when retrieval finds nothing, groundedness, citations` (domain=course) → 10 hits, DEGRADED RETRIEVAL
  - used: course/generative-ai/02-rag-retrieval/notes/06-generation-for-rag.md
  - used: course/generative-ai/08-eval/notes/07-evaluating-rag-and-grounding.md
- query: `chunking markdown documents, contextual retrieval, reranking` (domain=course) → 10 hits, DEGRADED RETRIEVAL
  - used: course/generative-ai/02-rag-retrieval/notes/05-chunking-query-parsing-and-reranking.md
- query: `incremental indexing keeping a RAG index fresh when documents change, stale chunks` (domain=course) → 10 hits, DEGRADED RETRIEVAL
  - used: course/generative-ai/02-rag-retrieval/notes/07-rag-in-production.md
  - used: course/generative-ai/02-rag-retrieval/notes/09-vector-database-comparison.md
- query: `evaluating RAG retrieval recall@k golden set faithfulness` (domain=course) → 10 hits, DEGRADED RETRIEVAL
  - used: course/generative-ai/08-eval/notes/07-evaluating-rag-and-grounding.md
  - used: course/generative-ai/02-rag-retrieval/notes/11-retrieval-improvements.md

### Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `T/core/pipelines/corpus/ingestion.py` | ADAPT | Title parsing and the `Article` load shape | `glob("*.md")` at line 18 is non-recursive, so nested wiki spaces would be skipped silently; the filename stem can collide as an ID |
| `T/core/pipelines/corpus/preprocessing.py` | SKIP | SHA-256 content hash and JSONL writer | Line 20 collapses all whitespace, which destroys headings and code blocks; exact-duplicate removal could also hide a page from links |
| `T/core/pipelines/corpus/index.py` | ADAPT | Overwrite-rebuild pattern and result shape | Default tokenizer fails on codes (F3); `search` opens a connection and runs `INSTALL fts` per call |
| `RAG/graph.py`, `RAG/nodes/retrieve.py`, `RAG/nodes/generate.py` | SKIP | The node split, and `Source` shape from `RAG/schema.py` | No gate edge; dense-only; `generate.py:17-18` still calls the model with "(no matching articles found)"; the checkpointer and thread model suit chat, not one-shot lookup |
| `RAG/confidence.py` | SKIP | Only the `None` = no results distinction | Informational by its own docstring; `threshold` is unused; any result counts as confident |
| `RAG/vectorstore.py.jinja` (DuckDB) | ADAPT | Backend factory and table layout | Python-loop scan is about 57× slower than SQL in the probe; no delete path |
| `RAG/vectorstore.py.jinja` (OpenSearch, pgvector) | ADAPT | Use if already operated | Only worth using when the team already runs that system |
| Copier `rag_impl`: `bedrock_kb`, `vertex_rag` (`copier.yaml`) | SKIP | Nothing for the gate; checked: ranks alone can't support it | Limited score visibility undermines calibration (`notes/09`); not read beyond option text and course notes |
| `RAG/model/gateway.py` | REUSE | n/a | Single call seam and `max_tokens` handling; only partly read, so confirm during planning |
| `T/{{ eval_root }}/metrics/retrieval.py` | REUSE | n/a | Pure `hit_rate` and MRR over nullable ranks; abstention metrics must be added beside it |
| `T/{{ eval_root }}/graders/citation.py` | ADAPT | `grade_retrieval` | Despite the filename, it has no citation check; vocabulary overlap can't catch a changed command |
| `T/{{ ai_source_root }}/guardrails/guards.py.jinja` | ADAPT | Narrow patterns and `GuardResult` | Its patterns do not appear to target shell commands, which is good; the error path must surface as `error`, and verbatim checks must use the unfiltered source |
| `runs/ai/marketing-comms/src/guardrails/fallback.py` | SKIP | Degradation reporting and re-validation | Its goal is to always return something, using filler, which is the opposite of what is needed here |
| `runs/ai/marketing-comms/src/guardrails/validator.py` | ADAPT | Typed-violation pattern | Rules are copy-length specific; only signatures were read |
| `cap-guardrails.md` grounding rule, via `runs/ai/marketing-comms/docs/cap-reuse.md:16` | ADAPT | The `cannot_verify` idea | Only the reference was read, not the source |

Marketing-comms has no retrieval to reuse (`runs/ai/marketing-comms/docs/DESIGN.md:93`, `:399-401`). Its "fits in a prompt" reasoning does not transfer to 4M tokens.

### Assumptions
- **Assumption:** No five-layer spec exists, but the consumer and cost of being wrong are clear enough to research the retrieval pipeline. — **Evidence:** request only. — **If wrong:** an unstated requirement could change the gate or answer states; run `/proto-design` before `/proto-plan`. — **Confidence:** Medium
- **Assumption:** The tool is read-only, single-turn, and never executes steps. — **Evidence:** request describes search and an answer. — **If wrong:** execution needs a separate safety design; chat adds query rewriting and memory risks. — **Confidence:** High
- **Assumption:** Every on-call engineer may read every indexed page. — **Evidence:** none. — **If wrong:** permissions must filter inside retrieval, and `not_found` could reveal that a restricted page exists. — **Confidence:** Low
- **Assumption:** Pages and queries may be sent to third-party embedding, rerank and model APIs. — **Evidence:** none. — **If wrong:** self-hosted models or a private endpoint change latency, cost and quality. — **Confidence:** Low
- **Assumption:** Pages contain no secrets worth excluding from indexing or traces. — **Evidence:** none; runbooks often risk this. — **If wrong:** ingestion needs secret scanning or redaction. — **Confidence:** Low
- **Assumption:** An answer within about 3 seconds is acceptable, with links sooner. — **Evidence:** incident context and spec budgets. — **If wrong:** rerank or generation may need to become optional. — **Confidence:** Medium
- **Assumption:** The wiki can provide a recursive export or API with stable IDs, revisions and change or delete events. — **Evidence:** "markdown pages" only. — **If wrong:** freshness needs periodic full reconciliation. — **Confidence:** Medium
- **Assumption:** The wiki mixes runbooks with other pages such as postmortems and designs. — **Evidence:** "across our platform wiki". — **If wrong:** page-type handling can be simpler; if right and ignored, a one-off postmortem action could be presented as a runbook step. — **Confidence:** Medium
- **Assumption:** Codes are not unique across all services. — **Evidence:** none. — **If wrong:** a literal hit becomes stronger evidence; if right, answers must show the service for each match. — **Confidence:** Low
- **Assumption:** Pages are mostly English. — **Evidence:** both example queries. — **If wrong:** stemming and embedding choices change. — **Confidence:** Medium
- **Assumption:** Incident tickets and postmortems can seed a golden set. — **Evidence:** typical on-call practice, not confirmed here. — **If wrong:** the first evaluation depends on synthetic queries, and its results should be treated as provisional. — **Confidence:** Medium

### Disconfirming Evidence
- **F1, fixed pipeline.** A query class that needs several hops, such as following a linked runbook, would contradict it. Nothing in the request shows that, and the course's LLM planner lost on both MRR and latency (`notes/11`). This has not been tested on real incident queries.
- **F2, literal path.** Good dense-only code retrieval would weaken the case for the literal path: bge-small found every code in one 18-page corpus (`notes/03`). But that test had few near-identical pages. Also, the absence guarantee comes from literal lookup even if dense ranking proves excellent.
- **F3, tokenizer.** I looked for a config that fixes this and found one, so it is a template default rather than a DuckDB limit. The probe used five synthetic documents.
- **F4, hybrid and rerank.** Contradicting evidence exists: RRF lowered MRR, and a reranker harmed recall on one corpus (`notes/03`, `notes/05`). Anthropic's positive numbers are vendor-reported on other corpora and measure top-20 retrieval failures, not abstention. Hence "measure as switches".
- **F6, gate.** Generation-level abstention could be good enough with newer models. The cited studies predate current models, and I found no current benchmark. But it would not remove the need for a gate here, because the cost of being wrong is high and the gate also saves a model call. Search found no direct evidence on thresholds for RAG abstention, so calibration remains an open empirical question.
- **F7, rendered steps.** Engineers may reject raw sections as too long during an incident, or the model may select the wrong section. Verbatim rendering also faithfully repeats a wrong or poisoned page: anyone with wiki write access can place a step in production's path, and no pipeline check detects that (`.claude/specs/agent-safety.md:82`). No user test was available.
- **F10, freshness.** If incident-time edits matter within minutes, a batch sync would be too slow. The request gives a daily change rate but not edit timing during incidents, and nothing here settles it.
- **F11, store.** Scale could be contradicted if the real chunk count is much higher because of long pages or attachments, or if multi-instance serving is required. Page length distribution is unknown. Probe vectors were random and timings came from one laptop.
- **F12, cost.** Most vendor prices came from search excerpts and third-party pages, and the Haiku 5.5 tiering appeared only in a search summary. Even if they are several times higher, the conclusion holds at this volume.

### Key Unknowns
1. **False-answer rate on this corpus.** This matters most. Whether scores can separate a right runbook from a near-miss has no answer until no-answer cases run on real pages.
2. **What counts as acceptable false-answer and false-abstention rates.** The request states the asymmetry but sets no target; someone must own that trade-off.
3. **Answer format.** Whether on-call engineers accept rendered sections as a "short answer", or need something shorter, is untested.
4. **Page mix and quality.** The share of real runbooks, duplicates, stale or conflicting pages, code usage and pages over the embedder limit are unknown.
5. **Access and data rules.** Page permissions, external API approval and secret handling are unknown.
6. **Wiki change feed.** Rename, delete and revision signals, and the realistic freshness limit, are unknown.
7. **Embedder and reranker choice.** Neither was tested on real codes. Reranker score semantics need checking before any are used as thresholds.
8. **Availability needs.** A tool used during incidents may fail in the same outage if it shares infrastructure with the affected platform. The dependency footprint was not assessed.

### Recommendation
The research supports a fixed, gated pipeline: literal lookup for error codes, hybrid BM25 and dense search for descriptions, measured reranking, a pre-generation evidence gate, and answers whose commands and steps come verbatim from the cited source, ending in `answer`, `partial`, `not_found` or `error`. A small store and exact scan are enough, and scale should not be the focus. Before committing to components, the planner should treat three things as the first proof points: a tokenizer test for present and absent codes, a labelled evaluation with enough realistic no-answer cases, and failure tests showing outages and stale indexes never read as "found nothing". The template's corpus and eval pieces are useful parts, but its RAG starter should not be taken as the design because its confidence signal does not gate anything. Open access, data-handling and risk-target questions should be settled through `/proto-design` or an equivalent owner decision before `/proto-plan` relies on them.
