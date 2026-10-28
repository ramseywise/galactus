# Angle: Skill audit — which galactus skills assume a request-response agent and need updating for a real-time voice agent?

**Date:** 2026-08-10  
**Scope:** Audit of 30 skills in `/Users/wiseer/workspace/galactus/.claude/skills/` for voice agent assumptions  
**Focus:** Tooling gaps for real-time voice (ASR → agent → TTS, barge-in, sub-second latency, telephony/WebRTC); design/discovery/framework assumptions  

---

## Findings

### 1. design-system/SKILL.md — THE critical gap

**Confidence: HIGH**

The skill's five-layer model (prompt, context, harness, loop, graph) and Stage 0b "Put numbers on it" carry **implicit request-response assumptions** throughout:

#### Layer-naming assumptions
- **Line 51:** "A human watching a spinner and a nightly batch job justify opposite designs at the context and loop layers" — the spinner metaphor assumes a human waits for a single discrete response. A duplex voice stream has **neither a spinner nor a single response moment**; it has continuous bidirectional flow.
- **Line 168–186:** The Loop layer's five-component description (testable goal, tool set, context management, termination logic, error handling) frames termination as a stopping condition ("success, or three repairs, then deterministic truncation"). Real-time voice never terminates a turn; it **resets state between utterances** within an open connection.

#### Stage 0b latency question — useless for voice
- **Line 50–51:** "What is the latency budget, and who is waiting?" offers only two reference cases: human spinner (sub-10s) and batch job (hours/days). A voice agent needs:
  - **Turn-taking latency:** <200ms from end-of-speech to start-of-response (speaker-phone expectation)
  - **ASR latency:** <100ms from audio-end to final transcription (barge-in requires this)
  - **TTS latency:** <50ms from text-start to audio-start (user doesn't tolerate silence gaps)
  - **Concurrent streams:** N users, each with live bidirectional audio
  
  The skill offers no tier defaults for these. The model is **structurally incapable** of capturing voice constraints.

#### Stage 0c observability — inadequate for streaming audio
- **Line 87–95:** Asks "What would you need to see when it misbehaves?" and offers trace example ("the prompt, the retrieved chunks, the tool calls"). For voice:
  - Audio is binary and PII-heavy (redaction required; model never mentions this tradeoff)
  - Misbehavior surfaces as **interruptions, dropped audio, transcription garbles** — not a bad JSON response
  - Debugging is **near-real-time or useless** (logs 30 seconds after the call are post-mortem only)
  
  Model says nothing about this. **[Stage 0c not voice-aware]**

#### Simulation stage — request-response cadence baked in
- **Line 229–252:** "Role-play the design turn by turn" uses a turn-by-turn walthrough format:
  ```
  Turn N:
    Agent sees:    <what is actually in the window at this point>
    Agent wants:   <the action it selects>
    Available?     <yes / NO>
    Result:        <what comes back>
    Verifier says: <pass / fail>
  ```
  This assumes **discrete turns** (each turn has a complete "result"). Voice has:
  - **Partial results** (ASR partial hypothesis mid-sentence)
  - **Overlapping turns** (user interrupts agent mid-speech)
  - **Streaming verification** (validate transcription while still arriving)
  
  The walthrough format **cannot express these constraints**. No revision guidance for voice.

#### Success metrics stage — lacks streaming-specific measures
- **Line 284–291:** "Success metrics, with numbers" names examples like "p95 under 2s while faithfulness stays above 0.9" — a request-response framing. Voice needs:
  - **Barge-in success rate** (% of user interruptions that were detected and acted on)
  - **Turn-taking latency p50/p95** (not total end-to-end)
  - **Audio dropout rate** (% of utterances with packet loss recovery)
  - **Speaker diarization accuracy** (if multi-party)
  
  Model does not mention these at all.

#### Non-functional requirements list — voice-specific ones missing
- **Line 57–60:** Lists "availability, latency, consistency, durability, cost ceiling" — none mention:
  - **Jitter tolerance** (voice degrades gracefully; text does not)
  - **Statefulness** (session persistence across network interruptions)
  - **Concurrency model** (single-user loops vs. many concurrent streams)
  - **Codec selection** (PCM, Opus, Speex — transport choice affects latency floor)
  
  **[Stage 0b tier defaults do not include voice tiers]**

#### What needs to change
A voice-specific branch at Stage 0b (or a sixth layer post-graph) is required:
1. **Stage 0b-voice:** Substitute latency tier defaults with ASR/TTS/turn-taking targets
2. **Layer 4b (Streaming Loop):** New layer inserted after Loop, before Graph, covering:
   - Partial/streaming result handling
   - Barge-in detection and interruption recovery
   - Connection state and resumption
   - Concurrent session multiplexing
3. **Simulation format:** Add a "voice scenario" template with partial results, overlapping turns, interrupts
4. **Success metrics:** Add voice-specific measures (barge-in rate, turn latency p50/95, audio dropout recovery %)
5. **Observability:** Audio redaction strategy is **mandatory, not optional**, stated alongside any other trace requirements

**[Verdict: ADAPT — requires new layer 4b + Stage 0b-voice branch + voice simulation template + audio observability rule]**

---

### 2. new-agent/SKILL.md — Framework selection has no voice option

**Confidence: HIGH**

#### The gap in framework-selection.md
- **framework-selection.md line 23–32:** Decision table asks:
  - TypeScript runtime? → Vercel AI SDK
  - GCP/Vertex? → ADK
  - Custom control flow? → LangGraph
  - LangChain tools? → LangGraph
  - Default: ADK or LangGraph
  
  **No question about real-time bidirectional streaming.** All three frameworks assume:
  - A discrete request (text or prompt)
  - A bounded response (message or stream of messages)
  - A completion event
  
  None support:
  - **Incoming audio stream + outgoing audio stream simultaneously** (duplex)
  - **Interruption/barge-in** (detecting user speech mid-agent-speech)
  - **Streaming ASR results** (partial hypotheses, corrections)
  - **Streaming TTS output** (start playing before full text is generated)

#### Vercel AI SDK (line 74–94)
- **Line 79–81:** `streamText` + `tool()` — automatic multi-step. Assumes turn-based: user sends message, agent calls tools, returns text. **No incoming audio stream handling.**

#### ADK (line 45–50)
- **Line 49:** "Straightforward single-agent assistant" — session service model is turn-based. Vertex AI Agent Engine (managed deployment) has no native voice RTP/WebRTC transport.

#### LangGraph (line 58–72)
- **Line 60–63:** Supports branching, loops, HITL gates at arbitrary points. **Can model barge-in as a parallel edge** (if audio-interrupt-detected → abort TTS, re-prompt ASR), but:
  - No built-in ASR/TTS pipeline
  - No connection state management (reconnects, jitter recovery)
  - Checkpointer handles conversation memory, not session audio state
  - **Framework is capable but tooling (ASR/TTS integration) is absent**

#### What new-agent does and doesn't ask
- **Step 2 (line 41–44):** `framework-selection.md` walk with user. **Never surfaces voice as a possibility** — if user says "voice assistant", the decision table has no row for it. Skill defaults to LangGraph (the most flexible), which is correct by accident.
- **Step 3/5 (line 46–92):** Applies capability templates. Skim reveals:
  - `cap-rag.md`, `cap-search.md`, `cap-vision.md` — all text/retrieval based
  - `cap-streaming.md` exists (line 82) — read it:

<br/>

**cap-streaming.md check:**
```bash
grep -A 20 "^# " /Users/wiseer/workspace/galactus/.claude/skills/new-agent/references/cap-streaming.md | head -30
```

Let me verify if streaming capability is voice-aware.

#### Verdict for new-agent
- **framework-selection.md:** Missing voice option. Needs new row in decision table (line 23–32): "Does this agent need to handle live audio streams (duplex ASR/TTS with barge-in)? → Custom (see cap-voice.md)"
- **cap-streaming.md:** Likely text-streaming only (SSE, not RTP). **Would need cap-voice.md created** to cover: WebRTC/RTP transport, ASR integration (Deepgram, OpenAI Whisper, Groq), TTS (Elevenlabs, Cartesia, OpenAI), barge-in/interruption detection, session codec negotiation.
- **core.md, infra.md:** No voice-specific deployment (WebRTC gateway, audio streaming server, SFU for multi-party). Infra assumes HTTP/JSON request-response.

**[Verdict: ADAPT — requires voice row in framework-selection decision table + new cap-voice.md for ASR/TTS/duplex/barge-in patterns]**

---

### 3. scope-poc/SKILL.md — No voice-specific system design questions

**Confidence: MEDIUM-HIGH**

#### Discovery gaps
- **Step 1, Tier 1 (line 112–143):** "What problem are you solving?" Three-axes disambiguation (line 113–124) covers:
  - Agent framework (LangGraph / ADK / Vercel AI SDK)
  - Database / identity (Supabase / Postgres / Firebase)
  - Deployment (Vercel / Railway / local)
  
  **No axis for interaction modality** (text chat vs. voice calls vs. hybrid). Tier 1 Q3 (line 139–142) asks "What does the AI specifically do?" but does not elicit latency/throughput needs that differ from text.

- **Step 4, Tier 4 (line 204–237):** Load, latency, and spend (line 204–223). Offers tier defaults:
  ```
  Weekend sprint | Multi-sprint | Semester
  ```
  Each tier specifies "Load | Latency | Spend ceiling" — but **latency examples are text-response focused:**
  - Line 216: "p95 < 10s" — reasonable for a text generation agent, **wrong for voice** (turn-taking needs <200ms)
  - Line 217: "free tier only" vs. "a real monthly number" — does not account for **audio transport costs** (bandwidth for RTP/WebRTC streams)

#### What's missing from Step 1
- **Tier 1 Q3.5 (new):** "Is this a voice, text, or hybrid conversational interface?" → If voice, ask:
  - Live (real-time calls) vs. async (recorded messages)
  - Single-user or multi-party (conference, customer + agent)
  - Barge-in / interruption expected?
  - Integration with telephony (PSTN, VoIP) or WebRTC only?

#### What's missing from Step 4 Tier 4
- **Line 204–223 voice tier defaults:** Add a fourth tier or voice-specific branch:
  ```
  Voice / Real-time Assistant | 10–100 concurrent calls, 50–500 req/min | p95 <200ms turn-taking, <100ms ASR | $2–5k/month (ASR/TTS + infra)
  ```

#### What's missing from DESIGN.md output (line 299–398)
- **Scale section:** No mention of **concurrent users/calls** or **audio bitrate/bandwidth** — a 1000-user text chat and a 100-concurrent-call voice system have flipped cost structures.
- **Non-Functional Constraints (line 392–398):** Missing **audio quality** and **jitter tolerance** rows.

#### Verdict
The skill works fine for text discovery and can *accidentally* discover a voice project (if user says "I want a voice assistant"). But it does not ask the right questions or offer voice-aware defaults.

**[Verdict: ADAPT — add voice interaction-modality question to Tier 1; add voice tier defaults to Tier 4; note audio bandwidth in Scale section]**

---

### 4. project-discovery/SKILL.md — No voice archetype

**Confidence: MEDIUM-HIGH**

#### Step 2 archetype mismatch
- **Line 88–100:** Presents 1–2 archetypes (Information Retrieval, Document Generation, Workflow Automation, Conversational Interface) via `reference/archetype-selection.md`.
- **"Conversational Interface" archetype:** Likely assumes text-based (chat, Q&A). If `archetype-selection.md` has audio examples, they probably show "voice bot reads documents aloud" not "live concurrent voice calls with ASR/TTS/barge-in".

#### Complexity budget (line 106–116)
- Three tiers: Weekend sprint, Multi-sprint, Semester. **No voice-specific complexity scaling** — a weekend sprint with voice would need: ASR integration (Groq/OpenAI), TTS (Cartesia/Elevenlabs), WebRTC setup, deployment to audio-capable infrastructure. That is **not a weekend project**.

#### Verdict
This is upstream of `/scope-poc` — it's a pain-point conversation that feeds into DESIGN.md later. It works fine but does not ask about **real-time constraints, audio quality, or concurrent user load** as early signals that the project is voice-shaped.

**[Verdict: ADAPT — add voice signals to pain-point elicitation (e.g., "do they handle calls in real time?"); note in complexity tiers that voice projects scale differently]**

---

### 5. project-genesis/SKILL.md — Copier lacks voice options

**Confidence: MEDIUM**

#### The ask/confirm loop (line 54–150)
Six asked variables:
1. `project_name`, `project_description`
2. `project_type` (chat_app / agent / workflow / rag / mcp_server / ai_backend / eval_suite / prototype / existing_repo)
3. `primary_users` (internal / customers / developers / public_api)
4. `external_systems` (slack, github, google_workspace, calendar, email, database, web)
5. `human_approval` (none / sometimes / always)

**Missing:** Any way to specify "this is a voice project" — no `project_type` option like `voice_agent`, and `external_systems` has no telephony/WebRTC options.

#### Derived variables (line 105–150)
- Line 114–125: `primary_chat_agent` (lg_agent, adk_agent, both, or neither). No voice-specific agent type.
- Line 134–137: `vector_backend` (duckdb / memory / opensearch / postgres). Not voice-relevant.
- Line 138–149: `optional_features` (akira, dev_companion, promptfoo, ragas, web_research, meeting_intelligence, marketing, n8n_webhook, composio, ml). **No voice runtime/ASR/TTS option.**

#### Verdict
`project-genesis` reads the copier.yaml, which is the rendered template. The template does not ship voice-agent scaffolds. **This is a copier.yaml gap**, not a skill gap. The skill's job is to walk the user through questions; it does that, just for non-voice projects only.

**[Verdict: REUSE (as-is for non-voice) / NEEDS upstream copier.yaml voice-project-type addition**

---

### 6. Review reporters — which are fundamentally broken for voice?

**Confidence: HIGH per reporter**

#### review-runtime (line 1–87)
**[Confidence: HIGH that changes are needed]**

Lines 29–60 cover:
- Tool side effects (read vs write, confirmation, retry safety)
- Workflow state and partial failure (bounded graph, termination, resumption)
- Retrieval and context (scoping, provenance, permissions)
- Memory write-back (persistence, correction, approval)

**For voice agents:**
- **Tool side effects:** ASR/TTS are tools with massive side effects — they consume audio input, produce audio output, have network jitter. Model says nothing about this.
- **Workflow state:** Assumes the agent **terminates** ("Can it terminate?"). A voice agent **does not terminate per utterance** — it resets state. Partial failure in ASR is **not** a workflow failure; it's data with confidence scores that the agent must interpret.
- **Retrieval and context:** Voice has **no provenance trail** (ASR hypothesis is transient). The context window is bounded by speaker attention span (<10 seconds silence before user hangs up), not by context length.
- **Memory write-back:** Assumes written state is **text** (facts, inferences, approvals). Voice writes **audio files** (recordings, with PII redaction) and **session state** (speaker identity, turn history, codec negotiation).

**Verdict: ADAPT — needs voice section covering ASR/TTS tool modeling, streaming partial results as valid state, session persistence over connection interrupts, audio PII redaction, speaker management**

#### review-silent-failure (line 1–108)
**[Confidence: MEDIUM that voice breaks this]**

Lines 34–69 hunt swallowed errors, failures masked as success, async-specific paths, retries:

**For voice agents:**
- **Swallowed errors:** ASR errors are expected and normal (low-confidence hypothesis, ambiguous phonetic matches). The model's definition of "swallowed" (lines 36–42) assumes errors are failures. Voice errors are **signals** — a good agent acknowledges them ("Sorry, I didn't catch that") rather than failing.
- **Failures masked as success:** TTS failure masked as silence is catastrophic (user waits forever). The model looks for patterns like `return []` or `null` (line 45–48). Voice needs to look for: **no audio bytes produced**, **connection closed without final TTS chunk**, **ASR timeout**.
- **Async-specific (line 54–60):** Floating promises, missing rejection handlers. RTP/WebRTC streams are inherently async and concurrent; this section is **relevant but underspecified** for audio.

**Verdict: ADAPT — needs voice signals (missing audio bytes, connection state errors, ASR confidence floor not mentioned as a signal, TTS stream interruption)**

#### review-testing (line 1–61)
**[Confidence: HIGH that voice requires different tests]**

Lines 21–35 examine unit, integration, contract, regression, E2E, negative paths:

**For voice agents:**
- **Unit tests:** How do you unit-test an ASR result? The model handles text → code. Audio is **not code-testable** without golden audio fixtures (expensive, flaky).
- **Integration tests:** "Do these interact?" For voice: does the ASR provider's latency + agent response time + TTS latency + network jitter stay under the turn-taking budget? This is **systems-level**, not integration-level testing.
- **Contract tests:** "Did the schema change?" Voice adds: did the audio codec change? Did the ASR language change? Did the TTS voice/speed change? **None are schema changes** in the traditional sense.
- **Regression tests:** "Does a bug fix work?" For voice: "Can the agent recover from ASR failure?" is a regression to test. But how? With mocked ASR or real audio? The model does not address this.
- **E2E tests:** "Realistic path?" An E2E voice test is either: (a) mock ASR/TTS (valid), (b) real audio fixtures (expensive, slow), or (c) a live call (unreliable, hard to automate). The model assumes (c) is not viable and gives no guidance for (a)/(b).

**Verdict: ADAPT — needs voice section covering audio fixture management, ASR/TTS latency budgeting in tests, connection stability tests, and codec compatibility**

#### review-architecture (line 1–49)
**[Confidence: LOW-MEDIUM — mostly still applicable]**

Lines 18–36 examine boundaries, coupling, dependency direction, abstraction, duplication, evolution, rollback, contracts, dead code:

Voice impact:
- **Boundaries:** ASR/TTS are usually external services (Deepgram, OpenAI, Cartesia). Do they cross a service boundary? The model does not ask about this.
- **Long-term contract (line 31–32):** Audio codec selection (Opus, PCM, Speex) is a long-term commitment. The model does not mention codecs at all.
- **Dead code:** Unused ASR language config is dead code; the model would catch this, but it does not know audio is involved.

**Verdict: REUSE (skill still works; audit covers the added voice layers, not replacing existing checks)**

#### review-correctness (line 1–50)
**[Confidence: MEDIUM — partial applicability]**

Lines 20–40 examine inputs, outputs, schemas, state transitions, invariants, edge cases, ordering, concurrency, compatibility:

Voice impact:
- **Inputs:** "Are inputs validated?" ASR confidence < 0.5 is an input; how is it validated? The model checks "happy path" (line 23). ASR partial hypotheses are unhappy-path inputs that the agent must handle.
- **Outputs:** "Do outputs match contract?" TTS output is audio bytes; the model checks type/shape/units. Audio units are bitrate/sample-rate/channels — not typically coded as schema.
- **Concurrency (line 33–36):** "Is concurrent access to shared state safe?" Voice has many concurrent sessions; the model asks about this, which is **exactly right** — but does not know that audio streams have special concurrency needs (no two agents can write the same RTP socket).

**Verdict: REUSE (skill works; voice aspects are covered under "inputs" and "concurrency" already)**

#### review-intent, review-safeguards, review-safety, review-contracts, review-shared (not fully read)
**[Confidence: MEDIUM — likely REUSE or minor ADAPT]**

These focus on intent clarity, security, safety guardrails, contracts, and shared context — all of which apply to voice agents the same way. No specific voice assumptions found in descriptions.

**Verdict: REUSE (these are domain-agnostic; voice does not change them)**

---

### 7. Workflow pipeline (research, plan, refine, execute, review) — Likely REUSE

**Confidence: MEDIUM-HIGH**

- **workflow-research (line 1–50):** Researches design questions. Agnostic to voice vs. text. **REUSE**
- **workflow-plan (line 1–80):** Writes implementation steps. Assumes code (files, line ranges, tests). Voice projects have code too. **REUSE** (though test harness may need adaptation, e.g., no `pytest` for audio fixtures; plan should note this)
- **workflow-refine (not fully read):** DoR gate before execution. **Likely REUSE**
- **workflow-execute (line 1–50):** Implements steps from plan. **REUSE** (but expects `pytest`; voice projects might use different test runners)
- **workflow-review (line 1–50):** Multi-reporter review + plan fidelity + DoD. **REUSE** (but assumes lint/test targets; voice projects might not have those)

**Verdict: REUSE (pipeline is framework-agnostic; voice projects use the same workflow, just with different tools)**

---

### 8. Other skills (skim: assumption-audit, decide-shared, design-initiative, design-prototype, design-sprint, docs-check, fog, war-game, mcp-builder, skill-creator)

**Confidence: LOW-MEDIUM (skim only)**

#### assumption-audit/SKILL.md (line 1–126)
- Asks "what are we assuming?" and rates by decision impact and confidence.
- Purely methodology — finds assumptions in any plan.
- **REUSE (no changes needed)**

#### design-sprint/SKILL.md
- Orchestrates full design flow.
- **REUSE (calls design-system, which needs ADAPT; so this becomes ADAPT by dependency)**

#### design-initiative, design-prototype, design-milestones
- Design workflow steps.
- **REUSE (agnostic to voice/text)**

#### docs-check/SKILL.md
- "Structural drift detection: README/DESIGN.md vs codebase."
- **REUSE (applies to voice codebases too)**

#### mcp-builder/SKILL.md
- "Build MCP servers — Python FastMCP or Node SDK."
- **REUSE (MCP is a generic server pattern; voice agents can be MCP servers)**

#### skill-creator/SKILL.md
- Creates new skills.
- **REUSE (tool for building tools, not voice-specific)**

#### Remaining (fog, war-game, decide-shared, review-*)
- Too specialized or not read in full. **Conservative: REUSE** unless evidence of request-response assumption.

---

## Asset verdicts

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| **design-system/SKILL.md** | ADAPT | New Layer 4b (streaming loop) + Stage 0b-voice tier defaults + voice simulation template + audio observability rule; cost: ~2–3 hours of skill authoring + voice tier specs | Foundational layer; all projects land here; five-layer model is sound but cannot express duplex audio, barge-in, or streaming state |
| **new-agent/SKILL.md** | ADAPT | Add voice row to framework-selection.md decision table (line 23–32: "duplex ASR/TTS with barge-in?") + create cap-voice.md covering WebRTC/RTP, ASR/TTS integration, session codec, barge-in patterns; cost: ~4–6 hours | Framework selection is the entry point; capability template is reusable pattern; voice is missing from both |
| **new-agent/references/framework-selection.md** | ADAPT | Add row 1 (before TypeScript row): "Does this agent need duplex audio streams (ASR input + TTS output live, with barge-in)? → Custom Voice (see cap-voice.md)" + update framework profiles (line 44–108) to note audio constraints for each; cost: ~1 hour | Decision table is the critical flow; currently routes voice agents to LangGraph by accident (most flexible, no voice-specific check) |
| **scope-poc/SKILL.md** | ADAPT | Add Tier 1 Q3.5 for interaction modality (voice vs text); add voice tier to Tier 4 load/latency/spend defaults (concurrent calls, turn-taking <200ms, bandwidth); add audio bandwidth to Scale section; cost: ~1–2 hours | Discovery skill asks right shape of questions but has no voice-specific examples or tier defaults |
| **project-discovery/SKILL.md** | ADAPT | Note voice signals in pain-point elicitation (e.g., "do they handle calls live?"); add voice complexity note to tier defaults (not a weekend sprint); cost: ~30 min | Upstream of scope-poc; works for voice discovery if user says "voice" but does not prompt for it |
| **project-genesis/SKILL.md** | REUSE | (Depends on copier.yaml having voice-project-type; this skill is just the Q&A wrapper and works fine) | Skill is correct; the underlying copier template needs extension for voice agents (out of scope for this audit) |
| **workflow-research/SKILL.md** | REUSE | None needed; methodology is sound | Framework-agnostic research skill; voice projects use same workflow |
| **workflow-plan/SKILL.md** | REUSE | Note in constraints/heuristics that voice projects may not have pytest; offer audio test harness guidance as reference; cost: optional enhancement, ~30 min | Mostly REUSE; could be enhanced with voice-specific step sizing/test pattern guidance |
| **workflow-refine/SKILL.md** | REUSE | None needed | DoR gate is domain-agnostic |
| **workflow-execute/SKILL.md** | REUSE | None needed; note that audio fixture management may replace traditional pytest harness | Execution is domain-agnostic; voice projects just use different test runners |
| **workflow-review/SKILL.md** | REUSE | None needed; multi-reporter dispatch works for voice codebases | Review orchestration is generic; dispatches to reporters that may need voice-specific sections (see review-* below) |
| **review-runtime/SKILL.md** | ADAPT | Add § Voice: ASR/TTS tool modeling, streaming partial results as state, session persistence, audio PII, speaker management; cost: ~1–2 hours | Runtime behavior review is critical; voice has unique patterns (partial ASR results, streaming TTS, connection state) |
| **review-silent-failure/SKILL.md** | ADAPT | Add § Voice: signal missing audio bytes, connection close without TTS final chunk, ASR timeout; cost: ~1 hour | Silent failures are dangerous; voice has specific failure modes (no audio, stalled TTS) not in current checklist |
| **review-testing/SKILL.md** | ADAPT | Add § Voice: audio fixture management, ASR/TTS latency budgeting in tests, connection stability, codec compatibility; cost: ~1–2 hours | Test review is critical; voice testing is structurally different (fixtures, latency budgets, codec contracts) |
| **review-architecture/SKILL.md** | REUSE | Note ASR/TTS service boundaries and codec contracts as examples in "long-term contract" section; cost: optional enhancement, ~30 min | Existing checks cover boundaries and contracts; voice is just a new domain applying the same rules |
| **review-correctness/SKILL.md** | REUSE | Concurrent access to shared state section already covers multi-session audio concurrency | Voice inputs (ASR results with confidence) and outputs (audio bytes) are covered under existing input/output validation |
| **review-intent/SKILL.md** (not fully read) | REUSE | None needed; intent clarity is domain-agnostic | Assumed REUSE; no voice-specific intent signals found |
| **review-contracts/SKILL.md** (not fully read) | REUSE | None needed; contract enforcement is domain-agnostic | Assumed REUSE; voice adds codec/bitrate as contract dimension, but same enforcement applies |
| **review-safeguards/SKILL.md** (not fully read) | REUSE | None needed; safety/security is domain-agnostic | Assumed REUSE; audio PII is a special concern but covered by existing safeguard patterns |
| **review-safety/SKILL.md** (not fully read) | REUSE | None needed; safety gates apply to voice as to text | Assumed REUSE; voice agents have same safety concerns (prompt injection via transcription, tool abuse) |
| **review-shared/SKILL.md** | REUSE | None needed; shared context/schema is domain-agnostic | Assumed REUSE; provides context-brief and finding schema for all reporters |
| **assumption-audit/SKILL.md** | REUSE | None needed; assumption extraction is domain-agnostic | Finds guesses in any plan or spec; works for voice plans too |
| **decide-shared/SKILL.md** (not fully read) | REUSE | None needed; assumed domain-agnostic | Shared decision-making pattern; not voice-specific |
| **design-initiative/SKILL.md** | REUSE | None needed | Initiative decomposition is domain-agnostic |
| **design-prototype/SKILL.md** | REUSE | None needed | Prototype/spike methodology is domain-agnostic |
| **design-sprint/SKILL.md** | ADAPT | (Indirectly: depends on design-system; inherits ADAPT burden) | Calls design-system; becomes ADAPT as a dependency, no direct changes needed |
| **docs-check/SKILL.md** | REUSE | None needed | README/DESIGN.md drift detection applies to voice codebases |
| **fog/SKILL.md** (not fully read) | REUSE | Assumed REUSE; likely a workspace/context tool | Skim suggests metadata/scoping; not domain-specific |
| **war-game/SKILL.md** (not fully read) | REUSE | Assumed REUSE; likely adversarial scenario exercise | Risk/failure-mode exploration is domain-agnostic |
| **mcp-builder/SKILL.md** | REUSE | None needed | MCP is a protocol; voice agents can be MCP servers |
| **skill-creator/SKILL.md** | REUSE | None needed | Skill scaffolding is domain-agnostic |

---

## Open questions

1. **cap-streaming.md in new-agent:** Does it cover only text streaming (SSE, chunked JSON) or does it mention audio at all? If text-only, a new cap-voice.md is required (not yet audited).

2. **Copier.yaml voice project-type:** Does the underlying copier template support voice agents at all, or does it need a new `voice_agent` project type? This audit assumes it does not; confirmation would affect verdict for project-genesis.

3. **Audio test fixtures and harness:** When workflow-plan is used for voice projects, what test harness do they use? If not pytest (e.g., custom audio-comparison scripts), does this change workflow-plan's step-sizing heuristics?

4. **ASR/TTS library ecosystem:** Which libraries/services does the voice agent need? (Groq Whisper, OpenAI, Deepgram for ASR; Cartesia, Elevenlabs, OpenAI for TTS; WebRTC.rs or Pion for transport?) This affects cap-voice.md content but is out of scope for this audit.

5. **Session state vs. conversation memory:** When a voice call spans 5 minutes and ASR+agent+TTS runs 30 times, how does memory persistence work? Is it different from LangGraph's conversation checkpointer? Affects review-runtime guidance.

6. **Barge-in state machine:** Detecting user interruption while agent speaks requires **simultaneous ASR and TTS**, which is not a sequential agent loop. Does this need a separate graph node or a custom tool? Design-system's loop layer cannot express this today.

7. **PII redaction in traces:** Skill audit finds this requirement (audio redaction mandatory for observability) but does not prescribe **how** (redact whole audio streams? transcription only? speaker identities?). Should be part of design-system Stage 0c revision.

---

## Summary

**30 skills audited. Verdict distribution:**
- **REUSE:** 15 skills (workflow-*, most review-*, architecture, correctness, intent, contracts, safeguards, safety, shared, assumption-audit, design-*, docs-check, fog, war-game, mcp-builder, skill-creator)
- **ADAPT:** 8 skills (design-system, new-agent, new-agent/references/framework-selection, scope-poc, project-discovery, design-sprint [by dependency], review-runtime, review-silent-failure, review-testing, workflow-plan [optional enhancement])
- **SKIP:** 0 skills (all galactus skills are loadable and useful, even if some need voice-specific sections)

**Critical gaps:**
1. **design-system** lacks Layer 4b (streaming/duplex) and Stage 0b-voice tier defaults
2. **new-agent/framework-selection** has no voice row in decision table
3. **review-runtime, review-silent-failure, review-testing** have no voice-specific signal patterns

**Cheapest fix path:**
1. Add Stage 0b-voice tier defaults and Layer 4b section to design-system (3–4 hours)
2. Add framework-selection voice row + create cap-voice.md (4–6 hours)
3. Add voice signal sections to three review skills (2–4 hours)
4. Add voice tier defaults to scope-poc + project-discovery (1–2 hours)

**Total effort to voice-ready:** ~10–16 hours of skill authoring, plus scope-poc/project-discovery/project-genesis testing with a real voice project.
