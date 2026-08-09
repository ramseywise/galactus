# Agent Safety — Conventions

**Durable question:** What can the agent not do, and where is that enforced? What does a hostile input or a compromised tool get access to?

*Promoted and generalized from an earlier five-layer safeguards model (May 2026). That model held across ADK + LangGraph + TS implementations — the durability test for convention promotion.*

**Agent security status (2026):** No consensus defense against prompt injection. Write the boundary/threat model (what has access to what), not a recipe. This section will need re-review as practice settles.

**This is our convention, not an industry standard.** The five-layer model is a local invention that has proven durable; it is not a published framework.

---

## 1. Five protection layers

Apply in order. Each layer is independently toggleable — they are not a monolith.

```
Layer 1: Pre-input     — sanitize, detect injection, redact PII
Layer 2: Pre-retrieval — routing confidence gate; reject low-confidence intent before retrieval
Layer 3: Pre-generate  — retrieval quality gate (CRAG, confidence threshold); skip generation on poor evidence
Layer 4: Post-generate — structural output check (citation integrity, grounding, boundary adherence)
Layer 5: Escalation    — friction signals route to human; non-fatal errors are catchable here
```

Layers 1 and 4 are mandatory for any agent that surfaces output to a user. Layers 2, 3, and 5 are context-dependent — apply when the agent does retrieval (layers 2+3) or supports human handoff (layer 5).

The offline eval pipeline (LLM-as-judge grading) sits **outside** this hot path. Runtime layers must be fast (< 5ms each). Semantic grading is the eval harness's job, not a runtime guard.

> **Conflict — flagged, not resolved.** The wiki's own per-layer latency figures do not fit under a blanket 5ms ceiling: L1 <1ms, L2 0ms, **L3 (CRAG) 0–300ms**, L4 <1ms, L5 0ms. Layer 3 is documented at up to 60× the stated bound. The wiki justifies the spend in context rather than in isolation — retrieval + rerank already costs 500–1500ms and generation 800–2000ms, and the *"score delta guard... saves 1–2s"* by skipping generation on poor evidence. So a gate can be net-negative latency even at 300ms. Either the <5ms rule applies only to gates that do not themselves make a retrieval-quality judgement, or CRAG is not a "layer" under the model above. Unreconciled. *(Source: `infra/safeguards-five-layers.md`)*

### Layer 4 is a three-tier structural check

The label "structural output check" has a specific mechanism behind it:

| Tier | Check | Action on failure |
|---|---|---|
| 1 | Cited URLs exist | Hard fail |
| 2 | Claim-level citations declared | Hard fail |
| 3 | Verbatim quote overlap | Soft — log |

Plus a missing-citation guard. The wiki is emphatic on the boundary this spec already draws: ***"Do NOT use LLM-as-judge for runtime grounding."***

The layer emits named metrics — `grounding.hallucination_rate`, `grounding.missing_citation_rate`, `grounding.escalation_rate`, `grounding.zero_score_claims`. *(Source: `infra/safeguards-five-layers.md`)*

### Mitigate where the risk is created

A layered model invites a central implementation — one supervisory wrapper around the model call. The wiki argues against it: *"guardrails need to target the specific underlying use case and be implemented in their respective platform component or layer."* Its examples are placement claims: memory poisoning is mitigated *"at the memory write path"*, credential abuse *"at credential issuance"*, resource overload *"in the loop controller"* — and **"a supervisory layer positioned at the model call sees none of those."**

This is why the layers above are independently toggleable rather than a monolith: they are not a pipeline the request flows through, they are placements. *(Source: `infra/agent-security-risk-taxonomy.md`)*

### Guardrails you don't measure aren't reliability

*"You can't guardrail your way to reliability without measuring whether the guardrails fire."* Three readings and what each means:

| Observation | Diagnosis |
|---|---|
| Never fires | Not wired, or threshold is dead |
| Fires constantly | Threshold miscalibrated; users are learning to ignore it |
| Fires on successful runs | False-positive tax on correct work |

The sharpest version of this failure is a control that exists in the codebase and is never called. In one rendered scaffold, `security/guards.ts` and `guards.py` *"shipped in every rendered project... and **nothing called them**."* — *"a scaffold that ships an input guard, a content filter and an output scrubber *looks* protected and is not."* Every layer above needs a firing counter before it counts as present. *(Source: `infra/bounding-agents.md`, `infra/streaming-output-scrubbing.md`)*

### Escalation is a success outcome, not an error branch

Layer 5 above says *"non-fatal errors are catchable here"*, which files escalation under error handling. The wiki argues that framing is itself a hazard: *"when escalation is modeled as failure handling, the agent's implicit objective becomes 'answer anyway'... Making it a legitimate terminal state means the agent can be **right** to stop."*

Relatedly, termination reasons must stay distinguishable — *"hit the retry cap"* and *"the tool hung"* require different responses, and collapsing them into one "failed" branch destroys the distinction. *(Source: `infra/bounding-agents.md`)*

---

## 2. Threat model — what has access to what

Before writing any security control, map the boundary:

| Zone | Trusted? | What enters it |
|---|---|---|
| User input | Untrusted | Raw text; may contain injection payloads |
| Retrieved content | Semi-trusted | External documents; may contain indirect injection |
| Tool inputs | Agent-composed | Model-generated; validate before execution |
| Tool outputs | Semi-trusted | External system responses; may be adversarially shaped |
| Agent state / memory | Trusted | Internal — protect from write by untrusted sources |
| Credentials / secrets | Trusted | Never in context window; loaded from vault at egress |

**Injection surface:** any text that the model reads and might act on is an injection surface. This includes retrieved documents, tool outputs, and subagent responses — not just the user message.

### A risk taxonomy to check the zone map against

The wiki carries a sixteen-risk taxonomy (R1–R16) in five families: behavioural/deception, security vulnerabilities, operational resilience, multi-agent collusion, and human oversight. Two of its observations bear directly on the table above.

On memory poisoning and its neighbour: **"both convert a transient failure into a durable one by writing it to storage."** The "Agent state / memory" row above is marked *Trusted*, which is a statement about who may write to it — not a guarantee that what got written is true. A poisoned memory is trusted by construction, which is what makes it durable.

On oversight: **"R15 is the most operationally common and the least defended"** — and *"an oversight mechanism can be **weakened by adding more of it**."* More gates produce click-through; see the over-gating note in §5.

*The page is tagged `confidence: medium`. Treat the taxonomy as a checklist to test coverage against, not as a settled standard.* *(Source: `infra/agent-security-risk-taxonomy.md`)*

### The label is documentation; the grant is the boundary

*"Permission rules are enforced by the harness, not by the model."* A subagent labelled "read-only" *"can still `rm -rf` if its actual tool grant includes `Bash`."*

This is *encode constraints, don't document them* applied to permissions, and the wiki calls it **"the most commonly violated instance of it."** The "Tool inputs" row above assumes grants match documented roles; that assumption is exactly the one that fails. Audit the grant, not the label. *(Source: `harness/execution-boundaries-and-guardrails.md`)*

### Deny rules are themselves untested code

The controls in this spec have no verification mechanism attached to them. Canary testing supplies one: run the same probing task twice, once without the deny rule and once with it, and compare. **"File survival alone proves nothing"** — if the baseline run didn't attempt the deletion, *"you have observed a model's mood"*, not a boundary.

Measured against `Bash(rm:*)`, three probes gave three different verdicts:

| Probe | Verdict |
|---|---|
| `rm -f` | **HELD** |
| `find -delete` | **INCONCLUSIVE** |
| Overwrite via a file-writing tool | **BYPASSED** |

*"`rm` is a spelling of 'delete,' not the definition of it."* Hence: **"deny-listing is a weak boundary"** — prefer allow-listing tools, or a real sandbox (§6). This generalizes §3's caveat that pattern deny-lists are *"not sufficient alone"* from injection strings to permission rules. *(Source: `harness/canary-testing-for-permission-boundaries.md`)*

### The adversary is an optimizer, not a stochastic input

Everything above this line models threats as *access*: which zone can reach which resource. That is a static picture, and it is the one a table can hold. It leaves out the property that makes an adversary different from noise: **an adversary observes your defense and adapts to it, so the failure distribution is chosen rather than sampled.**

Three consequences the zone map does not express, each with a concrete form here:

- **Defenses are selection pressure.** The `rm` probe table above is the demonstration: deny `rm` and the surviving deletion paths are `find -delete` and overwrite-via-write-tool. The rule did not remove the capability; it selected for the spellings not enumerated. Expect any pattern-matched control to move attempts toward its complement, and prefer controls whose complement is empty — an allow-list or a sandbox — over controls whose complement is merely unlisted.
- **The measured metric becomes the target.** Any number a system optimizes against — an eval score, a guardrail's firing count, a grounding threshold — degrades as a measure once something optimizes for it. This holds without a hostile actor: a self-correcting loop tuning its own output against its own grader is the same mechanism. `agent-eval.md`'s rule that the evaluator sits outside the agent's write boundary is the structural defense; Goodhart is the reason it is not merely tidy.
- **A firing counter can be gamed by suppression.** §1 requires a firing count before a control counts as present. The adversarial form: a control that fires *less* may mean the attack changed shape, not that the risk fell. Read a falling counter as unexplained until explained.

**Where this stops.** Adversarial framing costs something — every design can be made to look fragile by positing a sufficiently motivated attacker, and a design attacked without a named actor generates fog rather than findings. Bound it: name who benefits, what they can observe, and what they can change. If none of the three can be named, the concern belongs in `agent-uncertainty.md` as an ordinary unknown, not here. `/war-game` runs this section against a specific design; this section holds the rules that pass answers to.

---

## 3. Prompt injection

No consensus defense exists. What has held up in practice:

- **Delimit untrusted content** structurally in the prompt (XML tags, section headers). The model is less likely to treat delimited content as instructions.
- **Deny-list structural injection patterns** in Layer 1 (e.g., `</system>`, `Ignore all previous instructions`). This is not sufficient alone.
- **Instruction hierarchy**: system prompt > developer context > user input. Do not let user input override system-prompt constraints.
- **Tool input validation**: validate that model-generated tool inputs conform to the expected schema before execution. A compromised model output should not execute arbitrary shell commands.
- **Egress control**: the agent must not exfiltrate data (secrets, PII, session state) through tool calls to external services. Rate-limit and audit outbound tool calls.

### The root cause, in one line

```python
full_prompt = system_prompt + "\n\nUser: " + user_input   # vulnerable
```

*"The model has no principled basis for treating that as data rather than instruction."* Every defence below is a mitigation of this, not a fix for it. *(Source: `prompting/prompt-injection.md`)*

### Assume it lands

Best-of-N attacks report *"~89% success on GPT-4o and ~78% on Claude 3.5 Sonnet given enough attempts"* (Hughes et al.), and *"the scaling is **power-law**"* — more attempts keep buying success rather than hitting a wall. The design conclusion: *"design as though injection will eventually land, and bound what it can do."*

Which reorders the list above. **Least privilege is first**, because it is *"the only defence that bounds **impact** rather than probability."* The operative question is not *will this be blocked* but *assume injection succeeds and ask what it can then reach.* *(Source: `prompting/prompt-injection.md`)*

### Attack surface, enumerated

| Family | Instances |
|---|---|
| **Direct** | Instructions in the user message |
| **Indirect / remote** | Payload in a fetched document or page |
| **Obfuscation** | base64, **typoglycemia**, best-of-N |
| **Structural** | HTML/Markdown, multimodal, RAG poisoning, multi-turn |
| **Agent-specific** | Thought injection, observation injection, tool manipulation, context poisoning |

The agent-specific family is the one the zone table in §2 under-covers: thought and observation injection target text the model produces or reads *inside* the loop, where no input gate sits. *(Source: `prompting/prompt-injection.md`)*

### The dual-LLM pattern

Structurally stronger than any filter: *"a **privileged LLM** holds the tools but never reads untrusted content directly; a **quarantined LLM** reads untrusted content but cannot act."* Injection into the quarantined model buys the attacker no capability, because that model has none. This is least privilege expressed as topology rather than as configuration. *(Source: `prompting/prompt-injection.md` — Simon Willison)*

### A concrete input pipeline

The bullets above are principles; the wiki supplies a pipeline that implements them:

```
[1] Normalise → [2] Size check → [3] Domain classify → [4] Injection detect (11 categories)
  → [5] PII redact (13 types) → [6] XML envelope → [7] Advisory notes
```

`MAX_INPUT_CHARS = 4000`. The 13 redacted PII types: *"email, phone, credit card, SSN, API key, JWT, IBAN, IP address, date of birth, postcode, CVV, passport, national ID."*

Two design rules come with it. **Guardrails are deterministic and LLM-free** — *"an LLM-based guardrail can be bypassed by the same injection techniques it is defending against."* And **dual enforcement**: the system prompt *also* instructs the model to stay in domain, so that *"both layers must be defeated independently."* Note what that does to §3's instruction hierarchy — here the system prompt is not the authoritative control but a second, deliberately redundant backstop behind a deterministic one.

For deny-list matching, prefer an established string metric — *"Levenshtein / Damerau-Levenshtein at threshold 1–2, or Jaro-Winkler when prefixes are preserved"* — while treating it as *"necessary but insufficient."* *(Source: `infra/input-guardrails-pipeline.md`, `prompting/prompt-injection.md`)*

> **Conflict — flagged, not resolved, and open upstream.** The wiki disagrees with itself on whether guardrails may use a model. `infra/input-guardrails-pipeline.md`: *"guardrails must be deterministic and LLM-free."* `prompting/prompt-injection.md` (following OWASP): a purpose-trained guardrail model screens input, output, and action *"alongside the deterministic controls... not in place of them"* — naming Llama Guard, ShieldGemma, Granite Guardian, Prompt Guard, NeMo Guardrails — on the grounds that pattern-matching *"does not reliably catch indirect injection."* The wiki's `_conflicts.md` records this as open, with a practical dial rather than a resolution: *"cost/latency is the practical dial: reserve model-based checks for high-risk paths... keep deterministic checks on routine traffic."* This spec's own "no consensus defense" framing is the honest position; do not silently pick a side.

---

## 4. Credential and secret custody

Rules that are non-negotiable:

- Credentials are **never in the context window**. Load from vault or environment at request time; do not pass as tool parameters or inject into prompts.
- API keys are **server-side only** — never in client-accessible env vars, never logged, never in tool outputs returned to the model.
- Supabase/DB credentials: row-level security (RLS) is the defense for multi-tenant data. Do not bypass RLS with a service role key in a user-facing route.
- Path inputs from the model: validate against an allowlist. Model-supplied file paths can traverse to unexpected locations — `../../../etc/passwd` is a real risk if paths are passed to filesystem tools.
- **Not even in error messages.** Secrets must never appear in tool responses, *"even in error messages"* — the path most likely to leak them is the one nobody reviews. Prefer to make a tool server *"stateless and secret-free by design"* rather than to redact on the way out. *(Source: `mcp/mcp-server-security-patterns.md`)*

### Pre-publish audit

Before any repo, wiki, or artifact goes out, four passes:

1. API keys and tokens across **all** files, not just source.
2. Markdown scanned for client data.
3. `.gitignore` coverage verified against what is actually tracked.
4. **JSONL session files scanned** — agent transcripts capture whatever was in context.

*(Source: `mcp/mcp-server-security-patterns.md`)*

### Scrubbing a stream

Post-hoc redaction assumes a whole response to redact. A streamed response has none. Three seams are available — poison the stream, buffer the whole response, or **transform in transit** — and the wiki chooses the third.

The mechanism is a **carry window**: hold back the last `CARRY_CHARS` characters of each chunk and prepend them to the next, so a pattern straddling a chunk boundary still matches. *"The window is sized **above the longest pattern** rather than guessed."* It works on bounded-shape secrets — `sk-…`, `AKIA…`, `ghp_…`.

Its residual limitation is stated rather than hidden: *"a credential longer than `CARRY_CHARS` straddling a boundary can slip through."* *(Source: `infra/streaming-output-scrubbing.md`)*

---

## 5. Write-operation confirm gate

Any tool that writes, mutates, or deletes requires a **two-phase confirm gate** in the agent loop:

- **Phase 1 (plan):** Model describes the intended write operation; sets a `confirm: true` signal. No write executed.
- **Phase 2 (execute):** User (or orchestrator) affirms. Model executes the write.

The confirm gate is an agent loop responsibility, not a tool responsibility. The tool should still be idempotent (see `agent-tools.md §1`), but the gate is what prevents accidental execution.

### Gate by allowlist, and only what needs gating

The gate has to know which operations it applies to, or it applies to everything. The wiki's split:

| Gated | Ungated |
|---|---|
| Edit files, apply patches, `sanyi --fix` | Read, grep |
| Commit, push | `git diff` / `git status` |
| Post / approve / request-changes on GitHub | Test discovery |
| Delete files, modify config | |

Residual rule: unknown scripts are inspected before execution. Governing principles: **"the final decision belongs to the human"** and **"automate coverage, not accountability."**

The distinction it turns on is not *does this touch a artifact* but *does this commit*: *"drafting one and surfacing it in the report requires no authorization... Writing it into `SANYI.md` does."*

And the failure mode in the other direction is real — **"gating reversible operations is the most common way to make an agent useless."** Over-gating is the mechanism behind R15 in §2: more oversight producing less. *(Source: `patterns/read-only-by-default-with-authorization.md`, `harness/execution-boundaries-and-guardrails.md`)*

> **Two strategies, different domains.** The allowlist above grants the powerful tool and gates its use. `agent-tools.md §5` does the opposite for a knowledge-serving MCP server: the write tool is *never exposed*. Both are in the wiki and neither is wrong — the gate fits a general-purpose agent whose write set can't be enumerated in advance; non-exposure fits a server with a fixed, narrow contract. State which regime a component is in.

### Search → ask → act

*"Exhaust available information first, ask only when the information genuinely isn't there, and never act on a guess when the action is irreversible."* When asking, a multiple-choice `askUser` beats an open question — it bounds the answer into something the loop can branch on. *(Source: `harness/execution-boundaries-and-guardrails.md`)*

### Rollback is the other half of the gate

A gate prevents; rollback undoes. The spec above only documents the first. **"Git is the default rollback mechanism"** — branch-per-agent — and *"sandbox snapshots roll back environment state, not just files."*

**"Investment in rollback buys autonomy."** That is the trade the previous subsection needs: the reason you can afford to leave reversible operations ungated is that they are genuinely reversible, which is a property you build rather than assume. *(Source: `harness/execution-boundaries-and-guardrails.md`)*

---

## 5a. Cost as a boundary

*"A loop with no cost ceiling will find a way to spend without bound."* Instrument token spend per run, set a ceiling, and **"fail closed with a partial result rather than silently continuing."**

This is the direct mitigation for R9 (resource overload) in §2's taxonomy, and it is a safety control rather than a budgeting one: an unbounded loop is an availability failure with a bill attached. Note the failure shape it prescribes — partial result, loudly — which is the same rule `agent-reliability.md §5` applies to degradation. *(Source: `harness/execution-boundaries-and-guardrails.md`)*

---

## 6. Sandboxing

When the agent can write and execute code:

- Code execution happens in an **isolated sandbox** (container, VM, or managed execution environment). The sandbox must not have access to the host filesystem, network credentials, or other agents' state.
- The sandbox has explicit egress rules: which outbound calls are allowed (e.g., package downloads from approved registries only).
- Sandbox output is captured and returned as a structured result — not passed directly to another tool call without inspection.
- Anthropic's code execution tool runs in a managed sandbox with no persistent state. Self-hosted sandboxes (Docker, gVisor, firecracker) must explicitly define these boundaries.

### Choosing a backend

| Backend | Isolation | Speed | Use |
|---|---|---|---|
| Local | Weakest | Fastest | Trusted code, dev |
| In-memory | Middle | Fast | Bounded evaluation |
| Remote cloud | Strongest | Slowest | Untrusted code |

Cloud sandboxes carry a lifecycle problem the table doesn't show: *"they cost money while idle."* That pushes toward tearing them down, which conflicts with reattaching on retry — see `agent-runtime.md` on keying a sandbox by run id.

**"Backend independence is the design rule"** — *"swap the backend, the tools don't change."* Isolation strength then becomes a deployment decision rather than a rewrite. *(Source: `harness/execution-boundaries-and-guardrails.md`)*

---

## 7. PII handling

- Redact PII from inputs before logging (Layer 1 responsibility).
- Do not log raw user messages — log hashes or anonymized summaries.
- Do not pass PII to third-party tool endpoints unless that endpoint is approved for PII handling.
- Ensure `structlog.contextvars` does not carry PII across requests.

### Picking a masking approach

| Approach | Cost | Latency | Weakness |
|---|---|---|---|
| Regex | ~0 | <1ms | Misses contextual PII |
| LLM-based | ~$0.01–0.03 / conversation | 200–800ms | Cost at volume |
| Hybrid | — | — | — |

Above **>10K conversations/day**, LLM-based masking becomes expensive — *"revisit with a purpose-built NER model."*

The hard rule: **"the masking layer must not be skippable or bypassable. This is a hard gate."** Note also the opposite-direction failure the rules above don't consider — over-masking degrades the very content the agent is reasoning over, so a masker with no false-positive measurement is as unaudited as a guardrail that never fires (§1). *(Source: `infra/pii-masking-approaches.md`)*

---

## 8. Reliability primitives that safety depends on

Seven, from the risk taxonomy: durable messaging, explicit task state, dependency tracking, idempotent processing, isolated side effects, structured handoffs, and **deterministic verification**.

The last is load-bearing, and the wiki says why: *"a verification step implemented as an LLM judgment inherits every risk in this taxonomy."* A verifier that can be talked out of its verdict is not a control. This is the same boundary §1 draws around Layer 4 and around LLM-as-judge, restated as a general principle: the thing that checks must not be susceptible to what it checks for. *(Source: `infra/agent-security-risk-taxonomy.md`)*

---

## Sources

- Topics 6.2, 6.3, 6.9 from `2026-07-19-research-B-topic-canon.md`
- Anthropic vault-credentials-at-egress model
- Research B emerging/settled table (injection defense = unsettled, high stakes)
- `infra/safeguards-five-layers.md` — per-layer latency budget; Layer 4 three-tier grounding check; grounding metrics
- `infra/agent-security-risk-taxonomy.md` — R1–R16; mitigate-at-the-risk-site; the seven reliability primitives
- `infra/input-guardrails-pipeline.md` — the seven-stage pipeline; `MAX_INPUT_CHARS`; 11 injection categories; 13 PII types; dual enforcement
- `prompting/prompt-injection.md` — root cause; BoN success rates; attack-surface taxonomy; dual-LLM pattern; defence ranking; fuzzy-match thresholds
- `_conflicts.md` — the open deterministic-vs-model-based guardrail conflict
- `harness/execution-boundaries-and-guardrails.md` — label vs grant; sandbox backends; cost envelope; rollback; search → ask → act
- `harness/canary-testing-for-permission-boundaries.md` — deny rules as untested code; the `Bash(rm:*)` probe results
- `infra/bounding-agents.md` — guardrail firing diagnostics; escalation as a terminal state; termination reasons
- `patterns/read-only-by-default-with-authorization.md` — the gated/ungated allowlist; drafting vs writing
- `infra/pii-masking-approaches.md` — masking cost/latency table; the 10K/day threshold
- `infra/streaming-output-scrubbing.md` — carry-window scrubbing; the shipped-but-unwired case
- `mcp/mcp-server-security-patterns.md` — secrets never in error messages; pre-publish audit
