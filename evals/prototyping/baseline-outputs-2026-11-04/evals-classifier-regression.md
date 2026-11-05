# classifier-regression-check
Date: 2026-11-04
Status: RESEARCHED
Track: agent

## Research

### Summary
The 150 labelled emails are enough to catch a bad prompt change, as long as each change is compared to the current prompt email by email and not by comparing two accuracy numbers. A one-command local run that exact-matches labels, saves per-email outputs, and lists "newly wrong / newly right" fits one person changing a prompt monthly; LLM judges, CI gates and hosted platforms do not earn their cost here. The honest limit: 150 rows reliably detects drops of about 5 points only when nothing offsets them, and it misses a 2-3 point drop, so the design should cover that gap with a read of every newly wrong email plus the production record of agents moving emails.

### Scope
Investigated: what to measure, how to tell a real regression from noise at n=150, how much tooling this justifies, and what in the snapshot can be reused.

Out of scope: prompt wording, model choice, the service's code (not available), and the implementation (left to `/proto-plan`).

**Track reasoning:** `agent`. The system calls Claude and fits nothing, and the skill names fitting as the tell (`.claude/skills/proto-research/SKILL.md:47-49`). "Classify" and "CSV" make it look like `ml`, but the CSV is a test set, not training data, so there is no fold or fitted transform to leak. The one analogue of leakage is in Finding 7.

**Frame check:** no FRAME gap, so `/proto-design` is not needed. The consumer is the maintainer deciding whether to ship a prompt, correct means matching the hand label, and the cost of wrong is stated (a few minutes).

### Findings

**1. The comparison must be paired: same emails, old prompt vs new prompt. Confidence: High.**
Two accuracy figures with separate error bars are the wrong instrument. At 150 rows, 90% accuracy has a 95% Wilson interval of 84.2-93.8% (my calculation), so most real changes would sit inside the overlap. What separates the prompts is only the emails on which they disagree about correctness. McNemar's test uses exactly those. Dietterich's comparison of five tests found McNemar keeps false alarms low when an algorithm can be run only once, and that a test of two proportions produces too many false alarms ([abstract](https://mlanthology.org/neco/1998/dietterich1998neco-approximate/); I could not extract the full PDF text). That setting involves training variation, which does not apply here, so it supports the test by analogy rather than directly. The exact binomial form is the one to use when disagreements are few ([secondary source](https://machinelearningmastery.com/mcnemars-test-for-machine-learning/)).

*For the planner:* the core output is the list of newly wrong and newly right emails. The accuracy figure is secondary.

**2. 150 rows detects large regressions only, and that limit should be stated rather than hidden. Confidence: High for the arithmetic, Medium for how it applies.**
Exact McNemar, two-sided p < 0.05 (my calculation):

| Emails the new prompt fixed | Newly wrong needed to call it a regression |
|---|---|
| 0 | 6 |
| 1 | 8 |
| 2 | 10 |
| 3 | 12 |
| 4 | 13 |
| 5 | 15 |

Chance of detecting a true regression (my simulation, 8,000-20,000 trials, assumes independent rows and no flip noise, so it is optimistic):

| True effect (rates per email) | Net drop | n=75 | n=150 | n=300 |
|---|---|---|---|---|
| 3% break, 0% fixed | 3 pts | 2% | 29% | 89% |
| 5% break, 0% fixed | 5 pts | 17% | 76% | ~100% |
| 5% break, 2% fixed | 3 pts | 5% | 18% | 43% |
| 7% break, 2% fixed | 5 pts | 16% | 44% | 79% |

So "not significant" does not mean "no regression". Significance can reject a change; it cannot clear one. Mixed changes, which break some emails and fix others, are the common case for a prompt edit and the hardest to detect.

*For the planner:* treat a significant result as stop, and everything else as "read the rows". Do not build a pass/fail gate that passes on non-significance.

**3. The small drops 150 rows cannot see are also cheap. Confidence: Medium, because volume is unknown.**
Extra agent time per month at 3 minutes per misroute:

| Emails per month | 2-pt drop | 5-pt drop |
|---|---|---|
| 300 | 0.3 h | 0.8 h |
| 1,000 | 1 h | 2.5 h |
| 5,000 | 5 h | 12.5 h |

Misroutes here are visible and corrected by hand, so errors do not accumulate silently. That justifies a light check. At 5,000 a month the argument weakens, and growing the set becomes worthwhile (Finding 7).

**4. Grade with exact match. No LLM judge. Confidence: High.**
The right queue is a closed set of four labels, so correctness is decidable by code. Anthropic's docs describe exact match as suited to clear-cut categorical answers ([docs](https://platform.claude.com/docs/en/test-and-evaluate/develop-tests.md)). The repo's own rules say the same: objective correctness means golden-set grading (`.claude/skills/proto-scope/reference/eval-approaches.md:88`), and code beats judgement when a property is decidable (`.claude/specs/agent-eval.md:214`). A judge would add cost and variance while answering nothing. Unparseable output and refusals should be counted as wrong and reported separately (`.claude/specs/agent-eval.md:117-118`), because a prompt edit can break the output format and that would look like a routing change.

**5. Noise has to be measured, and temperature 0 will not remove it. Confidence: High on the docs, Medium on the protocol.**
Anthropic states that even at temperature 0 results are not fully deterministic ([glossary](https://platform.claude.com/docs/en/about-claude/glossary)). On API version `2026-10-21`, sending `temperature` at all returns a 400, and Claude 4.7 and later accept only the defaults ([migration guide](https://platform.claude.com/docs/en/api/migration-2026-10-21)). Advice to "set temperature to 0" is therefore unavailable on current models.

Without a noise measurement, a flip from chance reads as a regression. Running the same prompt several times gives the noise floor and marks unstable emails. Three traps:

- **Repeats are not more data.** Three passes over 150 emails is still 150 emails. Feeding 450 rows into the test would overstate significance. Use one data point per email in the test.
- **Do not report majority-vote accuracy.** Production makes one call. A row that is right 70% of the time scores 78% under majority-of-3 (my calculation), so voting flatters the prompt. The headline should be the mean across passes.
- **Report `n`** and the number of passes (`.claude/specs/agent-eval.md:58`).

Anthropic's ticket routing guide suggests a consistency target of 95% or higher on standardized inputs ([guide](https://platform.claude.com/docs/en/about-claude/use-case-guides/ticket-routing)). Useful as a reference point, not as a requirement.

**6. Model drift is mostly controlled, so a run needs to record the full configuration. Confidence: Medium-High.**
Anthropic says every Claude model ID is a pinned snapshot, including the dateless ones from the 4.6 generation on ([models overview](https://platform.claude.com/docs/en/about-claude/models/overview)). The bigger risk is the eval and the service drifting apart: different preprocessing, truncation, output parsing or effort setting. A result is only about production if it goes through the same code path. Each run should record prompt version, model ID, request settings and dataset version (`.claude/specs/agent-eval.md:164`), and a model change should be treated like a prompt change.

Re-running the current prompt on the same day as the candidate removes the assumption that snapshots behave identically over time. At these prices (Finding 9), that is cheaper than reasoning about it.

**7. Reused rows will overstate accuracy, but the fix is fresh emails, not a holdout carved from 150. Confidence: Medium.**
Three separate problems:

- **Contaminated rows (the leakage analogue).** Any email from the CSV that is used as a few-shot example in the prompt, or was closely paraphrased into it, will score well for that reason alone. Such rows should be excluded from scoring.
- **Holdout split.** The usual remedy is train/dev/test splitting, for example 10-20 / 40-45 / 40-45 ([Husain's FAQ](https://hamel.dev/blog/posts/evals-faq/), written for LLM judges). At this size it is costly: dropping to 75 rows cuts detection of a pure 5-point drop from 76% to 17% (Finding 2).
- **Staleness.** Recht et al. rebuilt CIFAR-10 and ImageNet test sets and found accuracy drops, but attributed them to new data being harder rather than to adaptive overfitting, and gains on the old sets carried over to the new ones ([arXiv 1902.10811](https://arxiv.org/abs/1902.10811)). This is image benchmarking, so it transfers only loosely, but it points the same way: the larger risk is that the set stops resembling the inbox.

Adding a small number of new production emails each month addresses all three: they are unseen when added, can be scored separately first, and grow the set toward the n=300 column. Label them without looking at the model's answer, to avoid anchoring. Seeding from failures is already the repo's guidance (`.claude/specs/agent-eval.md:134`), but a set grown only from failures would skew harder and stop estimating production accuracy, so failures and random samples should be tagged separately.

**8. Agents moving emails are the best production signal, if they are logged. Confidence: Medium, because availability is unknown.**
A moved email is a free label on the real distribution, which the CSV cannot provide. At 1,000 emails a month and about 90% accuracy, a month of data gives about +/-1.9 points (my calculation), tighter than the CSV can manage. This is the one thing that covers Finding 2's blind spot. Caveats: comparing windows is unpaired, so a shift in email mix looks like a prompt effect; and an unmoved email is not proof of correct routing, since agents may handle a misroute rather than move it.

**9. The right tool is a small local script; the tooling options differ mainly in the paired report. Confidence: Medium.**
Cost is negligible, assuming 1,500 input tokens per call and 150 emails over 6 passes (3 per prompt), at [current prices](https://platform.claude.com/docs/en/about-claude/pricing):

| Model | Approx. cost, minimal output (20 tokens) | With 500 output tokens per call |
|---|---|---|
| Haiku 5.5 | $0.15 | $0.37 |
| Sonnet 5.5 | $2.90 | $7.20 |
| Opus 5.5 | $5.80 | $14.40 |

The Batch API's 50% discount, with results in up to 24 hours, is not worth the wait at these amounts.

| Option | Fit | Assessment |
|---|---|---|
| Small local script | Reads the CSV, reuses the service's call path, saves per-email output | Best fit. Paired list and test are a few lines. The service's own code path can be called directly (Finding 6). |
| promptfoo | [Loads CSV with `__expected` as equals checks](https://www.promptfoo.dev/docs/configuration/test-cases/), supports `--repeat`, [Compare diff and a two-prompt scatter](https://www.promptfoo.dev/docs/usage/web-ui/) | Credible second choice if a viewer is wanted. Tests a config rather than the service's path. I found no paired test or noise-floor report. Not run. |
| Claude Console Evaluate | [CSV import, side-by-side prompts, versions, 5-point manual grading](https://platform.claude.com/docs/en/test-and-evaluate/eval-tool) | Useful for one-off exploration. I saw no exact-match scoring, and manual grading of 150 rows per change does not fit. The search summary of this page was the source; I could not read its relevant section directly. |
| Hosted eval platforms | Not investigated | Set aside on proportion: multi-user and dashboard features answer problems a solo monthly workflow does not have. Low confidence, since no product was assessed. |
| CI gate | | Not needed at first. A person decides, monthly. Hard gates matter for automated loops (`.claude/specs/agent-eval.md:188`). Revisit if runs get skipped. |

Husain's FAQ says to start with error analysis rather than infrastructure and that CI checks should favour deterministic assertions ([FAQ](https://hamel.dev/blog/posts/evals-faq/)), which matches this.

**10. Per-queue accuracy is for reading direction, not for decisions. Confidence: High.**
If 150 rows split evenly, each queue has about 37, and 90% on 37 rows has an interval of about 75-96% (my calculation). Scores per queue will swing on one or two emails. The confusion matrix still earns its place, because a concentrated shift (queue A leaking into B) has a cause you can read, and diffuse change is usually variance (`.claude/specs/agent-eval.md:151`). Also report majority-class accuracy once. If one queue dominates, overall accuracy flatters the prompt, and if the CSV's mix differs from the inbox's, its overall figure does not estimate production accuracy.

**11. The labels are themselves a source of error, and label fixes must not mix with prompt changes. Confidence: Medium.**
Reading newly wrong rows will sometimes reveal that the label, not the model, is wrong. Fixing the label is right, but if it happens in the same comparison as a prompt change, the accuracy shift cannot be attributed to either. Version the dataset (`.claude/specs/agent-eval.md:132`), and rescore stored outputs when labels change, which needs no API calls. Labels written by one person also have an unknown ceiling: emails that could reasonably go to two queues will look like model errors no matter how good the prompt is.

### Asset verdicts

Paths are relative to the snapshot root.

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `.claude/specs/agent-eval.md` (conventions) | ADAPT | n/a | Sections 1, 2a, 5 and 6 apply. Sections 2 and 3 (retrieval gates, grader calibration) do not fit a single-prompt classifier. Its "regression suite should pass near 100%" (line 142) does not fit a set whose baseline may be about 90%; the newly wrong list plays that role. |
| `.claude/specs/agent-eval.md` section 2, grader interface | SKIP | The `metadata` fields: `model_id`, `prompt_version` (line 38) | The rest (`retrieved_context`, `dimensions`, reasoning) has no job when grading is an equality check. |
| `.claude/skills/proto-scope/reference/eval-approaches.md` | ADAPT | n/a | The decision shortcut (line 228) reaches the right answer. Its ladder (line 240) adds an LLM judge, which does not apply, and 10-20 pairs are far below what exists. |
| `template/_scaffold/{{ py_project_root }}/{{ eval_root }}/` eval tree | SKIP | `pipelines/compare.py.jinja` has the idea of baseline compare with exit codes; `pipelines/redaction.py` may help with Key Unknown on PII. Neither was read in full. | About 58 template files for scaffolded agent and RAG projects. Far too large for the job. `compare` is aggregate only, with a fixed 5% metric threshold (line 3), so offsetting errors can cancel out and the row-level view is lost. |
| `template/_scaffold/promptfoo.config.yaml.jinja` | SKIP | The approach of `contains`/deterministic assertions | Targets a RAG `/chat` HTTP endpoint, so it would need rewriting anyway. |
| `ml/stats_testing/ab_test.py` | ADAPT | n/a | `proportion_ci` (line 46) gives the Wilson interval. No paired test was found in the file. Pulling in a statsmodels-dependent module for one function may not be worthwhile for an external small service. |
| `ml/evaluation/baselines.py` | SKIP | The principle at line 136: a gate that cannot be evaluated must not report success | Targets fitted-model metrics such as average precision. Wrong shape for label matching. |
| `experiments/record.py` `RunRecord` | SKIP | Its field list as a checklist of what a run should record (line 133) | Built for this repo's ML runs and heavier than a results file needs to be. |
| `.claude/skills/new-agent/references/eval.md` | SKIP | Nothing found that applies, after reading the first 70 lines | Templates for a scaffolded harness with forecast and intent graders. |

These assets live in a template repo; the service is separate, so reuse means copying ideas rather than importing code.

### Assumptions
- **Assumption:** Prompt changes are made and judged by one person, with a person's decision at the end, and no automation depends on the result. — **Evidence:** the request. — **If wrong:** a hard gate becomes necessary, and Finding 2's power figures make it a weak one. — **Confidence:** High.
- **Assumption:** All misroutes cost about the same, and no queue has legal or urgency consequences. — **Evidence:** the request's "a few minutes"; queues are not named. — **If wrong:** overall accuracy is the wrong metric; a cost-weighted view or a per-queue floor is needed, along with more rows for that queue. — **Confidence:** Medium.
- **Assumption:** Volume is about 1,000 emails per month, used for illustration only. — **Evidence:** none; the request gives no volume ("small service"). — **If wrong:** Finding 3 shifts, per its table. — **Confidence:** Low.
- **Assumption:** Each email has one correct queue, and the CSV contains the full email as the service sees it. — **Evidence:** "hand-labelled with the right queue". — **If wrong:** multi-valid emails would need an accept-list, and missing fields would make the test unrepresentative. — **Confidence:** Medium.
- **Assumption:** The service outputs one label per call, single-pass, with no retry or vote. — **Evidence:** "calls Claude with one prompt". — **If wrong:** the eval must replicate what the service does, or its headline will not match production. — **Confidence:** Medium.
- **Assumption:** About 1,500 input tokens per call, for the cost table. — **Evidence:** none measured. — **If wrong:** even tenfold, this is under about $150 at the most expensive listed model and much less on Haiku. Still small against monthly changes, though worth revisiting on Opus. — **Confidence:** Medium.
- **Assumption:** The questions the skill would have asked were not asked, because nobody could answer. Track was decided without asking because the request was not ambiguous under the skill's rule. — **Evidence:** task instructions. — **If wrong:** see each item above. — **Confidence:** High.

### Disconfirming Evidence
- **Finding 1 (paired test).** Contradicted if two prompts' errors were independent, which would remove the pairing advantage. Unlikely on the same emails. Dietterich's setup differs (learned algorithms on train/test splits), and I read only the abstract. No source found against using a paired test on a fixed test set. The exact test's threshold of 25 disagreements came from secondary sources only, so it is not relied on here.
- **Finding 2 (power).** The simulation assumes independence and no flip noise; real results would be worse, which strengthens rather than weakens the point. It does overstate how much the table applies if emails cluster (for example many near-duplicate templates), since then effective n is below 150. Not checkable without the CSV.
- **Finding 3 (cheap drops justify light checks).** Looked for a reason misroutes could cost more: delayed response, an SLA breach, or a misrouted urgent email. The request says minutes, but it describes the agent's move time and not the customer's delay. If delay matters, this finding fails. Not resolvable from the request.
- **Finding 4 (no judge).** Would fail if emails often have several valid queues. Even then an accept-list would be better than a judge. Anthropic's "volume over quality" principle is compatible, since exact match is automated.
- **Finding 5 (noise).** Vendor blogs report varied flip rates; the search turned up one report of 29 of 103 flapping cases on a non-Claude model, blog-level and not directly relevant. A classifier with a four-label output may flip far less than this, in which case repeat passes add little. So this is a measurement to take, and if it reads near zero, repeats can be dropped after the first baseline. I did not find a published flip rate for Claude on short classification.
- **Finding 7 (fresh rows over holdout).** Against it: Husain's FAQ recommends an untouched test set, and repeated fitting to one set is a known risk. Recht et al. is the main evidence against adaptivity being dominant, but it covers image benchmarks with many researchers, not one person hand-editing a prompt who reads the errors directly, which may be a stronger form of adaption. With about 12 edits a year, a split might be better once the set exceeds about 300 rows.
- **Finding 9 (no platform, no CI).** Searched for a case for tooling first: promptfoo does offer CSV, repeat and diff, and could plausibly be faster to start. Its lack of a paired report is based on documentation searches, not on running it, so it may exist. Anthropic's advice to prioritize volume, with examples of 1,000 and 10,000 items, also cuts against treating 150 as sufficient. That advice applies when errors are costly or the goal is a precise estimate; it is the main reason to grow the set.
- **Recommendation overall.** It would be wrong if the real problem is not measurement. Monthly prompt tweaks with no clear gain might mean the categories overlap or the labels disagree; then an eval only reports the stalemate. First-run results (Finding 11) should reveal this.

### Key Unknowns
- **Monthly email volume.** Sets the regression cost and whether 150 rows is enough. Not stated.
- **Whether moved emails are logged,** with the original and final queue. Determines whether Finding 8 is available at no extra work.
- **Current accuracy.** A prompt at 97% needs different treatment from one at 80%. Fewer existing errors means fewer rows to read and a narrower interval; at 80% the priority is likely labels or categories rather than regression checks.
- **Queue mix in the CSV vs in production, and how the 150 were chosen.** Random sample, recent, or hand-picked hard cases. Decides whether accuracy estimates production or only supports comparison. The comparison holds either way.
- **The true flip rate** for this prompt and model. Measurable in one run.
- **Label reliability.** Re-labelling a subset blind after a gap would give a ceiling. Not known.
- **Whether customer emails may be stored or kept in git,** and whether sending them for repeat evals fits the service's data handling. Saved outputs next to the prompt would contain customer text unless excluded or redacted.
- **Which model the service uses.** Sets cost and whether `temperature` is currently being sent (which would break on API version `2026-10-21`).
- **Actual promptfoo and Console capabilities** beyond their docs; neither was run.

### Recommendation
Treat this as a paired before/after check, not a score: a single local command that runs the current and candidate prompts over the 150 emails through the service's real call path with a pinned model, grades by exact match, and saves per-email outputs with the prompt, model and dataset versions, then reports the newly wrong and newly right emails first, followed by mean accuracy, an exact McNemar result, a confusion matrix and which emails flipped between repeat runs. A first baseline run should come before any new prompt edit, to get the noise floor and flush out label errors. The decision is the maintainer's: a significant result means stop, while a non-significant one still requires reading every newly wrong email, since 150 rows will miss most drops under 5 points. To cover that gap at low effort, add a few blind-labelled production emails monthly and watch the agent move rate after each change if it is logged, and leave out LLM judges, CI gates and hosted platforms until volume or the cost of a misroute changes. `/proto-plan` should begin by settling the Key Unknowns on volume, move logging and the CSV's sampling, since those decide how much weight the CSV figures can carry.
