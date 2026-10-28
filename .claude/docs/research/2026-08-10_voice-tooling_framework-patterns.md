# Angle: Framework and coding-pattern audit — which existing agent framework patterns survive real-time voice, and which fail?

## Findings

### Template Skills Assessment (A)

**framework-selection/SKILL.md** [Confidence: High]
- **File:line** `/Users/wiseer/workspace/ai-project-template/template/.agents/skills/framework-selection/SKILL.md:20-39`
- Has NO realtime/streaming/voice branch in the decision tree. Decision guide asks: TypeScript runtime (→Vercel), GCP/Vertex (→ADK), control-flow needs (→LangGraph), existing LangChain (→LangGraph). Stops there.
- **For a voice agent today**, the framework-selection skill would route you to **ADK** if deploying on GCP (mentioning Vertex AI in the examples), or **LangGraph** for "anything that needs to run anywhere else". Neither is wrong, but neither explicitly acknowledges the realtime constraint.
- **Gap**: The decision procedure has no question like "Does this need bidirectional streaming, sub-second latency, or persistent WebSocket connection?" which would be the realtime disqualifier or selector.

**adk-dev-guide/SKILL.md** [Confidence: High]
- **File:line** `/Users/wiseer/workspace/ai-project-template/template/.agents/skills/adk-dev-guide/SKILL.md:1-30`
- ADK is presented as "fast-prototype choice; production auditability needs → LangGraph" (per global ref `google-adk.md:11`).
- **Does NOT mention** Gemini Live API, bidirectional streaming, or the `run_live` capability that Google ADK *does* ship. The skill covers scaffolding, implementation, evaluation, deployment — standard request/response patterns only.
- **This is the single highest-value gap**: Google ADK has first-class streaming support (documented in Google's own `adk-docs/streaming/` tree), and the template's ADK skill completely omits it. A developer choosing ADK for a voice project finds no guidance here.

**adk-scaffold/SKILL.md** [Confidence: High]
- **File:line** `/Users/wiseer/workspace/ai-project-template/template/.agents/skills/adk-scaffold/SKILL.md:1-50`
- Scaffolder covers: agent templates (standard `adk`, `adk_a2a`, `agentic_rag`), deployment targets (Agent Engine, Cloud Run, none), session types (in_memory, cloud_sql, agent_engine).
- **No streaming template or session-service mode for realtime bidirectional connections.** Scaffolding assumes request/response (202 async or synchronous).

**langgraph-fundamentals/SKILL.md** [Confidence: High]
- **File:line** `/Users/wiseer/workspace/ai-project-template/template/.agents/skills/langgraph-fundamentals/SKILL.md:1-40`
- Covers StateGraph, state schemas, nodes, edges, streaming via `astream_events()` (implicit in token-by-token messaging).
- **Streaming section exists (implied by design)** but is NOT explicitly covered in this excerpt. Does mention streaming in the web-search context: LangGraph can stream token-by-token via `astream_events`, which is good, but that is UX latency, not architectural bidi support.
- **Limitation**: LangGraph is a stateful graph, not a bidirectional real-time transport. A voice agent using LangGraph needs an external voice framework (Pipecat, LiveKit, Vapi) to manage audio transport and turn-taking.

**langgraph-scaffold/SKILL.md** and **langgraph-persistence/SKILL.md**, **langgraph-human-in-the-loop/SKILL.md** [Confidence: High]
- **File:line** `/Users/wiseer/workspace/ai-project-template/template/.agents/skills/langgraph-scaffold/SKILL.md:1-50`
- Scaffold covers checkpointer choice (dev vs prod), human-in-the-loop via `interrupt()`, stateless and service deployment.
- **No realtime audio primitives.** HITL (human-in-the-loop) uses `interrupt()` to pause the graph, which assumes a text-driven control flow, not audio turn-taking.

**vercel-ai-sdk-scaffold/SKILL.md** [Confidence: High]
- **File:line** `/Users/wiseer/workspace/ai-project-template/template/.agents/skills/vercel-ai-sdk-scaffold/SKILL.md:1-50`
- TS-native, single `streamText` tool-calling loop, Vercel zero-config deployment.
- **No audio transport.** The skill is for typed assistant APIs, not voice interfaces. Streaming is token-streaming (for UI latency), not bidirectional audio.

### Global Refs Assessment (B)

**google-adk.md** [Confidence: High]
- **File:line** `/Users/wiseer/.claude/refs/google-adk.md:1-55`
- Binding table (line 21-32) lists capabilities: RAG, Vision, A2A, Batch, HITL — **no streaming row**. The brief mentions Gemini/Vertex as "first-party LLM" but does not surface Gemini Live API support.
- **Gap**: The ref correctly states ADK is for "quick POCs" and production auditability goes to LangGraph. But it omits the asymmetry: ADK has realtime streaming built-in, LangGraph does not.

**langgraph.md** [Confidence: High]
- **File:line** `/Users/wiseer/.claude/refs/langgraph.md:1-60`
- Capabilities table (line 51-59) lists: RAG, Compaction, Streaming, Batch, A2A, HITL.
- **Streaming row** (line 56): "graph.astream_events(); stream tokens, not full responses" — **this is token-streaming for latency, not bidirectional audio streaming**. The streaming capability is over HTTP, not WebSocket/WebRTC for voice.
- **Accurate assessment**: "LangGraph is the production-grade choice for auditable, stateful agents" but "ADK for quick POCs." The ref does not say "ADK has voice support LangGraph doesn't."

**python.md, typescript.md** [Confidence: Medium]
- **File:line** `/Users/wiseer/.claude/refs/python.md`, `/Users/wiseer/.claude/refs/typescript.md` (not read in full, inferred from CLAUDE.md context)
- These are stack bindings for async, imports, and SDK patterns — not voice-specific. Likely to have patterns for streaming I/O and WebSocket handling, but no voice-domain coverage.

**galactus vendored copies** [Confidence: Medium]
- Galactus has `.claude/specs/langgraph.md`, `.claude/specs/python.md`, `.claude/specs/typescript.md` (per CLAUDE.md line 26). These are intentional renders from global canon. Per the context provided, they are deliberately vendored for self-containment.
- Galactus's `.claude/specs/agent-runtime.md` (read above) covers streaming at §6 with the guidance "Stream early. Do not buffer full responses if the client supports streaming." That is output-latency optimization, not realtime voice architecture.

### ml6 Prototype Patterns (C) — What Transfers, What Fails

**Pattern: 202 async job-id + polling API** [File:line `ml6/src/galactus/api.py:1-160`] [Confidence: High]

**Transfer to voice?** ❌ **ACTIVELY WRONG**

- ml6 returns `202 Accepted` with a job id, client polls `GET /jobs/{id}`. Line 6-10 explains: "Generation takes several seconds and may make up to four model calls, which is past what a client should hold a connection open for."
- **In voice**: The entire premise inverts. A voice call is a **persistent bidirectional connection that must NOT be broken and polled**. The latency budget is **sub-500ms end-to-end**, not "several seconds backgrounded". Switching from WebSocket to polling would introduce unacceptable latency gaps and would break the conversational flow.
- **Pattern verdict**: The polling-job API is a solution to the constraint "generation is slow and clients shouldn't wait." Realtime voice reverses that constraint: generation must be fast and streaming, and the connection is never dropped.

**Pattern: Deterministic validator as binding constraint** [File:line `ml6/src/galactus/models.py:105-150`, `ml6/src/galactus/generate.py:1-40`] [Confidence: High]

**Transfer to voice?** ⚠️ **SURVIVES with modification**

- ml6's thesis (per CLAUDE.md): "Counting characters is a job for code; the model's job is content." The pipeline is: LLM generates → JSON Schema shapes it → deterministic validator checks constraints → repair loop on violation → truncation fallback.
- **In voice**: Deterministic validation still applies — e.g., "don't speak over 30 words per turn", "don't use words outside this vocabulary" — but the binding enforcement changes.
  - **Character/word counts**: Lexical counting still works. ASR transcript can be bounded the same way.
  - **Structure validation**: Voice doesn't return JSON; it returns audio. But the underlying turn structure (Speaker A, Speaker B, handoff) is still contractual. You can validate turn boundaries before synthesis.
  - **Repair loop**: ml6's ≤3 repair attempts cannot work in realtime. Mid-utterance, a user is waiting. You cannot re-prompt and regenerate during audio playback. **Repair only works pre-call**, not mid-call. The architecture must shift to constraints-first generation, not generate-and-repair.
- **Pattern verdict**: The thesis survives — determinism matters. But the repair mechanism does not transfer directly. Voice requires **upfront constraint satisfaction**, not reactive repair.

**Pattern: LLM provider-port + adapter** [File:line `ml6/src/galactus/llm/port.py:1-59`] [Confidence: High]

**Transfer to voice?** ✅ **REUSES**

- ml6 defines a minimal Protocol: `async def complete_structured(prompt: str, schema: dict) -> dict`. One method. No assumptions about streaming, multi-turn, or media.
- **In voice**: The same port can abstract OpenAI Realtime API, Google Gemini Live, Anthropic's voice capabilities (if added). Swap implementations, same interface. The port is provider-agnostic, which is exactly what a voice agent needs.
- **Caveat**: The protocol is JSON-request/JSON-response. Voice-specific providers (Gemini Live, OpenAI Realtime) use audio frames + JSON control. The port would need extension: `async def stream_audio(audio_frames: AsyncIterator[bytes], model_context: str) -> AsyncIterator[bytes]` alongside the structured method.
- **Pattern verdict**: The abstraction layer is reusable, but the signature must expand from "structured generation" to "streaming multimodal I/O".

**Pattern: Structured logging and per-call spans (obs.py)** [File:line `ml6/src/galactus/obs.py:1-150`] [Confidence: High]

**Transfer to voice?** ✅ **REUSES**

- ml6's `AgentSpan` dataclass (line 43-66) emits OTel GenAI semconv v0.4 attributes. Span per LLM call, never aggregated. Metadata carries pipeline identity (`stage`, `attempt`, `job_id`).
- **In voice**: Spans still work. You'd add fields: `latency_to_first_token`, `turn_duration_ms`, `asr_confidence`, `tts_model_latency`. The contract ("one span per call, never aggregated") survives; the fields grow.
- **Caveat**: Streaming introduces a new observation shape. A single "LLM call" in ml6 is now a stream of events: "generate started", "first token", "token 1..n", "stream ended". You might emit sub-spans (prefix tokens, synthesis prefill vs decode), or one span with timing arrays. The observatory pattern is sound; the instrumentation detail grows.
- **Pattern verdict**: REUSE the span contract and emission discipline. Adapt the field set to voice specifics.

### Web Research: Real-Time Voice Frameworks (D)

**Pipecat** [Confidence: High, URL: https://github.com/pipecat-ai/pipecat]
- **What it is**: Open-source Python framework (v1.0 stable April 2026). Connects STT, LLM, TTS into a real-time pipeline, handles audio transport, turn-taking, and interruption detection. Supports 100+ AI services.
- **Turn-taking/VAD/Barge-in**: YES — "handles audio transport, turn-taking, and interruption detection" per search results. Full-duplex voice conversation.
- **Transport**: WebRTC, WebSocket, and others (integrates with Daily for media).
- **Agent framework composition**: Pipecat wraps around an LLM. You provide a tool-calling loop or a graph (LangGraph, ADK, or custom). Pipecat handles audio I/O and synchronization. **Voice framework calls agent framework, not the reverse.**
- **Architectural shape**: (A) Voice framework that CALLS an existing agent graph — yes, this is Pipecat's design.

**LiveKit Agents** [Confidence: High, URL: https://livekit.com/voice-agents]
- **What it is**: Open-source Python/Node framework, 11k+ GitHub stars, Apache-2.0. Runs on LiveKit's WebRTC infrastructure. Two pipeline shapes: (i) Cascade (STT → LLM → TTS, 3 vendors) or (ii) Speech-to-speech models (OpenAI Realtime, Gemini Live).
- **Turn-taking/VAD/Barge-in**: YES — WebRTC native, built-in VAD and interruption.
- **Transport**: WebRTC. Can join video conferences, screen shares.
- **Agent framework composition**: Like Pipecat, LiveKit wraps an LLM. You can plug in any LLM provider. But the framework that's doing the work is LiveKit, not the agent framework.
- **Architectural shape**: (A) Voice framework that CALLS an existing agent, or (B) direct speech-to-speech model that REPLACES ASR → LLM → TTS.
- **Latency**: 700ms–1.2s end-to-end on cascade; 450ms on direct speech-to-speech (per web search results).

**Google ADK with Gemini Live API** [Confidence: High, URL: https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/bidirectional-streaming]
- **What it is**: ADK's streaming module provides bidirectional streaming via WebSocket to Gemini Live API. Handles multimodal input (audio, video, text), session management, tool orchestration, and state persistence.
- **Turn-taking/VAD/Barge-in**: YES — "interruptions, and VAD" per search results. BIDI over WebSocket with natural conversation flow.
- **Transport**: WebSocket (over HTTP/HTTPS).
- **Agent framework composition**: **ADK IS the framework.** You write the agent in ADK, and ADK natively supports `run_live()` or bidirectional streaming mode. This is NOT "voice framework calls agent framework"; it is "agent framework has streaming built-in."
- **Architectural shape**: Hybrid. ADK can either (A) call a cascading STT/LLM/TTS pipeline, or (B) delegate to Gemini Live API, which handles audio natively.
- **Key finding**: The template's ADK skill omits this entirely. Developers looking at ADK find no guidance on how to enable streaming.

**OpenAI Realtime API** [Confidence: High, URL: https://developers.openai.com/api/docs/guides/realtime]
- **What it is**: Unified API released May 2026 (gpt-realtime production model). Audio in → audio out with sub-300ms latency. Single model handles ASR, reasoning, and TTS. Supports tool calling, MCP servers, image input, SIP phone calling.
- **Turn-taking/VAD/Barge-in**: YES — audio-in/audio-out with interruption support via WebSocket.
- **Transport**: WebSocket.
- **Agent framework composition**: **OpenAI Realtime replaces the framework.** You don't use LangGraph or ADK for realtime calls; you use OpenAI's API directly. It is a speech-to-speech model, not an orchestration framework.
- **Architectural shape**: (B) Speech-to-speech model that REPLACES the ASR → LLM → TTS cascade.
- **Pricing**: $32/M for audio input (≈$0.06/min), $64/M for audio output (≈$0.24/min) — realtime is expensive per minute.

**Vapi** [Confidence: High, URL: https://www.reactify-solutions.com/articles/voice-ai-agents-production-2026]
- **What it is**: Developer platform for building phone and web voice agents. You bring your own LLM, STT, TTS, and telephony provider; Vapi orchestrates them with sub-600ms latency.
- **Turn-taking/VAD/Barge-in**: YES — inherent to the architecture.
- **Transport**: Telephony (SIP), WebSocket (web).
- **Agent framework composition**: (A) Voice framework that CALLS an existing agent. You plug in GPT-4, Claude, Gemini, etc. Vapi handles synchronization.
- **Architectural shape**: (A) Voice framework that CALLS an existing agent graph.

**LangGraph + LiveKit Adapter** [Confidence: Medium, URL: https://github.com/ahmad2b/langgraph-voice-call-agent]
- **What it is**: Community pattern for adapting LangGraph into a voice agent via LiveKit. Composition: LiveKit handles audio transport and turn-taking, LangGraph handles the stateful logic.
- **Turn-taking/VAD/Barge-in**: YES — via LiveKit.
- **Transport**: WebRTC (LiveKit).
- **Agent framework composition**: (A) Voice framework (LiveKit) CALLS agent framework (LangGraph). Token-by-token streaming via `astream_events()` lets TTS start before full reply.
- **Architectural shape**: (A) Classic composition.
- **Key finding**: This adapter proves LangGraph is composable into voice, but it requires external plumbing. The LangGraph skill in the template does NOT mention this pattern.

---

### Architectural Shapes Emerging

Three patterns dominate production voice agents in 2026:

1. **Voice framework CALLS agent framework** (Pipecat, LiveKit-with-LangGraph, Vapi): You write an agent logic in your preferred framework (LangGraph, ADK, custom), and a voice framework orchestrates the audio I/O, turn-taking, and synchronization. **Pros**: Reuse existing agent code, clear separation of concerns. **Cons**: One more layer to integrate; latency is ~700ms–1.2s.

2. **Unified speech-to-speech model** (OpenAI Realtime, Gemini Live): One model handles everything — ASR, reasoning, TTS, tool-calling. **Pros**: Lowest latency (~300ms), simplest integration. **Cons**: Locked into one provider's reasoning, no custom stateful graph.

3. **Managed agent platform with streaming** (ADK with Gemini Live, LangGraph Cloud if streaming added): Your agent framework natively handles streaming and session management. **Pros**: Single system boundary, first-class observability. **Cons**: Requires framework-specific setup.

---

## Asset Verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| **framework-selection/SKILL.md** | ADAPT | Add a "Does this need persistent bidirectional audio connection?" question that routes to "ADK (if GCP + Gemini Live)", "OpenAI Realtime (if voice-first)", or "External voice framework + LangGraph/ADK". The existing decision tree is sound for request/response but misses realtime branching. Cost: one new decision row + two new outcomes. |
| **adk-dev-guide/SKILL.md** | ADAPT | Add a "Streaming workflows" section referencing ADK's `run_live()` capability and Gemini Live API integration. Cost is minimal (200–300 lines of patterns + examples). This is the highest-leverage gap: ADK has the capability; the skill just doesn't document it. |
| **adk-scaffold/SKILL.md** | ADAPT | Add a streaming scaffold template mode (e.g., `--agent adk_streaming` or `--deployment-target agent_engine_realtime`). Currently covers standard + RAG + A2A; add realtime as a template variant. Reference the Gemini Live session-service setup. Cost: new template path in ASP's internals (likely out of scope for the skill itself, but the skill should call it out). |
| **langgraph-fundamentals/SKILL.md** | REUSE | The state and node patterns transfer to voice — no change needed. Voice agents have state (conversation history, turn count, grounding facts) just like text agents. Keep as-is. |
| **langgraph-scaffold/SKILL.md** | ADAPT | Add deployment target option: "Is this agent going into a voice framework (LiveKit, Pipecat, Vapi)?" If yes, scaffolding should set up async patterns and `astream_events()` correctly for token-by-token TTS streaming. Document the LiveKit Agents + LangGraph pattern. Cost: one conditional branch + reference to the adapter pattern. |
| **langgraph-persistence/SKILL.md** | REUSE | Checkpointing transfers unchanged. Voice agents are still stateful and need durable session storage. Keep as-is. |
| **langgraph-human-in-the-loop/SKILL.md** | SKIP | Human-in-the-loop (approval gates via `interrupt()`) is a text/async pattern. In realtime voice, a human interrupt is a *call disconnect* or *explicit vocal command*, not a text approval. The mechanism is fundamentally different. However, the **salvageable part** is the checkpoint-and-resume discipline — voice sessions can also resume from checkpoints (e.g., client reconnection mid-call or call transfer to a queue). Reuse the checkpointing layer; discard the `interrupt()` pattern for voice. |
| **vercel-ai-sdk-scaffold/SKILL.md** | SKIP | TypeScript SDK is not designed for realtime audio. It is an HTTP-based tool-calling loop. A realtime voice agent in TS would need a different runtime (Node.js with a native audio library, or a WebSocket layer). The tool-calling pattern is reusable (e.g., tools can still call external APIs), but the streaming is token-streaming for UI latency, not audio frames. Don't use this scaffold for voice; the gap is architectural, not just a missing feature. Reusable salvage: the tool registry pattern (one file per tool, index.ts re-exports) and the settings/config factory pattern. Cost to adapt for voice: complete rewrite of the handler and agent.ts to use Node audio libs + WebSocket instead of `streamText`. |
| **google-adk.md** | ADAPT | Add a streaming row to the capabilities table with "Bidirectional streaming", "Gemini Live API via `run_live()`", and a cross-reference to `adk-dev-guide` section on realtime. Cost: three lines in the table + one short paragraph. This ref is accurate but incomplete. |
| **langgraph.md** | ADAPT | Clarify that the "Streaming" row refers to token-streaming over HTTP, not bidirectional audio. Add a note: "For realtime voice, compose with an external voice framework (LiveKit, Pipecat) that calls the LangGraph agent." Cost: one clarification paragraph in the streaming row. |
| **python.md, typescript.md** | SKIP | Stack bindings don't mention voice; they don't need to. They cover imports, async patterns, SDK usage — generic to the language, not voice-specific. Reusable salvage: async/await patterns (voice agents are deeply async), WebSocket client patterns (for bidirectional streaming), and structured logging imports. These are foundational, not domain-specific. |
| **ml6 pattern: 202 async polling** | SKIP | The polling-based job API is actively wrong for voice. It assumes latency is not a constraint and that long-running generation can be backgrounded. Voice reverses both. Do not port this pattern to voice. Reusable salvage: the job-tracking state model (ml6's PipelineState, ml6's models.py). You can track a voice call's state (name, attempt count, start time) the same way. But the API surface must flip from `202 + polling` to `101 Upgrade + WebSocket`. |
| **ml6 pattern: deterministic validator + repair** | ADAPT | The thesis (constraints are a code job) survives voice. But the repair loop cannot. In ml6, repair is a re-prompt after generation. In voice, you cannot re-prompt mid-utterance. Solution: shift to constraints-first prompting (ask the model to respect limits before generating, not after). Pre-generation validation of the prompt constraints themselves (e.g., "the vocabulary limit has N tokens; your response will be clipped to ≤N words"). Keep the validation dataclass (Violation, FieldConstraint). Discard the repair loop or move it off-call (pre-record a corrected version for re-use). Cost: rewrite generate.py's flow from generate-validate-repair to validate-generate-enforce. |
| **ml6 pattern: LLM provider port** | REUSE | The protocol (one method, schema in/dict out) is reusable. Extend it with a streaming variant: `async def stream_audio(...)`. Existing implementations (ml6's Anthropic adapter) can coexist with new streaming implementations (OpenAI Realtime, Gemini Live). Keep the interface contract; expand the method set. Cost: zero for the port; implementation cost per new provider. |
| **ml6 pattern: OTel spans** | ADAPT | The span contract (one span per LLM call, semconv v0.4 attributes) transfers to voice. Adapt the field set: add `latency_to_first_token_ms`, `turn_duration_ms`, `asr_confidence`, `interruption_count`. Keep `operation_name`, `model`, `input_tokens`, `output_tokens`, error tracking. The emission discipline ("never aggregate") survives. Cost: new field definitions + test coverage for voice-specific metrics. The existing ml6 span structure in obs.py is a good template. |

---

## Open Questions

1. **ADK streaming skill**: Is the streaming module (Gemini Live integration) actively used in GCP production voice agents, or is it an experimental surface? If experimental, should the template recommend it, or should it recommend composing with Pipecat/LiveKit instead?

2. **Checkpointer choice for voice**: A voice call over WebSocket is a long-lived process (§1 of agent-runtime.md). But it is not a "service" in the traditional sense — it is one connection per call. Should the checkpointer be process-local (speed) with periodic snapshots to external storage, or external from the start? ml6 doesn't face this (async jobs finish; no session resume). Does galactus have guidance?

3. **Multi-agent orchestration in voice**: LangGraph and ADK both support multi-agent systems (via subgraphs and sub_agents). In voice, can agents hand off mid-call (e.g., "Let me transfer you to an agent who speaks Spanish")? Or is multi-agent in voice only a pre-call routing decision? The frameworks support handoff; the voice transport may not.

4. **Tool latency budget in voice**: ml6's tools are synchronous calls that block generation. In voice, a tool call during a turn means the user hears silence. How long is too long? Is there a voice-specific tool latency budget (e.g., "tools must complete in <200ms or the agent should apologize and continue")? Neither LangGraph nor ADK docs mention this.

5. **ASR confidence and retry**: When ASR returns low-confidence transcription, should the voice framework ask "did you say [phrase]?" (re-prompt), or should the agent handle it (via tool calls or reasoning)? If the agent handles it, how should it signal uncertainty to the framework? There's no contract for this in either LangGraph or ADK.

6. **Galactus voice agent target shape**: Will the voice prototype be deployed as (A) a long-lived service (one agent, many concurrent calls via different threads/async tasks)? (B) One call = one process/function invocation (like ml6)? (C) Serverless with WebSocket upgrade (AWS Lambda + API Gateway, Google Cloud Functions + WebSocket)? The checkpointer, deployment, and observability patterns differ sharply.

---

## Sources

- [Pipecat: Build Real-Time Voice AI Agents in Minutes](https://www.blog.brightcoding.dev/2026/02/18/pipecat-build-real-time-voice-ai-agents-in-minutes)
- [Pipecat Documentation](https://docs.pipecat.ai/overview/introduction)
- [GitHub - pipecat-ai/pipecat: Open Source framework for voice agents](https://github.com/pipecat-ai/pipecat)
- [Build and Deploy LiveKit AI Voice Agents: The 2026 Playbook](https://www.forasoft.com/blog/article/livekit-ai-agents-guide)
- [LiveKit Agents: What They Are and How to Build One (2026)](https://www.cekura.ai/blogs/livekit-agents)
- [LiveKit voice agents](https://livekit.com/voice-agents)
- [Bidirectional streaming | Gemini Enterprise Agent Platform](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/bidirectional-streaming)
- [ADK Gemini Live AI Toolkit - Agent Development Kit](https://adk.dev/streaming/)
- [ADK Gemini Live API Toolkit: A Visual Guide](https://medium.com/google-cloud/adk-bidi-streaming-a-visual-guide-to-real-time-multimodal-ai-agent-development-62dd08c81399)
- [OpenAI Realtime API: Build a Voice Agent in 2026](https://www.open.cx/blog/openai-realtime-api-voice-agent-guide-2026)
- [Introducing gpt-realtime and Realtime API updates for production voice agents](https://openai.com/index/introducing-gpt-realtime/)
- [Realtime and audio | OpenAI API](https://developers.openai.com/api/docs/guides/realtime)
- [LangGraph Streaming Explained: How to Stream Agent Outputs in Real Time](https://langchain-tutorials.github.io/langgraph-streaming-explained-real-time/)
- [LangGraph for Voice AI Agents: Strengths, Limits, and Production Risks](https://buildingagenticai.com/blog/langgraph-for-voice-ai-agents/)
- [langgraph-voice-call-agent: Real-time voice AI agent over LiveKit](https://github.com/ahmad2b/langgraph-voice-call-agent)
- [Vapi Review 2026: The Main Caveat With Voice AI Agents](https://medium.com/@elena.voss/vapi-review-2026-the-main-caveat-with-voice-ai-agents-36bbc16a4983)
- [Voice AI agents in production 2026: LiveKit Agents, OpenAI Realtime, Pipecat, Vapi compared](https://www.reactify-solutions.com/articles/voice-ai-agents-production-2026)
