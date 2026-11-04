# Runbook search retrieval pipeline
Date: 2026-11-04
Status: RESEARCHED
Track: agent

## Research

### Summary
Build two search paths and a checked answer step. Error codes get a literal lookup that returns `not_found` when the code is absent; descriptions get BM25 plus dense search over whole pages, fused with RRF; then the model must either quote steps verbatim from a retrieved page or decline, and code checks each quote. No retrieval score could detect a missing runbook in my tests (86–98% of those queries still passed), so a reranker, a score threshold and a vector database all stay out. The largest open risk is the model's decline decision, which is untested and should be the first thing measured.

### Scope
**Investigated:** retrieval, the "found nothing" decision, step-invention controls, index freshness, cost and latency, and reusable template assets. I ran a throwaway test on `prometheus-operator/runbooks` (commit a685d14), plus synthetic pages I generated.

**What the test can and cannot show:**
- The corpus is 108 real pages, about 2% of the wiki's scale, and they are short: a mean of 143 words against about 667 tokens per wiki page (4M / 6,000).
- I wrote the 50 paraphrase queries, the 30 never-in-corpus queries and the 2,000 near-duplicate code pages myself. The paraphrases deliberately avoid title words, which biases them against BM25.
- Hit rates at n=50 have wide uncertainty.
- No Claude model was called, because no API key was supplied. Everything about model behaviour is unmeasured.

**Out of scope:** UI, on-call tool integration, wiki content quality, and implementation sequence.

### Smallest design
The least that meets the request:

1. **Sync:** keep a local copy of the wiki pages in a BM25 index.
2. **Search:** BM25 over whole pages, top 5.
3. **Answer:** the model answers only from those pages and links the pages used, or says it found nothing.

That design fails this request in the ways below. Each component added to it names the failure and its evidence:

| Added component | Failure it prevents | Evidence |
|---|---|---|
| Literal code lookup that stops on zero hits, before any fusion | An absent code returns neighbouring pages. `E6305 on the service` returned three unrelated NodeNetwork pages under OR search, and dense search returned a page for 100/100 absent codes | Test |
| Dense search fused with RRF for descriptions | BM25 misses paraphrases such as `pods keep restarting over and over`: r@5 .78 vs .88, discordant pairs 6 v 1 | Test (biased, see Finding 2) |
| Model makes an explicit sufficient/insufficient decision over page text | Scores cannot detect a missing runbook: 86–98% false-pass when the right page is deleted | Test for the failure; the decision itself is untested |
| Steps returned as verbatim quotes with a page ID, checked by code; any failed check gives no answer | Invented steps. Only 25 of 293 real steps (9%) carry a code span, so checking commands alone misses most steps | Test on the check; model behaviour untested |
| Typed outcomes: `answer`, `not_found`, `error` | A search failure reading as "found nothing". Raw FTS5 MATCH raises on `E-4021` and on `payments queue backing up?` | Test; `.claude/specs/agent-uncertainty.md` §2 |
| Sync handles deletes as well as changes | Retired procedures keep being served. `course/generative-ai/02-rag-retrieval/notes/01-rag-pipeline.md` describes this failure | Source |
| Long pages matched by section (or an embedder that covers the whole page), returning the parent page | Silent truncation. The mean wiki page (about 667 tokens) exceeds the 512-token limit the course note gives for bge-base (`course/generative-ai/02-rag-retrieval/notes/03-keyword-semantic-and-hybrid-search.md`) | Source and my arithmetic; my short test corpus did not exercise it |
| Show each page's last-modified date and a stale-index signal | A correct quote of an out-of-date page. Faithful is not correct (`course/generative-ai/08-eval/notes/07-evaluating-rag-and-grounding.md`) | Source; the control is my reasoning |
| On description `not_found`, optional links labelled "closest pages, not checked"; none on the code path | A flat dead end when r@5 is .88 but the model declines. The code path has no such case, because a literal miss is exact | My reasoning; product decision |

### Findings

**1. Route code-shaped queries to a literal lookup, and stop on zero hits. Confidence: High for the routing; Medium for the regex, until real code shapes are seen.**
- With the code present across 2,000 near-duplicate pages, BM25 r@1 was 1.00 and dense r@1 was .52, with r@5 .76.
- With the code absent (100 codes), BM25 returned zero rows every time, which is a true "not found". Dense and RRF returned a page every time. Dense's top page shared at least 2 digit positions with the query 62% of the time, against about 5% by chance (my calculation), so it looks plausible while being wrong.
- Dense score cannot detect this: AUROC .664 (CI .587–.738), mean top score .699 present vs .689 absent.
- The literal check must run before fusion, because RRF always returns something.
- A query with an absent code plus words should report the code as not found and invite a rephrase. That is the smallest safe behaviour.
- **Code variants do not unify.** `E4021` does not match `E-4021` or `ERR_4021` under either FTS5 tokeniser tested. Bare `4021` matches the variants under `unicode61` and nothing under `tokenchars '-_'`. The regex and normalisation must come from the real wiki. A wrong `not_found` here sends an engineer away from a runbook that exists.
- The course makes the same point with `EADDRNOTAVAIL (99)`, and with `HTTP-404` returning an honest nothing (`course/generative-ai/02-rag-retrieval/notes/03-keyword-semantic-and-hybrid-search.md`).

**2. Use BM25 + dense with RRF over whole pages for descriptions. Confidence: Medium.**

| Corpus | Method | r@1 | r@3 | r@5 | MRR |
|---|---|---|---|---|---|
| Real, 108 pages | BM25 | .50 | .68 | .78 | .625 |
| | Dense | .58 | .86 | .88 | .719 |
| | RRF | .66 | .84 | .88 | .769 |
| | RRF + cross-encoder | .66 | .84 | .88 | .748 |
| | RRF over sections | .58 | .88 | .90 | .725 |
| Padded, 2,108 pages | BM25 | .56 | .70 | .84 | .664 |
| | Dense | .56 | .78 | .78 | .668 |
| | RRF | .66 | .86 | .90 | .763 |
| | RRF + cross-encoder | .66 | .82 | .86 | .747 |

- RRF is the stable choice. On real pages it ties dense at r@5 and leads at r@1. With near-duplicates added, dense fell .88→.78 while RRF held (RRF vs dense discordants 7 v 1).
- OR semantics are required: implicit AND returned zero pages for 98% of paraphrases. It follows that **zero hits cannot be the abstention signal for descriptions**; OR returned zero pages for 0%.
- Sectioning gained nothing on these short pages, but that does not transfer to a wiki whose pages are about 3.6× longer. See the section row above and Key Unknowns.
- User text must be tokenised and quoted before it reaches FTS5.

**3. Do not use a score threshold as the "found nothing" gate. Confidence: High that the scores tested fail on the dangerous case; Medium on the magnitudes.**

False-pass rate is measured at the threshold that keeps 95% of answerable queries.

| Signal | Page deleted: AUROC [95% CI] | False-pass | Never in corpus: AUROC [95% CI] | False-pass |
|---|---|---|---|---|
| Dense | .648 [.542–.754] | .92 | .839 [.746–.921] | .90 |
| Dense gap | .571 [.456–.679] | .98 | .613 [.484–.731] | .967 |
| BM25 | .653 [.547–.754] | .88 | .855 [.763–.931] | .633 |
| Cross-encoder | .672 [.563–.772] | .86 | .922 [.858–.973] | .40 |
| Cross-encoder gap | .555 [.441–.668] | .92 | .729 [.609–.833] | .867 |

- The dangerous case is a missing runbook with a sibling page present. After deletion, `pods keep restarting over and over` ranks `AlertmanagerClusterCrashlooping` first, and `cluster lost quorum and the API went read only` ranks `KubeAggregatedAPIErrors` first. Scores cannot separate these.
- Even the best signal on the easy case lets 40% through. Drop the threshold for now and record scores for later analysis.
- This rules out the CRAG/threshold convention as the gate here (`.claude/specs/agent-safety.md` §1). What survives from that spec is the collapse rule in `.claude/specs/agent-uncertainty.md` §2: retrieve, evaluate evidence, answer or abstain. The evaluation has to read page text.

**4. Have the model select verbatim steps, and have code verify them; do not let it write steps. Confidence: High for the check itself; Low for end-to-end behaviour, which is untested.**
- A quote check on 238 real prose steps, normalising whitespace and case, passed all 238 unmodified and 0 of 238 with one word changed.
- 72 of 76 mutated commands were flagged. I did not inspect the other 4; a mutation can land on text that is still on the page.
- The check also confirms each cited page ID is in the retrieved set. Code citation checks are the course's recommendation (`course/generative-ai/08-eval/notes/07-evaluating-rag-and-grounding.md`), and `.claude/specs/agent-safety.md` §1 makes a structural output check mandatory.
- Any generated connective prose is an unverified surface. The answer should be page title, quoted steps and link, plus fixed template text.
- **What the check does not catch:**
  - a real step quoted from the wrong page, such as a sibling service;
  - a dropped precondition, or steps quoted out of order;
  - an accurate quote of a stale or wrong page.

  Only the sufficiency decision and the visible source page address these. This is why Key Unknown 1 comes first.
- **Unknown false-reject rate.** The check will turn some correct answers into no answer if the model paraphrases or the markdown is awkward. That failure is safe but costs usefulness, and it needs measuring.

**5. Keep the index on simple local infrastructure, and sync often. Confidence: High on this scale; Medium on the embedder.**
- Brute-force vector search took 0.05 ms per query at 6,000×384, and 0.51 ms using 82 MB at 20,000×1024.
- FTS5 at 6,000 pages × about 450 words built in 0.2 s, queried in 3.45 ms, and replaced 50 pages in 68.7 ms.
- Embedding 50 real pages took 2.25 s on a laptop CPU.
- The course places the need for ANN past about 100k vectors (`course/generative-ai/02-rag-retrieval/notes/04-vector-databases-and-ann.md`), and `.claude/skills/proto-scope/reference/data-pipeline-patterns.md` already steers small corpora to simple backends. A vector database is not needed.
- 50 changes a day is about 33k tokens, roughly $0.002 at voyage-4's $0.06/M list price (my calculation). A full re-embed of 4M tokens costs about $0.24. Sync frequency is therefore limited by the wiki's change feed, not by cost. Deterministic IDs make ingestion idempotent (`course/generative-ai/02-rag-retrieval/notes/04-vector-databases-and-ann.md`). Comparing page hashes against the current page listing also catches deletes (my reasoning).

**6. Do not optimise model cost, and do not cache answers. Confidence: High on cost; the cache call is my reasoning.**
- About 29 queries a day × (about 4k input + 500 output tokens) at the $10/$50 per MTok top-tier list price comes to about $1.90 a day (my calculation).
- `.claude/specs/models.md` says to pay for judgment, and a wrong sufficiency decision is the expensive error here, so cost is not a reason to choose a weaker model. Latency may be. It was not measured and no target was stated.
- A cache saves almost nothing at 29 queries a day, and a stale cached procedure is the failure this system exists to prevent.
- If the model is down, degrade to labelled links, with a clear statement that no answer was generated. Do not report `not_found`.

**7. The eval must score retrieval and the abstention decision separately, and false-answer rate is the primary metric. Confidence: High.**
- Mean recall hides this system's main risk. The golden set needs four row types: code present, code absent, page deleted, and never in corpus. Hold-one-out page deletion is a cheap way to build the third.
- Score generation only on eligible rows, and make k match what reaches the prompt (`course/generative-ai/08-eval/notes/07-evaluating-rag-and-grounding.md`). A first set of 20–50 rows is enough (`course/generative-ai/08-eval/notes/03-eval-datasets.md`).
- If "I don't know" scores the same as a wrong answer, guessing wins, so the grader must reward declining (`course/generative-ai/08-eval/notes/04-graders.md`). The spec's failure labels already fit (`.claude/specs/agent-eval.md` §4).
- 200 searches a week is too few to wait for, so seed the set from past incident queries. A few weeks of real traffic can then replace my paraphrase bias.

### Course grounding
- query: `hybrid retrieval BM25 and vector search for exact identifiers and error codes` (domain=course) → 10 hits — DEGRADED RETRIEVAL
  - used: course/generative-ai/02-rag-retrieval/notes/03-keyword-semantic-and-hybrid-search.md
  - used: course/generative-ai/02-rag-retrieval/notes/04-vector-databases-and-ann.md
- query: `abstain when retrieval finds nothing, grounded generation, citations and refusal gate` (domain=course) → 6 hits — DEGRADED RETRIEVAL
  - used: course/generative-ai/08-eval/notes/04-graders.md
  - used: course/generative-ai/08-eval/notes/07-evaluating-rag-and-grounding.md
- query: `keeping an index fresh: incremental re-indexing, deletes, stale documents` (domain=course) → 6 hits — DEGRADED RETRIEVAL
  - used: course/generative-ai/02-rag-retrieval/notes/01-rag-pipeline.md
- query: `evaluating retrieval recall@k golden set unanswerable questions faithfulness` (domain=course) → 6 hits — DEGRADED RETRIEVAL
  - used: course/generative-ai/08-eval/notes/07-evaluating-rag-and-grounding.md
  - used: course/generative-ai/08-eval/notes/03-eval-datasets.md
- query: `when is a reranker worth adding; whole document versus chunks context size` (domain=course) → 6 hits — DEGRADED RETRIEVAL
  - used: course/generative-ai/02-rag-retrieval/notes/05-chunking-query-parsing-and-reranking.md

### Asset verdicts

Paths below are relative to `template/_scaffold/{{ py_project_root }}/`, with `AGENTS` standing for `{{ ai_source_root }}/agents/`.

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `AGENTS/rag_agent/graph.py`, `nodes/` | SKIP | Nothing from the graph or nodes; the separable parts are the corpus pipeline and golden-QA eval, which have their own rows | `graph.py:16-18` runs retrieve → generate with no gate. `nodes/retrieve.py:11` is dense-only at a fixed k. `nodes/generate.py:17` turns empty context into `"(no matching articles found)"` and still calls the model, which is exactly the collapse site this request forbids |
| `AGENTS/rag_agent/confidence.py` | SKIP | Nothing, after checking: `score()` ignores its threshold | Informational only by its own docstring (`confidence.py:1`), and Finding 3 removes score gating anyway |
| `AGENTS/rag_agent/vectorstore.py.jinja` | SKIP | The per-backend upsert code, if a persistent store is later needed | Exposes `upsert` and `similarity_search` only; a grep found no delete or keyword method (grep only; the file was not read in full). Brute force is enough at this scale |
| `AGENTS/rag_agent/build_index.py` | ADAPT | n/a | Upsert only (`:35`), so deleted pages would remain. Needs delete handling |
| `core/pipelines/corpus/index.py` | ADAPT | n/a | **As shipped it would break the code path.** With the same default `create_fts_index` call (`:45`), DuckDB returned zero rows for `E4021` and `E4012` on a 3-page test, even though both codes were in the pages: a false "found nothing". Setting `ignore='(\\.|[^a-z0-9])+'` fixed it. Its full rebuild does handle deletes. Tested on DuckDB 2.0.0; the template's pinned version was not checked. FTS5 is the tested alternative |
| `core/pipelines/corpus/ingestion.py`, `preprocessing.py` | ADAPT | n/a | Markdown ingestion is a starting point. Only the ingestion title handling was seen, not the full files |
| Template golden-QA eval, `tests/unit/core/test_retrieval_quality.py` | ADAPT | n/a | Provides a retrieval-eval starting point. The shipped sample corpus is appliance manuals (`data/raw_corpus/`, file names only), so the rows must be replaced. I did not read the eval or test code |
| ragas 0.4.3 via the template | SKIP | Metric definitions | The template catalog records a broken import, and the code checks in Finding 4 do not need it |
| `runs/ai/marketing-comms/docs/cap-reuse.md:16` grounding rule | ADAPT | n/a | The concept carries: every claim traces to a passage, else `cannot_verify`. The run has no retrieve stage (`docs/DESIGN.md:93,399`) so no code carries. `src/guardrails` was not read |
| `.claude/skills/proto-scope/reference/data-pipeline-patterns.md` | ADAPT | n/a | Batch ingest fits, but its slowly-changing-content assumption is weaker at 50 changes a day |
| `.claude/specs/agent-uncertainty.md`, `agent-context.md`, `agent-eval.md`, `agent-safety.md`, `agent-architecture.md` | REUSE | n/a | Reused as conventions, except the threshold gate (Finding 3) and any stage without a measured failure, which `agent-context.md` §1a itself permits |
| SQLite FTS5 | REUSE | n/a | Tested with `porter unicode61 tokenchars '-_'`; meets the latency and update needs |
| `fastembed` with `BAAI/bge-small-en-v1.5` | ADAPT | n/a | Works locally for testing. Not validated as the production embedder, and long pages need handling |

### Assumptions
- **Assumption:** Every on-call engineer may read every page, so no per-page permission filter is needed. — **Evidence:** none stated; the request says "platform wiki". — **If wrong:** the filter must be pushed into both searches (`.claude/specs/agent-context.md` §1a), or the system leaks restricted pages. — **Confidence:** Medium
- **Assumption:** Pages may be sent to the model and any embedding vendor. — **Evidence:** none. Runbooks commonly hold hostnames and sometimes secrets (my reasoning). — **If wrong:** this forces a local embedder and a different model hosting route, or a redaction step. — **Confidence:** Low
- **Assumption:** The wiki can be exported as markdown with a usable change and delete feed, or at least a listing that can be diffed. — **Evidence:** the request gives counts only. — **If wrong:** full re-crawls stay cheap (Finding 5), but freshness gets worse. — **Confidence:** Medium
- **Assumption:** Error codes have recognisable shapes. — **Evidence:** one example, `E4021`. — **If wrong:** codes fall through to the description path, where an absent code gets neighbour pages. — **Confidence:** Medium
- **Assumption:** Pages are mostly English. — **Evidence:** the examples only. — **If wrong:** the stemmer and embedder choices change. — **Confidence:** High
- **Assumption:** An answer within a few seconds is acceptable during an incident. — **Evidence:** none stated. — **If wrong:** the design may need streaming or a faster model. Links can come back before the answer regardless, since search takes milliseconds. — **Confidence:** Medium
- **Assumption:** Wiki editors are semi-trusted, and page text is data rather than instructions. — **Evidence:** `.claude/specs/agent-safety.md` §1. — **If wrong:** a malicious page could influence the sufficiency decision. Quote checking would not stop a malicious step that really is on the page. — **Confidence:** Medium
- **Assumption:** This is not a FRAME gap, although no `/proto-design` spec exists and nobody could be asked. — **Evidence:** the request names the consumer (on-call engineers) and the cost of being wrong (a step run on production). — **If wrong:** run `/proto-design` before planning; the layer choices above are my inference. — **Confidence:** Medium

### Disconfirming Evidence
- **Finding 1 (literal code path).** Contradicted if codes rarely appear literally in pages, or if variants dominate. I tested variants and they do break matching, which is why this is Medium on the regex. My code pages are synthetic templates, so the 1.00 and .52 figures are artificial. Direction is supported by Anthropic's "TS-999" example in its Contextual Retrieval post. I found no rigorous identifier benchmark.
- **Finding 2 (hybrid).** The evidence is mixed:
  - The course's own run on 18 pages found RRF did not raise recall and lowered MRR, and a DPR example lost 1.8 points on NQ (`course/generative-ai/02-rag-retrieval/notes/03-keyword-semantic-and-hybrid-search.md`).
  - BM25 was nearly level with RRF on the padded corpus (r@5 .84 vs .90, discordants 3 v 0), on queries biased against it.
  - Dense ties RRF at r@5 on real pages.
  - So hybrid is not proven better than either single method on real wiki queries. It is kept because the cost is small, and because each single method failed one test. The real-corpus eval could still remove a branch.
- **Finding 2 and reranker cut.** Three sources favour reranking: Anthropic reports failures falling from 2.9% to 1.9% with rerank; the non-course wiki page "RAG Retrieval Strategies" reports hybrid 58% → 68% on a single Danish corpus; and Zhao et al. (via `course/generative-ai/02-rag-retrieval/notes/05-chunking-query-parsing-and-reranking.md`) find answer quality falls as lists grow. My test found net zero on real pages (3 v 3) and slightly worse on padded pages (r@5 .90 → .86), at 343 ms per query. That test used one general model on one small corpus, and the course records the same domain-mismatch pitfall. This cut is the likeliest to reverse at 6,000 pages, so it sits in Test later with a signal.
- **Finding 3 (no score gate).** Contradicted if scores separate better at 6,000 pages or on domain-tuned models. Literature partly supports my result: a 2025 JTIE paper on SQuAD 2.0 reports evidence-calibration AUROC .5475. A preprint (arXiv 2609.22056) claims score-distribution features do better, and I did not test those. The cross-encoder's .922 on never-in-corpus queries suggests a floor could catch easy cases, so it is in Test later.
- **Finding 4 (model decides, code checks).** This is the weakest link. NoMiracl reports that LLMs identify unanswerable questions poorly, which bears directly on the chosen gate. I did not run any model, so this risk is neither confirmed nor ruled out here. My verbatim-check result is close to true by construction: it shows the check works, not that models pass it or that answers are useful. I could not read the Claude Citations documentation, so whether it could replace some of this check is unknown.
- **Finding 5 (no vector DB).** Contradicted by a hard requirement for concurrent multi-process writes, or by section-level vectors passing about 100k. At 4M tokens and 512-token sections, the count is on the order of 10k. A brute-force test used random vectors, so latency says nothing about quality. Existing Postgres would be a fair reason to use it (`course/generative-ai/02-rag-retrieval/notes/04-vector-databases-and-ann.md`); blog sources note `ts_rank` is weaker than BM25.
- **Finding 6 (no cache).** Contradicted if bursts during major incidents repeat the same query with a hard latency need. There is no traffic data, and the top-tier price is an upper bound I did not compare with lower tiers (those prices could not be obtained).
- **Finding 7 (eval).** Contradicted if real queries are nearly all answerable, which would make recall matter more. Even then, the stated cost of a false answer keeps it primary.

### Key Unknowns
1. **Model false-answer rate on page-deleted queries.** Measure this first; the design rests on it. If it is high, the safe fallback is links without answers.
2. **Correct-answer rate after the quote check**, meaning how often true answers are rejected.
3. **Real code shapes and variants** in the wiki, including how many codes appear in tables or as ranges.
4. **Page length distribution** and how section structure varies. The mean exceeds common embedder limits, and my test corpus topped out at 699 words.
5. **Real query mix:** codes vs descriptions, and how many have no runbook.
6. **Whether retrieval numbers hold at 6,000 pages**, and which embedder to use. Voyage list prices are known, but quality on this wiki is not.
7. **Change feed and export** capability, and what sync lag is acceptable.
8. **Secrets in pages** and whether vendors are permitted.
9. **Claude Citations behaviour with structured output.** The documentation could not be read this session, so this is unverified. The design does not depend on it, because the check is local code.
10. **The right k.** RRF r@10 was .94 real and .90 padded vs r@5 of .88 and .90, and the wiki's pages are longer. `.claude/specs/agent-context.md` §1a calls fixed k a bug, but I found no failure that justifies a dynamic k yet.

### Test later
| Component | Signal that would justify it |
|---|---|
| Reranker | Real-corpus eval shows rank misses, where the right page is in the top 20–50 but not the top 5 |
| Contextual prefixes on chunks | Recall is low on long pages specifically; Anthropic's result assumes larger documents than these |
| LLM query expansion, multi-query, HyDE | Misses are vocabulary gaps like `dead man's switch heartbeat stopped`, and real queries repeat them |
| Score floor as an extra early exit | The model is observed answering never-in-corpus queries that a floor would have caught (cross-encoder AUROC .922 there) |
| Dynamic k | The eval shows answerable queries lost between ranks 5 and 10 |
| Vector database / ANN | More than about 100k vectors, or concurrent-write needs |
| Answer or retrieval cache | Measured repeated queries with a latency problem, and an invalidation story |
| Query router beyond the regex | Code-shaped queries are misrouted in real traffic |
| Graph or agent framework, retry loops | A second retrieval round demonstrably rescues queries; three branches do not need it |
| NLI or second-model verifier | Quote-passing answers from the wrong page show up in the eval or in use |
| Live re-fetch of the page at answer time | Answers are observed quoting text changed since the last sync |
| Per-page permission filter | The wiki turns out to have restricted pages |

### Recommendation
Build retrieval as two deterministic paths and a checked model step, not as one RAG pipeline with a confidence score. Treat code-shaped queries as a literal lookup whose miss is a final `not_found`; treat descriptions with BM25 and dense search fused by RRF over whole pages, making sure long pages are fully represented; and let the answer consist only of steps the model quoted and code verified, with search failures kept distinct from "found nothing". Leave out the reranker, score thresholds, vector database and caches until the listed signals appear. Before committing to the answer step, measure how often the model answers when the right page has been removed, since that is the one risk the retrieval design cannot reduce and nothing here has tested it; if that rate is not acceptable, the same pipeline can ship as ranked links with no generated answer. Do not take the template's `rag_agent` or its default DuckDB tokeniser unchanged: the first has no gate and the second reported present error codes as missing.
