# sms-copy-guardrails
Date: 2026-11-04
Status: RESEARCHED
Track: agent

## Research

### Summary
Both of Legal's rules can be decided by code, so neither should depend on the model or the marketer noticing. There are two separate problems. Marketer annoyance is best reduced by having code own the footer, which leaves the model a 138-character body budget, plus a bounded retry when the body runs long. The compliance risk is closed only by a hard check at the point of sending, on the final text after any marketer edit. A check placed around the model never sees that text. When retries run out, show the marketer the over-long draft flagged and unsendable rather than truncating it, because truncation can change an offer and still pass both rules.

### Scope
Investigated: where each guardrail should sit, what the model can and cannot be relied on for, what happens when guardrails fail, what "160 characters" means on the wire, and what in the galactus snapshot (commit `ae2315d`) can be reused. Snapshot paths below are relative to its root.

Out of scope: implementation design, consent capture, content quality, and whether Legal's two rules are sufficient. No model was called, so nothing here measures an SMS draft. The existing service's code was not available.

### Findings

**F1. Have code own the footer, so the model never writes it. Confidence: High.**
"Reply STOP to opt out" is 21 characters (computed). With a one-character separator, the body budget is 138; the budget is the same whether that separator is a space or a newline. Code-added text removes the wrong-wording, wrong-case, trailing-period and missing-footer failures from generated drafts altogether, instead of detecting them later. This follows the repo's rule that truth lives in deterministic systems (`.claude/specs/agent-uncertainty.md:19`) and its thesis that counting is code's job (`CLAUDE.md:6`). A recent law-firm summary of FCC Order 26-67 uses this exact sentence as its example of disclosure placed separately from other content ([DLA Piper, 20 Oct 2026](https://www.dlapiper.com/en/insights/publications/2026/10/fcc-tcpa-rule)). That is supporting context and does not replace Legal's reading.
*Planner:* the model's output contract is the body only, and the footer is a single constant.

**F2. Only a check at the send boundary gives a compliance guarantee. Confidence: High.**
A check around the model cannot see what changes afterwards: marketer edits, merge-field expansion, link shortening or tracking, and any send path that skips generation. The repo makes the same placement argument, that a layer at the model call "sees none of those" risks (`.claude/specs/agent-safety.md:47`). An SMS cannot be recalled once sent, which puts it in the repo's "irreversible external action" row (`.claude/specs/agent-uncertainty.md:96`). The gate should therefore evaluate the exact bytes handed to the provider, per rendered message if personalisation exists, and should block rather than warn. It should enforce only Legal's rules plus the empty-body case in F6, so it does not become a false-positive tax (`.claude/specs/agent-safety.md:53`). The repo also counts documented-but-unwired controls as absent (`.claude/specs/agent-uncertainty.md:38`).
*Planner:* find every path that reaches the provider. "Cannot bypass the gate" is an acceptance criterion, not an assumption.

**F3. Marketer review should not be the control for these two rules. Confidence: Medium.**
Counting to 160 by eye is a poor use of a person, and a tool that is usually right invites complacency. The Parasuraman and Manzey review says complacency occurs under multiple-task load, affects experts as well as novices, and "cannot be overcome with simple practice" ([abstract](https://trid.trb.org/View/1085175); abstract only, not the full paper, and not an LLM or SMS study). Once code decides format, the marketer's attention can go where code cannot check: invented discounts, wrong dates, tone and claims. Both of Legal's rules can pass on a message whose offer is false, so review remains necessary for content.
*Planner:* a live count and a locked footer belong in the review surface. Keep human review, but scope it to content.

**F4. Length instructions and schemas help but do not bind. Confidence: High on the schema facts, Medium on model behaviour.**
- Anthropic lists `minLength` and `maxLength` as unsupported. SDK helpers strip them, and only some helpers validate the response client-side ([structured outputs docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)). This agrees with `runs/ai/marketing-comms/src/generate.py:11-18`.
- OpenAI's list of supported string properties includes `pattern` and `format` but not the length keywords ([docs](https://developers.openai.com/api/docs/guides/structured-outputs)). A provider-enforced regex might therefore be able to constrain length. I did not test it, and a hard stop at a character boundary could produce the same bad endings as truncation (F5).
- Both providers document refusal and `max_tokens` exceptions to schema conformance.
- In the reference run, on a different and harder nine-field contract, only 33.3% of drafts passed first time, and 41.7 / 33.3 / 33.3% across three runs (`runs/ai/marketing-comms/docs/DESIGN.md:313,328-329`). This does not predict the SMS rate, but it shows a deterministic layer holding the contract while the model's own pass rate moves.
*Planner:* state the budget in the prompt as an optimisation, and treat code as what decides.

**F5. When retries run out, escalate. Do not truncate. Confidence: Medium.**
The reference design's "always succeeds" fallback suits a consumer that must receive valid JSON (`runs/ai/marketing-comms/src/guardrails/fallback.py:1-11`). Here a person is already in the loop, so nothing forces a mechanical result. I ran the reference's own `_truncate_to_chars` on an illustrative 146-character body that I wrote, cutting to the 138-character budget. The result was "...excludes clearance items and gift cards, online orders over Reply STOP to opt out", which is 158 characters and passes both of Legal's rules. A cut-off condition such as this one can misstate an offer's terms, and it turns a visible formatting failure into a compliant-looking content failure. The repo treats escalation as a legitimate outcome rather than an error (`.claude/specs/agent-safety.md:65`).
*Planner:* the terminal state is a typed "needs shortening" status with the full text visible and sending blocked.

**F6. Three inputs pass the rules while being wrong. Confidence: High on the logic; the behaviour of the target service is unknown.**
- **Empty body:** the footer alone is a 21-character message that passes both rules (computed). This is the repo's "what does it return when it was given nothing?" collapse site (`.claude/specs/agent-uncertainty.md:68`).
- **Output cut off by `max_tokens`:** a partial sentence fits the budget more easily than a complete one, so a length check alone will pass it. Stop reason has to be checked.
- **Refusal or provider failure:** this must not be retried or reported as a length violation (`.claude/specs/agent-reliability.md:17`, `.claude/specs/agent-uncertainty.md:77`).
A body that includes its own opt-out sentence is a lesser case. It wastes budget and reads badly, so it should trigger regeneration at draft stage but need not be a send-gate rule.
*Planner:* each of these needs a named outcome and a test.

**F7. "160 characters" has at least three meanings, and they diverge on characters LLMs commonly produce. Confidence: High on the arithmetic; Legal's intent is unknown.**

| Measure | Example | Result |
|---|---|---|
| Python `len` (code points) | A message with one emoji | The emoji counts as 1; it is 2 in UTF-16 (computed) |
| GSM-7 septets | 160 characters including one `€` | 161 septets, 2 segments at 153 per segment |
| UCS-2 | 160 characters including one curly apostrophe | Whole message switches encoding, 3 segments at 67 per segment |

The limits and the curly-quote behaviour come from [Twilio's glossary](https://www.twilio.com/docs/glossary/what-sms-character-limit). That page also says Twilio Smart Encoding replaces curly quotes, which would mean the sent text differs from what was approved. If messages are restricted to the basic GSM-7 alphabet, all three measures agree and 160 characters is exactly one segment. The cost is no emoji, no `€`, and limited non-English support. Replacing typographic punctuation with its plain equivalent before review keeps approved and sent text identical.
*Planner:* treat this as a Legal and marketing decision and use the assumption below until it is answered. The count definition must be single and shared by prompt, validator, review UI and send gate.

**F8. Generic guardrail frameworks and LLM judges add nothing for these rules. Confidence: High for LLM judges, Medium for frameworks.**
Every LLM call must justify itself against a character count (`.claude/specs/agent-uncertainty.md:147`), and a verifier that can be talked out of its verdict is not a control (`.claude/specs/agent-safety.md:338-340`). Guardrails AI offers `ValidLength` with `reask` and `fix` policies ([hub page, from search results](https://hub.guardrailsai.com/validator/guardrails/valid_length)), which is the same loop behind a dependency, and it does not reach the send path. NeMo Guardrails was not assessed because the search returned nothing on it.
Scale does not push the other way. 400 a month is about 13 a day, and even four calls per message at the reference's rough $0.003 per piece (`runs/ai/marketing-comms/docs/DESIGN.md:339`) is about $4.80 a month. That figure comes from a different workload and is only an order of magnitude, but it shows cost should not drive this design.
*Planner:* keep this as a small amount of plain service code.

**F9. Guardrails need counters and falsifiable tests. Confidence: High.**
A guardrail that never fires may simply be unwired, and one that fires constantly gets ignored (`.claude/specs/agent-safety.md:53-61`). The useful signals are: first-pass rate, retries per draft, exhausted drafts, send-gate blocks split by whether the marketer edited the text, and how often marketers shorten drafts by hand. The reference already tracks the first three equivalents (`runs/ai/marketing-comms/evals/run.py:478-484`). Tests must be able to fail (`.claude/skills/review-shared/dimensions/review-safeguards.md:37`): 160 and 161 at the boundary, a trailing period, wrong case, a doubled footer, an empty body, a non-breaking space inside the footer, and a typographic apostrophe.
*Planner:* "fewer marketer complaints" needs a baseline from existing logs before anything ships.

**Guardrails mapped to the failure each one addresses**

| Guardrail | Addresses | Needed for compliance? |
|---|---|---|
| Code-owned footer | Rule 2 breaches in drafts | No, the gate covers it; this is the largest annoyance fix |
| Budget stated in the prompt | Long first drafts | No |
| Draft validator with bounded retry | Long, empty or cut-off drafts reaching marketers | No |
| Flagged escalation when retries run out | Mechanical truncation of offers | Indirectly; protects content |
| Live count and locked footer in review | Marketer edits breaking the rules | No, but it prevents gate blocks |
| **Send-boundary gate** | Any breach from any path | **Yes, this is the control** |
| Counters and audit record of sent text | Unwired or drifting controls; later evidence | Supports proving it |

### Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `runs/ai/marketing-comms/src/guardrails/validator.py` | ADAPT | Pattern is separable: pure function, returns all violations with a repair hint | Has no exact-suffix constraint, and `max_chars` uses `len` (`:109`), which F7 may rule out |
| `runs/ai/marketing-comms/src/generate.py` (repair loop) | ADAPT | Bounded loop, exact-violation feedback, counters on state (`:221-239`) | Right shape. Its "always succeeds" contract and fallback branch do not apply |
| `runs/ai/marketing-comms/src/guardrails/fallback.py` | SKIP | Re-validate rather than trust, and typed degraded marking (`generate.py:241-256`). Not truncation or the "and" filler | Mechanical repair is harmful for promotional claims (F5) |
| `runs/ai/marketing-comms/evals/run.py` | ADAPT | Metric definitions (`:478-484`). Cases are not reusable | The cases test a PDF-grounded layout contract, not SMS |
| `.claude/specs/agent-safety.md` five-layer model | ADAPT | Layer 4 and Layer 5 placement, plus the firing-counter rule | Layers 2 and 3 concern retrieval and do not apply unless drafts are grounded in documents |
| `.claude/skills/new-agent/references/cap-guardrails.md` | SKIP | The fast-check versus offline-eval split, per `runs/ai/marketing-comms/docs/cap-reuse.md:25-36` | Scaffold is shaped around an agent loop and raises on first failure. I read its contract and the reuse triage, not the whole scaffold |
| Provider structured outputs | ADAPT | Body-only output shape | Shape only, and not binding on length (F4) |
| Guardrails AI | SKIP | Nothing beyond the reask/fix vocabulary | Same loop plus a dependency, and no reach into the send path |

### Assumptions
- **Assumption:** the skill's FRAME-gap stop does not apply, even though no `/proto-design` spec exists. — **Evidence:** the consumer (marketer), the checkable definition of correct and the cost of being wrong are all stated in the request. The question concerns one harness boundary. — **If wrong:** run `/proto-design` before `/proto-plan`; prompt, context and graph answers here are minimal. — **Confidence:** Medium
- **Assumption:** the five layers resolve minimally: prompt asks for body only; context is the marketer's brief; harness is validator plus gate; loop is a bounded retry; graph is a single call followed by a human pause. — **Evidence:** the request, plus F1 and F2. — **If wrong:** multi-step generation adds more places for a draft to change, but the gate position does not move. — **Confidence:** Medium
- **Assumption:** the track is `agent`. — **Evidence:** the feature calls a model and fits none (skill routing rule). — **If wrong:** would need a training dataset, and none is mentioned. — **Confidence:** High
- **Assumption:** until Legal answers, "160 characters" is enforced as at most 160 on the GSM-7 basic alphabet, which also forces one segment. — **Evidence:** F7. — **If wrong:** if Legal means literal characters and marketing wants emoji, relax the alphabet and accept multi-segment sends. — **Confidence:** Medium
- **Assumption:** "exact text" means case-sensitive, byte-identical and final, with nothing after it, including whitespace or punctuation. — **Evidence:** Legal's wording in the request. — **If wrong:** the gate becomes slightly looser. — **Confidence:** High
- **Assumption:** 400 means 400 distinct drafts, each reviewed. — **Evidence:** "reviews each one". — **If wrong:** if one approved template fans out to many recipients, per-recipient rendered length becomes the main risk. — **Confidence:** Medium
- **Assumption:** the galactus reference run is not the existing service. — **Evidence:** it generates PDF-grounded layout collateral and the snapshot has no SMS references (repo-wide search). — **If wrong:** asset verdicts move towards REUSE. — **Confidence:** Medium
- **Assumption:** US-style English SMS. — **Evidence:** the footer wording and STOP convention. — **If wrong:** translated footers and non-GSM alphabets reopen F1 and F7. — **Confidence:** Medium

### Disconfirming Evidence
- **F1:** Contradicted if Legal requires the opt-out woven into the copy, or if the separated footer hurts copy quality. Nothing in the request suggests the first, and the FCC summary leans the other way. The second is unmeasured.
- **F2:** Contradicted if marketers effectively never miss a breach and no edits or later rendering occur, in which case the gate would rarely fire. I found no data on this. The gate is cheap and a miss cannot be recalled, so it holds even at a low firing rate.
- **F3:** The strongest counter-evidence is that the complacency literature comes from other domains, and that a marketer making a deliberate approval at about 13 messages a day is not under the multi-task load it describes. I weighted this by lowering confidence to Medium. The Goddard et al. systematic review was located, but its text could not be fetched, so it is not relied on.
- **F4:** [LIFEBench](https://arxiv.org/abs/2505.16234) says most models "reasonably follow short-length instructions", which argues against the claim that models cannot do this at SMS scale. It measures word counts from 16 words up (abstract read only), not character ceilings. Prompt methods such as [CAPEL](https://arxiv.org/abs/2508.13805) report better exact-length compliance (search summary only). These could raise the first-pass rate and reduce retries, but they do not replace the gate.
- **F5:** The steel-man is that a clearly labelled truncated suggestion saves the marketer time, and the reference's fallback rate was only 0.0 to 8.3%. A labelled suggestion alongside the full original is defensible. The firm requirement is that a truncated draft is never presented as a normal one. My example is constructed and shows the failure is possible, not how often it occurs.
- **F7:** Contradicted if Legal's rule is purely textual and the provider handles encoding acceptably. In that case the alphabet restriction is unnecessary. Sources agree on the headline limits but differ on how they describe header overhead; this does not affect the single-segment case.
- **F8:** A framework would earn its place if the service already uses one or if many more content rules are coming. I could not check the service, and the request names only two rules.

### Key Unknowns
- **Current failure rates:** how often each rule breaks, and how often marketers fix drafts by hand. This baseline is needed to set the retry budget and to show improvement. The reference uses 3 repairs (`runs/ai/marketing-comms/src/config.py:18`), while `.claude/specs/agent-reliability.md:18` says one retry for schema violations. A length miss is arguably not a schema violation, and the repo does not reconcile the two.
- **Legal's definition of a character**, and whether emoji or `€` are wanted (F7).
- **The service's send paths:** how many reach the provider, and whether anything alters text after approval (merge fields, link shortening, provider encoding or added text).
- **Provider and model:** determines schema capabilities and stop-reason handling. Whether `pattern` enforcement yields acceptable copy is untested.
- **STOP handling in practice:** the footer promises a behaviour. [Twilio's docs](https://www.twilio.com/docs/messaging/tutorials/advanced-opt-out) describe default keyword blocking for long codes, with toll-free behaving differently, but the provider here is unknown. Per the DLA Piper summary, one-way senders have extra disclosure duties, and revocations must be honoured within ten business days. It is a secondary source and the order's effective date was not confirmed, so route this to Legal.
- **Input trust:** whether briefs are staff-written or draw on external feeds. `.claude/specs/agent-safety.md:25` makes Layer 1 mandatory. Injection cannot beat code-enforced format rules, but it can affect content, and recipient data should not need to reach the prompt.
- **Audit requirements:** what Legal needs retained as proof, and whether rendered messages contain personal data that limits logging.
- **Rule override:** whether anyone may ever send outside the rules. The assumption here is no, short of a change by Legal.

### Recommendation
Treat the two rules as code-decided and separate the two goals. To reduce annoyance, the research supports having code own the footer, giving the model a 138-character body budget, and using a small bounded retry with exact feedback, ending in a flagged escalation rather than truncation. To remove the compliance risk, it supports a hard, non-bypassable check on the final rendered text at the send boundary, with marketers reviewing content rather than counting characters. It does not support an LLM judge, a guardrail framework or reusing the reference's truncation fallback. Before planning, get Legal's definition of "character", a baseline of current failures, and a list of every path that reaches the SMS provider.
