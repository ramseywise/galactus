# Order assistant: guardrails against cross-customer disclosure
Date: 2026-11-04
Status: RESEARCHED
Track: agent

## Research

### Summary
The breach risk is best closed by access control outside the model, not by detecting prompt injection: if `get_orders` takes the customer from the logged-in session and the orders system enforces it, a fully hijacked model still cannot fetch another customer's orders. Launch needs five controls: that identity binding, no data shared across conversations, output that cannot send data to an outside address, a cross-customer test with no model in it, and audit logging with an off switch. Injection filters, LLM judges and human review should not count toward this risk, and the other low-stakes errors need no runtime guardrail.

### Scope
Investigated: how another customer's order data could reach a logged-in customer or an attacker, which controls bound that, and which do not. Sources are the galactus specs and template, plus public security guidance and incident reports.

Out of scope: the shop's code, which was not available, so nothing here confirms how `get_orders` works today. Also out of scope are answer quality, tone, implementation design and a legal opinion on notification.

No `/proto-design` spec exists for this feature. See Assumptions.

### Findings

#### 1. Injection should be assumed to succeed, so the control has to hold when it does (High)
OWASP says it is "unclear if there are fool-proof methods of prevention" and advises handling privileged functions "in code rather than providing them to the model" ([LLM01](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)). In [The Attacker Moves Second](https://arxiv.org/abs/2510.09023), adaptive attacks bypassed 12 published defenses, with success above 90% for most, though most had originally reported near-zero attack success. The repo reaches the same conclusion: least privilege is "the only defence that bounds impact rather than probability" (`.claude/specs/agent-safety.md:154`).

Retries make a probabilistic control weak here. As an illustration, suppose a filter stops 99% of attempts and each attempt is independent. A logged-in attacker then has a 50% chance of success by attempt 69 and 95% by attempt 299, while the 2,000 legitimate daily conversations gain nothing from the filter.

**For the planner:** judge every guardrail by one question: if the model is fully hijacked, what can it still reach?

#### 2. The documented failures of this type are missing authorization, not clever prompts (High)
- A customer-support chatbot passed an order ID to a lookup with no ownership check. Predictable IDs let an outside user pull other customers' emails and shipping details ([arXiv 2608.10281, §3.5](https://arxiv.org/pdf/2608.10281); the company is unnamed).
- McHire exposed data on more than 64 million job applicants by changing `lead_id` in an API call. The researchers' prompt injection attempt failed and was not part of the exploit ([write-up](https://ian.sh/mcdonalds)).
- Millie's CVE-2026-4400 let anyone who knew a conversation ID read that private conversation ([INCIBE](https://www.incibe.es/en/incibe-cert/notices/aviso/multiple-vulnerabilities-1millionbot-millie-chatbot)).

Schema validation does not help, despite being the spec's listed control for tool inputs (`agent-safety.md:81`, `:139`): another customer's order ID is perfectly well formed.

**For the planner:** treat this as an access-control problem with an LLM in front of it, owned jointly with whoever owns the orders API.

#### 3. Guardrails needed for launch (High for the first and fourth; Medium for the second, third and fifth)
These are required properties, not designs.

| Guardrail | Property required | Failure it stops | Evidence that it holds |
|---|---|---|---|
| **Identity bound outside the model** | The model cannot name a customer. The customer comes from the authenticated session on the server. Any order number argument only narrows that customer's own orders. The orders system checks ownership with that user's authority, not a service account that can read everything. Fields returned match what the customer's order page shows. | Injection, or a plain request, for another customer's orders | Cross-customer test below |
| **Nothing shared across conversations** | Conversation history is checked for ownership on every read. No response or semantic cache and no memory crosses users. Prompts, examples and retrieved content hold no real customer data. Rows returned are checked against the session customer before they enter the model's context. | Data bleed with no attacker involved, such as a cache bug or a guessed conversation ID | Tests with two accounts; alert on any owner mismatch |
| **Output cannot call out** | The chat UI loads no remote images automatically and makes links live only for the shop's own domains. This is enforced in the renderer and the page's content security policy, not by asking the model. | A victim's assistant being steered into sending the victim's orders to an attacker (Finding 4) | UI test with a planted image and link; policy check |
| **Cross-customer test with no model in it** | Using customer A's session, every parameter combination for customer B's data returns nothing. It runs in CI and blocks release. It is first shown to fail against a deliberately unscoped version. A separate injection run plants a marker order on account B. It passes only if the marker never appears in a tool result. | A control that exists but is not wired or does not work | CI result, plus the recorded failing run |
| **Audit trail and off switch** | Each tool call logs the session customer, the owners of the rows returned and the conversation ID, in an access-restricted store. A mismatch pages someone. A flag can turn the assistant off without a deploy. A named person owns the breach decision. | A breach nobody can detect, scope or stop | Fire a test alert; flip the flag in production before launch |

Reasoning behind these requirements:
- **Identity binding:** OWASP asks for execution "in the context of that specific user" and "authorization in downstream systems rather than relying on an LLM" ([LLM06](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)). The nearest repo rule is `agent-safety.md:197`, which says not to bypass row-level security with a service key in a user-facing route. A useful acceptance line is that the assistant can never show anything the same login could not see on the order page. Account takeover then gains no new reach through chat.
- **Row owner check:** in the [March 2023 ChatGPT incident](https://openai.com/index/march-20-chatgpt-outage/), a Redis client bug exposed other users' chat titles and billing details with no injection involved. OpenAI's fix included redundant checks that returned data matched the requesting user. That page returned 403 to direct fetch, so this comes from search excerpts of the postmortem.
- **Test design:** the test checks the tool result rather than the model's wording, because a model that merely declined tells you nothing about the boundary. The spec's point is the same: without a baseline that attempts the action, "you have observed a model's mood" (`agent-safety.md:104-116`). Zero successes in 300 injection attempts would only bound the rate near 1% (rule of three), and only for non-adaptive attacks, so this run is a wiring check, not proof of safety.
- **Audit trail:** where GDPR applies, the 72-hour notification clock and the duty to document every breach ([Art. 33](https://gdpr-info.eu/art-33-gdpr/)) both need this record. Logs will now hold order data, so hash tool inputs and keep full payloads only in a restricted audit store (`.claude/specs/agent-observability.md:131`).

**For the planner:** make these the launch gate. Settle the identity binding first, because it carries the largest schedule risk (Key Unknowns).

#### 4. "Read-only" does not cover the output channel (Medium)
Scoping `get_orders` stops an attacker fetching a victim's orders from the attacker's own session. It does not stop an attacker reaching them through the victim's session. Willison's [lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/) is private data, untrusted content and a way to communicate externally. The assistant has the first. It has the second if any order field can be written by someone else, such as a gift message, marketplace seller text or a product name, or if a victim is talked into pasting a prompt. Rendered Markdown supplies the third: an image URL carrying encoded data sends it to the attacker's server when the browser loads it. This has been reported against [ChatGPT](https://simonwillison.net/2023/Dec/21/openai-begins-tackling-chatgpt-data-leak-vulnerability/), and Mistral Le Chat and GitHub Copilot Chat responded by disabling external image loading or image rendering (search excerpts; the Le Chat and Copilot reports were not read in full).

Removing the outbound channel closes this path without classifying any text. Confidence is Medium because those reports concern other products, and this path depends on order fields not yet inventoried.

**For the planner:** list every order field a third party can write. Keep the rendering restriction whatever that list shows, because the paste path remains and it is cheap.

#### 5. What not to count toward this risk (High for filters and judges; Medium for the rest)

| Candidate | Verdict | Why |
|---|---|---|
| Injection filter on input (regex or model) | Optional, log-only signal. Not a control for this risk. | It lowers probability but bounds nothing. Pattern filters push attacks toward whatever is unlisted (`agent-safety.md:118-124`). |
| Vendor guardrail product | Do not rely on it for this risk | Willison calls a claimed 95% catch rate "very much a failing grade" for security. |
| LLM judge on output | Skip | A checker that can be talked out of its verdict is not a control (`agent-safety.md:340`). |
| System prompt saying "never show other customers' orders" | Fine for polite refusals. Not a control. | The model is the thing assumed to be compromised. |
| Dual-LLM design | Skip | It solves the problem of a model holding powerful tools. With scoping and no outbound channel, little remains for it to protect. |
| Human review of responses | Skip | Roughly 2,000 conversations a day cannot be reviewed in real time, and the errors left are low stakes. |
| Hallucination or grounding checks at runtime | Skip as a guardrail; keep as a quality eval | The stated cost of these errors does not justify the latency or false refusals. |
| PII redaction of input (`agent-safety.md:172-181`) | Skip here | It would strip the addresses and order details customers ask about, and does nothing about whose data is fetched. |
| Rate limiting | Cost control only | Once orders are scoped there is nothing to enumerate. It becomes a security control only if the scoping fails. |

One cheap addition is worth considering after the launch gate. A deterministic check on the output could withhold any order-number-shaped string that did not come from this conversation's tool results, and raise an alert. It would catch bleed that the row owner check cannot see, such as through history or a cache. It needs a stable ID format and, if responses stream, the carry-window approach in `agent-safety.md:212-220`. It should be a tripwire rather than a launch requirement.

**For the planner:** spend the three weeks on Finding 3. Each item above that gets built should have a firing counter (`agent-safety.md:63`) and should not appear in the security sign-off as breach mitigation.

#### 6. The repo's safety spec conflicts with this conclusion in one place (High)
`agent-safety.md:25` and `.claude/skills/new-agent/references/cap-guardrails.md:37` make injection detection and a post-generation check mandatory for any user-facing agent. Applied literally, this team could tick both boxes and still be exposed, because neither limits what the tool can fetch. The same spec's later text points the other way (`:47-51`, `:154`). It also has no explicit rule that end-user identity must stay out of the model's reach. `agent-tools.md` has no such rule either, based on a keyword search rather than a full read.

**For the planner:** meet the mandate cheaply with an input size cap, delimiting and a log-only filter, plus the output tripwire if built. Record that these are not the breach control. The gap in the spec is worth raising separately.

### Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| `.claude/specs/agent-safety.md` | ADAPT | n/a | The threat model and "assume it lands" section apply directly. The mandatory layer list does not fit this risk (Finding 6). |
| `.claude/specs/agent-uncertainty.md` | REUSE | n/a | Asymmetric cost (`:89`) and deterministic-over-LLM checks (`:147`) support the split between one critical risk and the low-stakes rest. |
| `.claude/skills/review-shared/dimensions/review-safety.md` | REUSE | n/a | Its authz and tenant isolation questions (`:22-24`) suit the code review of this work. |
| `.claude/skills/new-agent/references/cap-guardrails.md` | SKIP | The structure of the violation type and the layer placement table | It centers on deny-lists and grounding, and its PII patterns target a different problem. |
| Template `guardrails/guards.py.jinja` | ADAPT | n/a | Fail-closed behavior, never surfacing rule IDs to callers, and wiring tests that name the deletion that breaks them are all worth keeping (`guardrails/README.md.jinja`). Its `check_output` PII scrub would mask a customer's own email and phone, and would not recognize another customer's order. |
| Template `middleware/auth.py.jinja` | ADAPT | n/a | Applies only if the service is built from this template. When `SUPABASE_URL` is unset, `get_current_user_id` returns one fixed user ID instead of a 401 (`:78-79`). For this feature, a misconfiguration should fail closed. |
| Template `agents/*/nodes/guardrail.py` | SKIP | The pattern of one module owning the verdict and the node owning the state change | It only wraps the input filter, which is not a control for this risk. |

### Assumptions
- **Assumption:** the request can proceed without a `/proto-design` spec. The consumer and the cost of being wrong are stated, and this question does not turn on the unanswered layers. — **Evidence:** request text; `.claude/skills/proto-research/SKILL.md:160-162`, which would otherwise send this back to design. — **If wrong:** run `/proto-design`; these findings feed its safety section. — **Confidence:** Medium.
- **Assumption:** a customer's identity is available server-side from an existing authenticated session. — **Evidence:** "logged-in" in the request; code not seen. — **If wrong:** the identity binding has no foundation and the launch date is at risk. — **Confidence:** Medium.
- **Assumption:** the orders system has, or can get, a path enforcing per-user ownership, ideally what the order page already uses. — **Evidence:** a shop with logged-in order history normally needs one; not verified. — **If wrong:** new authorization work becomes the main three-week risk. — **Confidence:** Medium.
- **Assumption:** the assistant has no tool beyond `get_orders`, and its UI renders Markdown or could be made to. — **Evidence:** the request states one tool; the UI is unknown. — **If wrong:** with plain-text rendering the output guardrail is already met, while any new tool means reassessing the whole model. — **Confidence:** Medium.
- **Assumption:** a cross-customer disclosure is reportable, as Security says, and GDPR is used only as an example. — **Evidence:** request; jurisdiction not stated. — **If wrong:** the timing and audit details change, but the controls do not. — **Confidence:** Medium.
- **Assumption:** other errors really are low stakes, as stated. — **Evidence:** request; see the challenge below. — **If wrong:** add controls for the specific claim type that matters. — **Confidence:** Medium.

### Disconfirming Evidence
- **Scoping closes the direct path.** It would be contradicted by a case where properly enforced per-user access still gave one customer another's orders via injection. I searched and found none; the cases found were missing authorization or outbound leaks. That is absence of evidence from one targeted search, and the scoping itself can have bugs, such as merged accounts, guest orders or staff impersonation. Hence the test and the row owner check.
- **Filters do not count.** OWASP lists filtering as a mitigation, and the repo records an open disagreement over model-based guards (`agent-safety.md:187`). A filter does raise attacker effort and provides telemetry, which is why it stays as an optional signal. Limit on the evidence: I read the summary of *The Attacker Moves Second*, not its per-defense tables, and those defenses are not necessarily the products this team would buy. The conclusion here rests on the fact that a filter does not bound impact, so a better catch rate would not change it.
- **The outbound channel matters here.** The reports found concern assistants that read web pages or documents, not order tools. If no order field can be written by a third party, only the paste route remains, which needs a persuaded victim and leaks only that victim's data. The restriction stays because it costs little, but the path may be rare.
- **"Everything else is low stakes because a person can correct it."** In [Moffatt v. Air Canada](https://decisions.civilresolutionbc.ca/crt/crtd/en/525448/1/document.do), a tribunal held the airline liable for its chatbot's wrong refund advice, so correction after the fact does not always erase the consequence. The award was about C$812 in total (search excerpts; decision not read in full), which supports low stakes in money. The premise holds, with one caution: an order assistant can still state refund or delivery promises in text.
- **Three weeks is enough.** I could not test this without the code. If the orders API offers only service-wide access, this finding could be wrong.

### Key Unknowns
These are ordered by what they could do to the launch.

1. **Does `get_orders` already exist, and with what parameters and credentials?** If it takes a customer ID or uses a service account, the identity binding is real work. Answer this first.
2. **Does an ownership-enforcing orders path already exist?** Reusing the order page's path would be the cheapest route to the acceptance line in Finding 3.
3. **Which order fields can a third party write?** This sets how much the outbound path matters.
4. **How are shared cases handled:** guest orders, merged or business accounts, staff impersonation, and logout on a shared device?
5. **Is any cache, memory feature or retrieved corpus planned?** Each would need the same per-user isolation.
6. **Which jurisdictions and notification thresholds apply?** Counsel or the DPO needs to confirm; nothing here is legal advice.
7. **Do provider and logging arrangements cover order data?** Sending personal data to a model provider and storing it in traces is a separate review, and may already be needed before launch.

### Recommendation
Treat this as an access-control launch gate rather than a guardrail-product selection. The research supports requiring five things before launch: identity bound outside the model and enforced by the orders system, no data shared across conversations, output that cannot send data outward, a release-blocking cross-customer test with no model in it, and audit logging with a tested off switch. Filters, judges and prompt instructions can be added for signal or user experience, but should not be counted in Security's sign-off, and the other low-stakes errors need no runtime guardrail. The most useful next step is to answer Key Unknowns 1 and 2 against the real code, since they decide whether three weeks is realistic, then take this to `/proto-plan`.
