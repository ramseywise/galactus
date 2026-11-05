# handbook-answers
Date: 2026-11-04
Status: RESEARCHED
Track: agent

## Research

### Summary
Use no retrieval layer: send the whole handbook, split into sections by its headings, with every question, and take the section reference from the citation on the answer. At about 10,000 tokens the handbook is too small for retrieval to save anything that matters (under $8 a month at most), while retrieval would add a way to miss the right section silently. The one real doubt is that a whole-document prompt may answer questions the handbook doesn't cover, so test that on 50+ real questions before launch. Add retrieval only if that test or later growth calls for it.

### Scope
Investigated: how the handbook reaches the model, where the section reference comes from, what the bot does when the handbook has no answer, and which assets in this repo apply.

Out of scope: Slack integration, hosting, final model choice, and the build plan (`/proto-plan`).

Track is `agent`: the bot calls a model and fits none, so the routing is not ambiguous (`.claude/skills/proto-research/SKILL.md`, Track routing).

### Findings

**1. The retrieval question is settled by size. Confidence: High on "don't build retrieval first"; Medium on answer quality until tested (Finding 6).**

40 KB at about 4 characters per token is about 10,000 tokens (estimate; the handbook was not available to count). Anthropic's guidance is that below 200,000 tokens "you can just include the entire knowledge base in the prompt", "with no need for RAG or similar methods" ([Contextual Retrieval, 2024](https://www.anthropic.com/news/contextual-retrieval)). This handbook is 20 times under that line, and being off by a factor of 2 changes nothing. That source is a vendor's rule of thumb, not a measurement, so Finding 6 tests it.

| Option | Input tokens per question | Can silently miss the right section? | Work when the handbook changes | Where the section reference comes from |
|---|---|---|---|---|
| **A. Whole handbook, split by section** | ~10,000 | No, the model always has it (it can still misread it) | Replace the file | Citation on the answer |
| B. Headings list plus a fetch-section tool | ~500 to 3,000 (estimate) | Yes, the model can pick the wrong section; adds a round trip and varies between runs (`agent-context.md:64`) | Replace the file | Section fetched |
| C. Hybrid or embedding RAG | ~600 (top 3 of 200-token chunks, as in Agri-Query) | Yes, the retriever can miss, with no signal to the reader | Re-chunk, re-embed, re-tune | Chunk metadata |

The kind of content also argues against chunking: questions such as notice periods or leave can depend on a rule in one section and an exception in another. Whole-document input keeps both in view. This last point is reasoning, not a measured result.

**2. Retrieval's usual payoffs are absent here. Confidence: High on the arithmetic; prices checked 2026-11-04.**

At 20 questions a day and 21 working days, that is 420 questions a month. Assuming a 150-token question and a 250-token answer, with [current list prices](https://platform.claude.com/docs/en/about-claude/pricing):

| Model | Whole handbook, no caching | Most retrieval could save (10,000 down to 600 input tokens) |
|---|---|---|
| Claude Haiku 5.5 | $0.48/month | $0.39/month |
| Claude Sonnet 5.5 | $9.58/month | $7.90/month |

- **Cost:** the saving is less than the upkeep of any index.
- **Scale and freshness:** 20 questions a day and two edits a year create no pressure on either. Replacing one file is the whole update.
- **Access control:** the repo context spec treats permission filtering as a security reason to filter before retrieval (`agent-context.md:83`). This does not apply if every employee may read the whole handbook (see Assumptions).

**3. Prompt caching is optional, and the default setting would not help. Confidence: Medium (assumes questions arrive evenly over an 8-hour day).**

Twenty questions in 8 hours is one every 24 minutes on average. With random arrivals, only about 19% come within the [default 5-minute cache lifetime](https://platform.claude.com/docs/en/build-with-claude/prompt-caching). At a 1.25x write price, that costs slightly more than no caching. The 1-hour option (2x write) would hit about 92% of the time and bring Sonnet 5.5 to roughly $3 to $4 a month. That is worth a line of configuration, but no design decision depends on it. Real questions probably cluster, which would raise hit rates.

**4. The section reference can be produced without retrieval. Confidence: High that the mechanism exists; Medium on fit until tried on the real file.**

Anthropic's [citations feature](https://platform.claude.com/docs/en/build-with-claude/citations) accepts a document as a list of content blocks, cites by block index, and does no further chunking. One block per handbook section therefore lets code map a citation straight to a heading. The only "chunking" this design needs is splitting on headings.

Limits the planner must carry forward:
- The docs guarantee citations are valid pointers into the document. They do not guarantee the passage supports the claim, so a wrong section can still be cited. HR reading the channel is the check for that.
- Citations cannot be combined with structured outputs, and JSON-only prompts can return few or no citations. The reply should be prose.
- A citation may be absent, so code must handle that case (Finding 5).
- Citations work with caching when `cache_control` is on the document block.
- If another provider is chosen, the fallback is to have the model name the section and have code check that name against the real headings.

**5. "Not in the handbook" must be a distinct outcome, but it doesn't need heavy machinery. Confidence: High on the need; Medium on the check being sufficient.**

The repo's collapse rule requires the system to keep "no evidence" separate from an answer, in structure and not only by asking the model to be careful (`agent-uncertainty.md` §2). The bot should treat an answer with no citation as "I can't find this in the handbook, HR will pick it up", and should treat a failed API call as an error, not as that same message.

The stated cost of a wrong answer is one HR follow-up in a channel HR already reads. Under the repo's cost table (`agent-uncertainty.md` §3), that does not justify a confidence gate, reranker or second-model verifier. Also, with no retrieval there is no retrieval score to set a threshold on.

**6. The real uncertainty is answer quality on the actual handbook, and it is cheap to measure. Confidence: High.**

The research cannot settle this without the handbook. A test set of 50 or more real questions fits the repo's guidance (real queries, 50 to 200 rows: `agent-eval.md:129,133`). It should score:
- correct answer and correct section
- correct refusal on questions the handbook doesn't cover (Agri-Query shows this is the weak spot)
- questions needing two sections
- results by where the answer sits in the file (start, middle, end), to detect the position effect

Retrieval metrics such as `rank_miss` don't apply. The failure labels `unsupported_claim` and `wrong_escalation` do (`agent-eval.md:114,116`). Twenty questions a day means Slack history probably already holds enough.

**What would change the recommendation:**
- The test shows errors that less context would fix, such as answers to uncovered questions or misses concentrated mid-document, and prompt changes don't fix them.
- The source grows by about an order of magnitude or gains several documents. The evidence does not agree on an exact limit: Anthropic says 200,000 tokens, while Agri-Query saw trouble at 59,000.
- Different employees may only see different policies, which would require filtering.

### Asset verdicts

The project is new, so the assets are this repo's template and specs. The Slack path through Composio (`copier.yaml:228`) was not assessed, as it isn't a retrieval question.

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| Template `rag` shape, `rag_agent` (`TEMPLATE.md:110`) | SKIP | The "answer only from the context, say so plainly otherwise" wording in `nodes/generate.py:6-8` | Its vector store, index build and retrieve node solve a problem this project lacks. |
| `rag_agent/nodes/retrieve.py`, `confidence.py` | SKIP | Nothing: both depend on similarity scores this design doesn't have | Fixed `k=5` (`settings.py.jinja:35`), and the confidence signal is explicitly "informational only", so it doesn't gate anything. |
| Corpus pipeline `core/pipelines/corpus/index.py`, `lg_agent` BM25 | SKIP | Nothing: splitting one file on headings is simpler than adapting a JSONL-to-DuckDB index | It exists to search a corpus, and this design doesn't search. |
| `evals/graders/citation.py` | ADAPT | `grade_answer_overlap` (`:107`) as a free smoke check | `grade_retrieval` (`:81`) doesn't apply. It checks retrieval rank, not section citations, so a section-match check would be new. |
| `runs/ai/marketing-comms/src/generate.py:107-117` | ADAPT | The source-delimiting and "treat as data" prompt pattern | Same need: answer only from supplied source material. Its fact-extraction pipeline doesn't carry over. |
| `.claude/specs/agent-eval.md` | REUSE | n/a | Its golden-set rules and failure labels apply, minus the retrieval gate. |
| `.claude/specs/agent-uncertainty.md` | REUSE | n/a | It supplies the abstention and cost-of-wrong rules used in Finding 5. |
| `.claude/specs/agent-context.md` §1a | ADAPT | Its failure modes and diagnostics | This recommendation departs from its 80% rule (see Disconfirming Evidence). Its cache note (`:141`) also needs a caveat: 5 minutes is only the default, and a 1-hour option exists. |

### Assumptions
- **Assumption:** No `/proto-design` spec is needed before this answer. The skill calls a missing layer answer a FRAME gap and says to stop, but nobody can be asked here and only one file may be written. Consumer and cost of wrong are stated in the request, and the retrieval question sits in the context layer. — **Evidence:** request; `SKILL.md:160-162` — **If wrong:** prompt, harness and HITL layers remain unspecified; run `/proto-design` before `/proto-plan`. — **Confidence:** Medium
- **Assumption:** Every employee may read the entire handbook, and one version applies to all. — **Evidence:** "one markdown file" — **If wrong:** per-country or per-grade rules can produce a confident answer from the wrong rule, and filtering by audience becomes necessary. — **Confidence:** Medium
- **Assumption:** A wrong answer really does end in a follow-up. — **Evidence:** request — **If wrong:** if HR misses one on a busy day and someone acts on a wrong notice period, the cost is higher than stated and Finding 5's light check may not be enough. This is the assumption most worth confirming with HR. — **Confidence:** Medium
- **Assumption:** The handbook is about 10,000 tokens and its headings are useful units for citing. — **Evidence:** 40 KB at about 4 characters per token; file not seen — **If wrong:** token count would need to be off by far more than expected to matter; poor headings would mean coarse or misleading section references, and would need a light edit or finer splitting. — **Confidence:** High on size, Medium on headings
- **Assumption:** Anthropic models, since no provider was named and this repo's stack uses the Anthropic SDK. — **Evidence:** `CLAUDE.md` Stack — **If wrong:** Finding 1 and the costs change little, but Finding 4 needs the fallback. — **Confidence:** Medium

### Disconfirming Evidence

**The strongest counter-evidence: Agri-Query. Looked for, found, and it limits confidence without reversing the call.** On one 165-page, ~59,000-token manual, [Hybrid RAG beat direct long-context prompting](https://arxiv.org/html/2508.18093v2) (English accuracy):

| Model | Full manual | Hybrid RAG |
|---|---|---|
| Gemini 2.5 Flash | 0.694 | 0.880 |
| Qwen 2.5 7B | 0.398 | 0.861 |

Gemini's specificity on the full manual was 0.500, so it answered about half of the unanswerable questions. Why it doesn't decide this case:
- The manual is about 6 times this handbook's size. The paper gives no tabulated results near 10,000 tokens (only plots, which I did not read).
- Most of its models are small quantized open models, unlike what this project would likely use. Gemini 2.5 Flash is the closest comparison, and it did better on the full manual than the others listed.
- Half of its questions were deliberately unanswerable, and they target fine detail. It doesn't test multi-section synthesis, where retrieval is weakest.
- Its authors note a single document, no significance testing, an unvalidated LLM judge, and different judge models for the two arms, which confounds this exact comparison.

It still justifies making refusal on uncovered questions a scored part of the test. I read this paper through a fetch tool's extraction of its text and tables, not the PDF directly.

**Position effects: real in older models, unmeasured for this case.** [Lost in the Middle](https://ar5iv.labs.arxiv.org/html/2307.03172) found GPT-3.5-Turbo at 75.8% with the answer document first, 53.8% in the middle and 63.2% last, at only about 3,000 tokens. So the size of this handbook does not by itself rule the effect out. But that setup used 2023 models and retrieved distractor passages, not one coherent document with headings. I looked for primary results on current models at around 10,000 tokens and found none; one secondary source claims large improvements, which I did not rely on. Hence the position breakdown in Finding 6.

**Long documents can also cause false refusals.** Anthropic reported [Claude 2.1 going from 27% to 98%](https://claude.com/blog/claude-2-1-prompting) on a planted-sentence test with one prompt change. The failure was refusal rather than wrong answers, and the test was at around 200,000 tokens on a 2023 model and used a deliberately out-of-place sentence. Weak relevance here, but the test should count wrong refusals too (`wrong_escalation`).

**This repo's own context spec points the other way.** `agent-context.md` says "it fits in the window" is not an argument for including something (§0), and that anything needed on fewer than 80% of turns should be fetched on demand (`:68`). No single section is needed on 80% of questions, so read literally, the rule favours option B. I am departing from it deliberately. Its motivating arithmetic is 250,000 tokens pre-loaded against 15,500 (`:62`); here the most that could be saved is about 10,000. Occupancy is around 5% of a 200,000-token window, against the spec's ~50% warning level (`:322`). If the test shows distraction errors, option B is the first alternative to try, because it needs no index.

**Could retrieval be needed for the section reference?** I checked, because the request's "says which section it used" sounds like it needs retrieval. Finding 4 shows it doesn't.

**Published handbook-specific evidence:** I searched for HR or handbook chatbot comparisons and found no benchmark. All external evidence here is from other document types.

### Key Unknowns
- **Actual quality on this handbook.** Unknown until the Finding 6 test runs. This is the deciding unknown.
- **Handbook structure:** heading depth, tables (leave accrual tables may be cited awkwardly), and cross-references. Not seen.
- **Audience variation** by country, grade or contract, and whether answers should defer to the employment contract. Notice periods in particular often vary by contract.
- **What may be logged and sent to a provider.** Questions in an HR channel can include health, pregnancy or dismissal details. This doesn't affect retrieval, but the skill's upstream design stage treats redaction as mandatory, and nobody has answered it. It also needs a check on the provider's data terms.
- **Share of questions the handbook really answers.** "About 20 a day" is the request's figure. A large uncovered share would make the refusal path the main path.
- **Whether follow-up questions in a thread need history.** Not stated; it would be the only part of the context that grows.

### Recommendation
The research supports no retrieval layer: send the full handbook with each question, split by heading so citations resolve to sections, and treat an uncited answer as "not found, HR will follow up". It does not support a vector store, BM25, reranker or confidence gate at this size, since they could save at most about $8 a month while adding a silent way to miss the right section. Confidence is High that retrieval shouldn't come first, because the choice is cheap to reverse and a wrong answer costs one follow-up, but only Medium that whole-document answers will be good enough, because the closest published comparison (at 6 times the size, with mostly smaller models) favoured RAG and no evidence exists for this handbook. So the planner should make a test of 50+ real Slack questions the first step, score refusals, multi-section questions and answer position, and treat a headings-plus-fetch design as the next option if it fails. Confirm with HR the assumptions on audience variation and on wrong answers always being caught, and settle what may be logged, before planning proceeds.
