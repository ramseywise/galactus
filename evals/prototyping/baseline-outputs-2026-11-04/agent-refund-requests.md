# refund-agent
Date: 2026-11-04
Status: RESEARCHED
Track: agent

## Research

### Summary
The agent should be a short fixed workflow with one narrow model step, not a free act-observe loop with a refund tool: the model reads the email, code checks the order and the rule and moves the money, and every run ends as `refunded`, `handed_off` or `outcome_unknown`. The varying paths (missing order number, several orders) belong in a bounded, read-only resolve stage; nothing the model says can widen what the code would allow, and there is no automatic denial. The worst per-item error is capped by the rule, so the bigger risks are duplicate refunds, ambiguous API timeouts and correlated failures, and those shape the design more than model accuracy does.

### Scope
**Investigated:** loop shape, who decides what, failure and termination behaviour, handling of the two named path variations, rollout evidence, and which repo assets apply. Evidence is the snapshot's specs and skills plus public sources.

**Out of scope:** implementation, framework choice as a final decision (`/proto-plan`), model choice, and the rest of the support inbox.

**Not available:** the refund API, the order API, the policy document, ticket history and the support team's tooling. Everything about them is an assumption or a Key Unknown.

**Pipeline note:** `CLAUDE.md` enters `/proto-research` once a spec exists, and no spec exists for this request. The request does state a consumer (refund API, or a person) and a cost of being wrong (real money, hard to recover), but it does not answer every layer of the five-layer stack. `/proto-design` could not be run here, so finding 8 gives provisional layer answers and Key Unknowns lists the open FRAME items.

### Findings

**1. Use a fixed workflow (orchestration level 3), with no model-driven path to the refund. Confidence: High.**
The money decision is decidable: amount, delivery date and order ownership are fields, and the rule is a comparison. The repo's rule is that a deterministic check wins whenever it can answer (`.claude/specs/agent-uncertainty.md:147`) and that truth stays in deterministic systems (`agent-uncertainty.md:19`). This request also matches the stated refactor trigger, "if the tool result shows X, then call tool Y" (`agent-architecture.md:24`), the auditable-control-flow signal (`:35`), and the name-every-node test (`:44`). ReAct's reported sweet spot is 1-3 calls on low-stakes tasks, and it breaks down when partial failure leaves inconsistent state (`:78`), which is exactly the multi-order case.

The shape the planner should take forward:

```
inbox event
  -> EXTRACT      model, no tools: is this a refund request? which order refs? (typed output)
  -> VALIDATE     code: schema valid; each order ref appears literally in the email
  -> RESOLVE      code, read-only: fetch each order; confirm sender owns it
  -> EVALUATE     code, every order, before any money moves: the rule + exclusions + limits
  -> all pass? --no--> HAND OFF (reason + what was checked + what was not)   [handed_off]
       | yes
  -> RE-READ      code: fresh order state immediately before commit; any change -> HAND OFF
  -> COMMIT       code: record intent durably, issue with a business key
  -> READ BACK    code: success -> [refunded]; ambiguous -> [outcome_unknown], priority person
```

The only cycles are bounded retries: transient failures up to 3 and tool errors 1, with one budget per run (`agent-reliability.md:64`, `:71`), plus a per-run cost ceiling that fails closed (`agent-safety.md:264`). A failed gate is terminal. It gets no repair edge back to the model, because that would turn the model into an optimiser against the gate. This is where `marketing-comms` must not be copied: its repair-then-fallback loop (`runs/ai/marketing-comms/src/generate.py:5-6`) forces compliance, and here the only safe fallback is a person.

**2. The model may narrow what happens, never widen it. Confidence: High.**
The model supplies intent and candidate order references only. Amount, delivery date, customer identity and refund history come from the order record. The refund tool is not available to the model at all, which is stronger than a confirm gate because "an absent tool cannot be called" (`agent-tools.md:160`). Model confidence can send a case to a person but cannot authorise a refund, since rank-by-blast-radius rules confidence out as the sort key (`agent-uncertainty.md:100`).

The residual probabilistic risk is intent: "I may want a refund if it doesn't arrive by Friday", or "what is your refund policy?". This cannot be made decidable, so it has to be measured (finding 7). A second model pass is not independent verification (`agent-eval.md:208-216`).

**3. Handle the variable paths in RESOLVE, conservatively. Confidence: Medium, because API search capability is unknown.**

| Case | Treatment | Why |
|---|---|---|
| No order number | Lookup by verified sender if the API supports it. Exactly one candidate order that is also consistent with the email continues; zero or several hands off | "Never act on a guess when the action is irreversible" (`agent-safety.md:252`) |
| Order number not in email text | Hand off | Catches a hallucinated reference deterministically |
| Sender does not own the order | Hand off | Stops cross-customer refunds whatever the email says |
| Several orders | Evaluate each one, then apply request-level limits; any failure hands off the whole request before money moves | The aggregate limit is a true dependency (`agent-architecture.md:195`), and a person should not inherit a half-finished case |
| Asking the customer | Defer | It adds a customer-facing write, a third outcome and a wait of days, and the request names only two outcomes. Reconsider if shadow data shows missing references are a large share |

At about 60 emails per working day (300 / 5), neither parallel fan-out nor a latency-driven design is warranted. A queue trigger with a seconds-to-minutes expectation fits (`agent-runtime.md:44`). If deterministic resolve leaves too many cases unresolved, the next step is a small read-only model loop capped at about 3 calls inside RESOLVE, which adds no refund risk because COMMIT is still downstream of EVALUATE.

**4. Handing off should be terminal, which removes the need for pause and resume. Confidence: Medium.**
The spec's strongest argument for graph machinery is that a pausing loop "has nowhere to put its stack" (`agent-architecture.md:105`). That applies only if the agent waits for a human and then continues. The request says the request is passed to a person, who can then use the normal process. Escalation as a legitimate terminal state is the repo's own framing (`agent-safety.md:67`). Terminal handoff removes the interrupt, resume and re-execution hazards (`.claude/skills/langgraph-human-in-the-loop/SKILL.md:31`, confirmed by the [LangGraph interrupt docs](https://docs.langchain.com/oss/python/langgraph/interrupts)). Durability is still needed for the commit record, not for a suspended run.

The handoff is a product surface. It must carry the decision evidence and declare what was not checked (`agent-architecture.md:171`), or the person repeats all the work.

**5. The dangerous failures sit around COMMIT, and the spec's default key is not enough. Confidence: High on the logic, unknown on API behaviour.**
- **Duplicate refund:** the spec's example key is `run_id + step_id + tool_name` (`agent-reliability.md:114`). A customer's follow-up email ("where is my refund?") is a new run with a new run ID, so that key would allow a second refund. The key must come from business identity (order and refund scope), and the same order must be single-flight across runs and against human agents.
- **Key lifetime:** do not assume server-side keys last forever. Stripe's v1 API, as an external comparison, says keys can be removed after at least 24 hours, and a reused key then generates a new request ([Stripe](https://docs.stripe.com/api/idempotent_requests)). A durable intent record on the agent's side covers this.
- **Timeout on issue:** the money may or may not have moved. This is neither success nor failure, and treating it as failure invites a person to refund again. It needs its own state (`agent-uncertainty.md:77`). If the API has no keys, the call must not be retried (`agent-reliability.md:120`).
- **Stale evaluation:** the order can change between evaluation and commit, hence the re-read.

**6. Collapse sites: each of these must route to a person rather than read as an answer. Confidence: High.**
Per `agent-uncertainty.md:68`, ask what each step returns when given nothing.

| Site | Silent wrong reading | Required behaviour |
|---|---|---|
| Delivery date null, including every "never arrived" claim | Treated as in-window, or date arithmetic on a default | Unknown means hand off |
| Refund history missing or lookup partial | "No prior refunds" | Unknown means hand off; a prior refund counts against the limit |
| Lookup error versus no such order | Same empty result | Distinct codes; the error retries, not-found hands off |
| Non-EUR order, tax or shipping ambiguity | 50 compared with the wrong number | Non-EUR hands off; the definition of amount comes from the policy |
| Day-30 boundary, timezone | Off by one | Pin down and unit test |
| Handoff channel down, or ingestion drops an email | Request vanishes, which looks like no work | Conservation check: emails in = refunded + handed_off + outcome_unknown + in flight; alert otherwise |
| Rule breaker trips | Treated as eligible or ineligible | Handoff reason names it |

**7. The auto lane should be earned with evidence, and its worst case is a correlated failure. Confidence: High on the arithmetic, Medium on the rollout order.**
Per-item loss is capped by the rule at 50 EUR, so per-item error is affordable. Illustratively, at a 50% auto share and a 1% wrong rate, that is 300 x 0.5 x 0.01 x 50 = at most 75 EUR per week. If the cap applies per request, the theoretical ceiling is 300 x 50 = 15,000 EUR per week; if it applies per order, multi-order requests raise that figure. The expensive scenarios are correlated: a retry bug, a policy or API field change, or an injection pattern. So the design needs an aggregate breaker on auto-refund count and value over time, set by the business and outside the agent's write boundary (`agent-architecture.md:345`).

Suggested evidence ladder: **shadow** (agent recommends, people do everything; `agent-tools.md:181`, `agent-observability.md:197`) -> **recommendation on the handoff** (watch for rubber-stamping; `agent-safety.md:94`) -> **auto lane** with a lower starting cap and limit, then ratchet up. Sample audits of auto refunds supply the path by which the system learns it was wrong (`agent-observability.md:264`).

Using the [rule of three](https://en.wikipedia.org/wiki/Rule_of_three_(statistics)), zero errors in n decisions gives a 95% upper bound of about 3/n, assuming independent trials. Correlated errors make these figures optimistic.

| Wrong-refund bound to demonstrate | Clean decisions | Weeks at 50% auto-eligible | Weeks at 20% auto-eligible |
|---|---|---|---|
| 1% | 300 | 2 | 5 |
| 0.5% | 600 | 4 | 10 |
| 0.1% | 3,000 | 20 | 50 |

Report the wrong-refund rate paired with the automation rate, and watch handoff rate as the counter-metric (`agent-architecture.md:341`). `pass^k`, not one-off success, is the relevant claim for repeated runs (`agent-eval.md:56`). Historic tickets could seed the regression suite: 100-1,000 rows (`agent-eval.md:142`) is about 2 working days to 3.5 weeks of volume, subject to the caveats under Key Unknowns.

**8. Provisional answers for the five layers, and the injection boundary. Confidence: Medium.**
- **Prompt:** one job, typed output with an explicit `unclear` option, so that abstaining is representable. Business rules stay out of the prompt, because a prompt-only invariant is soft (`.claude/skills/review-shared/dimensions/review-contracts-violations.md:47-50`).
- **Context:** the email only, delimited as untrusted (`agent-context.md:150`). No policy text and no retrieval are needed for extraction. Four pages is also too small to justify RAG if a person-facing summary is wanted later.
- **Harness:** the gate, single-flight, breaker, audit trail and conservation check are all code. Record model and prompt version, policy version, inputs to the decision and outcome. Check redaction before traces store customer email content (`agent-safety.md:295-298`), and redact at prompt assembly whatever extraction does not need (`agent-memory.md:74`).
- **Loop:** finding 1.
- **Graph:** a linear flow with exits. No multi-agent split: none of the permitted reasons applies (`agent-architecture.md:197-202`).
- **Injection:** the email is the attack surface. There is no consensus defence (`agent-safety.md:7`), so bound the impact (`:154`). This is a form of the quarantined-reader pattern (`:170`). [Beurer-Kellner et al.](https://arxiv.org/abs/2506.08837) likewise argue that after ingesting untrusted input an agent must be constrained so that input cannot trigger consequential actions, and note that a quarantined model remains injectable. The result here is that a successful injection achieves about what a plain lie achieves: an in-rule refund on the sender's own order. Note that **this design does not detect a lying customer**. The stated rule has no reason check, so abuse is a policy and limits problem, not a loop problem.
- **Customer messages:** use templates. A generated reply could promise a refund, and a company can be held responsible for what its bot says ([Moffatt v. Air Canada, 2024 BCCRT 149](https://www.mccarthy.ca/en/insights/blogs/techlex/moffatt-v-air-canada-misrepresentation-ai-chatbot); a Canadian tribunal decision, not EU law). Refund-confirmation messaging is absent from the request, and without one customers will send follow-up emails.

### Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `.claude/specs/agent-{uncertainty,reliability,safety,tools,architecture,eval,observability}.md` | REUSE | n/a | Directly govern this design; two conflicts are noted under Disconfirming Evidence |
| `runs/ai/marketing-comms` | ADAPT | n/a | Reuse the "pure function decides, model's cooperation is optional" thesis and its behaviour counters. Do not copy the repair loop or the forced-compliance fallback (`generate.py:5-6`) |
| `.claude/skills/new-agent/references/cap-hitl.md` | SKIP | Yes: the payload-surfaced-to-a-person idea and the agnostic contract table (`:7-15`), if a later version needs pause and resume | Unsafe as a money gate as written: disabled by default (`:37`), a missing confidence reads as 1.0 (`:64`), confidence is the trigger (`:67`), and the operator can "pass" on a best guess (`:126`, `:156`) |
| `.claude/skills/new-agent/references/cap-guardrails.md` | ADAPT | n/a | Layer structure is useful. Its score-based escalation can route toward a person only and must not be read as authorising; deny-lists are not the boundary |
| `.claude/skills/framework-selection` | ADAPT | n/a | It points at LangGraph for HITL or branching, but offers no "plain code plus structured calls" option. With terminal handoff that option deserves consideration in `/proto-plan` |
| `.claude/skills/langgraph-*`, `.claude/specs/langgraph.md` | ADAPT | n/a | Sound if LangGraph is chosen (`langgraph.md:44-46`). The HITL skill is not needed for v1 under finding 4 |
| `copier.yaml` `project_type: workflow` | ADAPT | n/a | Named fit for a new project (`:118`, archetype at `proto-scope/reference/archetype-selection.md:110-127`), but it derives `lg_agent` (`:450`). Not rendered or tested here. `/new` picks the landing place |
| `template/llm_kit` | SKIP | Possibly the call and cost helpers, for a shadow-mode spike only | Explicitly a 60-minute starter that does not ship into rendered projects (`README.md`) |

The internal order and refund APIs and the policy document were not available, so they get no verdict. See Key Unknowns.

### Assumptions
- **Assumption:** A refund always returns to the original payment method; the caller cannot choose a destination. — **Evidence:** none; not stated. — **If wrong:** blocker. A spoofed or injected email could redirect money, and the bounded-injection argument in finding 8 fails. — **Confidence:** Medium
- **Assumption:** The 50 EUR limit applies to the total auto-refunded per request and cumulatively per order. — **Evidence:** the conservative reading of "up to 50 EUR". — **If wrong:** more handoffs than necessary if the true rule is per order. This errs in the cheap direction. — **Confidence:** Low
- **Assumption:** "Everything else needs a person" means the agent never denies. — **Evidence:** the request's wording. — **If wrong:** adds a customer-affecting decision, a generated or templated denial, and GDPR Art. 22 questions (next assumption). — **Confidence:** High
- **Assumption:** The EU is in scope, given EUR. No automatic denial and a human route lower exposure under [GDPR Art. 22](https://gdpr-info.eu/art-22-gdpr/). — **Evidence:** inferred from the currency; my reading, not legal advice. — **If wrong:** counsel may need to review the design. — **Confidence:** Low
- **Assumption:** Partial-order requests go to a person in v1, and the amount always comes from the order record. — **Evidence:** the safe default; line-item support is unknown. — **If wrong:** a lower automation rate until added. — **Confidence:** Medium
- **Assumption:** A person takes over through the existing support process and never returns the case to the agent. — **Evidence:** "passes it to a person". — **If wrong:** durable pause and resume are needed, and finding 4 reverses. — **Confidence:** Medium
- **Assumption:** The rest of the 4-page policy contains exclusions beyond the two stated conditions. — **Evidence:** the length of the document compared with a two-condition rule. — **If wrong:** the encoding work is smaller. — **Confidence:** Medium
- **Assumption:** Latency is unimportant: minutes are acceptable. — **Evidence:** inbox channel; about one email per 8 working minutes on an 8-hour day. — **If wrong:** only if a live-chat channel is added. — **Confidence:** High

### Disconfirming Evidence
- **Finding 1 (code decides, not a free agent).** *What would contradict it:* good evidence that models follow refund policy reliably in a free loop, or a policy that is mostly judgment. *Looked:* [Anthropic's agent guidance](https://www.anthropic.com/engineering/building-effective-agents) names customer support as a good agent fit and says refunds "can be handled programmatically", though it also advises the simplest solution first and doesn't address refund approval. [τ-bench](https://arxiv.org/abs/2406.12045) reported under 50% task success for gpt-4o in 2024; aggregator pages suggest roughly 80-85% on τ²-bench for 2026 models. Those newer figures are unverified against the official board, and they measure whole simulated conversations, not this narrow task. *Result:* models have improved materially, so the "models can't do this" argument is dated. The conclusion survives because code is still better on a decidable check. A policy dominated by judgment would lower the automation rate, not move the money decision to the model. I could not check the policy.
- **Finding 2 (deterministic gate is enough to act).** *What would contradict it:* the repo's own table says an irreversible external action needs "human approval before execution" (`agent-uncertainty.md:96`), and `agent-tools.md:179` requires a confirm step. *Looked:* `agent-safety.md:227` allows the "orchestrator" to affirm. *Result:* an open tension, not a clean pass. I read the rule as a business-accepted risk within a capped lane, with code as the orchestrator. If the owner of that spec disagrees, the auto lane needs per-refund human approval, which removes most of the value. It must be accepted explicitly.
- **Finding 4 (terminal handoff).** *What would contradict it:* people can only approve, or only the service can reach the refund API, or approve-and-execute is wanted in one click. *Looked:* the request only; no access to the support tooling. *Result:* unverified.
- **Finding 5 (business key).** *What would contradict it:* the refund API already enforces cumulative per-order limits and exposes history reliably. *Looked:* the API was unavailable. *Result:* unverified; this would make the design simpler, not unsafe.
- **Whole approach (is an agent justified?).** *Steel-man:* a required order field on a refund form removes extraction, injection and most of the resolve stage, and a plain rule could then issue refunds. If the auto-eligible share is small, a triage aid gives most of the value with no money-moving risk. *Looked:* Anthropic's guidance notes the answer may be no agentic system at all. *Result:* not refuted. The auto-eligible share decides it, and it is unknown. Shadow mode answers it before any money is at risk.
- **Limits of this evidence.** The specs' "wiki" quotations come from pages not in the snapshot and could not be checked. Web pages were read through a summarising fetch. Moffatt rests on a law-firm summary and a search summary rather than the decision itself. The last ~9,000 characters of the Beurer-Kellner HTML were not read. I found no production postmortem of a refund agent, so the failure scenarios here are reasoned from the specs and sources, not observed.

### Key Unknowns
Blocking before `/proto-plan`:
1. **Refund API:** idempotency keys? How long are they retained? Is the status queryable by key? Destination selectable? Partial refunds? Server-side limits? A timeout's semantics?
2. **Order API:** search by customer or email, or only by ID? Are delivery date, currency, line items, prior refunds and customer identity all reliable fields? Is delivery date sourced from the carrier, and how fresh is it?
3. **Policy text:** every clause needs classifying as encoded rule, forced handoff, or irrelevant. Who owns it, and how does a change reach the code? What does "up to 50 EUR" apply to, and is day 30 inclusive?
4. **Human side:** where does a handoff land, can it be monitored, and does anyone other than the agent issue refunds on the same orders concurrently?

Needed for rollout decisions:
5. **Mix of requests:** what share is auto-eligible, missing a reference, multi-order or never-arrived? This sets the value of the whole project.
6. **Cost figures:** handling cost per request today, the actual cost of a wrong refund (including any recovery), and the risk appetite for breaker limits. None was stated, so the ROI was not calculated.
7. **History quality:** are past tickets exportable and linked to outcomes? Can order state at that time be reconstructed? Human decisions may be more lenient than the policy, so they are not automatically ground truth.
8. **Sender trust:** are SPF/DKIM results available at ingestion? What about language mix, attachments, and threads that span several emails?
9. **Data handling:** is customer email approved for the model vendor and trace backend? What retention does the audit trail need?

FRAME items still open, best settled through `/proto-design`: acceptance of the auto-lane risk against `agent-uncertainty.md:96`; whether a customer is told anything and when; a target rate for wrong refunds; and a monthly cost ceiling.

### Recommendation
The research supports a fixed workflow in which the model only reads the email, deterministic code resolves orders and applies the rule to all orders before any money moves, and every other case, including every unknown, ends with a person. It suggests treating handoff as a terminal outcome, keying refunds on business identity rather than run identity, giving an ambiguous refund result its own state, and adding aggregate limits against correlated failure. It also suggests that the auto lane be earned through shadow-mode evidence rather than assumed at launch, because the auto-eligible share determines whether the money-moving part is worth building at all. Before planning, the refund API's idempotency and destination behaviour, the order API's search and field reliability, and a clause-by-clause reading of the policy should be established, and someone with authority should explicitly accept the auto-lane risk.

**Next step:** `/proto-plan refund-agent` once this is reviewed, ideally after `/proto-design` closes the FRAME items above.
