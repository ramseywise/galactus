# Angle: Spec gap audit — are galactus's agent-* convention specs sufficient for a real-time duplex voice agent?

## Findings

**Confidence: High** — The specs are thoroughly designed for request-response loops with discrete turns. A real-time bidirectional voice stream breaks core assumptions across all 10 specs at multiple layers. The gaps are not edge cases; they are foundational.

### Core assumption breaking (per spec)

**agent-architecture.md (§2, line 86):** "A turn ends when the model emits a **stop_reason** that is not a tool call." 
- **Breaks in voice:** There is no discrete turn boundary. ASR produces partial hypotheses continuously; the agent reasoning loop must operate over *incremental, non-final input* while simultaneously streaming TTS output. A "turn" in voice is not a request-response event — it is a continuous state with two concurrent streams (in/out) and no natural endpoint until the user stops speaking.
- **Confidence: High** — This is structural, not a tuning parameter.

**agent-runtime.md (§2, line 68):** "Stateless function constraints are non-negotiable for stateless deployments... No background tasks — any async work must complete before the function returns."
- **Breaks in voice:** Real-time voice requires persistent TCP/WebSocket connections across multiple turns. A Lambda function cannot maintain a connection; it must be a long-lived process. The section assumes a function invocation lifecycle; voice is a session-level persistence requirement from the first second of connection.
- **Confidence: High** — Stateless is fundamentally incompatible with persistent audio streaming.

**agent-reliability.md (§3, line 110):** "Idempotency — Key is caller-generated (e.g., `run_id + step_id + tool_name`)."
- **Breaks in voice:** Idempotency keys assume discrete tool invocations with stable inputs and outputs. In a streaming voice loop, the same "tool" (e.g., query a knowledge base) is called with continuously-updated hypotheses. By the time ASR finalizes a transcript, three prior partial versions have already been sent to the LLM. Retrying with an idempotency key assumes "same input = same call"; in voice, the stream of inputs is fundamentally stateful and non-idempotent at the granularity the spec assumes.
- **Confidence: High** — Partial input streams violate the stable-input assumption.

**agent-context.md (§2, line 91):** "Load only what the current turn needs. Do not inject full conversation history if a compressed summary suffices."
- **Breaks in voice:** There is no "current turn" with a clear start/end. Context compression happens at phase boundaries (§3, line 164: "Apply compaction before the window is full — reactive compaction mid-run risks losing context at a decision point"). In voice, a 5-minute conversation is one continuous event. Compaction mid-conversation would mid-stream alter the prompt and potentially invalidate cached prefixes — which agent-context.md §2 (line 143) names as a hard cost: "Cache TTL is 5 minutes; the prefix must be byte-identical to hit." A compaction at 4:50 of a 5-minute call invalidates the cache for the final 10 seconds.
- **Confidence: High** — Compaction timing is incompatible with session lifetime.

**agent-observability.md (§1, line 33):** "Four span types cover a complete agent trace... All nested under a root `invoke_agent` span."
- **Breaks in voice:** An `invoke_agent` span assumes one request-in-response-out. In voice, there are hundreds of micro-invocations: partial transcript hypotheses, TTS streaming, barge-in cancellations, retry after user interrupts. A single span per connection is too coarse; dozens of spans per second is not a "trace" but a fire hose. The spec's span hierarchy (agent invocation > model call > tool execution) assumes causal nesting; voice has overlapping, concurrent spans for ASR processing, LLM reasoning, and TTS output *all at the same time*. Line 56 already flags a naming divergence with ADK; voice makes this worse — the span model itself (tree-shaped, synchronous nesting) does not fit a bidirectional stream.
- **Confidence: High** — Span nesting assumes sequential causality.

**agent-eval.md (§2a, line 52):** "A single run is not a measurement... Reset the environment between trials."
- **Breaks in voice:** A voice interaction is a *session*, not a run. A user calling a voice agent in the morning, hanging up, and calling again in the afternoon is *two separate trials* that share state (user memory, session context). But the spec assumes each "run" is independent for eval purposes. A multi-turn voice conversation on a single call is *not independent* — prior turns set up context for later ones. The spec's pass@k and pass^k metrics assume you can repeat the whole sequence identically; in voice, user input is non-deterministic speech, and you cannot replay a user's words.
- **Confidence: High** — Trials cannot be reset in a voice interaction; they are inherently dependent.

**agent-memory.md (§3, line 54):** "Checkpoint after each plan step completes, not only at session end."
- **Breaks in voice:** What is a "step" in a voice conversation? If the user asks "What's the weather?" and the agent says "It's raining," is that one step? If the user then says "Thanks, now what's the forecast?" — is that a new step, or a continuation? The spec assumes steps are discrete, planned, bounded in time. Voice turns are user-initiated and asynchronous; the boundary between "step" is the user's speech, which is not under the agent's control. Checkpointing every user utterance (not every plan step, but every ASR finalization) produces checkpoints at 1–2 second intervals in a 5-minute call = ~150–300 checkpoints per session, versus 5–10 checkpoints in a typical multi-step task. That is not a scaling difference; it is a different phenomenon.
- **Confidence: High** — "Step" is undefined in voice context.

**agent-safety.md (§1, line 18):** "Layer 1: Pre-input — sanitize, detect injection, redact PII."
- **Breaks in voice:** Pre-input redaction assumes you have the full input before processing. In voice, ASR outputs partial hypotheses continuously. A PII redaction rule that depends on the final transcript cannot fire until the end — and by then the partial transcript (containing the PII) has already been in context, processed by the LLM, and possibly injected into tool calls. Pre-input redaction is incompatible with streaming ASR input.
- **Confidence: High** — PII redaction timing is incompatible with incremental ASR.

**agent-tools.md (§0, line 9):** "Tools consume context twice: their definitions sit in the window permanently, and their results enter it per call."
- **Breaks in voice:** In a streaming voice context, tool definitions still consume context, but a single "tool result" is replaced by *continuous streaming results*. A tool that searches a knowledge base returns a ranked list; in voice, it returns a stream of results as they are retrieved, and the agent must synthesize over partial results in real-time. The spec assumes tool results are discrete, bounded artifacts; voice tool results are streams.
- **Confidence: High** — Tool result shape is incompatible with streaming.

**agent-uncertainty.md (§2, line 46):** "The collapse rule: a component that cannot distinguish 'no evidence' from 'evidence says no' will report both as an answer."
- **Breaks in voice:** ASR partial hypotheses are *uncertain evidence*, not absent evidence. The agent must act on partial, non-final input: if the user says "book me a…" and the agent begins generating "Sure, I can book you a flight" while ASR is still listening, and then the user says "coffee" (not "flight"), the agent must interrupt itself. This is not a collapse-site problem (not "no evidence"); it is a *confidence levels in evidence* problem that the spec does not address. The spec discusses "abstain if no evidence" but not "act with low confidence on partial evidence and be ready to reverse."
- **Confidence: Medium** — The spec's binary unknown/known framing does not cover partial confidence.

### Assumed discrete-turn boundaries violated

(These are meta-findings across multiple specs):

**agent-architecture.md (§5, line 134):** "The HITL confirmation gate sits **after the planner, before the executor** — approving a plan is cheap, approving 40 executed steps is not."
- In voice, there is no "plan approval" step. The user is speaking; the agent is listening and thinking in real-time. Human-in-the-loop becomes *simultaneous* with the agent's own loop, not a gate between phases. A user interrupting the agent (barge-in) is a form of HITL, and it must interrupt a *currently executing* model call, not wait for a phase boundary.
- **Confidence: High**

**agent-runtime.md (§6, line 166):** "Stream early. Do not buffer full responses if the client supports streaming... Streaming errors mid-stream: close the stream with an error event."
- The spec names streaming as a UX latency lever, not a structural necessity. In voice, streaming is *mandatory* and *concurrent with input processing*. While TTS is streaming a response, ASR is receiving the next user utterance. The spec's error handling assumes a streamed response ends; in voice, the response *ends while the user is still talking*.
- **Confidence: High**

---

### Candidate topics for a new agent-voice.md spec

**1. Turn-taking / endpointing / VAD (voice activity detection)**
- **Belongs in:** New `agent-voice.md` section or as extension to `agent-architecture.md §2`
- **Why separate:** This is architectural and changes the event model fundamentally. VAD is not a tool or a context concern; it is part of the orchestration layer's control flow. It decides *when the user's turn ends*, which is prerequisite to every other voice-specific rule. Agent-architecture.md's section 2 ("What terminates a turn") currently names only model-generated stop_reasons; VAD-based termination is a parallel mechanism.
- **Load-bearing detail:** VAD endpointing must be configurable (some domains allow interruption mid-word; others require completion). The spec must name whether endpointing is a hard boundary or a soft signal.

**2. Barge-in and interruption (user talks over agent)**
- **Belongs in:** New `agent-voice.md` section
- **Why separate:** This is a runtime control-flow primitive with no analogue in request-response. Agent-reliability.md names "retry" and "cascade"; voice adds "cancel in-flight work." Cancelling in-flight TTS and LLM generation is not a retry (not a reliability concern) and not a safety gate (not a guardrail concern). It is a concurrency primitive: two generation tasks (LLM reasoning, TTS synthesis) must both support cancellation on user input.
- **Interacts with:** agent-reliability.md (idempotency and cancelability), agent-tools.md (which tool calls can be safely cancelled mid-execution).

**3. Latency budget decomposition**
- **Belongs in:** New `agent-voice.md` section or extension to `agent-runtime.md §4` (Cost and latency levers)
- **Why separate:** Agent-runtime.md§4 names "perceived latency" vs "total cost" for streaming. Voice needs the inverse: *hard latency requirements* at each hop. ASR partial → LLM first-token → TTS first-audio, each with a sub-second SLA, summed to a total voice-turn latency budget (typically 800–1200ms for a natural conversation). This is a *constraint*, not an optimization lever. It changes tool selection (use fast read-only tools, not slow search), model selection (latency-optimized models, not strongest models), and context strategy (minimal context, not comprehensive).
- **Load-bearing detail:** The budget is per-turn in voice (not per-session like in written contexts), and turns happen every 1–3 seconds, not every 30 seconds.

**4. ASR error propagation**
- **Belongs in:** Extension to `agent-uncertainty.md §2` (collapse rule) or new section in `agent-voice.md`
- **Why separate:** ASR hypothesis is noisy, non-final input. A 95% WER (word-error rate) in some domains means 1 in 20 words is wrong. The collapse rule says "do not conflate 'no evidence' with 'evidence says no'"; ASR adds a third case: "evidence with signal + noise mixed." The spec must name how to treat ASR error in the context window — do you mark it as uncertain? Wrap it in tags? Inject raw score with the hypothesis?
- **Interacts with:** agent-uncertainty.md (confidence and actionability), agent-context.md (how ASR error is formatted and prioritized).

**5. Partial hypotheses / incremental processing**
- **Belongs in:** New `agent-voice.md` section
- **Why separate:** Agent-runtime.md §2 assumes "no background tasks"; incremental ASR output is a background stream the model must process in real-time. The spec must define: (a) at what confidence threshold does ASR output enter the context window, (b) what happens to prior hypotheses when a new one arrives with different content, (c) does the model re-generate after each ASR update, or does it wait for finalization?
- **Load-bearing detail:** Re-generating after each partial is expensive (hundreds of LLM calls per turn); not re-generating risks generating over stale partial hypotheses. The choice is a fundamental architecture decision.

**6. TTS streaming and audio buffer management**
- **Belongs in:** New `agent-voice.md` section
- **Why separate:** Agent-tools.md §0 says "return typed structure always"; TTS is inherently a stream, not a discrete result. The spec must name: (a) how audio chunks are queued and buffered (ring buffer? FIFO? priority for low-latency delivery?), (b) what happens if TTS output falls behind real-time (skip frames? slow down playback?), (c) how cancellation works (can you interrupt mid-chunk, or only at chunk boundaries?).
- **Interacts with:** agent-runtime.md (streaming, section 6).

**7. Session state across turns in a long-lived connection**
- **Belongs in:** Extension to `agent-memory.md` or new `agent-voice.md` section
- **Why separate:** Agent-memory.md §1 names three tiers (episodic, semantic, procedural); voice adds a fourth: *working memory specific to this session*. In a 5-minute call with 20 user utterances, the agent must retain the *current goal* (e.g., "user is booking a flight") across 20 turns without checkpointing to disk every turn. This is neither episodic (too short-term) nor semantic (too volatile). It is a session-scoped working context that is not in the context window (it's too much) but not in permanent storage (it's too temporary).
- **Load-bearing detail:** This state must survive mid-call model errors and tool failures; it is checkpointed somewhere (memory, session cache), but not in the context window. Agent-memory.md does not name this tier.

**8. Speech-to-speech models vs. cascaded ASR→LLM→TTS**
- **Belongs in:** Extension to `agent-architecture.md §1` (Loop shapes) or new `agent-voice.md` section
- **Why separate:** This is an architectural choice at the orchestration level (like choosing Plan-then-Act vs. ReAct). A cascaded system (ASR → LLM → TTS) is controllable and debuggable; a speech-to-speech model (user audio → model → response audio) is latency-optimal but opaque. Both are valid; the spec must name the trade-offs and the scenarios where each wins. The rule is the same as agent-architecture.md's: "Pick the simplest loop shape that fits"; for voice, that rule maps onto "monolithic speech-to-speech vs. decomposed pipeline."
- **Interacts with:** agent-observability.md (tracing a monolithic model vs. tracing three hops) and agent-eval.md (evals are tool-specific in a cascaded system, end-to-end in a monolithic one).

---

### Interaction points with existing specs

**agent-eval.md** needs **voice-specific golden datasets:** You cannot replay a user's speech. Evals must use recorded audio, but recorded audio is a *single deterministic input* — you cannot test pass@k (success across multiple trials) because you only have one trial per recording. The spec's assumption that you can run the same input 100 times breaks for voice.
- **Extension needed:** A section on eval strategies for non-deterministic user input (recorded audio, simulated users via TTS, synthetic variations of a script).

**agent-safety.md §1** (Layer 1 input sanitization) needs **streaming input redaction:** The current model assumes you have the full input before processing. For ASR, you have pieces of the input as they arrive. The spec must name when redaction happens (real-time as ASR outputs arrive, or batched at finalization).
- **Extension needed:** A subsection on redacting streaming input and handling contradictions when later chunks reveal PII the earlier chunks did not contain.

**agent-observability.md** needs **concurrent span support:** The current span hierarchy is tree-shaped (parent → child nesting). Voice has concurrency: ASR, reasoning, and TTS are simultaneous. The tree model needs an extension for concurrent child spans.
- **Extension needed:** A subsection on parallel span nesting and how to query traces where multiple spans overlap in time.

---

## Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| **agent-architecture.md** | ADAPT | Section 2 ("What terminates a turn") and section 1 ("Loop shapes") need voice-specific guidance on VAD-based turn boundaries and real-time event loops. The rest holds. | Request-response assumption is orthogonal to orchestration levels and multi-agent patterns. VAD endpointing is an input-side analogue to the output-side stop_reason. Reusable: the framework of orchestration levels (1–4) still applies; the decision logic differs. Cost: ~50 lines to add VAD as a turn terminator alongside model stop_reason. |
| **agent-runtime.md** | ADAPT | Section 1 ("Topology variants") needs a fourth topology: persistent connection (long-lived process with bidirectional streaming). Section 6 ("Streaming") is mostly reusable; add a subsection on streaming *input* to match streaming output. | Long-lived process topology already exists in the spec; voice is just a required instance of it. Streaming output is discussed; streaming input is symmetrical and reusable. Cost: ~40 lines to formalize persistent-connection topology and clarify concurrency model. |
| **agent-reliability.md** | ADAPT | Section 3 ("Idempotency") needs a companion rule for *partial input idempotency* — how to handle retries when prior partial ASR hypotheses contradict current ones. Section 2 retry policy is reusable as-is (transient, tool error, schema violation all apply to voice). Add cancellation as a new failure response alongside retry. | Retry logic for discrete tools is orthogonal to streaming voice. Idempotency key concept reusable; application to streaming input needs clarification. Cost: ~30 lines to define partial-input retry semantics and cancellation response codes. |
| **agent-context.md** | SKIP | Request-response context assembly does not transfer to continuous voice. Compaction timing (§3) is incompatible with long-lived sessions. The retrieval strategy (§1a) is reusable but requires a note that voice is a continuous-context scenario. | Salvageable: (1) The four-lever model (§1) applies to voice — write, select, compress, isolate are all valid moves. Reuse the lever names and ordering. (2) The four context types (§2) are reusable — static, dynamic, retrieved, historical all appear in voice. (3) Progressive disclosure (§5) is directly applicable — load a minimal prompt for voice, load task-specific skills on demand. (4) The five-layer anatomy (§2) is reusable wholesale. What doesn't transfer: phase-boundary compaction (there are no phases), cache optimization around compaction (voice doesn't have clean compaction points), and the turn-start-to-end context lifecycle. A voice-focused doc can reuse §1, §1a (with a note on continuous retrieval), §2 (five-layer model), §5 (progressive disclosure), and the injection-defense ladder (§7). Cost of salvage: extract the reusable sections; write a 50-line companion on voice-specific context pressures (continuous occupancy, no clear eviction boundaries). |
| **agent-observability.md** | ADAPT | Section 1 ("Required span types") needs concurrent-span support. The current four span types (invoke_agent, chat, execute_tool, retrieve) are reusable; add a metadata field for concurrent-parent pointers. Section 2 (agent invocation span) needs a note that `run_id` is per-*session*, not per-*invocation* in voice. | Span types are reusable; span *hierarchy* (tree-shaped, sequential) is not. Cost: ~25 lines to add concurrent-span example and clarify run_id scope in voice. The rest (span content, cost attribution, error returns) is directly reusable. |
| **agent-eval.md** | ADAPT | Sections 1–4 (unit/eval seam, grader interface, gate ladder, failure taxonomy) are directly reusable. Section 2a (non-determinism) needs a voice-specific note that *recorded audio is deterministic* (you can replay it exactly) but *user utterances are not* (different calls have different speech). The golden dataset section (§5) needs a companion on audio-based golden sets. | The grader interface (§2) works for voice: query is the audio, response is the agent's audio, expected is an annotated ground-truth response. Pass@k is inapplicable (one recording = one shot), but pass^k (reliability across retries) is meaningful if the recording is played multiple times. Cost: ~40 lines to clarify audio-golden-set curation and eval metrics for voice. |
| **agent-memory.md** | ADAPT | Sections 1–2 (memory taxonomy, state persistence by lifetime) are directly reusable. Section 3 (checkpointing) needs a companion rule for *per-utterance checkpoints* (not per-step) in voice. Section 6 (memory vs. context) is reusable; the read path (§6) applies to voice with a note on *timing* — memory retrieval in voice must be fast (<200ms to stay in latency budget). | Tiers (episodic, semantic, procedural) are reusable. Write discipline (§4) is reusable. The main adaptation: clarify that voice has many more checkpoint events (per ASR finalization, not per logical step). Cost: ~30 lines to formalize checkpoint semantics in voice. Salvageable at lower cost: everything except the "step" abstraction. |
| **agent-safety.md** | ADAPT | Layers 1–5 are reusable with footnotes. Layer 1 (pre-input) needs a streaming variant. Layer 4 (post-generate) is fully reusable. Layer 5 (escalation) applies to voice — escalation is *live* in voice (route to human operator immediately), not async. | Input-sanitization ladder (§3) is reusable for final ASR output; rewrite the pre-input layer to handle streaming. The dual-LLM pattern (§3) is reusable. The threat model (§2) is reusable; the risk taxonomy (16 risks) is reusable. Cost: ~40 lines to adapt Layer 1 for streaming input and clarify escalation timing in voice. |
| **agent-tools.md** | ADAPT | Sections 1–4 (tool design principles, schema rules, registry) are directly reusable. Section 5 (MCP vs. in-process) is reusable with a note: voice has tighter latency budgets, which may push more tools in-process. Section 6 (write-operation safety) is reusable; two-phase gates are still required. | Tool result streaming (§0) needs a note on streaming tool results, but the principle (tools consume context) is unchanged. Cancellation of in-flight tool calls (new for voice) is a runtime feature, not a tool-design concern. Cost: ~20 lines to name latency-tier tool selection for voice and clarify streaming results. |
| **agent-uncertainty.md** | REUSE | The four-quadrant model (§1) is directly applicable to voice ASR. "Unknown knowns" (missing specs or unwired hooks) is a problem in voice too. The collapse rule (§2) is the load-bearing rule: partial ASR hypothesis is *uncertain evidence*, not absent evidence — the spec already covers this distinction. Least commitment (§4) and ranking by blast radius (§3) are core to voice (every decision is partially reversible on barge-in). Close the loop (§6) applies to voice eval. | No adaptation needed. ASR partial hypotheses fit into the "uncertain answer" row of §2's state table. The entire spec is reusable. |

---

## Open questions

1. **Voice-specific orchestration level:** Does the addition of real-time concurrency (ASR, reasoning, TTS happening simultaneously) warrant a new orchestration level in agent-architecture.md? Or is it a tool-layer concern (a new tool pattern: streaming input, streaming output)? This determines whether the new guidance goes into agent-architecture or agent-voice.

2. **Endpointing strategy:** VAD-based turn-taking is standard in telephony but optional in chat-based interfaces. Should the spec name VAD endpointing as mandatory for voice, or as a configurable option? The choice affects the architecture of every component downstream.

3. **Latency SLA enforcement:** Agent-runtime.md §4 names cost levers; agent-voice.md would need to name *latency SLA enforcement* as a first-class constraint. How should the loop respond when latency budgets are exceeded — abort, degrade, or cascade to a fallback model? This is a new policy decision.

4. **Session memory tier naming:** Agent-memory.md names three tiers; voice needs a fourth (session working memory: the current goal state, shorter-lived than episodic, longer-lived than context-window working memory). Should this go into agent-memory.md as a fourth tier, or into agent-voice.md as a voice-specific memory layer? This affects where agents building voice systems look for the guidance.

5. **Concurrent span semantics:** Agent-observability.md's span model assumes sequential nesting. Should concurrent spans be a voice-specific extension, or should it be promoted to a general agent-observability concern (other domains also have concurrency, e.g., multi-threaded RAG retrieval)? This determines whether the guidance applies narrowly to voice or broadly to concurrent systems.

6. **Barge-in as a control-flow primitive:** User interruption (barge-in) must cancel in-flight work (LLM generation, TTS streaming). Is this a *cancellation pattern* (belongs in agent-reliability or agent-architecture as a retry-like strategy), or a *concurrency pattern* (new to voice)? The answer determines where the spec lives.

7. **Monolithic vs. cascaded architecture:** Agent-architecture.md's loop-shapes section (§1) does not cover speech-to-speech models (monolithic, end-to-end, black-box). Should this be a new loop shape or a variant choice *within* a shape? This affects how voice is taught to new agent builders (as a new mental model, or as a variant of existing ones).

8. **Prompt versioning in voice:** Agent-context.md §4 requires prompt versioning. In voice, the prompt version is fixed for a deployment, but the TTS voice, ASR model, and LLM model are separate versioned components. Should agent-voice.md require versioning of all three, or is it enough to version the prompt and let the infrastructure version the I/O models? This affects observability and reproducibility.

---

## Spec indexing and naming conventions

**Current convention (from CLAUDE.md):** Agent-*.md specs index against the five-layer stack: architecture, context, tools, memory, and runtime (control flow). Agent-uncertainty.md cuts across all and is called out as a cross-cutting concern.

**For voice:** A new spec should follow the convention:
- **Name:** `agent-voice.md` or `agent-realtime.md` (voice is more specific; realtime is more general and covers WebRTC, streaming APIs, etc.). **Recommendation: `agent-voice.md`** — the angle is specifically a voice interface, and "realtime" is vague enough to attract non-voice concurrent systems that should use agent-uncertainty.md instead.
- **Header:** Durable question format (matching existing specs):
  ```markdown
  # Agent Voice — Conventions
  
  **Durable question:** How does a real-time bidirectional audio stream change the agent's core loop? What are the new primitives (VAD endpointing, barge-in, latency budgets) and how do they interact with the five-layer stack?
  ```
- **Structure:** Follow the existing alphabetical-by-topic structure (architecture, context, tools, memory, runtime, plus voice-specific sections like turn-taking, barge-in, latency). Use numbered sections like §1, §2, etc.
- **Conflicts:** Include a "Conflicts — flagged, not resolved" pattern for any ambiguities (e.g., monolithic vs. cascaded, latency budget distribution).
- **Sources:** Follow the wiki-citation format. Voice is a new frontier topic, so sources will be fewer (mostly intra-repo references to the five-layer stack and mentions of industry practices like WebRTC, telephony VAD).

**Versioning:** The spec should carry the same disclaimer as agent-safety.md:
```markdown
**Agent voice status (2026):** No consensus on endpointing strategies or barge-in handling. Write the architectural choices (VAD threshold, interruption latency, TTS buffering), not a recipe. This section will need re-review as practice settles.

**This is our convention, not an industry standard.** Voice agent design is frontier; the shapes that survive will inform standards, but today this is a local convention in a showcase repo.
```

---

## Summary: what agent-voice.md must own

A complete agent-voice.md needs to own these topics (not addressed in existing specs):

1. **Turn-taking and endpointing (VAD)** — when does a user's utterance end and the agent's response window begin?
2. **Barge-in and interruption** — how to cancel in-flight work when the user talks over the agent.
3. **Latency budget decomposition** — allocating sub-second budget across ASR → LLM reasoning → TTS.
4. **Partial ASR hypothesis handling** — how the agent reasons over non-final, uncertain input streams.
5. **TTS streaming and buffer management** — how to manage audio output concurrency.
6. **Session-scope memory** — short-lived session state across many turns in one connection.
7. **Architectural choice: monolithic vs. cascaded** — speech-to-speech models vs. ASR→LLM→TTS pipeline.
8. **Voice-specific observability** — concurrent span nesting and per-session run tracing.
9. **Voice golden datasets and evals** — how to measure agent quality when input is recorded audio (deterministic) not user utterances (non-deterministic).
10. **Streaming input redaction** — PII/injection defenses for continuous ASR output.

**Total estimated scope:** 150–200 lines for a new agent-voice.md that stands alone, plus another 100–150 lines of amendments across the existing specs (mostly in agent-runtime.md, agent-observability.md, agent-reliability.md, and agent-safety.md).

**Write-now vs. defer:** The spec is write-now if the voice prototype (doctolib scheduling) is in the plan phase. Defer if it is a future sprint — the frontier status and lack of consensus on VAD/barge-in handling means the spec will be rewritten once implementation reveals which design choices hold up.
