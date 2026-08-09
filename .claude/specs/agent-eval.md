# Agent Evaluation — Conventions

**Durable question:** How do we know a change made it better, and at what confidence? What is unit-testable vs. only eval-testable in a nondeterministic system?

*Contract + seam only. Harness specifics, grader calibration results, and gate thresholds stay project-local. Promoted from an earlier grader-interface and gate-contract design (interface and ladder shape only — per-gate thresholds are project-specific).*

---

## 1. The unit/eval seam

The most important design question for testing an agent system: **is this behavior deterministic?**

| Behavior | Testable how | Why |
|---|---|---|
| Schema validation (output matches declared schema) | Unit test | Deterministic — same input produces same structure |
| Tool routing (correct tool called for given input) | Unit test with mocked model | Deterministic given a fixed stub |
| Retry logic / error handling | Unit test | Control the failure; assert the recovery |
| Prompt template rendering | Unit test | String manipulation is deterministic |
| Retrieval ranking (given fixed corpus) | Unit test | Math is deterministic |
| Answer quality / relevance | Eval (LLM-as-judge) | Nondeterministic — model output varies |
| Grounding / citation accuracy | Eval (heuristic or LLM) | Requires ground truth; varies by model version |
| End-to-end behavior on real queries | Eval (golden dataset) | Full stochastic; sampling required |

**Rule:** write assertions against deterministic behavior. Write evals against nondeterministic behavior. Never write a unit test that asserts a specific LLM response string — it will fail on model version changes.

---

## 2. Grader interface contract

Any grader (heuristic, LLM-as-judge, or composite) must implement this interface:

```
Input:
  query:              string
  response:           string
  expected:           string | null   -- null for open-ended tasks
  retrieved_context:  list[string]    -- required for passage-dependent graders
  metadata:           dict            -- run_id, model_id, prompt_version, gate

Output (GraderOutput):
  score:         float [0.0, 1.0]
  is_correct:    boolean              -- threshold applied
  reasoning:     string               -- why this score (required; enables audit)
  dimensions:    dict[str, float]     -- sub-scores when relevant
  labels:        list[string]         -- failure taxonomy labels (see §4)
```

Graders that require `retrieved_context` must declare it. A grader that silently accepts missing context and scores anyway produces misleading results. Label such rows `context_missing` and exclude from hard release decisions.

---

## 2a. Non-determinism is the measurement problem, not a nuisance

A single run is not a measurement. The wiki states the arithmetic plainly: `pass@k` rises with `k` while `pass^k` falls, and they answer different questions. A step that succeeds 75% of the time succeeds across three consecutive trials only `0.75³ ≈ 42%` of the time. An agent evaluated once looks far better than the same agent evaluated as a chain.

- **Choose the metric that matches the claim.** `pass@k` ("can it ever do this?") is a capability claim. `pass^k` ("does it do this every time?") is a reliability claim. Reporting the first while shipping against the second is the standard way an eval flatters a system.
- **Reset the environment between trials.** Trials that share state are not independent, and a variance estimate over dependent trials understates variance.
- **Report `n`.** A score without a trial count is not comparable to another score.

*(Source: `eval/eval-non-determinism.md`)*

---

## 3. Gate ladder

A gate ladder separates the eval question into sequential stages, each answering a distinct question. Do not collapse multiple questions into one score.

> **Naming caution.** The wiki carries three distinct things called ladders — this gate ladder, an eval *maturity* ladder (how sophisticated the eval practice is), and the enforcement ladder in `DESIGN-PROCESS.md §3`. They are easy to conflate and answer different questions. When citing "the ladder," name which one. *(Source: `eval/eval-maturity-ladder.md`)*

General shape (adapt to project):

| Gate | Question | Fail consequence |
|---|---|---|
| 1 — Data quality | Is the evaluation dataset valid? | Do not proceed — garbage in, garbage out |
| 2 — Retrieval | Does the retrieval system find the right evidence? | Fix retrieval before evaluating generation |
| 3 — Generation | Does the agent use evidence correctly? | Fix generation; don't blame retrieval |
| 4 — Grader calibration | Do graders match user outcomes? | Graders are not yet trustworthy for hard gates |
| 5 — Release | Does the change improve quality without regression? | Hold the release |

**Handoff contract between gates:**
- Each gate emits a pass/fail status, metric summary, row-level diagnostics, failure labels, and a recommended next action.
- Downstream gates must not silently include rows that the upstream gate marked ineligible.
- Every stakeholder claim must name the gate, row pool, sample size, and source artifact behind it.

---

## 4. Failure taxonomy

Use stable labels so notebooks, pipelines, and reports aggregate failure modes consistently. Minimum required labels:

```
source_missing:          expected source absent from corpus
rank_miss:               expected source indexed but not in top-k
citation_hallucination:  answer cites a URL outside the retrieved set
unsupported_claim:       claim not grounded in retrieved passages
context_missing:         passage-required grader received no passage text
wrong_escalation:        agent escalated when it should have answered (or vice versa)
schema_violation:        output did not match declared schema
refusal:                 model declined to respond
```

Failure labels enable: root-cause triage, dataset improvement targeting, and regression detection across model versions.

---

## 5. Golden dataset curation

Golden datasets are the foundation of repeatable evals. Rules for keeping them representative:

- **Source of truth**: golden cases come from real user queries (sampled, anonymized) — not from synthetic generation alone.
- **Balanced coverage**: include edge cases, adversarial inputs, and failure modes — not just easy queries the current model handles well.
- **Eligibility labels**: every golden row must carry eligibility status for each gate (e.g., `retrieval_eligible: true`). Do not use ineligible rows to measure retrieval metrics.
- **Versioning**: the golden dataset is versioned. When you add or remove rows, bump the dataset version. Grader calibration is invalidated on dataset version changes.
- **Size discipline**: a quality_sample for LLM grading is cost-constrained — 50–200 rows is sufficient for most gates. Do not grade the full dataset with an LLM judge unless required.
- **Seeding from failures**: failed runs and human-corrected outputs are the best source of new golden cases. Build a pipeline to promote them.

### One dataset is the wrong shape

This section describes a single versioned dataset. The wiki splits it in two, and the split matters because **the two suites want opposite pass rates**:

| Suite | Purpose | Healthy pass rate | Size |
|---|---|---|---|
| **Regression** | Nothing that worked has broken | Near 100% — anything less is a bug | 100–1,000 rows (CI) |
| **Capability** | Can it do the harder thing yet? | Well below 100% — a capability suite at 100% has stopped measuring anything | 20–50 rows (spec-time) |

A suite that mixes both cannot be read: a drop is either a regression (stop the release) or an un-earned capability (expected), and one number cannot tell you which. Keep them separate files with separate thresholds.

**When a score drops, debug in this order** — the wiki is explicit that skipping ahead is the common failure:

1. **Infrastructure** — did the harness change, did a dependency move, did the dataset version bump?
2. **Traces and grader** — read actual failing rows. A grader regression looks exactly like an agent regression from the summary line.
3. **Per-category breakdown** — is the drop concentrated or diffuse? Concentrated drops have causes; diffuse drops are usually variance (see §2a).
4. **Only then, the agent.**

*(Sources: `eval/eval-harness-anatomy.md`, `eval/eval-suite-maintenance.md`, `eval/golden-set-mechanics.md`)*

---

## 6. Prompt version impact on evals

When a prompt changes:
- Re-run the full eval suite before promoting to production.
- Cached model responses for prior prompt versions are invalid.
- Grader calibration baselines that used the prior prompt version may no longer hold.
- Record the `prompt_version` in every eval artifact (see `agent-observability.md §2`, `agent-context.md §4`).

A threshold change to a grader without liked/disliked separation evidence is commentary, not release policy.

---

## 7. Experimental vs. hard-gate graders

Every grader is in one of three states:

| State | Use |
|---|---|
| **Heuristic** | Rule-based, fast, reliable — suitable for hard gates (e.g., citation hallucination) |
| **Calibrated** | LLM-as-judge with evidence of liked/disliked separation — suitable for hard gates |
| **Experimental** | Uncalibrated or insufficient sample — tracking only; never a release gate |

Experimental graders may inform investigation. Stakeholder recommendations and release decisions must cite only heuristic or calibrated graders.

---

## 8. What an eval set must be to support hill-climbing

`DESIGN-PROCESS.md §4` names this spec as the prerequisite for a level-4 loop — one that improves its own criterion over runs. The wiki states the prerequisite as a **bound**, not an aspiration:

> **An automatic gate that can fail the work.**

Everything else is downstream of that. Three properties follow:

**1. The evaluator must be outside the agent's write boundary.** *"An agent that can edit its own evaluator does not have a verifier; it has a negotiation."* Karpathy's `autoresearch` (2026-03-06, MIT, ~630 lines) enforces exactly this at the filesystem layer: the agent may write `train.py` and may not touch `prepare.py`. The separation is a **permission**, not an instruction — which is the enforcement ladder applied to evaluation.

**2. The hit rate will be low, and the loop must be sized for that.** In `autoresearch`, 20 of roughly 700 experiments were stackable — under a 3% hit rate. A hill-climbing loop that assumes most iterations improve things is mis-specified. Budget for the 97%.

**3. The bottleneck is verification capacity, not generation capacity.** *"If you have an objective metric, you are the bottleneck."* The Amdahl-style consequence: once generation is cheap, total improvement rate is set by how fast candidate changes can be **checked**, not how fast they can be **proposed**. Adding generation throughput to a loop whose gate is a human reading diffs buys nothing.

**Corollary for this repo.** The gap `DESIGN-PROCESS.md §4` reports is not "we lack a dataset." It is that a level-4 loop needs a gate that (a) fails automatically, (b) the agent cannot edit, and (c) is cheap enough to run per candidate. The current level-2 gates — hook exit codes, test results, the merge verdict — satisfy (a) and (b) already; §5's suites are what supply (c). Note that the merge verdict is *computed* rather than judged, which is what makes it eligible as a gate at all.

**The subtraction case.** The same requirement is what makes harness *removal* possible: *"Without it, subtraction is unmeasurable and nobody dares — which is exactly how harnesses calcify."* An eval set earns its cost as much by licensing deletion as by catching regressions.

*(Sources: `loop/recursive-self-improvement.md`, `harness/iterative-harness-simplification.md`, `harness/verification-loops.md`)*

---

## 9. Verification is asymmetric

A gate is only a gate if it is harder to fool than to pass. The wiki's rule: **the verifier must be structurally smarter than the generator** on the dimension being verified — not merely a second call to the same model with the same context.

Structural asymmetry comes from at least one of:

- **Different information** — the verifier sees the ground truth, the test output, or the retrieved passages that the generator did not.
- **Different capability tier** — a stronger model checks a cheaper one.
- **A determinism advantage** — the check is code, and code beats judgement whenever the property is decidable (`DESIGN-PROCESS.md §3`).

Symmetric verification — same model, same context, "now check your work" — measures self-consistency, not correctness. Note the tension with `agent-runtime.md §5`, which treats model escalation as a last resort on cost grounds: that guidance is about *retrying generation*, not about *staffing the verifier*. Cheapest-model-that-works is a generation policy; it is the wrong policy for a gate.

Two constraints from `agent-uncertainty.md` bind here and are easy to lose in grader design. First, a grader must be able to return **abstain** — a grader forced into pass/fail on a case it cannot judge is a collapse site (`§2` there), and it launders "I don't know" into a score that moves the gate. Second, once a score is optimized against it stops measuring what it measured; that is why §8's evaluator sits outside the agent's write boundary, and why `agent-safety.md`'s adversarial section treats Goodhart as structural rather than hypothetical.

*(Source: `harness/verification-loops.md`)*

---

## Sources

- Topics 4.1, 4.2, 4.3 from `2026-07-19-research-B-topic-canon.md`
- `new-agent/references/eval.md`, `test.md`
- `eval/eval-non-determinism.md` — `pass@k` vs `pass^k`; trial independence
- `eval/eval-harness-anatomy.md`, `eval/eval-suite-maintenance.md`, `eval/golden-set-mechanics.md` — capability vs regression suites; debugging order
- `eval/eval-maturity-ladder.md` — the three ladders
- `loop/recursive-self-improvement.md` — the hill-climbing prerequisite; `autoresearch`
- `harness/iterative-harness-simplification.md` — subtraction requires measurement
- `harness/verification-loops.md` — asymmetric verification
