# Evaluation Approaches

How you'll know your AI is actually working. The eval approach determines whether
you can confidently ship, catch regressions, and prove value to the nonprofit.
This choice is made early (during discovery/scoping) because it shapes what data
you need to collect from day one.

---

## Quick Comparison

| Approach | Setup effort | Confidence level | Best for |
|----------|-------------|-----------------|----------|
| Golden-set grading | Medium (need curated Q&A pairs) | High (repeatable, automated) | Retrieval, factual Q&A |
| LLM-as-judge | Low (prompt-based) | Medium (subjective, variable) | Generation quality, tone |
| User feedback loops | Low (integrate thumbs up/down) | Medium-High (real signal) | Any user-facing system |
| Manual review | None | Varies (depends on reviewer) | Early prototypes, one-off demos |
| Heuristic metrics | Low (automated) | Medium | Pipeline reliability, latency |

---

## Golden-Set Grading

### What it is
A curated set of question-answer pairs (the "golden QA set") that represents what
the AI should be able to handle. The eval harness runs all questions, compares
answers to expected outputs, and scores metrics like hit_rate and MRR (Mean
Reciprocal Rank). Automated, repeatable, runs in CI.

### When to use it
- The AI answers factual questions from a known corpus
- You can define "correct" objectively (the answer is in document X, section Y)
- You want automated regression testing (catch when updates break retrieval)
- The project has a retrieval/RAG component

### When NOT to use it
- Answers are subjective (tone, style, creativity)
- There's no corpus yet (nothing to write questions about)
- The AI's job is to take actions, not answer questions

### Complexity rating
**Multi-sprint** — needs: 10-50 curated Q&A pairs (each with: question, expected
answer, source document), ingestion of the source documents, an eval runner that
grades hits vs. misses.

### How to get started
1. Ask the nonprofit: "What are the 10 most common questions your staff/clients ask?"
2. Find the correct answer in their documents (cite the source)
3. Format as `golden_qa.jsonl` (one JSON object per line: question, expected_answer, source_article)
4. The template's eval harness (`make eval-heuristic`) handles the rest

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `project_type` | `rag` | Golden-set grading is native to RAG projects |
| (auto-included) | — | The eval harness ships with every full scaffold |
| `optional_features` | `[ragas]` (optional) | Adds LLM-judge grading alongside heuristic metrics |

### What the template gives you
- `evals/pipelines/run.py` — orchestrates eval runs per retrieval backend
- `evals/targets.yaml` — metric thresholds (`hit_rate: 0.8`) that `make eval-gate` enforces
- `data/corpus/golden_qa.jsonl` — where your Q&A pairs live
- `evals/graders/` — heuristic scorers (hit_rate, MRR, answer_overlap)
- `make eval-heuristic` (run evals) + `make eval-gate` (fail CI if below targets)

### Trade-offs
- **Pro:** Fully automated; catches regressions; quantifiable ("we're at 85% hit_rate"); no LLM cost per eval run (heuristic grading)
- **Con:** Only as good as the golden set (if questions aren't representative, metrics lie); time investment to curate; doesn't measure generation quality
- **Key insight:** Start with 10 pairs. Bad eval with 10 real questions beats no eval with plans for 500.

---

## LLM-as-Judge

### What it is
A separate LLM call evaluates the AI's output against criteria (relevance,
accuracy, helpfulness, tone). The judge LLM scores each response on a scale or
as pass/fail. More flexible than heuristic grading but more expensive and variable.

### When to use it
- Output quality is subjective (summaries, drafts, recommendations)
- You need to evaluate tone, completeness, or style — not just factual accuracy
- You want automated scoring but can't define "correct" with exact string matches
- You're evaluating generation (documents, summaries) not retrieval (finding sources)

### When NOT to use it
- You can define "correct" objectively (use golden-set instead — cheaper, more reliable)
- Budget is very tight (each eval call costs money)
- You need deterministic results (LLM judges are inherently variable)

### Complexity rating
**Multi-sprint** — needs: evaluation criteria (rubric), a judge prompt, sample
inputs/outputs to calibrate against, integration with the eval runner.

### How to get started
1. Write 3-5 quality criteria: "Is the summary < 200 words? Does it include all action items? Is the tone professional?"
2. Create 5-10 sample inputs with human-graded "good" outputs
3. Write a judge prompt that scores against your criteria
4. Run the judge on your sample set; calibrate until it agrees with human grades

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `optional_features` | `[ragas]` | RAGAS provides LLM-judge grading infrastructure |
| `optional_features` | `[promptfoo]` | Promptfoo supports LLM-as-judge via config |

### What the template gives you
- `evals/graders/ragas_grader.py` — RAGAS-based LLM judge (when `include_ragas_grader`)
- `promptfoo.config.yaml` — Promptfoo eval harness with assertion-based scoring (when `include_promptfoo`)
- Both integrate alongside (not replace) the heuristic golden-set grading

### Trade-offs
- **Pro:** Evaluates subjective quality; flexible criteria; catches subtle regressions in tone/style
- **Con:** Costs money per eval run; non-deterministic (same input may score differently); requires calibration; judge can be wrong
- **Recommendation for DSSG:** Use as a complement to golden-set, not a replacement. Run heuristic grading (free, fast) in CI; run LLM-judge on demand for quality audits.

---

## User Feedback Loops

### What it is
The AI's actual users rate responses (thumbs up/down, star rating, "was this helpful?")
or implicitly signal quality (did they use the answer? did they ask a follow-up?).
Real signal from real usage.

### When to use it
- The system is deployed and has real users
- You want to know if the AI is actually helpful (not just technically correct)
- You're past the prototype phase and need ongoing quality monitoring
- The user base is engaged enough to provide feedback (even passively)

### When NOT to use it
- Pre-deployment (no users yet — use golden-set or LLM-judge)
- Users won't engage with feedback UI (too busy, too many pop-ups)
- You need immediate automated gating (feedback is slow and sparse)

### Complexity rating
**Multi-sprint** (to implement) — needs: feedback UI component, storage for
feedback data, dashboard or alerting on quality trends.

### How to get started
1. Add a simple thumbs up/down after each AI response
2. Store: timestamp, user_id, query, response, rating
3. Review weekly: what's getting thumbs down? Why?
4. Use thumbs-down cases to expand your golden QA set (real failures → new test cases)

### Maps to copier choices

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `project_type` | `chat_app` | Feedback loops fit conversational interfaces |
| `agent_memory` | `conversation` or `long_term` | Need to store context alongside feedback |
| `vector_backend` | `postgres` | Store feedback in the same Postgres as app data |

### What the template gives you
- No direct feedback infrastructure (this is application-specific)
- `agents/*/models.py` — Pydantic models are the extension point for adding a `FeedbackEvent` schema
- The eval harness can consume exported feedback as additional test cases

### Trade-offs
- **Pro:** Real signal from real users; catches issues automated eval misses; builds a ground-truth dataset over time
- **Con:** Slow (days/weeks to accumulate); sparse (most users don't rate); biased (angry users rate more); requires deployment first
- **Best practice:** Combine with automated eval. Golden-set catches regressions immediately; feedback catches "the AI is technically correct but unhelpful" over weeks.

---

## Manual Review

### What it is
A human (domain expert, program manager, or the volunteer team) reviews AI outputs
and judges quality. No automation, no infrastructure — just eyeballs.

### When to use it
- Early prototype phase (< 2 weeks in)
- You're still figuring out what "good" looks like
- The evaluation criteria haven't been defined yet
- Demo preparation (hand-pick the best examples)

### When NOT to use it
- Past prototype phase (doesn't scale)
- You need repeatable measurements (manual is inconsistent)
- You're making ship/no-ship decisions (too subjective without criteria)

### Complexity rating
**Weekend sprint** — literally just using the system and deciding "is this good?"

### How to get started
1. Use the system for 10-20 real queries
2. For each response, note: correct? helpful? would you show this to the nonprofit?
3. Identify patterns in failures
4. Use those patterns to define automated evaluation criteria (transition to golden-set or LLM-judge)

### Maps to copier choices
No specific copier implications — manual review is a process, not infrastructure.

### Trade-offs
- **Pro:** Zero setup; catches nuance that automated metrics miss; builds intuition about what "good" means
- **Con:** Doesn't scale; not repeatable; varies by reviewer; can't run in CI; blocks deployment if you require it for every change
- **Upgrade path:** Manual review → identify failure patterns → write golden QA pairs from real failures → automate with golden-set grading

---

## Heuristic Metrics (Pipeline Health)

### What it is
Automated measurements of system behavior: latency (how fast?), error rate (how
reliable?), token usage (how expensive?), retrieval recall (how complete?). Not
about answer quality — about operational health.

### When to use it
- You want to monitor system health in production
- You need to detect degradation before users complain
- You're tracking cost and performance over time
- Alongside any other eval approach (these complement, not replace)

### When NOT to use it
- As the only evaluation (a fast, cheap wrong answer still fails)
- Pre-deployment (no traffic to measure)

### Maps to copier choices
- Always available in the eval suite (latency + token tracking built into the pipeline)
- `optional_features: [promptfoo]` adds HTTP-level performance testing

---

## Decision Shortcut

| Question | Answer → Approach |
|----------|-------------------|
| "Can you define 'correct' objectively?" | Yes → Golden-set grading |
| "Is quality subjective (tone, style, completeness)?" | Yes → LLM-as-judge |
| "Do you have real users yet?" | Yes → User feedback loops |
| "Is this still a prototype?" | Yes → Manual review (for now) |
| "Which should I do first?" | Golden-set (10 pairs) → Manual review for edge cases → LLM-judge for subjective quality → User feedback when deployed |

---

## The Eval Ladder (recommended progression)

1. **Week 1 (prototype):** Manual review — use the system, note what works and fails
2. **Week 2-3 (building):** Golden-set grading — turn your best/worst examples into 10-20 Q&A pairs; `make eval-heuristic` runs them automatically
3. **Week 4+ (refining):** Add LLM-judge for subjective quality criteria; `make eval-gate` in CI prevents regressions
4. **Post-deploy:** User feedback loop — real signal; failures expand the golden set

Start at step 1. Progress as the project matures. Most DSSG POCs reach step 2-3
by demo day — that's sufficient to prove the system works reliably.
