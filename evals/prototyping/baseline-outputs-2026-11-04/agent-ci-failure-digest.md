# ci-failure-digest
Date: 2026-11-04
Status: RESEARCHED
Track: agent

## Research

### Summary
Use a fixed scheduled pipeline with one tool-less model call per failure, not an agent loop: code lists failures, filters logs, checks output and posts once, and the model only turns a filtered excerpt into a likely reason. No framework, graph, memory or subagents are justified at 0 to 5 failures a night. The unproven premise is that a filtered log gives enough for a useful reason, and replaying past failures can test that before anything is built.

### Scope
**Investigated:** what orchestration level, loop, runtime and permission shape fit this request; what the repo's specs and assets imply; what the CI and Slack APIs force; and published evidence on LLM analysis of CI logs.

**Out of scope:** implementation, code, the step-by-step plan, and anything that re-runs CI or touches code (excluded by the request).

**Track:** `agent`. The system calls a model and fits none, so routing was not ambiguous.

**Source limits:** the repo evidence is from the read-only snapshot. Web pages were read through a fetch tool's extraction, so quoted wording should be re-checked before it is relied on. That includes LogSage v2 (HTML version); figures in its charts were not visible to me.

### Findings

#### 1. Shape: a pipeline with a narrow model step (Confidence: High)
Nothing in this job requires the model to choose its next step. Every step is known before the run starts, so what remains probabilistic is one judgment per failure.

- The repo's rule is that every LLM call must justify itself against the deterministic alternative (`.claude/specs/agent-uncertainty.md:147`), and that truth lives in deterministic systems (`agent-uncertainty.md:19`).
- A single scripted call is a chain, not a loop (`.claude/skills/proto-design/SKILL.md:177`). This is level 1 on the ladder in `agent-architecture.md` §0, repeated per item inside code.
- Anthropic says the same: predefined code paths are "workflows", and well-defined tasks generally suit them better than agents. Its advice to start with the LLM APIs directly also applies ([Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)).
- The closest published system points the same way. LogSage's root-cause stage is one prompt over filtered log blocks, with an average of 1.0 queries reported and no tools or loop described ([arXiv 2506.03691v2](https://arxiv.org/html/2506.03691v2)).

This means the design is not an "agent" in the spec's sense, whatever the project is called.

| Option | What it buys | What it costs | Verdict |
|---|---|---|---|
| A. No model: code posts the failing step and error lines | Cannot invent a reason; no provider, cost or injection surface | Gives lines rather than an explanation; noisy on long failures | **Baseline to beat**, tested in the replay |
| B. Pipeline with one tool-less call per failure | The reason you asked for; failures stay isolated; code owns the facts | Needs log filtering and output checks | **Recommended**, if it beats A |
| C. Pipeline with one call over the whole night | Can spot a shared cause across failures | One bad log or overflow affects every row; the model could drop a failure | Rejected; matching error text in code can catch most shared causes |
| D. Tool-calling agent with CI tools and a post tool | Can pull more evidence when the excerpt is weak | Log text reaches a model that holds capabilities; needs loop bounds and can post wrongly | **Named escalation** only if the replay fails for lack of evidence (see Findings 7) |
| E. Graph or multi-agent (extract, summarize, verify) | Auditable nodes | About 3x tokens per cycle (`agent-architecture.md` §5) with no signal to justify it | Rejected |

The five graph signals (`agent-architecture.md:38`) all come back no:
- **Distinct specialties:** there is only one judgment.
- **Fan-out with a join:** analysing one failure does not read another's result, so the items are independent. At 5 items, sequential is fine.
- **Per-step model or tool variation:** there is only one model step.
- **Regulated audit:** not applicable.
- **Overloaded verifier:** the only verifier is a code check.

#### 2. What code owns and what the model owns (Confidence: High)
"What failed" must never depend on the model. If code builds the list, a model error cannot drop a failure or invent one.

| Job | Owner | Why |
|---|---|---|
| Time window, list of failures, job and step names, links | Code | Facts available from the API |
| Log fetching, filtering, secret scrubbing | Code | Decidable, and must happen before any model or Slack exposure |
| Likely reason, or "could not tell" | Model | The only real judgment in the system |
| Checking the cited evidence, message assembly, length limits, the single post | Code | Must hold even when the model misbehaves |

#### 3. Log filtering is the main quality lever, and it is deterministic (Confidence: Medium)
LogSage filters before the model sees anything:
- It keeps lines that match failure keywords and lines near the log tail.
- It drops lines matching templates mined from the 3 most recent successful runs of the same pipeline.
- It expands each key line to 4 lines before and 6 after, then selects blocks within a 22,000-token limit.

The authors tuned these values on ByteDance pipelines, so they are starting points rather than settings to copy. The log-diff step also assumes stable, repetitive pipelines.

**Do not plan around its 98% figure.** That precision was measured on identifying key log lines (at least 90% overlap with labels the authors made themselves, 250 test cases), and the matching rule differed from the baselines'. The figures closer to your question are from production: over 85% root-cause accuracy and over 80% end-to-end, from a manual review of 150 sampled cases a week over 10 weeks. Both are self-reported and neither transfers directly to your repo.

#### 4. Uncertainty must be visible in the message, by distinct state (Confidence: High)
The repo treats "no evidence", "evidence says no" and "the component did not run" as different results (`agent-uncertainty.md:68,77`), and requires degraded output to be loud (`agent-reliability.md:180`). Here that gives these states:

| Level | State | The message must say |
|---|---|---|
| Night | Listing succeeded, failures found | The failures, and how many runs were checked |
| Night | Listing succeeded, none failed, runs existed | "0 failures out of N runs" |
| Night | Listing succeeded, zero runs at all | Zero runs in the window, which may itself be a problem |
| Night | Listing failed | "Could not check CI", never "no failures" |
| Failure | Reason given, evidence verified | Reason, marked as likely, with log link |
| Failure | Model says it cannot tell | "Could not tell", with log link |
| Failure | Log missing, fetch failed, model error, refusal, truncation | "Not analysed" and why, with log link |
| Night | More failures than the cap | The true total, and how many were not analysed |

Posting on zero-failure nights is what makes silence meaningful. Without it, "nothing failed" and "the job died" look identical.

#### 5. The output check can catch fabrication, but not wrong reasoning (Confidence: High)
No code check can prove a reason is right. Code can, however, require the model to quote the log line it relied on and confirm that the line appears in the excerpt it was given. That is a real check, because the verifier has ground truth the model cannot alter (`agent-eval.md:214`).

It leaves one failure uncaught: a real error line with a wrong story attached, such as blaming the first noisy error rather than the actual cause. That is what the replay has to measure.

**The stated cost of being wrong rests on one premise worth testing.** "Someone opens the log" only happens if someone suspects the reason is wrong, and a plausible wrong reason looks the same as a correct one. Most of the time this is harmless, since whoever works on the failure will find out. The exception is a reason that makes people skip the failure, such as "flaky" or "infra blip". That is the case worth checking separately in the replay, and it is why a log link belongs on every row and the reason should read as likely rather than as fact.

#### 6. The boundary can be enforced by what the system is granted (Confidence: High for the shape, Medium for the threat)
"Only reads CI and posts one message" is enforceable without relying on the prompt, because an absent tool cannot be called (`agent-tools.md:160`).

- **Model:** no tools and no credentials (`agent-safety.md:195`). A manipulated model can then only affect text, and code can restrict that.
- **CI access:** read only. Job logs and listing need only read access to the repo (GitHub docs linked in Findings 8).
- **Slack access:** an incoming webhook is fixed to one channel and cannot change it ([Slack](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/)), which is a narrower grant than a bot token. The trade-off is that a webhook cannot delete a message, so a bad post is corrected by a person. The URL is itself a secret.

**Logs are untrusted input.** The repo says to assume injection eventually lands and bound what it can reach (`agent-safety.md:152-154`), and GitHub's own CI investigation sample says to treat logs as untrusted data ([gh-aw](https://github.github.com/gh-aw/gallery/ci-failure-investigation/)). I found no documented exploit of a log-summarising agent, so this is a plausible risk and not a demonstrated one. Exposure rises if fork or outside-contributor PR runs are in scope, because their authors control the log text.

With no tools, the remaining impact is misleading text in a trusted channel:
- Slack treats `&`, `<` and `>` as control characters, and `<!here>`-style mentions and `<url|text>` links use them ([Slack formatting](https://docs.slack.dev/messaging/formatting-message-text/)). Model text and quoted log lines need escaping so they cannot ping the channel or disguise a link.
- Links should come only from code, and unfurling should be off.
- The quote check does not help here, because an injected line really is in the log.
- A reason could still tell a reader to run a command, so the reason should state a cause and not give instructions.

**Secrets are the one irreversible failure in this design (Confidence: Medium).** GitHub warns that masking relies on exact matches and that structured data can defeat it ([hardening guide](https://docs.github.com/actions/security-guides/security-hardening-for-github-actions)). A secret that survives masking would reach the model provider, and could reach Slack through the quoted evidence, where the audience may be wider than the people with repo access. The request says nothing about this, and it is the main thing to settle before build. A pattern scrub reduces the risk but cannot remove it.

#### 7. The replay should come first, because it can change the design (Confidence: High)
The whole recommendation rests on the premise that a filtered log is enough for a useful reason. The test is cheap: logs are kept for 90 days by default on github.com, adjustable by the org down to 1 day ([GitHub](https://docs.github.com/en/organizations/managing-organization-settings/configuring-the-retention-period-for-github-actions-artifacts-and-logs-in-your-organization)), so past failures are likely still available. At up to 5 a night that is up to about 450 failures, and `agent-eval.md:133` suggests 50 to 200 rows is enough to grade.

Run Options A and B over the same failures, and have engineers judge each result, with "can't judge" allowed as an answer. Set the pass threshold before seeing results. Then:

| Replay result | Meaning | Next step |
|---|---|---|
| B clearly more useful than A | Premise holds | Build B |
| A about as useful as B | The model adds little | Ship A; it is cheaper and cannot be wrong about a reason |
| B wrong because the excerpt missed the evidence | Filtering problem | Improve filtering first (for example, the log diff) |
| B wrong because the log does not contain the cause | Evidence problem | Consider Option D, or accept more "could not tell" answers |

Real failures also become the regression set (`agent-eval.md:134`).

#### 8. API details that would silently break the digest (Confidence: High for the docs, unverified against a live repo)
These assume GitHub Actions, which the request does not state.

- **`status=failure` is not the same as "failed".** `failure` and `timed_out` are separate values of the filter, and there is also `cancelled` ([runs API](https://docs.github.com/en/rest/actions/workflow-runs)). Filtering on `failure` alone would silently omit timeouts.
- **`exclude_pull_requests` does not exclude PR runs.** Per the docs, it only empties the pull-requests array in the response. Scoping has to use the event or branch filters.
- **Results are capped.** The listing returns at most 1,000 results per search. That is not a concern at this volume unless the unfiltered night is enormous.
- **Log links last one minute.** Both log endpoints return a 302 to a URL that expires after 1 minute, so logs must be fetched straight away ([jobs API](https://docs.github.com/en/rest/actions/workflow-jobs)).
- **Job records give the failed step.** Jobs carry step-level conclusions, so code can name the failed step and use it to narrow the log, without any model involvement.
- **Re-runs need a rule.** Runs have `run_attempt`, and jobs can be listed for the latest attempt or for all attempts. A failure that passed on retry needs a deliberate decision.
- **Scheduled triggers can slip.** GitHub says `schedule` runs can be delayed under load and "some queued jobs may be dropped", and they run only from the default branch ([events docs](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)). A window of "the last 24 hours from now" would then miss or double-count failures, so it should use fixed clock boundaries. A dropped run means no message at all, which only a person noticing can catch. Running on the same platform as the CI it reports on also means an outage takes out both.
- **Failures may not map 1:1 to runs.** One run with a large matrix can produce many failed jobs, so "0 to 5" needs a defined unit and a cap (see Findings 4).
- **Message length.** Slack advises keeping `text` to about 4,000 characters and truncates at 40,000 ([chat.postMessage](https://docs.slack.dev/reference/methods/chat.postMessage/)). A long night could otherwise lose its last rows, so per-row limits belong in code.

#### 9. Cost does not drive the design (Confidence: High for arithmetic, Medium for inputs)
Assuming 5 failures, 22,000 input tokens each (the LogSage limit) and my guess of 500 output tokens each, at [list prices read today](https://platform.claude.com/docs/en/about-claude/pricing):

| Model | Input/output per MTok | Worst night | 30 worst nights |
|---|---|---|---|
| Haiku 5.5 | $0.10 / $0.50 | about $0.01 | about $0.37 |
| Sonnet 5.5 | $2 / $10 | about $0.25 | about $7.35 |

Model choice should therefore be settled on replay quality rather than price. A cap on analysed items is still required, because a bad night (a CI outage, for instance) could produce far more failures and the repo requires a ceiling that fails closed with a partial result (`agent-safety.md:264`). The 50% batch discount isn't worth the extra machinery at this spend.

#### 10. Five-layer read (Confidence: Medium; research-level, not a `/proto-design` spec)

| Layer | Answer from this research |
|---|---|
| Prompt | Role: explain one CI failure from a log excerpt. Schema-constrained output of reason, quoted evidence line and a "could not tell" state. |
| Context | Static instructions plus delimited, filtered, scrubbed excerpt, one failure per call. No history, so nothing is unbounded. |
| Harness | Check: quote appears in the excerpt, and every listed failure has a row. Boundary: Findings 6. Feedback: replay, then human reports. Rollback: disable the schedule; a posted message is corrected by a person. |
| Loop | None. It is a chain, so there is nothing to bound beyond the item cap and call timeouts. |
| Graph | None; no signal fires. |
| HITL | None before posting, since the output is advisory. The reader is the human check. |
| Runtime and memory | Stateless scheduled job (`agent-runtime.md:19,47`), no memory. |
| Streaming loop | N/A for a batch design. |

### Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `.claude/specs/agent-*.md` (architecture, uncertainty, safety, tools, reliability, eval, observability, runtime) | REUSE | n/a | These supply the rules applied above. |
| `.claude/specs/agent-voice.md`, `agent-memory.md` | SKIP | Nothing; checked. No duplex audio, and no state survives a run. | Do not apply here. |
| `template/llm_kit/` | ADAPT | n/a | Close fit: timeouts, retry budget, token guard, cost, and loud warnings on truncation. It is copied by hand, since it does not ship through copier (`README.md:11`). `parsed()` logs `stop_reason` but returns only the parsed object, so truncation and refusal handling must be added for the "not analysed" state. Its SDK call was not run against the current API. |
| `.claude/skills/framework-selection/` | SKIP | Its reasoning under "Not ideal when" (`SKILL.md:97`) supports using no framework. | It has no "no framework" outcome, and its fallback (`SKILL.md:34`) would return LangGraph or ADK for this job. Answered literally, it gives the wrong result. |
| `/new-agent`, `langgraph-*`, `adk-*` skills | SKIP | Nothing for v1; checked. They become relevant only if the replay forces Option D. | They scaffold an agent with a framework, and this job has neither a loop nor a graph. |
| `copier.yaml` template (`project_type: workflow`) | SKIP for v1 | `.claude` hooks and conventions, through the "layer onto an existing repo" mode. | The defaults pull in `lg_agent` (`copier.yaml:450`), and `composio` and `n8n_webhook` (`copier.yaml:923`), plus LangGraph and tool-heavy guidance in `archetype-selection.md:143-148`. `/new` steers kept work to a repo (`SKILL.md:75`), which is correct, but overrides would be needed to strip it back. Whether a smaller render is cheaper than an empty repo was not tested. |
| Composio (`integration-patterns.md`) | SKIP | Nothing; checked. Its value is managed OAuth across many apps. | One webhook and one read-only API do not need it, and it adds a third party with access to logs or tokens. |
| n8n webhook | SKIP | Nothing; checked. | Inbound event receiver, and this job has no inbound events. |
| `.claude/skills/new-agent/references/cap-batch.md` | SKIP | The contract line (`cap-batch.md:7`): per-item failure isolation, keyed by stable id. | The batch API is unnecessary at 5 items, but the contract applies. |
| `.claude/hooks/secrets_scan.sh` | ADAPT | n/a | Its token patterns (AWS, Anthropic, GitHub, private keys) are a starting list for the log scrub. As a hook it scans file writes, so only the patterns carry over. |
| `runs/ai/marketing-comms/` guardrails and evals | ADAPT | n/a | Pattern only: deterministic check plus safe degradation (`src/guardrails/`), and an eval harness with a dry-run mode (`evals/run.py`). Its code is about layout contracts and does not transfer. |
| gh-aw CI Doctor ([gallery](https://github.github.com/gh-aw/gallery/ci-failure-investigation/)) | SKIP | Its read-only permissions, untrusted-log instruction, confidence labels and "diagnosis may be incorrect" framing. | It fires on each failure, opens issues and investigates commits and PRs. You want one nightly digest from logs. Whether it can post to Slack was not checked. |

### Assumptions
Nobody could be asked, so these were assumed.

- **Assumption:** CI is GitHub Actions. — **Evidence:** none in the request; it is the likeliest case and the repo's own CI uses it. — **If wrong:** Findings 8 must be redone, while Findings 1 to 7 still hold. — **Confidence:** Medium.
- **Assumption:** "main repo" means the repository, and "0 to 5" counts what is in scope. — **Evidence:** the wording is ambiguous between the repo and the `main` branch. — **If wrong:** PR-run scope changes volume and raises injection exposure, and main-only scope lowers both. — **Confidence:** Low.
- **Assumption:** a message is posted every morning, including 0-failure nights. — **Evidence:** Findings 4. — **If wrong:** silence becomes ambiguous and a dead job goes unnoticed. — **Confidence:** Medium, as your team may find this noisy.
- **Assumption:** the repo is private and CI logs may be sent to an LLM provider under your existing terms. — **Evidence:** none. — **If wrong:** this could block the model step, leaving Option A or a provider inside your own boundary. — **Confidence:** Low.
- **Assumption:** everyone in the Slack channel may see CI log content. — **Evidence:** none. — **If wrong:** quoted evidence lines must be dropped from the message. — **Confidence:** Medium.
- **Assumption:** the model provider is Anthropic. — **Evidence:** repo default stack (`CLAUDE.md`). — **If wrong:** prices and `llm_kit` change, while the design does not. — **Confidence:** Medium.
- **Assumption:** the reason should come from logs alone, without commits or diffs. — **Evidence:** the request says "from the logs". — **If wrong:** code can add commit metadata to the prompt without a loop, and a need for code exploration points to Option D. — **Confidence:** High.

### Disconfirming Evidence
- **"No agent loop is needed."** GitHub's CI Doctor is a counter-example: it investigates commits, PRs and config as well as logs. I looked, and its job is wider (root cause and fixes filed as issues), so it doesn't settle this request. It also warns its own diagnosis may be incorrect and publishes no accuracy figure I could find; its 69% PR merge rate is self-reported and measures something else. What would truly contradict this finding is replay failures caused by missing evidence. **Not yet tested; Findings 7 is the test.**
- **"Log filtering plus one call gives useful reasons."** LogSage supports this, but it is one vendor's self-reported result, tuned on its own pipelines, with labels by its authors, and its log diff assumes stable pipelines. I did not find a breakdown of which failure types do poorly, though I read a digest of the paper rather than every section. Failures with an empty or cut-off log, such as a lost runner, may have no evidence at all. **Partly supported, not shown for your repo.**
- **"A model adds value over plain extraction."** I found no study comparing a model-written reason against showing the extracted error lines to engineers reading a digest. LogSage's baselines are other LLM log methods. If the error line already states the reason, as many test and compile failures may, Option A could be enough. **Open; the replay compares them directly.**
- **"Wrong reasons are cheap."** This is your stated position, and the design accepts it. The challenge is the "flaky" case in Findings 5. I found no data on how often readers skip a failure because of a confident label. **Open; low cost but worth checking.**
- **"Injection is a real risk."** I searched and found audits and guidance but no documented exploit through log text specifically, whereas documented attacks use PR titles and comments against agents that hold tools. This may be overweighted for a private repo. The mitigations are cheap and also fix ordinary formatting bugs from stray `<` characters, so they stay.
- **"A pipeline is enough for the long term."** Control logic accumulating around the model is the repo's sign that a graph wants to exist (`agent-architecture.md:24`). If the plan starts growing "if the excerpt shows X, fetch Y", that is the trigger to reconsider.

### Key Unknowns
1. **CI system and hosting:** GitHub Actions is assumed. Also where the job runs: a workflow in the main repo gets a short-lived scoped token but ties the job to CI's availability, while a separate project ("New project") needs its own long-lived read credential. Neither option was evaluated against your org's setup.
2. **Scope of "failed CI runs":** `main` only or all branches and PRs; whether timeouts and cancelled runs count; how re-runs that later pass are shown; the unit (run or job); and the night's boundaries and timezone, including weekends.
3. **Data policy:** whether logs may go to the provider, what your logs actually contain, and how far the channel's audience exceeds repo access.
4. **Is a model-written reason better than the extracted lines?** Only the replay can answer this. The pass threshold and who does the judging are also undecided.
5. **Log filtering performance on your logs:** log size and noise were not measured, and LogSage's values are not validated here. Whether the log diff is worth having depends on how stable your pipelines are.
6. **Model tier:** left to the replay.
7. **How the system learns it was wrong after launch:** nothing here closes that loop automatically (`agent-observability.md:264`). A person noticing is the only path at first. This is a known gap, in line with `agent-uncertainty.md` §6.
8. **Alerting when the digest does not arrive:** currently someone must notice. Whether that is acceptable depends on how consistently the team reads it.
9. **Run records:** what to retain per run (run ids, per-item state, prompt version, model, stop reason, cost). Excerpts may hold secrets, so they should not go to a third-party tracer by default.

### Recommendation
The research supports a stateless, scheduled pipeline in which code owns the facts, the single post and the checks, while a tool-less model is called once per failure to give a likely reason or say it cannot tell, with no framework, graph, memory or subagents. That fits the volume and low stakes, and it makes "only reads CI and posts one message" a matter of granted permissions and not of prompt wording. Before committing to it, the planner should settle the log-data question, since it is the only irreversible risk, and make the replay of past failures the first piece of work, comparing the model's reasons with plain extracted error lines. If plain extraction proves as useful, the project needs no model at all; if the model fails for lack of evidence, a bounded read-only agent is the named escalation.
