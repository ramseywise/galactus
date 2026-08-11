# Agent Voice — Conventions

**Durable question:** When audio flows both directions at once, what replaces the turn boundary — and what is the budget for every hop between the caller speaking and the caller hearing?

*Tooling-agnostic. Applies only to duplex designs: audio (or any stream) flowing both directions concurrently. If the design is request → response → done, this spec does not apply and `agent-architecture.md §1` does.*

**Status (2026):** Realtime voice practice is moving fast, and three things below are genuinely unsettled — endpointing thresholds, barge-in state serialization, and audio observability attributes have no standard. Where that is the case this spec says so and requires an explicit local design rather than inventing a number. Treat undated claims as current to 2026-08.

**Scope, and what this spec does not duplicate.** The layer specs remain in force; each carries a streaming qualification pointing here (§11). This spec owns what none of them do: **the replacement for the turn boundary, and the latency budget that constrains every other decision.** Turn-taking, critical-slot confirmation, and barge-in cancellation are deterministic control problems — the model supplies content, code decides when it is allowed to speak.

---

## 0. The one-sentence version

> **A duplex turn has no clean start, no clean end, and no replayable state — so every rule written for a turn that ends must be re-derived or explicitly scoped.**

Eight layer specs encode one assumption stated eight ways: a turn is a discrete, replayable, boundable unit of work. In a duplex stream the user may begin speaking before the agent stops (no clean start), barge-in truncates mid-utterance (no clean end), and the audio that produced the transcript is stochastic through VAD and ASR (no replay).

That is why this is a *loop-shape* gap and not a missing topic. A single voice spec sitting beside the others would leave eight live contradictions for anyone who opens a layer spec directly — so each of the eight carries a qualification pointing here (§11), and this file carries the depth. Every section below is a consequence of the sentence above.

---

## 1. Cascaded or speech-to-speech — the decision, not the answer

The first architectural choice, and it constrains everything downstream. **This spec presents the criteria; it does not pick for you.** The right answer is domain-dependent and the two domains that look similar diverge here.

| | Cascaded (ASR → LLM → TTS) | Speech-to-speech |
|---|---|---|
| Latency | 400–600ms optimized | 200–350ms |
| Cost | baseline | **~10×** |
| Audit trail | Text at every boundary | None — no deterministic transcript |
| Tool calling | Structured, predictable | Less reliable |
| Prosody / emotion | Lost at the ASR boundary | Preserved end to end |

Decide on these criteria, in this order:

1. **Is a transcript a product requirement, or a nice-to-have?** If the system holds regulated data, makes auditable commitments, or must answer "what exactly was said" months later, the text boundary *is* the requirement and cascaded wins before latency is discussed. See `agent-safety.md §7a`.
2. **How tool-heavy is the turn?** A turn that books, cancels, or mutates anything needs reliable structured calls. A turn that only converses does not.
3. **Does prosody carry meaning you would lose?** Distress, hesitation, and sarcasm survive S2S and die at the ASR boundary. For some domains that is the product.
4. **Only then, latency and cost.** The 150–200ms S2S saving is real but small against a budget dominated by LLM time-to-first-token (§2); the ~10× cost multiplier is not small.

The common error is reaching for S2S because "sub-second voice agent" sounds like it demands one — wrong for a high-tool-use, auditable, regulated workload, but stating that as a blanket verdict would mislead the next voice project that is none of those things. **Record which criterion decided it.**

---

## 2. Latency budget, decomposed per hop

A single end-to-end number is not a budget — it cannot be allocated, and it cannot be blamed. Decompose it, state a target per hop, and sum:

| Hop | Typical | Notes |
|---|---|---|
| Endpointing hold | 200–500ms | The tunable one; see §3. Directly trades against false cutoffs. |
| ASR finalize | 100–200ms | Streaming ASR emits interim results earlier; finalize is the cost of certainty. |
| **LLM time-to-first-token** | **400–800ms** | **Dominates.** |
| TTS first audio | 100–200ms | Streaming synthesis; not full-utterance synthesis. |
| Transport | 20–50ms | Negligible. Do not optimize here. |

**The load-bearing consequence: LLM TTFT dominates, and architecture cannot optimize around it. Model tier is the latency knob.** A voice agent may have to accept a smaller, faster model's reasoning to hit its target. That is a design-time constraint on the whole graph — it bounds how much reasoning any node can do — not a deployment detail to tune later. Decide it at design time or discover it at integration time.

Two rules follow. **Every in-turn tool call spends this budget** — a 2s call is invisible in chat and fatal on a phone call (`agent-tools.md`). And **sub-budgets are per hop, not fungible**: spending the endpointing hold to buy LLM headroom means cutting users off mid-sentence.

---

## 3. Endpointing — what ends a user turn

There is no `stop_reason` on an audio stream. Something must decide the user stopped talking, and it is a **probabilistic judgement that can be wrong in both directions**: cutting the user off mid-thought, or sitting through a pause they meant as a comma.

- **Acoustic VAD alone is insufficient** — roughly 85–90% accurate in production, which at conversational turn rates is a defect every few turns. **Production practice blends acoustic and semantic signals** (silence duration plus whether the transcript so far is a plausible complete utterance), reported 92–96%.
- **Thresholds are domain- and accent-specific and must be tuned empirically.** This spec deliberately states no number: an invented one would be worse than "tune this," because it would be copied.

The hard cases cluster on exactly the values you most need correct, because users pause *inside* critical slots. "September… 15th." Phone numbers read digit by digit. "Allergic to… penicillin and… sulfa." An endpointer tuned on conversational speech truncates all three.

**Requirement:** name the endpointing mechanism, state that its thresholds are empirical, and name the failure direction you biased toward. Do not leave it to the framework default and do not leave it unstated.

---

## 4. Barge-in and cancellation state

When the user speaks while the agent is speaking, something must be cancelled and something must be recorded. Both halves are commonly missed; the second is missed silently.

**Cancellation.** Name what stops: TTS playback, the in-flight LLM stream, or both. Stopping playback while the LLM keeps generating burns budget on audio nobody will hear; stopping the LLM without stopping playback leaves the caller listening to a sentence the system has already abandoned. Target: **barge-in to silence under 200ms** — past that the caller repeats themselves and you have two overlapping inputs.

**State.** Three facts must survive the interruption, and they are not the same fact: what the agent **generated** (the full intended utterance), what the user actually **heard** (an offset into it, in words or milliseconds), and the **interruption marker** itself, so the history is not silently reconstructed as a completed turn.

Only the second is what the user is responding to. A history that records the first as if it were delivered will make the model reason about a confirmation the caller never heard — a silent failure with no error and no trace unless you instrument it.

**There is no standard serialization for this.** Pipecat, LiveKit, and others each do it differently. The requirement is an explicit local design plus **audit-trail test coverage** asserting the three facts are distinguishable after the fact. Do not prescribe a format; do not inherit one unexamined.

---

## 5. ASR errors and critical slots

ASR is a probabilistic component whose output the rest of the system treats as text. That boundary is where mis-heard values enter as facts.

- **Bias the recognizer toward the domain vocabulary** — proper names, drug names, the date grammar. Biasing moves accuracy on exactly the tokens that matter most and costs nothing at runtime.
- **Keep n-best, not just the top hypothesis.** A single-best transcript discards the evidence that the recognizer was unsure, which downstream disambiguation and confirmation both need.
- **Confirm critical slots explicitly, and define which slots are critical at design time.** A slot is critical when getting it wrong is costly *and* not self-correcting. Confirmation is a deterministic gate, not a prompt instruction — the model asks, but code decides that it must.
- **Low confidence on a critical slot is an abstention, not a guess.** `agent-uncertainty.md` already owns this: abstention, asymmetric cost, and reversibility cover "ASR confidence is 0.6 on a drug name" without amendment. Read it alongside this section rather than restating it here.

**Partial hypotheses revise.** Streaming ASR emits interim transcripts that change as more audio arrives. Name what the system may act on before a transcript is final. Acting on an interim hypothesis that later revises — a tool call fired on a value the recognizer then corrected — is a silent-failure class with no analogue in text. Related: `agent-safety.md §1`'s pre-input layer assumes stable text to inspect before acting, which streaming ASR does not provide.

---

## 6. TTS streaming

The rule is short: **synthesize and play incrementally; never synthesize a full utterance before speaking.** Full-utterance synthesis puts the whole generation length into the first-audio budget, which §2 does not have room for.

Three consequences, each of which surprises people:

- **The LLM must stream too.** Token-by-token output feeds the synthesizer; a structured-output call that returns only when complete cannot be spoken incrementally. This constrains how output-schema discipline is applied inside a turn.
- **Sentence boundaries are the synthesis unit**, not tokens — prosody is computed over a phrase. Chunk on punctuation and clause boundaries.
- **Audio already emitted cannot be retracted**, which kills the generate-validate-repair loop used elsewhere in this repo: there is no re-prompt once the speaker is playing. **Voice is constraints-first** — bound the output before generating it. The deterministic-validator thesis survives; the repair loop does not.

---

## 7. Session state and lifetime

A call is a **long-lived stateful process**, which directly contradicts the stateless-request default in `agent-runtime.md`. The contradiction is real and is resolved by scope, not by preference: stateless holds for the tool-calling leaves; the session process is the exception.

Name, explicitly:

- **What owns connection lifetime** — who holds the socket, who detects a drop — and **reconnect semantics**: whether a caller who reconnects resumes the same session, and how long state survives without a connection.
- **Cleanup on disconnect**, including the mid-turn case where an utterance is in flight and a tool call may be pending. A dropped call mid-tool-call is the standard partial-failure case, and the tool may have committed.
- **Checkpoint granularity** — turn boundaries, not plan steps and not mid-utterance (`agent-memory.md`).
- **Session-level termination** — turns per session, wall-clock, and spend. The per-turn iteration cap in `agent-architecture.md §2` still bounds tool calls *within* a turn; it does not bound the session.

---

## 8. Telephony, codecs, and channel

The transport choice is a product decision with a measurable accuracy cost, so it belongs in the design, not the deployment config.

- **SIP/PSTN vs WebRTC.** Telephony reaches anyone with a phone — no app, no browser, no bandwidth floor — which matters when the caller population is elderly, low-connectivity, or simply calling a published number. WebRTC gives wideband audio and lower latency but imposes a client.
- **The cost of telephony is measurable: 8kHz narrowband degrades ASR by roughly 5–10% WER** against wideband-trained models. Budget for it rather than discovering it.
- **Name the escalation path** — SIP REFER to a human, DTMF as a fallback input when recognition fails repeatedly. A voice agent with no handoff is a trap for the caller. **State the codec** and whether any hop transcodes; transcoding twice is a quiet accuracy loss.

---

## 9. Observability — the audio attribute extension

`agent-observability.md` targets OTel GenAI semconv, which as of 2026 covers LLM and tool spans and **does not cover audio frames, VAD confidence, or TTS buffer state.** There is no standard to adopt, so this repo defines a local extension and marks it as such.

**Span shape is not a tree with one root per request.** A voice session is `session → turn → {asr, llm, tts}` with **overlapping** spans — TTS begins before the LLM finishes. Tooling assuming strict nesting will render this wrong or drop it. Local attributes, until standardized:

| Attribute | Meaning |
|---|---|
| `vad.confidence` | Endpointer confidence at the turn-end decision |
| `asr.confidence_score` | Confidence on the final transcript |
| `asr.n_best_count` | Alternatives retained (§5) |
| `tts.latency_ms` | Time to first audio out |
| `audio.codec` | Codec in use on this leg (§8) |
| `latency_to_first_token` | The dominant hop in §2's budget |
| `turn_duration_ms` | Wall-clock for the full turn |

> **Conflict — flagged, not resolved.** These names are local and will collide with the OTel GenAI SIG's eventual audio conventions. Marking them local-until-standardized is the cheapest available mitigation; renaming later is a dashboard migration, not a code one. Whether to propose them upstream is recorded as open, not actioned.

**Retention is a legal question here, not an ops one.** Audio is the raw special-category artifact; see `agent-safety.md §7a` and `agent-memory.md` for erasure scope.

---

## 10. Evaluation — no end-to-end deterministic replay

Stated here because it inverts the eval default and `agent-eval.md` carries the amendment.

**Identical audio yields identical ASR output but different LLM output.** There is no end-to-end deterministic replay for a voice pipeline, so "reset the environment between trials" holds per component and fails for the pipeline. Testing splits in two:

- **Deterministic** — component replay, tool-call success, infrastructure latency, barge-in cancellation timing.
- **Statistical** — task-completion rate, barge-in and endpointing accuracy, user behaviour.

**Task success is the primary metric; WER is a component metric that does not predict it.** 20% WER concentrated on filler words still books the appointment. 5% WER on the doctor's name does not. Reporting WER in place of task completion is the standard way a voice eval looks healthy while the product fails.

---

## 11. Pointers to qualifications in other specs

This spec is the depth; the layer specs carry the qualification at the point of use.

| Spec | What it qualifies |
|---|---|
| `agent-architecture.md` | Turn end has no `stop_reason`; the streaming-loop variant of the stack |
| `agent-runtime.md` | Session-scoped state as the exception to stateless requests (§7) |
| `agent-reliability.md` | A truncated utterance is **superseded**, not retried |
| `agent-observability.md` | Overlapping span shape, audio attributes, retention (§9) |
| `agent-eval.md` | Deterministic/statistical split; task success over WER (§10) |
| `agent-memory.md` | Turn-level checkpoints; erasure scope across audio, transcript, derived context |
| `agent-safety.md` | Partial-hypothesis pre-input; §7a regulated domains |
| `agent-tools.md` | In-turn latency budget (§2) |
| `agent-uncertainty.md` | **Unmodified** — abstention and asymmetric cost already cover §5 |

One deliberate non-amendment: **`agent-context.md:143`'s 5-minute cache TTL on a byte-identical prefix is voice-hostile** — a session's prefix changes every turn and a call outlives the window. The rest of that spec is loop-shape-independent and transfers whole, so it is not amended; this pointer is the whole correction.

---

## Sources

- Local synthesis (2026-08-10), from `.claude/docs/plans/2026-08-10-voice-capability-parity.md` and the five scout reports in `.claude/docs/research/`.
- `agent-uncertainty.md` — abstention and asymmetric cost, used whole by §5.
- `agent-architecture.md §2` — the `stop_reason` turn boundary this spec replaces.
- `agent-safety.md §7a` — regulated-domain constraints, referenced by §1 and §9.
- `.claude/skills/design-system/SKILL.md §4b` — the streaming-loop layer this spec supplies depth for.
- `.claude/skills/new-agent/references/cap-streaming.md` — framework streaming capability, incl. ADK `run_live()`.
- Endpointing accuracy, latency decomposition, and the cascaded/S2S cost delta: external realtime-voice practice as of 2026-08, via `.claude/docs/research/2026-08-10_voice-tooling_realtime-sota.md`.
