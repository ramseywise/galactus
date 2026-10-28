# Angle: Real-Time Voice Agent Architecture — State of the Art

**Target Application Context:** Doctolib-style medical appointment scheduling with live speech-in/speech-out, ASR → agent → TTS pipeline, barge-in support, turn-taking, sub-second latency, telephony or WebRTC.

This research establishes SOTA facts across eight angles to inform an `agent-voice.md` convention spec that will be substantive rather than hand-waving.

---

## 1. Cascaded vs. Speech-to-Speech Architecture

**Finding: Two competing approaches dominate; cascaded remains the production baseline despite higher latency, but S2S has clear use-case wins.**

### Cascaded (ASR → LLM → TTS)
- **Latency:** 400–600ms achievable in optimized production pipelines [Confidence: High] — source: [Speech-to-Speech vs Cascade: Voice Agent Architecture](https://deepgram.com/learn/speech-to-speech-vs-cascade-voice-agent-architecture)
- **Advantages:**
  - Every boundary is text: audit trail, moderation injection, tool-calling and structured extraction, context injection [Confidence: High]
  - Tool call reliability is predictable (text-in = structured outputs) [Confidence: High]
  - Transcript is deterministic and tamper-evident for compliance [Confidence: High]
  - Supports n-best hypothesis and confidence scores natively [Confidence: High]
- **Disadvantages:**
  - Loses acoustic information (prosody, emotion, voice identity) [Confidence: High]
  - Higher operational complexity: three separate service integrations [Confidence: High]
  - Latency dominance is in LLM and TTS, not ASR [Confidence: Medium]

### Speech-to-Speech (S2S, native audio-in-to-audio-out)
- **Latency:** 200–350ms end-to-end in 2026 production [Confidence: High] — source: [Gemini Live vs OpenAI Realtime API (2026)](https://www.justthink.ai/compare/openai-realtime-vs-gemini-live-api)
- **Providers:** OpenAI Realtime API (~320ms), Gemini Live (~200ms), Moshi by Kyutai (~200ms, open-source, on-device) [Confidence: High]
- **Advantages:**
  - 150–200ms latency reduction vs. cascaded [Confidence: High]
  - Preserves prosody, emotional tone, voice identity [Confidence: High]
  - Single model → single integration point [Confidence: High]
  - Moshi runs on-device (iPhone 15 Pro, single GPU) [Confidence: High]
- **Disadvantages:**
  - **Cost is ~10× cascaded pipelines** [Confidence: High] — critical for high-volume medical scheduling
  - No text intermediary = no audit trail, harder compliance [Confidence: High]
  - Tool calling less reliable (no structured text guarantee) [Confidence: High]
  - No deterministic transcript for medical records [Confidence: High]
  - Multimodal (images + audio) only on Gemini Live [Confidence: High]
  - Limited language support (Moshi: English only) [Confidence: High]
- **Token overhead:** S2S models often encode audio more aggressively than text; token efficiency unknown vs. cascaded [Confidence: Medium]

### Medical Appointment Scheduling Bias
For appointment booking (high tool-use, auditable, deterministic), **cascaded is the correct choice despite latency penalty** [Confidence: High]. The operator's spec should name this explicitly: S2S trades compliance and tool reliability for latency. See §8 for telephony specifics.

### Key Asymmetry
S2S models claim ~800ms "sub-second" latency on vendor docs; actual production figures are tighter. Cascaded's 400–600ms is not a ceiling, merely what operators report at p50 today. [Confidence: Medium]

---

## 2. Latency Budget Decomposition

**Finding: Sub-second (800ms) is the conversational threshold; most operators target 250–400ms p50; latency is dominated by LLM time-to-first-token, not transport.**

### Absolute Thresholds
- **<500ms p50:** Feels conversational, users do not consciously notice the gap [Confidence: High]
- **500–800ms:** Still acceptable for business calls, noticeable but not disruptive [Confidence: High]
- **800–1200ms:** Borderline acceptable, operator quality degrades [Confidence: High]
- **>1500ms:** Users recognize machine talking, conversation quality collapses [Confidence: High]
- **Sources:** [Voice AI Agents Compared on Latency (2026 Benchmarks)](https://telnyx.com/resources/voice-ai-agents-compared-latency), [Sub-Second Voice Agent Latency: A Practical Architecture Guide](https://sayna.ai/blog/sub-second-voice-agent-latency-practical-architecture-guide)

### 2026 Production Fleet Numbers
- **p50:** 680ms median end-to-end across the industry [Confidence: Medium]
- **p95:** 1180ms [Confidence: Medium]
- **Optimized targets:** p50 <250ms (with optimized stack), p50 <400ms (standard cloud stack) [Confidence: Medium]
- **Sources:** [Voice AI Agent Latency: How Fast Your Phone Bot Must Reply](https://www.famulor.io/blog/ai-voice-agent-latency-how-fast-your-phone-bot-must-reply)

### Component Breakdown (Cascaded Pipeline)
| Component | Latency Range | Bottleneck? |
|---|---|---|
| **Network / Transport** | 20–50ms | No (negligible) |
| **VAD endpointing** | 150–300ms | Moderate (user-configurable) |
| **ASR finalization** | Included in VAD | Part of endpointing delay |
| **LLM Time-to-First-Token (TTFT)** | 400–800ms | **YES — dominates** |
| **TTS time-to-first-audio** | 100–200ms | Moderate |
| **TTS streaming buffering** | 50–150ms | Optional (streaming reduces this) |
| **Total** | ~800–1500ms | LLM is the constraint |

[Confidence: High] — source: [Voice AI Latency: What's Fast, What's Slow, and How to Fix It](https://hamming.ai/resources/voice-ai-latency-whats-fast-what-slow-how-fix-it)

### Critical Implication for Specs
**LLM time-to-first-token dominates; the architecture cannot optimize around it.** Operator choice of model tier is the constraint, not pipeline design. Smaller, faster models (Haiku-tier) pay off 200–300ms here vs. frontier models (Sonnet). This is load-bearing for the spec: mention explicitly that a voice agent's latency is yoked to the model's TTFT, and medical scheduling may need to accept Haiku-tier reasoning to hit sub-second targets. [Confidence: High]

---

## 3. Turn-Taking and Endpointing

**Finding: Energy-based VAD alone is broken; the field has migrated to semantic or contextual models (2025–2026). Failure modes are well-characterized and unavoidable without model-based detection.**

### Three Endpointing Strategies (Ascending Complexity)

| Strategy | Mechanism | Accuracy | Cost | Failure Modes |
|---|---|---|---|---|
| **Acoustic VAD** | Silence detection on 20–80ms frames | 85–90% at 200ms after last speech | Negligible (~1ms latency) | Premature cut-off on pauses; misses end-of-turn without trailing silence |
| **Semantic VAD** | Evaluates whether transcribed text is complete (lexical, syntactic, intonation) | 92–96% with <100ms silence | Medium (runs ASR in parallel) | Misses pragmatic completeness ("uh" or "um" at end); false positives on incomplete sentences with natural falling intonation |
| **Model-Based** | LLM or specialized model predicts "speech onset time to next turn" | 95%+ with context-aware biasing | High (full inference per frame) | Slower feedback; requires LLM capacity |

[Confidence: High] — sources: [What Is Endpointing in Voice AI? A Guide to Turn Detection](https://www.cekura.ai/blogs/endpointing-in-voice-ai-turn-detection), [Turn-Taking in Voice Agents: Why Rule-Based VAD Is Broken](https://gradium.ai/content/turn-taking-voice-agents-vad)

### Medical Scheduling Specific Failure Modes
1. **Premature endpointing on dates/names:** "September [pause] 15th" read as "September" → agent responds prematurely [Confidence: High]
2. **Phone numbers:** Each digit often separated by breath; pure VAD cuts the turn too early [Confidence: High]
3. **Allergies/medications:** Users naturally pause between items ("I'm allergic to... [breath] penicillin and [pause] sulfa drugs"); semantic VAD must not cut on pauses [Confidence: High]

### Hybrid Approach in Production
Most 2026 voice agents blend acoustic (fast, cheap) + semantic (accurate, moderate cost): run acoustic VAD to gate; once speech stops, run ASR hypothesis through semantic evaluation. This delays true end-of-turn by ~150–300ms but catches 95%+ of cases correctly. [Confidence: High]

### New Research Direction
Recent work ("Phoenix-VAD: Streaming semantic endpoint detection," "Next-Turn: Duration-aware streaming endpoint detection") predicts *time-to-next-speech-onset* rather than binary "end of turn," allowing agents to know "user is pausing, not done" with higher confidence. Not yet widespread in production but emerging. [Confidence: Medium] — source: [Phoenix-VAD: Streaming Semantic Endpoint Detection](https://arxiv.org/pdf/2509.20410)

### No Consensus on Tuning
The spec should flag this explicitly: endpointing is config-heavy (VAD thresholds, semantic model weights, silence buffers), and the knobs differ per domain and accent. Medical scheduling will need tuning. [Confidence: High]

---

## 4. Barge-In and Interruption

**Finding: Barge-in is a fully-duplex architectural requirement, not a software feature. State consistency is genuinely hard; the field has converged on a limited set of solutions.**

### Architectural Prerequisite
Barge-in requires **full-duplex audio**: STT and TTS run on independent streams *simultaneously*, never alternating turns. Turn-based (half-duplex) architectures cannot support true interruption. [Confidence: High] — source: [Voice Agent Interruption Handling: Barge-In, Backchannels, and Turn Detection](https://hamming.ai/resources/voice-agent-interruption-handling-runbook)

### 2026 Production Standards (Benchmarks)
- **Barge-in detection latency:** <400ms from speech onset [Confidence: High]
- **False barge-in rate:** <2% (false positives are deeply frustrating) [Confidence: High]
- **Missed true interruptions:** <1% [Confidence: High]
- **TTS flush time (stop playback):** <60ms [Confidence: High]
- **Turn-taking gap after successful barge-in:** 200–400ms [Confidence: High]
- **Sources:** [Voice AI Barge-In and Turn-Taking: A 2026 Implementation Guide](https://futureagi.com/blog/voice-ai-barge-in-turn-taking-2026/), [AI Voice Agent Barge-In: How to Control Interruptions](https://famulor.io/blog/ai-voice-agent-barge-in-interruptions-enterprise-guide)

### Mechanism (What Gets Cancelled)
When barge-in fires:
1. **TTS playback** — stop audio immediately (hardware buffer clear, <60ms) [Confidence: High]
2. **In-flight LLM generation** — cancel or abandon (token cost is sunk; stopping saves TTS calls) [Confidence: High]
3. **Queued audio buffers** — discard pending frames from network or TTS [Confidence: High]
4. **Conversation history record** — **this is the hard part** (see below) [Confidence: High]

### State Consistency Problem (Load-Bearing)
The agent generated a sentence ("Your appointment is...") and spoke the first half before the user interrupted. The conversation history must record:
- **What the agent tried to say** (full sentence for debugging/audit)
- **What the user actually heard** (partial sentence, so they may know partial information)
- **Turn boundary marker** (user interrupted)
- **User's new intent** (what they said during interruption)

[Confidence: High — this is genuinely difficult]

Most frameworks handle this by:
1. **Logging both full LLM output and utterance-id / offset:** the agent's full sentence is in logs; the offset marks where playback was interrupted
2. **Conversation context carries cancellation marker:** `{"role": "assistant", "content": "Your appointment is...", "interrupted_at": 0.35, "user_interrupted": true}`
3. **Next turn uses user's new input, not the cancelled sentence:** the model sees the interruption marker and learns not to expect confirmation of the cancelled phrase

No single standard here; frameworks (Pipecat, LiveKit, Strands Agents) each have their own serialization. [Confidence: High] — source: [How to Build a Voice Agent That Handles Interruptions and Barge-Ins Naturally](https://vomyra.com/blogs/voice-agent-handle-interruptions-barge-in-naturally)

### For Medical Scheduling
Barge-in is **mandatory:** users interrupt with corrections ("No, I meant *afternoon*") or clarifications ("I said *Dr. Smith*, not *Jones*"). The spec must require:
- Full-duplex architecture
- <400ms barge-in detection
- Explicit logging of what was played vs. what was generated
- Test coverage for interrupted confirmations
[Confidence: High]

---

## 5. ASR Errors as a First-Class Input Problem

**Finding: ASR is noisy; the field has converged on a five-layer mitigation stack: contextual biasing, confidence scoring, n-best hypotheses, confirmation strategies, and error-recovery orchestration.**

### Contextual Biasing (Phrase Hints)
ASR systems can be biased toward domain vocabulary without retraining:
- **Medical scheduling:** patient names (from database), doctor names, facility names, common dates ("September 15th", "Tuesday at 2 PM")
- **Mechanism:** Weighted n-gram or embedding-based re-scoring of the hypothesis lattice; biasing does not forbid out-of-domain words but raises their scores
- **Gain:** 5–20% WER reduction on biased words; negligible cost overhead [Confidence: High]
- **Source:** [Fast and Robust Unsupervised Contextual Biasing for Speech Recognition](https://arxiv.org/pdf/2005.01677)

### Confidence Scores & N-Best Hypotheses
- **1-best:** ASR returns the top hypothesis + a confidence score (0–1)
- **N-best:** Top 5–10 hypotheses ranked by posterior probability; allows downstream recovery
- **Use:** If confidence <0.75 on a critical word (doctor name, date), ask for confirmation; if multiple hypotheses differ in critical slots, clarify [Confidence: High]
- **Source:** [Contextual ASR Error Handling with LLMs Augmentation](https://arxiv.org/html/2501.06129)

### Confirmation Strategies (Agent-Level)
1. **Implicit confirmation:** "Booking you for Tuesday at 2 PM with Dr. Smith" (agent repeats back, user nods or corrects)
2. **Explicit confirmation:** "Did you say Tuesday?" (agent asks for binary confirmation)
3. **Selective confirmation:** Only confirm when ASR confidence <threshold or word is in critical-slot list (names, dates, times)
4. **Correction workflow:** If user says "no, that's wrong," agent asks clarifying question and re-runs ASR on the correction

Medical scheduling **must use selective explicit confirmation:** dates, doctor names, phone numbers are all critical; casual speech ("and", "uh", "yeah") is not. [Confidence: High]

### N-Best Error Recovery (LLM-Select)
Recent work (RECOVER, 2026) shows LLMs can select the correct hypothesis from n-best by conditioning on task context:
- ASR provides top-5 hypotheses: ["Tuesday", "Thursday", "Friday", "Monday", "Saturday"]
- LLM reads: "I'm looking for an appointment next week" → LLM re-ranks, selects "Tuesday"
- Outperforms ROVER (voting) ensemble on medical/scheduling domains [Confidence: Medium]
- **Trade:** LLM token cost per error vs. asking user for confirmation [Confidence: Medium]
- **Source:** [RECOVER: Robust Entity Correction via Agentic Orchestration](https://arxiv.org/html/2603.16411)

### For Medical Scheduling (Load-Bearing)
The spec must define:
1. **Critical slot list:** {date, time, doctor_name, specialty, phone_number, medication, allergy}
2. **Confirmation rule:** explicit confirm if ASR confidence <0.8 OR word in critical list
3. **Retry budget:** max 3 attempts before escalating to human
4. **Context biasing:** supply patient DB, doctor roster, clinic hours to ASR provider
5. **Fallback:** if repeated failures, offer DTMF (dial 1 for "yes"), speech-to-text for names, or human handoff
[Confidence: High]

---

## 6. Testing and Evaluation of Voice Agents

**Finding: No deterministic replay (audio is inherently stochastic in VAD, ASR, TTS, LLM), so evaluation splits into deterministic (infrastructure, tool use) and statistical (user behavior, task success).**

### Test Fixtures & Deterministic Replay
- **Audio fixtures:** Capture production calls, replay against new agent versions (Roark, Braintrust platforms support this)
- **Caller simulation:** LLM-as-user harnesses; generate synthetic callers with different accents, speeds, emotional states
- **Replay limits:** Identical audio → same ASR but different LLM responses (model updates change outputs) → deterministic replay is per-component, not end-to-end
[Confidence: High] — source: [Top 5 Voice Agent Evaluation Tools in 2025](https://www.getmaxim.ai/articles/top-5-voice-agent-evaluation-tools-in-2025/)

### Evaluation Metrics (Four Layers)
| Layer | Metrics | Determinism |
|---|---|---|
| **Infrastructure** | Latency (p50, p95, p99), jitter, first-packet time, TTS buffer depth | Deterministic per call; statistically rolled up |
| **Execution** | Tool success rate (appointment booked? phone number stored?), hallucinations, OOD refusal | Deterministic per call; baseline-comparison (did model get *better* on this task?) |
| **User Behavior** | Barge-in rate, sentiment shift, CSAT, repeat queries | Statistical (requires user feedback or labeled corpus) |
| **Business Outcomes** | Task completion rate (FCR = first-contact resolution), escalation rate, cost-per-booking | Statistical; requires longitudinal data |

[Confidence: High] — source: [A Developer's Guide to Voice AI Evaluation Metrics (2026)](https://www.cekura.ai/blogs/voice-ai-evaluation-metrics)

### WER ≠ Task Success
Word Error Rate (WER, comparing ASR output to ground truth) does not correlate with appointment-booking success. A 20% WER might still book correctly if the errors are in filler words ("uh", "and"); a 5% WER might fail if the wrong doctor name was heard. The spec should mandate **task-success metrics, not WER**. [Confidence: High] — source: [How to Evaluate Voice Agents in 2025: Beyond ASR and WER](https://www.marktechpost.com/2025/10/05/how-to-evaluate-voice-agents-in-2025-beyond-automatic-speech-recognition-asr-and-word-error-rate-wer-to-task-success-barge-in-and-hallucination-under-noise/)

### Streaming Pipeline Specifics
Metrics like time-to-first-token, end-of-turn-detection latency, and barge-in accuracy depend *on how the agent runs*, not just the model. Text-replay testing misses these entirely. The spec must require **audio stream testing** for latency-sensitive features. [Confidence: High]

### No Consensus on Automated Grading
Braintrust, Hamming, and others offer custom scorers (LLM-as-evaluator, rule-based checks), but there is no settled standard. Each voice-agent platform has its own eval harness. [Confidence: Medium]

---

## 7. Observability — Tracing and Spans

**Finding: OpenTelemetry GenAI Semantic Conventions (v1.37+, exited experimental in early 2026) cover LLM calls and tool use; real-time audio evaluation has no standardized convention yet.**

### GenAI Semantic Conventions Coverage
- **In scope (v1.37+):** LLM invocations (model name, token counts, finish reason), tool calls (tool name, input/output schema), agent loop iterations
- **Out of scope:** Streaming audio frames, VAD confidence, TTS buffer state, real-time audio quality metrics [Confidence: High]
- **Sources:** [OpenTelemetry for AI Systems: LLM and Agent Observability (2026)](https://uptrace.dev/blog/opentelemetry-ai-systems), [OpenTelemetry GenAI Semantic Conventions](https://mlflow.org/docs/latest/genai/tracing/opentelemetry/genai-semconv/)

### Span Granularity for Voice Agents
No standard yet, but emerging practice:
| Level | Span Name | Duration | Attributes |
|---|---|---|---|
| **Session** | `voice_session` | Entire call | session_id, caller_id, language, sample_rate |
| **Turn** | `voice_turn` | User speech + agent response | user_intent, barge_in, vad_confidence |
| **ASR** | `asr_transcribe` | ASR latency | ASR model, confidence, n_best_count, wer_estimate |
| **LLM** | `llm_inference` | TTFT + generation | model, tokens_in, tokens_out, stop_reason |
| **TTS** | `tts_synthesize` | TTS latency | voice_id, audio_duration, sample_rate |

[Confidence: Medium — practice is emerging, not yet standardized]

### Platform Support
- **MLflow** recognizes OTel GenAI semconv traces from compliant tools
- **Datadog** natively supports v1.37+ (LLM, tool calls)
- **LiveKit Agents** emits OTel traces (partial coverage of above)
- **Pipecat** supports custom span injection but no native GenAI semconv yet [Confidence: Medium]

### For Medical Scheduling
The spec should mandate:
1. OTel spans for LLM, tool (booking), ASR, TTS
2. Session-level attributes: patient_id (pseudonymized for privacy), call_timestamp, escalation_reason
3. Latency breakdown: p50/p95 per hop
4. Flag all confirmations and corrections (data quality audit trail)
[Confidence: High]

---

## 8. Telephony vs. WebRTC

**Finding: Telephony (SIP/PSTN) and WebRTC are different transport layers with distinct codec, jitter, and latency profiles. Medical scheduling will almost always choose telephony (inbound/outbound phone lines), but WebRTC is emerging for internal/browser-based scheduling.**

### Telephony (SIP/PSTN)
- **Codec:** G.711 (narrowband, 8kHz) is standard for PSTN; wideband (16kHz) is rare but available on modern carriers
- **Jitter:** Unpredictable (public PSTN); requires 50–200ms jitter buffers [Confidence: High]
- **Latency:** Network varies widely; expect 100–300ms one-way (beyond agent's control) [Confidence: High]
- **Handoff:** SIP REFER protocol transfers calls to humans; standard but not universal
- **DTMF:** Full-duplex, always available (fallback for spelling names, entering codes)
- **ASR degradation:** 8kHz narrows the speech spectrum; acoustic models trained on wideband (16kHz) will degrade; 5–10% WER increase typical [Confidence: High] — source: [Healthcare Voice Agents: Complete Implementation Guide](https://www.assemblyai.com/blog/voice-agents-for-healthcare)

### WebRTC
- **Codec:** Opus (adaptive, 8–48kHz), VP8/H.264 for video [Confidence: High]
- **Jitter:** Managed by Jitter Buffer (browser or library); typically <50ms with modern networks [Confidence: High]
- **Latency:** Browser RTT + processing; often lower than PSTN for geographically close servers [Confidence: High]
- **Browser-based:** Mobile Safari, Chrome desktop; deployment simpler than PSTN integration
- **No fallback to voice call:** If connection drops, conversation ends (no handoff to phone)
- **Accessibility:** Requires tech-savvy users; not appropriate for all patient cohorts (elderly, rural, poor internet) [Confidence: High]

### Medical Scheduling Use Case
**Telephony (SIP/PSTN) is the correct choice.** Reasons:
1. Inbound: Patients call clinic's published phone number → automatic routing to agent
2. Outbound: Clinic can call patients for reminders/confirmations
3. Handoff: Transfer to human receptionist via SIP REFER
4. No tech burden on patient (just dial a number)
5. HIPAA alignment: Narrowband is acceptable for compliance; call logs are standard
6. Fallback: If agent system down, calls route to human queue

[Confidence: High]

### 2026 Shift: LiveKit Shipping Native SIP
Historically, agents needed a Twilio bridge to handle SIP/PSTN. In 2026, LiveKit shipped native SIP, allowing agents to accept inbound SIP directly. This simplifies architecture but does not change the recommendation. [Confidence: High] — source: [Build and Deploy LiveKit AI Voice Agents: The 2026 Playbook](https://www.forasoft.com/blog/article/livekit-ai-agents-guide)

### Spec Requirement
Mandate:
1. Telephony-first (SIP/PSTN) for inbound/outbound
2. ASR model trained on 8kHz (or apply bandwidth correction)
3. SIP REFER for human handoff
4. DTMF fallback for critical data entry (phone numbers, dates)
5. Jitter buffer configuration (50–200ms depending on carrier)
[Confidence: High]

---

## 9. Framework Landscape (2026 SOTA)

**Finding: Three frameworks dominate; each makes different tradeoffs. None is objectively "best"—the choice depends on latency target, telephony need, and deployment complexity.**

### Pipecat
- **Architecture:** Python-first pipeline (STT → LLM → TTS processors)
- **Latency:** Good for cascaded pipelines; no native S2S support
- **Telephony:** Requires external bridge (Twilio, SIP gateway)
- **State:** Processor-based (stateless pipeline model)
- **Maturity:** Open-source, active development, Pipecat Cloud reached GA in 2026
- **Best for:** Text-heavy tasks, research, quick prototypes
- **Weakness:** Telephony integration adds complexity [Confidence: High] — source: [Voice Agent Frameworks: Pipecat vs LiveKit](https://www.evalgent.com/blog/pipecat-vs-livekit)

### LiveKit Agents
- **Architecture:** Agent joins a WebRTC room as a headless participant (real-time infrastructure)
- **Latency:** Optimized for low-latency full-duplex (WebRTC native)
- **Telephony:** Native SIP support as of 2026 (game-changer for medical use)
- **State:** Room-based (agent as participant, shared state in room)
- **Maturity:** Open-source (Go runtime), production-ready, rapidly growing adoption
- **Best for:** Low-latency requirements, many simultaneous conversations, telephony
- **Weakness:** Opinionated architecture (can be over-engineered for simple tasks) [Confidence: High]

### Google ADK (Agents Development Kit)
- **Architecture:** Bidirectional streaming (Gemini Live API) with multimodal support
- **Latency:** 200–250ms claimed (S2S model)
- **Telephony:** Not native (WebRTC or custom integration needed)
- **State:** Session-based (Gemini Live manages conversation state)
- **Maturity:** Official Google product; active development (tutorials added 2026)
- **Best for:** Multimodal (voice + images), Google Cloud integration, high latency tolerance
- **Weakness:** Cost model (per-minute), S2S trade-offs noted above, weaker for deterministic tool-calling [Confidence: High] — source: [Build Your Voice Streaming AI Agents with ADK and Google Search grounding](https://medium.com/google-cloud/build-your-voice-streaming-ai-agents-with-adk-and-google-search-grounding-0cfcdec63d1e)

### OpenAI Realtime API
- **Architecture:** Bidirectional WebSocket, audio-native S2S
- **Latency:** 300–500ms (depends on model TTFT)
- **Telephony:** Not native (WebRTC or custom SIP gateway)
- **State:** Session-based (API manages turn-taking and interruption)
- **Maturity:** Production-ready; widely adopted
- **Best for:** S2S workflows, interruption handling built-in, low complexity
- **Weakness:** Cost (~10× cascaded), limited to audio (no structured extraction) [Confidence: High] — source: [OpenAI Realtime Voice API Deep Dive](https://dev.to/tyson_cung/openai-realtime-voice-api-deep-dive-audio-native-architecture-40eo)

### Recommendation for Medical Scheduling
**LiveKit Agents with native SIP is the SOTA choice** for 2026:
- Latency: optimizable for sub-second with cascaded ASR/LLM/TTS
- Telephony: built-in, no bridge needed
- Tool-calling: reliable (text-based pipeline)
- State: room-based allows easy agent pooling and failover
- Auditing: full control over transcript logging
[Confidence: High]

---

## 10. Open Questions & Field Consensus Gaps

**These are genuine unknowns; the spec should flag them as "resolved per deployment" rather than faking certainty.**

### 1. Endpointing Tuning is Config-Heavy
No closed-form solution; every domain (medical, e-commerce, technical support) needs different VAD/semantic thresholds. The spec should mandate a tuning process (A/B testing, user feedback collection) rather than recommend specific numbers. [Confidence: High]

### 2. Barge-In State Consistency (Hard Problem)
No single standard for logging "what was said, what was played, what the user heard." Frameworks differ. The spec should require explicit design per implementation, with audit-trail test coverage. [Confidence: High]

### 3. Real-Time Audio Observability Lacks Semconv
OTel GenAI semconv covers LLM/tool, not audio streams. An operator pursuing medical scheduling should extend GenAI semconv with:
- `audio.sample_rate`, `audio.codec`, `audio.duration_ms`
- `vad.confidence`, `vad.endpointing_method`
- `asr.confidence_score`, `asr.n_best_count`
- `tts.latency_ms`, `tts.voice_id`

Then contribute back to OpenTelemetry SIG. [Confidence: Medium]

### 4. ASR N-Best Error Recovery at Scale
Recent research (RECOVER, 2026) shows promise but lacks production deployment reports. Unknown: does LLM-based n-best selection beat rule-based confirmation at scale? Cost trade-off unclear. [Confidence: Low]

### 5. Semantic Endpointing Failure Modes Poorly Characterized
Academic work exists but production report are scarce. How often does semantic VAD false-positive on mid-sentence pauses in medical speech? Unknown. Recommend empirical tuning per domain. [Confidence: Medium]

### 6. Telephony Bandwidth: 8kHz ASR Models Degradation
5–10% WER increase is cited, but this is model-dependent. Modern ASR systems may mitigate this better. Unknown: does bandwidth-adaptation (lossy upsampling to 16kHz) help? Recommend empirical comparison. [Confidence: Medium]

### 7. Cost of S2S vs. Cascaded at Medical Scale
Vendor pricing is opaque. "~10× cascaded" is a broad estimate. Unknown: Does bulk volume (thousands of appointments/day) narrow the gap? Unknown for medical-domain-specific pricing. [Confidence: Low]

---

## Summary: What an agent-voice.md Spec Must Cover

The eight angles above map to a five-layer structured spec:

### **Layer 1: Architecture Choice (§1–2)**
- **Decision tree:** Cascaded vs. S2S (medical → cascaded)
- **Latency budget:** Sub-second threshold, component breakdown, LLM dominance
- **Model tier implication:** Haiku-level reasoning to hit latency targets
- **Framework selection:** Recommend LiveKit + SIP for medical

### **Layer 2: Audio Input (§3, §5, §8)**
- **Transport:** Telephony (SIP/PSTN) for medical
- **Codec:** 8kHz narrowband; ASR model training requirement
- **Endpointing:** Hybrid semantic + acoustic, domain-specific tuning required
- **ASR error mitigation:** Confidence scores, contextual biasing, n-best selection
- **Critical slot protection:** Explicit confirmation on dates, names, phone numbers

### **Layer 3: Agent Logic (§4, §5)**
- **State consistency:** Full-duplex architecture, barge-in cancellation logging
- **Tool reliability:** Structured extraction from transcripts, not audio
- **Confirmation strategies:** Selective, not universal; ASR confidence thresholds
- **Correction loops:** Retry budget, escalation trigger

### **Layer 4: Observability (§7)**
- **Tracing:** OTel GenAI semconv (LLM, tools); propose audio extension
- **Latency breakdown:** p50/p95 per hop (ASR, LLM, TTS, endpointing)
- **Audit trail:** Full transcript, barge-in markers, confirmation log

### **Layer 5: Testing & Eval (§6)**
- **No deterministic replay:** Audio is inherently stochastic; split testing into deterministic (tool success) and statistical (user behavior)
- **Metrics:** Task completion rate (FCR), not WER
- **Test fixtures:** Audio replay, LLM-as-caller harnesses
- **Regression testing:** Latency, barge-in accuracy, tool success

---

## Sources

- [Cascaded vs. Speech-to-Speech Voice Agent Architecture](https://deepgram.com/learn/speech-to-speech-vs-cascade-voice-agent-architecture)
- [Cascaded vs Speech-to-Speech Voice Architecture](https://inworld.ai/resources/cascaded-vs-speech-to-speech-voice-architecture)
- [Speech-to-Speech vs Cascade: Voice Agent Architecture](https://deepgram.com/learn/speech-to-speech-vs-cascade-voice-agent-architecture)
- [Cascaded Voice Agents vs Speech-to-Speech: Architecture Tradeoffs in 2026 | Gradium](https://gradium.ai/content/cascaded-voice-agent-vs-speech-to-speech-2026)
- [Pipeline vs. Realtime Voice Agent Architecture: Full Guide](https://rtcleague.com/blogs/pipeline-vs-realtime-voice-agent-architecture)
- [OpenAI Realtime API vs Gemini Live API (2026) — Honest Comparison](https://www.justthink.ai/compare/openai-realtime-vs-gemini-live-api)
- [Best Speech-to-Speech Model 2026: S2S Comparison](https://inworld.ai/resources/best-speech-to-speech-model)
- [Voice AI Agents Compared on Latency (2026 Benchmarks)](https://telnyx.com/resources/voice-ai-agents-compared-latency)
- [AI Voice Agent Latency: How Fast Your Phone Bot Must Reply](https://www.famulor.io/blog/ai-voice-agent-latency-how-fast-your-phone-bot-must-reply)
- [Voice AI Latency: What's Fast, What's Slow, and How to Fix It](https://hamming.ai/resources/voice-ai-latency-whats-fast-what-slow-how-fix-it)
- [Sub-Second Voice Agent Latency: A Practical Architecture Guide](https://sayna.ai/blog/sub-second-voice-agent-latency-practical-architecture-guide)
- [Voice Activity Detection (VAD): The Complete 2026 Guide to Speech Detection](https://picovoice.ai/blog/complete-guide-voice-activity-detection-vad/)
- [Voice Activity Detection: What it is & How to Use it in Your Technology [2025]](https://www.tavus.io/blog/voice-activity-detection)
- [What Is Voice Activity Detection (VAD)? A 2026 Guide](https://www.cekura.ai/blogs/voice-activity-detection)
- [Phoenix-VAD: Streaming Semantic Endpoint Detection](https://arxiv.org/pdf/2509.20410)
- [Voice Agent Interruption Handling: Barge-In, Backchannels, and Turn Detection](https://hamming.ai/resources/voice-agent-interruption-handling-runbook)
- [Voice AI Barge-In and Turn-Taking: A 2026 Implementation Guide](https://futureagi.com/blog/voice-ai-barge-in-turn-taking-2026/)
- [How to Build a Voice Agent That Handles Interruptions and Barge-Ins Naturally](https://vomyra.com/blogs/voice-agent-handle-interruptions-barge-in-naturally)
- [AI Voice Agent Barge-In: How to Control Interruptions](https://famulor.io/blog/ai-voice-agent-barge-in-interruptions-enterprise-guide)
- [Healthcare Voice Agents: Complete Implementation Guide](https://www.assemblyai.com/blog/voice-agents-for-healthcare)
- [AI Voice Agents for Healthcare: Top Platforms for 2026](https://rasa.com/blog/ai-voice-agents-for-healthcare-top-platforms-for-2026/)
- [Fast and Robust Unsupervised Contextual Biasing for Speech Recognition](https://arxiv.org/pdf/2005.01677)
- [A Neural Model for Contextual Biasing Score Learning and Filtering](https://arxiv.org/pdf/2510.23849)
- [Contextual ASR Error Handling with LLMs Augmentation](https://arxiv.org/html/2501.06129)
- [RECOVER: Robust Entity Correction via Agentic Orchestration](https://arxiv.org/html/2603.16411)
- [Top 5 Voice Agent Evaluation Tools in 2025](https://www.getmaxim.ai/articles/top-5-voice-agent-evaluation-tools-in-2025/)
- [Best voice agent evaluation tools in 2025](https://braintrust.dev/articles/best-voice-agent-evaluation-tools-2025)
- [A Developer's Guide to Voice AI Evaluation Metrics (2026)](https://www.cekura.ai/blogs/voice-ai-evaluation-metrics)
- [Voice Agent Testing Guide: Methods, Regression, Load & Compliance (2026)](https://hamming.ai/resources/voice-agent-testing-guide)
- [Voice AI Evaluation Infrastructure 2026: A Developer Guide](https://futureagi.com/blog/voice-ai-evaluation-infrastructure-developers-guide/)
- [How to Evaluate Voice Agents: Complete Framework for Testing & Monitoring](https://hamming.ai/resources/how-to-evaluate-voice-agents-2026)
- [How to Evaluate Voice Agents in 2025: Beyond ASR and WER](https://www.marktechpost.com/2025/10/05/how-to-evaluate-voice-agents-in-2025-beyond-automatic-speech-recognition-asr-and-word-error-rate-wer-to-task-success-barge-in-and-hallucination-under-noise/)
- [OpenTelemetry for AI Systems: LLM and Agent Observability (2026)](https://uptrace.dev/blog/opentelemetry-ai-systems)
- [OpenTelemetry GenAI Semantic Conventions](https://mlflow.org/docs/latest/genai/tracing/opentelemetry/genai-semconv/)
- [Datadog Agent Observability natively supports OpenTelemetry GenAI Semantic Conventions](https://www.datadoghq.com/blog/llm-otel-semantic-convention/)
- [OpenTelemetry for AI Observability: What It Covers and Where It Stops](https://www.fiddler.ai/blog/opentelemetry-ai-observability-guide)
- [Inside the LLM Call: GenAI Observability with OpenTelemetry](https://opentelemetry.io/blog/2026/genai-observability/)
- [OpenTelemetry just standardized LLM tracing](https://dev.to/vola-trebla/opentelemetry-just-standardized-llm-tracing-heres-what-it-actually-looks-like-in-code-2e5f)
- [How OpenTelemetry Traces LLM Calls, Agent Reasoning, and MCP Tools](https://greptime.com/blogs/2026-05-09-opentelemetry-genai-semantic-conventions)
- [Top Voice AI Agent Frameworks in 2026: A Complete Guide](https://medium.com/@mahadise0011/top-voice-ai-agent-frameworks-in-2026-a-complete-guide-for-developers-4349d49dbd2b)
- [Build and Deploy LiveKit AI Voice Agents: The 2026 Playbook](https://www.forasoft.com/blog/article/livekit-ai-agents-guide)
- [Voice agent frameworks: Pipecat, LiveKit Agents, and friends](https://soniox.com/wiki/voice-agent-frameworks)
- [6 Best Open-Source Voice Agent Frameworks (2026)](https://techsy.io/en/blog/best-open-source-voice-agent-frameworks)
- [Pipecat vs LiveKit: Which Voice Framework? (2026)](https://www.evalgent.com/blog/pipecat-vs-livekit)
- [Voice AI agents in production 2026](https://www.reactify-solutions.com/articles/voice-ai-agents-production-2026)
- [OpenAI Realtime Voice API Deep Dive - Audio-Native Architecture](https://dev.to/tyson_cung/openai-realtime-voice-api-deep-dive-audio-native-architecture-40eo)
- [OpenAI Realtime API: The Missing Manual](https://www.latent.space/p/realtime-api)
- [Realtime and audio | OpenAI API](https://developers.openai.com/api/docs/guides/realtime)
- [Build Your Voice Streaming AI Agents with ADK and Google Search grounding](https://medium.com/google-cloud/build-your-voice-streaming-ai-agents-with-adk-and-google-search-grounding-0cfcdec63d1e)
- [Part 5. Audio, Images, and Video - Agent Development Kit (ADK)](https://google.github.io/adk-docs/streaming/dev-guide/part5/)
- [Python - Agent Development Kit (ADK)](https://google.github.io/adk-docs/get-started/streaming/quickstart-streaming/)
- [Part 1. Intro to streaming - Agent Development Kit (ADK)](https://google.github.io/adk-docs/streaming/dev-guide/part1/)
- [ADK Gemini Live API Toolkit: A Visual Guide to Real-Time Multimodal AI Agent Development](https://medium.com/google-cloud/adk-bidi-streaming-a-visual-guide-to-real-time-multimodal-ai-agent-development-62dd08c81399)
- [What Is Endpointing in Voice AI? A Guide to Turn Detection](https://www.cekura.ai/blogs/endpointing-in-voice-ai-turn-detection)
- [What is Endpointing in Voice AI? Turn Detection Explained](https://decagon.ai/glossary/what-is-endpointing)
- [Semantic VAD: turn detection that uses meaning, not silence](https://gradium.ai/blog/semantic-vad)
- [Turn-Taking in Voice Agents: Why Rule-Based VAD Is Broken](https://gradium.ai/content/turn-taking-voice-agents-vad)
- [Turn Detection for Voice Agents: VAD, Endpointing, and Model-Based Detection](https://livekit.com/blog/turn-detection-voice-agents-vad-endpointing-model-based-detection)
- [Semantic VAD for Voice Agents: Turn Detection 2026](https://gradium.ai/content/semantic-vad-voice-agents-turn-detection-2026)
- [How intelligent turn detection (endpointing) solves the biggest challenge](https://www.assemblyai.com/blog/turn-detection-endpointing-voice-agent)

