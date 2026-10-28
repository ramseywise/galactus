# Voice capability parity — real-time voice readiness across galactus/.claude

Status: EXECUTED
Review: pending
Date: 2026-08-10
Prefix: GUA

## Context

The doctolib case study is a **real-time voice assistant** for medical appointment
scheduling: live speech-in/speech-out, barge-in, turn-taking, sub-second latency, over
telephony. It would be the third case study alongside [`ml6/`](../../../ml6) (generation
under a contract) and [`enam/`](../../../enam/README.md) (prediction under uncertainty).

Neither the galactus spec set nor its skill pipeline is ready for it. This document
records what exists, what breaks, and the recommended strategy — so the capability is
built in the same shape as the existing agentic tooling rather than improvised.

This is the sibling of [`2026-08-10-ml-capability-parity.md`](2026-08-10-ml-capability-parity.md),
written the same day for the enam/ML gap, and it inherits that document's governing
principle: *build the capability in the shape of the existing tooling — same pipeline
spine, same enforcement ladder, same "reporters catch silent failures" pattern. Do not
build a parallel process.*

**Scope decision (operator, this session):** updates land in `galactus/.claude` only.
Galactus is the self-contained showcase; upstream re-vendoring to `~/.claude` happens
later, once the shape is proven. Per the vendoring exception in
[`CLAUDE.md`](../../../CLAUDE.md), canon remains `~/.claude/` and generic fixes are
made there first — so anything in this plan that turns out to be generic rather than
voice-specific is flagged as an upstream candidate rather than silently forked.

---

## Research

### Summary

The gap is **real and structural, not incremental**: zero substantive voice/realtime
coverage across all 13 galactus specs, the 8 template agent-reference skills, and the 25
global refs. But it is a **loop-shape gap, not a missing-topic gap** — every spec and the
`design-system` five-layer model assume a request → response → done turn, and a duplex
audio stream breaks that assumption at the *loop* layer, which is why eight specs need
amendment rather than one new spec sitting beside them.

The recommended shape is **one new spec (`agent-voice.md`, ~150–200 lines) plus ~100–150
lines of surgical amendments across eight existing specs**, and **8 of 30 skills adapted
(0 skipped)**. The pipeline spine transfers unchanged — all five `workflow-*` skills are
REUSE — which independently confirms the ml-capability-parity finding that the spine is
domain-neutral and the leaves are not.

Two findings materially change the design and are load-bearing for the plan: the target
architecture is **cascaded (ASR→LLM→TTS), not speech-to-speech**, for audit and
tool-reliability reasons; and **Google ADK already ships the streaming capability the
tooling omits** (`run_live()` / Gemini Live), making the largest single lever a
documentation fix rather than a build.

### Scope

**Investigated** (5 parallel scouts, reports in [`.claude/docs/research/`](../research/)):

1. Spec gap — which of the 13 `.claude/specs/agent-*.md` break under a duplex loop, and
   what a new spec must own. → [`_spec-gap.md`](../research/2026-08-10_voice-tooling_spec-gap.md)
2. Framework patterns — reusable code patterns in `~/.claude/refs` and
   `ai-project-template/template/.agents/skills`. → [`_framework-patterns.md`](../research/2026-08-10_voice-tooling_framework-patterns.md)
3. Skill audit — all 30 galactus skills assessed. → [`_skill-audit.md`](../research/2026-08-10_voice-tooling_skill-audit.md)
4. Regulated domain — GDPR/health-data/consent constraints and where they belong. → [`_regulated-domain.md`](../research/2026-08-10_voice-tooling_regulated-domain.md)
5. Realtime SOTA — external state of the art, to keep the new spec substantive rather
   than hand-waving. → [`_realtime-sota.md`](../research/2026-08-10_voice-tooling_realtime-sota.md)

**Explicitly out of scope:**

- **Designing the doctolib application itself.** Every scout was instructed to research
  the tooling gap, not the app. Domain facts appear here only where they constrain what a
  spec must say.
- **Changes to `~/.claude/` or `ai-project-template/`.** Deferred by operator decision;
  upstream candidates are flagged, not made.
- **`ml6/`** — left alone per [`CLAUDE.md`](../../../CLAUDE.md); read for patterns only.
- **Whether doctolib is built at all.** This scopes the tooling that would make it
  buildable.

### Findings

#### Finding 1 — the gap is total, and it is a loop-shape gap [Confidence: High]

Grepping `voice|realtime|speech|asr|tts|barge-in|telephon` across `galactus/.claude`,
`ai-project-template/template/.agents`, `ai-project-template/template/.claude`,
`~/.claude/refs`, and `~/.claude/skills` returns **only incidental hits** — skill-creator
examples, akira eval scaffolds, an inbox-clean reference. Nothing substantive.

But the absence is not evenly distributed, and that is the useful part. The specs are not
missing *a topic*; they each encode an assumption that a duplex stream violates. Scout 1
documented ten, each with a citation:

| Spec | Assumption that breaks | Cite |
|---|---|---|
| agent-architecture | "A turn ends when the model emits a **stop_reason** that is not a tool call" | `agent-architecture.md:86` |
| agent-runtime | Stateless execution; "No background tasks" | `agent-runtime.md:68` |
| agent-reliability | Idempotency key is `run_id + step_id + tool_name` | `agent-reliability.md:110` |
| agent-context | 5-minute cache TTL on a byte-identical prefix | `agent-context.md:143` |
| agent-observability | Tree-shaped span nesting, one root per request | `agent-observability.md:33` |
| agent-eval | "Reset the environment between trials" | `agent-eval.md:52` |
| agent-memory | "Checkpoint after each plan step" | `agent-memory.md:54` |
| agent-safety | "Layer 1: Pre-input — sanitize, detect injection, redact PII" | `agent-safety.md:18` |

Read together these are one assumption stated eight ways: **a turn is a discrete,
replayable, boundable unit of work.** In a duplex stream a turn has no clean start (the
user may begin speaking before the agent stops), no clean end (barge-in truncates it
mid-utterance), and no replayable state (the audio that produced it is stochastic through
VAD and ASR).

This is why the fix is not one spec. A single `agent-voice.md` beside the others would
leave `agent-reliability` still telling an implementer to retry a turn, and
`agent-observability` still telling them to nest one span tree per request. The
amendments are the load-bearing part; the new spec is the place to put what has no home.

#### Finding 2 — cascaded, not speech-to-speech, and that inverts the naive expectation [Confidence: High]

The intuitive read of "sub-second latency voice agent" is *use a realtime speech-to-speech
model*. For medical scheduling that is the wrong call, and the spec must say so
explicitly or every implementer will reach for the Realtime API by default.

| | Cascaded (ASR→LLM→TTS) | Speech-to-speech |
|---|---|---|
| Latency | 400–600ms optimized | 200–350ms |
| Cost | baseline | **~10×** |
| Audit trail | Text at every boundary | None — no deterministic transcript |
| Tool calling | Structured, predictable | Less reliable |
| Prosody/emotion | Lost | Preserved |

For appointment booking — high tool-use, auditable, deterministic, and holding
special-category health data — the text boundary *is* the product requirement. The 150–200ms
latency saving buys nothing that offsets losing the transcript. [Confidence: High]

Two corollaries the spec must carry:

- **LLM time-to-first-token dominates the budget** (400–800ms of an ~800–1500ms total;
  transport is 20–50ms and negligible). Architecture cannot optimise around it — *model
  tier is the latency knob*. A voice agent may have to accept Haiku-tier reasoning to hit
  its target, which is a design-time constraint on the whole graph, not a deployment
  tuning detail. [Confidence: High]
- **Telephony (SIP/PSTN), not WebRTC**, for the medical case: inbound on a published
  number, SIP REFER handoff to a human, DTMF fallback, no tech burden on elderly or
  low-connectivity patients. Cost: 8kHz narrowband degrades ASR by 5–10% WER against
  wideband-trained models. [Confidence: High]

#### Finding 3 — ADK already ships the capability the tooling omits [Confidence: High]

The single highest-leverage finding. Google ADK has **first-class bidirectional
streaming** — `run_live()`, Gemini Live API, WebSocket transport, native VAD and
interruption, session and state management. The template's own ADK skills
(`adk-dev-guide/SKILL.md`, `adk-scaffold/SKILL.md`) **do not mention it at all**.

This is a documentation gap masquerading as a capability gap, and it has a visible
consequence: `framework-selection/SKILL.md:20-39` has no realtime branch, so a developer
answering its existing questions for a voice agent is **routed to LangGraph by accident**
— a framework that requires external plumbing (LiveKit or Pipecat) to do voice at all.
The decision tree is sound for request/response and silently wrong for duplex.

Supporting evidence in the refs: `~/.claude/refs/google-adk.md:21-32` has a capability
table with no streaming row; `~/.claude/refs/langgraph.md:56` has a "Streaming" row that
means token-streaming over HTTP, not bidirectional audio — a live ambiguity, since a
reader comparing the two refs would conclude LangGraph has the streaming story.

Both of those are **upstream files** (`~/.claude/refs/`), outside this plan's scope. They
are the clearest upstream candidates identified.

#### Finding 4 — 0 of 30 skills are SKIP; the spine holds [Confidence: High]

Scout 3 assessed every skill: **15 REUSE, 8 ADAPT, 0 SKIP** (7 assessed as not-applicable
rather than verdict-bearing). All five `workflow-*` pipeline skills are REUSE unchanged.

That zero is the finding. It independently reproduces the ml-capability-parity result
from the same day — the pipeline is *domain-neutral in its spine and agentic in every
leaf* — from a completely different domain. Two case studies (tabular ML, realtime voice)
now agree that the spine transfers and only the leaves need work, which is decent evidence
the spine is genuinely general rather than merely untested.

**`design-system` is the critical path.** Its Stage 0b — *"A human watching a spinner and
a nightly batch job justify opposite designs at the context and loop layers"* — offers
exactly two tiers, and a duplex voice stream is neither. The whole five-layer model
(prompt, context, harness, loop, graph) needs a **Layer 4b: Streaming Loop**, because in
voice the loop is not "call model until stop_reason" but two concurrent streams with a
cancellation protocol between them. Estimated ~2–3h. Everything downstream (`new-agent`,
`scope-poc`, the `review-*` reporters) depends on that model being right first.

Total skill work: **~10–16 hours**.

#### Finding 5 — regulated-domain constraints are legally-shaped, and the specs frame them as engineering problems [Confidence: High]

The specs are not silent on the underlying mechanics; they frame them as implementation
concerns without the legal frame that makes them binding.

| Spec | What it has | What is missing |
|---|---|---|
| agent-safety | PII masking, 13 types (`:291-308`) | No GDPR lawful-basis, consent, or special-category framing |
| agent-memory | Erasure as an implementation problem (`:194-196`) | Erasure as an Art. 17 legal obligation with a deadline |
| agent-observability | Compliance named as an audit-log purpose (`:187-197`) | No retention windows |
| agent-context | Regulatory boundaries **explicitly scoped out** (`:31-32`) | — (deliberate; see verdict table) |

The applicable constraints for a French medical-scheduling agent: **GDPR Art. 9**
(health data is special-category — consent or Art. 9(2)(h) healthcare-provision basis,
not legitimate interest), **Art. 17** (erasure, which for voice means the audio *and* the
transcript *and* the derived context), **HDS** (Hébergeur de Données de Santé — French
health-data hosting certification), **secret médical** (CSP L.1110-4), all-party recording
consent, and **EU AI Act Art. 50** (disclosure that the caller is speaking to an AI).

**Both relevant deadlines are already past** as of today (2026-08-10): HDS certification
(16 May 2026) and AI Act Art. 50 disclosure (2 August 2026). These are current
obligations, not roadmap items — the spec must state them as constraints on day one, not
as a future-compliance section. [Confidence: High]

One clean negative result worth recording: **Art. 22 (automated decision-making) does not
apply** to plain appointment scheduling. Booking a slot produces no legal or similarly
significant effect. It would apply to triage or eligibility decisions. Saying so
explicitly prevents an implementer over-engineering a human-review path the law does not
require here. [Confidence: Medium — depends on the agent staying scheduling-only]

`agent-uncertainty.md` is **REUSE, unmodified** — its abstention, asymmetric-cost, and
reversibility framing already covers "the ASR confidence is 0.6 on a drug name, escalate
to a human." No voice-specific amendment needed, which is a small vindication of the
cross-cutting spec design.

#### Finding 6 — ml6's patterns split cleanly into transfers and traps [Confidence: High]

| ml6 pattern | For voice |
|---|---|
| 202 + async polling API | **Actively wrong** — inverts the latency model; assumes generation can be backgrounded |
| Deterministic validator as binding constraint | **Survives, modified** — constraints-first, not generate-and-repair (you cannot re-prompt mid-utterance) |
| LLM provider port (`async def complete_structured`) | **Transfers** — needs a streaming sibling (`stream_audio(...) -> AsyncIterator[bytes]`) |
| `obs.py` span discipline | **Transfers** — add `latency_to_first_token`, `turn_duration_ms`, `asr_confidence` |

The thesis survives the domain change, which matters for the case-study narrative: ml6 is
*"counting characters is a job for code"*, enam is *"deciding who to call is not a model's
job"*, and the voice equivalent is that **turn-taking, confirmation of critical slots, and
barge-in cancellation are deterministic control problems** — the model supplies content,
code decides when it is allowed to speak. What does not survive is the *repair loop*: ml6
validates after generation and re-prompts up to 3×, which is unavailable when the audio is
already leaving the speaker.

#### Finding 7 — three genuine open problems the spec should flag rather than paper over [Confidence: High]

Recording these as unresolved is itself a spec requirement — a spec that invents numbers
here would be worse than one that says "tune this."

1. **Endpointing has no closed-form tuning.** Acoustic VAD alone is broken (85–90%);
   production blends acoustic + semantic (92–96%). Medical speech is a hard case
   specifically — users pause *inside* critical slots ("September… 15th", digit-by-digit
   phone numbers, "allergic to… penicillin and… sulfa"). Thresholds are domain- and
   accent-specific and must be tuned empirically.
2. **Barge-in state consistency has no standard.** When the user interrupts mid-sentence,
   the history must record what the agent *generated*, what the user actually *heard*
   (an offset into the utterance), and the interruption marker. Pipecat, LiveKit, and
   others each serialize this differently. The spec should require an explicit design and
   audit-trail test coverage, not prescribe a format.
3. **Real-time audio observability has no semantic convention.** OTel GenAI semconv
   (v1.37+, out of experimental in early 2026) covers LLM and tool spans; it does not
   cover audio frames, VAD confidence, TTS buffer state. Since
   `agent-observability.md` targets OTel GenAI semconv, the spec has to define a local
   extension (`vad.confidence`, `asr.confidence_score`, `asr.n_best_count`,
   `tts.latency_ms`, `audio.codec`) and mark it as local-until-standardized.

Related and load-bearing for `agent-eval`: **there is no end-to-end deterministic replay**
for voice. Identical audio yields identical ASR but different LLM output. Testing splits
into deterministic (tool success, infrastructure latency) and statistical (task-completion
rate, barge-in accuracy, user behaviour). And **WER does not predict task success** — 20%
WER on filler words books the appointment; 5% WER on the doctor's name does not.

### Asset verdicts

Consolidated from all five scouts. Where two scouts assessed the same asset, the row is
merged and both verdicts are reconciled in the Reason cell.

| Asset | Verdict | Salvageable at lower cost | Reason |
|---|---|---|---|
| **`agent-architecture.md`** | ADAPT | Five-layer model and spec-index role are unchanged; only the turn-boundary definition needs qualifying. | `:86` defines turn end by `stop_reason`. Duplex has no such boundary. Add a streaming-loop variant + index the new spec. ~20 lines. |
| **`agent-runtime.md`** | ADAPT | Stateless-request guidance stays correct for the tool-calling leaves. | `:68` asserts stateless, "No background tasks." A voice session *is* a long-lived background task with session-scoped state. ~25 lines. |
| **`agent-reliability.md`** | ADAPT | Retry taxonomy, backoff, and circuit-breaker guidance transfer unchanged. | `:110` idempotency key `run_id + step_id + tool_name` presumes a replayable turn. A truncated utterance cannot be retried; it must be *superseded*. ~30 lines. |
| **`agent-observability.md`** | ADAPT | Span discipline, attribute naming, and the OTel GenAI target all transfer. | Two scouts. Scout 1: `:33` tree-shaped nesting breaks — voice needs session→turn→{asr,llm,tts} with overlapping spans. Scout 4: `:187-197` names compliance as an audit purpose but sets no retention window. Merged: one amendment covering span shape + audio attribute extension + retention. ~40 lines. |
| **`agent-eval.md`** | ADAPT | The eval-harness structure and metric-definition discipline transfer. | `:52` "Reset the environment between trials" — audio is stochastic; no end-to-end deterministic replay. Needs the deterministic/statistical split and task-success-over-WER rule. ~30 lines. |
| **`agent-memory.md`** | ADAPT | Checkpoint/restore machinery and the memory-tier taxonomy transfer. | Two scouts. Scout 1: `:54` "Checkpoint after each plan step" has no analogue mid-utterance. Scout 4: `:194-196` frames erasure as implementation, not Art. 17 obligation. Merged: session-scoped state + turn-level checkpoint semantics + legal erasure scope (audio, transcript, derived context). ~35 lines. |
| **`agent-safety.md`** | ADAPT | All 13 PII types, the layered-defense model, and the injection ladder transfer intact. | `:18` "Layer 1: Pre-input — sanitize, detect injection, redact PII" assumes text you can inspect before acting; streaming ASR gives partial hypotheses that revise. Plus new §7a: GDPR Art. 9 lawful basis, consent, HDS, secret médical, AI Act Art. 50. ~500 words. |
| **`agent-tools.md`** | ADAPT | Tool-schema design, naming, and error-contract guidance transfer unchanged. | Tool calls inside a voice turn have a latency budget the text guidance never contemplates — a 2s tool call is invisible in chat and fatal on a phone call. Needs a latency-budget rule. ~20 lines. |
| **`agent-context.md`** | SKIP (salvage-heavy) | **Reuse verbatim:** §1 four-lever model (Write/Select/Compress/Isolate, in cost order), §2 five-layer anatomy, §5 progressive disclosure, §7 injection ladder. These are the spec's spine and are loop-shape-independent. | Two scouts, both SKIP, for different reasons — reconciled rather than merged. Scout 1: `:143` 5-min cache TTL on byte-identical prefix is voice-hostile, but that is one paragraph in an otherwise transferable spec. Scout 4: `:31-32` explicitly scopes regulatory boundaries out, deliberately, so it is the wrong home for GDPR. **Net: no amendment to this file; the cache paragraph gets a one-line pointer from `agent-voice.md` instead.** The SKIP is on *amending it*, not on *using it*. |
| **`agent-uncertainty.md`** | REUSE | — (no salvage needed; used whole) | Two scouts independently concluded no change. Abstention, asymmetric cost, and reversibility already cover low-ASR-confidence escalation and critical-slot confirmation. The strongest single validation of the cross-cutting spec design. |
| **`agent-voice.md`** (new) | CREATE | Conventions are fixed by the existing set: durable-question header, numbered sections, "Conflicts — flagged, not resolved", status disclaimer. Nothing to invent structurally. | Owns what has no home: cascaded-vs-S2S decision, latency budget decomposition, endpointing, barge-in + cancellation state, ASR error handling (biasing, n-best, critical-slot confirmation), TTS streaming, session state, telephony/codec, audio observability extension. Name `agent-voice.md` preferred over `agent-realtime.md` — narrower and honest about scope. 150–200 lines. |
| **`design-system/SKILL.md`** | ADAPT | Stages 0, 1–3 and the output-spec template are unchanged; the five-layer model is extended, not replaced. | **Critical path.** Stage 0b offers spinner-vs-batch tiers; duplex is neither. Needs Layer 4b (Streaming Loop), a voice tier in Stage 0b defaults, a voice simulation template, and an audio-observability rule. ~2–3h. Everything downstream depends on it. |
| **`design-sprint/SKILL.md`** | ADAPT | Sprint structure and HMW framing unchanged. | Dependency of `design-system` — inherits the Layer 4b extension. Small. |
| **`new-agent/SKILL.md`** + `references/framework-selection.md` | ADAPT | Existing decision tree is correct for request/response; add a branch, do not rewrite. | Currently routes voice to LangGraph **by accident** — no realtime question exists. Add "does this need a persistent bidirectional audio connection?" → ADK (GCP+Gemini Live) / OpenAI Realtime (voice-first) / external voice framework + agent graph. ~4–6h. |
| **`scope-poc/SKILL.md`** | ADAPT | Scoping stages transfer; only the "what is the thin slice" guidance changes. | A voice PoC's thin slice is one complete turn with barge-in, not one request. ~1–2h. |
| **`review-runtime/SKILL.md`** | ADAPT | Reporter structure and finding format unchanged. | Must learn session-lifetime and latency-budget failure modes. ~1–2h. |
| **`review-silent-failure/SKILL.md`** | ADAPT | Reporter structure unchanged. | The voice silent failures (ASR mis-hears a drug name at 0.9 confidence; barge-in drops a confirmation) are exactly this reporter's remit and none are in its checklist. ~1–2h. |
| **`review-testing/SKILL.md`** | ADAPT | Reporter structure unchanged. | Must encode "no end-to-end deterministic replay" and "task success, not WER." ~1–2h. |
| **`project-discovery/SKILL.md`** | ADAPT | Whole skill transfers; one question added. | Needs a "is this realtime/duplex?" discovery question. ~30 min. |
| **All 5 `workflow-*` skills** | REUSE | — | The spine is domain-neutral. Confirms the ml-capability-parity finding from an independent domain. |
| **Remaining 15 galactus skills** | REUSE | — | 0 SKIP across all 30. Nothing in the skill set is voice-hostile. |
| **`adk-dev-guide/SKILL.md`** (template) | ADAPT *(upstream — out of scope)* | ADK's own docs supply the content; this is transcription, not authorship. | Highest-leverage single gap found. ADK has `run_live()` + Gemini Live; the skill omits it entirely. ~200–300 lines. **Deferred: `ai-project-template`, not galactus.** |
| **`adk-scaffold/SKILL.md`** (template) | ADAPT *(upstream — out of scope)* | Existing standard/RAG/A2A template paths are the model; add one variant. | Needs a realtime scaffold variant + Gemini Live session-service setup. Actual template work likely sits in ASP internals; the skill should at minimum call it out. **Deferred.** |
| **`framework-selection/SKILL.md`** (template) | ADAPT *(upstream — out of scope)* | One new decision row + two outcomes; tree is otherwise sound. | Silently routes voice to LangGraph. **Deferred** — but note galactus's own `new-agent` reference has the same defect and *is* in scope. |
| **`langgraph-scaffold/SKILL.md`** (template) | ADAPT *(upstream — out of scope)* | One conditional branch. | Voice deployments need async + `astream_events()` set up correctly for token-by-token TTS. **Deferred.** |
| **`langgraph-fundamentals`, `langgraph-persistence`** (template) | REUSE | — | State, nodes, and checkpointing transfer unchanged. Voice agents are still stateful. |
| **`langgraph-human-in-the-loop/SKILL.md`** (template) | SKIP | **Salvage the checkpoint-and-resume discipline** — voice sessions resume too (client reconnect mid-call, transfer to queue). Discard only the `interrupt()` approval pattern. | `interrupt()` is a text/async approval gate. In voice a human interrupt is a disconnect or a vocal command — a different mechanism, not a slower one. |
| **`vercel-ai-sdk-scaffold/SKILL.md`** (template) | SKIP | **Salvage the tool-registry pattern** (one file per tool, `index.ts` re-exports) and the settings/config factory. Both are transport-independent. | HTTP tool-calling loop; its "streaming" is token-streaming for UI, not audio frames. Voice in TS needs Node audio libs + WebSocket — a rewrite of the handler and `agent.ts`, not a feature flag. |
| **`~/.claude/refs/google-adk.md`** | ADAPT *(upstream — out of scope)* | Three table lines + a paragraph. | `:21-32` capability table has no streaming row. Accurate but incomplete. **Deferred; strongest upstream candidate.** |
| **`~/.claude/refs/langgraph.md`** | ADAPT *(upstream — out of scope)* | One clarifying paragraph. | `:56` "Streaming" means token-over-HTTP, not bidi audio — actively misleading when read beside `google-adk.md`. **Deferred.** |
| **`~/.claude/refs/python.md`, `typescript.md`** | SKIP | **Salvage:** async/await patterns, WebSocket client patterns, structured-logging imports — all foundational for voice and already present. | Stack bindings are language-generic. They do not mention voice and do not need to. |
| **ml6 pattern: 202 + async polling** | SKIP | **Salvage the job-state model** (`PipelineState`, `models.py`) — a call's state (attempt count, start time, slot values) tracks the same way. The *API surface* must flip from `202 + poll` to `101 Upgrade + WebSocket`. | Actively wrong for voice: assumes latency is not a constraint and generation can be backgrounded. Voice reverses both. |
| **ml6 pattern: deterministic validator + repair** | ADAPT | Keep the validation dataclasses (`Violation`, `FieldConstraint`) as-is. | Thesis survives; the repair *loop* does not — no re-prompting mid-utterance. Shift to constraints-first (bound the output before generating) rather than generate-validate-repair. |
| **ml6 pattern: LLM provider port** | REUSE | — | `async def complete_structured(prompt, schema) -> dict` is unchanged. Add a streaming sibling `stream_audio(...) -> AsyncIterator[bytes]`; existing Anthropic adapter coexists with new realtime adapters. Zero cost to the port itself. |
| **ml6 pattern: `obs.py` span discipline** | REUSE | — | Transfers directly; add `latency_to_first_token`, `turn_duration_ms`, `asr_confidence`. |
| **`DESIGN-PROCESS.md`** | ADAPT | Trivial. | `:2` is stale — claims "14 skills, 4 subagents, 9 hooks, and 12 specs" against an actual 30/4/10/13. Ride-along doc-drift fix; a new spec makes it 14. |
| **`CLAUDE.md`** (galactus) | ADAPT | Spec-index paragraph is the only edit. | A new spec must be indexed, and `agent-voice.md`'s cross-cutting relationship stated the way `agent-uncertainty.md`'s is. |

### Assumptions

- **Assumption:** The doctolib prototype follows `enam/`'s pattern — a framing document
  first, code later or never. — **Evidence:** `enam/` contains only `README.md`; its
  Status is "Framing only — no data, no model." — **If wrong:** the ~10–16h skill
  estimate is the floor, not the total, and the template/upstream deferrals become
  blocking rather than optional. — **Confidence:** Medium
- **Assumption:** The agent stays scheduling-only (book, reschedule, cancel) and does not
  triage. — **Evidence:** operator framing, "the voice assistant" for appointments. —
  **If wrong:** GDPR Art. 22 engages, and the medical-device / AI Act high-risk analysis
  changes materially. — **Confidence:** Medium
- **Assumption:** Cascaded is the right architecture, so the tooling should teach
  cascaded first. — **Evidence:** audit trail, tool reliability, ~10× cost delta
  (`_realtime-sota.md` §1). — **If wrong:** the new spec's decision tree inverts, though
  most of its content (endpointing, barge-in, latency, observability) survives either
  way. — **Confidence:** High
- **Assumption:** Galactus-only scope will not create meaningful drift against
  `~/.claude/`. — **Evidence:** operator decision; the vendoring exception in
  `CLAUDE.md` anticipates exactly this and names canon. — **If wrong:** re-vendoring
  costs a merge rather than a copy. — **Confidence:** Medium
- **Assumption:** ~10–16h of skill work plus ~250–350 lines of spec work is the real
  size. — **Evidence:** scout estimates, bottom-up per skill. — **If wrong:** most likely
  underestimate is `design-system`, since every downstream skill depends on its model
  being right. — **Confidence:** Medium

### Disconfirming evidence

- **"The gap is total"** — would be contradicted by substantive voice content anywhere in
  the specs, skills, or refs. **Looked:** grepped seven terms across five trees.
  **Found:** only incidental matches. Holds. One qualification: `agent-uncertainty.md`
  turns out to cover its voice case *without mentioning voice*, so "zero coverage" is
  true of the vocabulary and not quite true of the substance.
- **"It's a loop-shape gap, not a topic gap"** — would be contradicted if the assumption
  breaks were confined to one or two specs. **Looked:** scout 1 enumerated per-spec with
  line cites. **Found:** eight of ten specs break, and they break on restatements of the
  same assumption. Holds, and is the reason the plan is amendments-plus-one rather than
  one-new-spec.
- **"Cascaded, not S2S"** — steel-manned: S2S is 150–200ms faster, preserves prosody
  (which matters for anxious patients), and is a single integration. **Found:** the ~10×
  cost and the missing transcript are decisive for a health-data booking system. But
  **this is domain reasoning, not tooling reasoning** — the spec should present the
  decision tree and its criteria rather than hardcode the answer, or it will mislead the
  next voice project that is not medical.
- **"0 SKIP across 30 skills"** — a suspiciously clean result; a scout looking for reasons
  to keep things would produce it artifactually. **Partially checked:** the same scout
  did return two SKIPs in the template set (`langgraph-human-in-the-loop`,
  `vercel-ai-sdk-scaffold`), so it was willing to reject. Confidence in the 0 is therefore
  Medium-High rather than High. **Not checked:** whether any of the 15 REUSE skills has a
  request/response assumption buried past the point the scout read. Flagged in Key
  Unknowns.
- **"ADK streaming is undocumented in the skills"** — would be contradicted by a streaming
  section anywhere in the ADK skills. **Looked:** grepped both skill files. **Found:**
  nothing. Holds, and is externally corroborated by ADK's own published streaming docs.

### Key unknowns

1. **Whether doctolib gets built or stays a framing document.** Changes whether the
   template/upstream deferrals are acceptable. Operator decision, not research.
2. **Whether any of the 15 REUSE skills has a buried request/response assumption.** The
   audit was breadth-first across 30 skills; a deep read of the REUSE set was not done.
3. **Real `design-system` cost.** Estimated 2–3h, but it is the critical path and the
   five-layer model is the repo's central abstraction. Extending it wrong is expensive to
   undo. This is the item most likely to want its own session.
4. **Whether `agent-voice.md` is one spec or two.** Scout 1 sized it at 150–200 lines
   assuming one. The regulated-domain material could plausibly justify a separate
   `agent-regulated.md` — the scout put it in `agent-safety` §7a instead, which is
   defensible but was not compared against the alternative.
5. **HDS / AI Act current-compliance posture.** Both deadlines have passed. Whether that
   is a live constraint depends on whether anything is deployed — unknown from here.
6. **Whether the local audio-observability attribute extension should be proposed
   upstream to the OTel GenAI SIG.** Out of scope, worth recording.
7. **No asset-verdict table from scout 5** (realtime SOTA) — correctly, since that angle
   was briefed as external research with no repo assets to assess. Noted here per the
   fan-out synthesis rule rather than silently omitted.

### Recommendation

Treat this as **one capability-parity work item shaped like the ml-capability-parity
sibling**, not as a doctolib project. The order is forced by dependency: extend
`design-system`'s five-layer model with a streaming loop **first**, because `new-agent`,
`scope-poc`, and the three `review-*` reporters all encode assumptions inherited from it —
adapting them before the model is settled means adapting them twice. Write `agent-voice.md`
alongside that, since the design-system extension needs somewhere to point. The eight spec
amendments are small, independent, and parallelizable once the new spec exists to reference.

Keep the scope decision honest about its cost: the single highest-leverage finding
(ADK ships `run_live()`; the skills never say so) sits **upstream in
`ai-project-template` and `~/.claude/refs`**, outside this plan. Galactus-only work will
produce a showcase that is internally coherent and still routes voice projects to the
wrong framework everywhere else. That is an acceptable trade for proving the shape first —
per the vendoring exception, canon is `~/.claude/` — but it should be a scheduled
follow-up with its own issue, not an implicit someday. Per the ml-capability-parity
precedent, **cross-repo work needs two GitHub issues** (prefix = repo being changed):
`GUA-` here, `AIT-` for the template.

Two ride-alongs: fix `DESIGN-PROCESS.md:2`'s stale counts, and resolve whether the
regulatory material is a section in `agent-safety` or a spec of its own — decide before
writing, since it is cheap now and a migration later.

---

## Plan
Date: 2026-08-10
Based on: `## Research` above, plus direct inspection of `design-system/SKILL.md` (346
lines), `agent-architecture.md` (354), `agent-safety.md` (336), and `CLAUDE.md` (67).

### Goal

Make galactus/.claude able to design a real-time duplex voice agent with the same
pipeline it uses for generation (ml6) and prediction (enam) — by extending the
five-layer model with a streaming loop, adding `agent-voice.md`, and amending the eight
specs whose turn-boundary assumptions break — so doctolib can be specced as a third case
study rather than improvised beside the tooling.

The deliverable is the **tooling gap**, not doctolib. doctolib is the proving case.

### Open Questions

Resolved this session (operator, 2026-08-10):

1. **Goal — capability parity as stated, not doctolib-first.** RESOLVED: plan targets the
   tooling gap. doctolib is the proving case, not the deliverable. Consequence: no step
   in this plan writes doctolib code or a doctolib spec.
2. **Key unknown #4 — where the regulated-domain material lives.** RESOLVED:
   `agent-safety.md` §7a, the scout's pick. Slots at `:311`, between §7 PII and §8
   Reliability primitives. Consequence: spec count goes to 14, not 15. Accepted risk,
   recorded here rather than silently: regulated-domain concerns are findable only by
   someone who opens the safety spec. If §7a outgrows ~600 words in review, extract to
   `agent-regulated.md` — cheaper at that point than after downstream skills cite it.
3. **Plan shape — phased A–C with review boundaries.** RESOLVED: matches the
   ml-capability-parity precedent (A–D). 19 steps total (A: 6, B: 8, C: 5) far exceeds
   the 8-step single-list rule, so phases are mandatory, not stylistic. Note that Phase B
   alone sits exactly at the 8-step limit — if B1–B8 prove larger than the "qualification
   plus a pointer" sizing assumed here, B splits again rather than running long.
4. **Upstream AIT work — no issue filed.** RESOLVED: operator declined. The ADK
   `run_live()` gap and the two `~/.claude/refs` fixes stay out of scope and untracked.
   Recorded here so the deferral is legible rather than lost: **anyone reading this plan
   should know galactus will be internally coherent and still route voice projects to
   the wrong framework everywhere else.** See Risks.

Resolved at refine (operator, 2026-08-10):

4a. **Execution shape — one doc, three sessions.** RESOLVED: this doc stays the single
   bus (one work item per plan doc holds), but **execute runs three times against it** —
   Phase A, review, Phase B, review, Phase C. DoR check 4 legitimately fails for the
   19-step whole; the phases are the seam and the plan already names them. Consequence:
   `Status:` flips `IN_PROGRESS` at the start of Phase A and reaches `EXECUTED` only
   after Phase C — do not flip it per phase, or the state machine reports the item done
   twice before it is. Each execute session starts by re-reading this doc and the prior
   phase's review verdict.
4b. **C1 is wiring, not authoring.** RESOLVED: see the correction block in Step C1. The
   ADK realtime branch points at the existing `cap-streaming.md`; Research Finding 3 is
   corrected in-place rather than left to mislead execute.
4c. **Content gates on A3 and C3 only.** RESOLVED: those two are the gates the refine
   pass and the independent failure pass both flagged as passable-against-wrong-content.
   A3 gains a per-section line-depth assertion; C3 names its six required checklist
   entries verbatim. The remaining gates stay presence-shaped, on the plan's own
   reasoning that doc correctness is review-shaped, not test-shaped
   (see Test Plan). **Consequence: DoR check 3 is closed for A3/C3 and remains
   knowingly weak elsewhere — `/workflow-review` at each boundary is the real gate.**

Open for the reviewer:

5. **Key unknown #2 — buried request/response assumptions in the 15 REUSE skills.** The
   research audit was breadth-first; no deep read was done. Plan default: accept the
   REUSE verdicts as-is and let Step C4's grep sweep catch violations cheaply. If the
   sweep returns >3 hits, that is a signal the REUSE verdict was artifactual and wants
   its own session.
6. **Key unknown #3 — real `design-system` cost.** Estimated 2–3h, flagged as the most
   likely underestimate and the critical path. Plan default: Phase A is its own review
   boundary precisely so a blown estimate surfaces before Phases B and C commit to its
   model. Do not start Phase B until A is reviewed.

### Approach

Dependency-forced ordering, in three phases with a review gate between each.

**Phase A** extends `design-system`'s five-layer model with **Layer 4b (Streaming Loop)**
and writes `agent-voice.md` in the same pass — the model extension needs somewhere to
point, and the spec needs the model to slot into. These two files are mutually
referential, so splitting them across a review boundary would mean writing each twice.

**Phase B** applies the eight spec amendments. These are small, independent, and
parallelizable *once `agent-voice.md` exists to reference* — each amendment is a
qualification plus a pointer, not a rewrite.

**Phase C** adapts the seven remaining skills and lands the two ride-alongs.

The key tradeoff: **amend eight specs rather than write one spec that supersedes them.**
The research is decisive that this is a loop-shape gap — eight specs restate the same
request→response assumption — so a single voice spec sitting beside them would leave
eight live contradictions for any reader who opens a layer spec directly. Amending costs
more edits now and prevents the tooling from disagreeing with itself.

### Out of Scope

Written before any steps, per the skill.

- **doctolib itself** — no prototype, no spec, no directory. This plan builds the
  tooling that would design it.
- **All `ai-project-template` work** — `adk-dev-guide`, `adk-scaffold`,
  `framework-selection`, `langgraph-scaffold`. Highest-leverage finding in the research;
  deliberately deferred and, per operator decision, not even issue-tracked.
- **All `~/.claude/refs/` work** — including the 4-line `google-adk.md` streaming-row fix
  and the `langgraph.md` "streaming" clarification. Galactus-only scope holds.
- **`agent-context.md`** — SKIP verdict, reconciled across two scouts. Gets a one-line
  pointer *from* `agent-voice.md` about the 5-min cache TTL; the file itself is untouched.
- **`agent-uncertainty.md`** — REUSE, two independent scouts. No edit.
- **The 15 REUSE skills and all 5 `workflow-*` skills** — no edits. Step C4 greps them
  for contradictions but does not adapt them.
- **`ml6/`** — CLAUDE.md rule: leave it alone unless the task is explicitly about it.
- **Fixing the broken pytest baseline** — see Risks. Pre-existing, unrelated, and this
  work item ships no Python.
- **Proposing the audio-observability attributes upstream to the OTel GenAI SIG**
  (research Key unknown #6). Recorded, not actioned.

### Baseline (verified this session)

- Branch: `spike/consolidate-claude-setup`. **Not a valid branch for this work** — see
  Step A0.
- `git status`: ` M .gitignore`, `?? enam/` — both unrelated to this plan.

> **Baseline re-verified at refine (2026-08-10). It had drifted:**
> - **Skills are 31, not 30.** `ls -d .claude/skills/*/ | wc -l` → 31. Every "30 skills"
>   count in this doc and in the research is off by one; `review-leakage/` is untracked
>   and was added after the research ran. **C5 must count fresh, not trust either number.**
> - **The working tree is dirtier than recorded.** Now also ` M .claude/skills/review-shared/references/finding-schema.md`,
>   ` M .claude/skills/workflow-review/SKILL.md`, ` M review/models.py`, ` M review/signals.py`,
>   `?? .claude/skills/review-leakage/`, `?? review/tests/fixtures/*.py`. **Step A0's
>   done-when ("no `enam/` or `.gitignore` carryover") will not hold as written** — these
>   belong to the review-subsystem work item, not this one. A0 must branch from a clean
>   `main`, leaving that work on the spike branch, and its done-when should assert the
>   absence of *all* of the above rather than two named paths.
> - Confirmed still accurate: 13 specs; pytest still fails at collection
>   (`ModuleNotFoundError: No module named 'galactus'`); `DESIGN-PROCESS.md:2` still
>   stale; `agent-safety.md` §7 at `:291` / §8 at `:312`, so B7's insertion point holds.
- `uv run pytest --tb=no -q` → **fails at collection**:
  `ModuleNotFoundError: No module named 'galactus'` in `tests/conftest.py:7`.
  Pre-existing and unrelated. **Consequence for this plan: pytest cannot serve as a
  "done when" check for any step.** Every step below uses a grep or line-count assertion
  that runs regardless of the broken harness.
- Counts confirmed by `ls`: 13 specs, 30 skills. Research doc's numbers are accurate;
  `DESIGN-PROCESS.md:2` claiming "12 specs / 14 skills" is confirmed stale.

---

## Phase A — the model extension and the new spec

Review boundary at the end. Do not begin Phase B until A is reviewed.

#### Step A0: Branch off the spike
**Files**: none (git only)
**What**: Current branch is `spike/consolidate-claude-setup`, which carries unrelated
changes (`.gitignore`, `enam/`). Per CLAUDE.md the work needs a `{PREFIX}-{NUM}-{slug}`
branch, and per the operator's global rules the dispatcher creates it with `--no-track`.
Requires a GUA issue number first.
**Snippet**:
```bash
# after the GUA issue exists:
git checkout main && git checkout -b GUA-<NUM>-voice-capability-parity --no-track
```
**Test**:
```bash
git branch --show-current
git status --short   # must show none of the spike-branch review-subsystem changes
```
**Done when**: current branch matches `GUA-[0-9]+-voice-capability-parity`, and
`git status --short` carries **none** of the spike branch's review-subsystem work —
`.gitignore`, `enam/`, `review/models.py`, `review/signals.py`,
`.claude/skills/review-shared/`, `.claude/skills/workflow-review/`,
`.claude/skills/review-leakage/`, `review/tests/fixtures/`. (Refine correction: the
original done-when named only `enam/` and `.gitignore`; the tree has drifted and that
assertion would now pass against six unrelated carried changes.)
**Blocker flag**: the GUA issue number is unknown from here. Execute must not invent one.
**Refine note (2026-08-10):** operator waived the issue number as a *gate* blocker. It is
still required before the branch is created — the dispatcher supplies it at execute time,
per CLAUDE.md. Execute still must not invent one.

#### Step A1: Extend the five-layer model with Layer 4b (Streaming Loop)
**Files**: `.claude/skills/design-system/SKILL.md` — insert after §4 Loop (ends `:191`),
before §5 Graph (`:193`). Also `:101` (the nesting sentence) and `:317-320` (output
template).
**What**: Add a Layer 4b section for the duplex case. §4's five required loop components
assume a re-prompt cycle with a stop condition; a duplex audio loop has no turn boundary
to stop at. State the five *streaming* components: endpointing (what ends a user turn
when no `stop_reason` exists), barge-in + cancellation state, latency budget per hop,
session lifetime, and partial-hypothesis handling. Point to `agent-voice.md` for depth
rather than inlining it.
**Snippet**:
```markdown
### 4b. Streaming loop — the duplex case            <!-- NEW, after :191 -->

If audio (or any duplex stream) flows both directions continuously, §4's components
are necessary but not sufficient: they assume a turn that *ends*. A duplex loop has no
`stop_reason`. Five additional components are required — see `agent-voice.md`:

1. **Endpointing** — what decides the user stopped talking...
2. **Barge-in and cancellation** — ...
3. **Latency budget, decomposed per hop** — ...
4. **Session lifetime** — ...
5. **Partial-hypothesis handling** — ASR revises; ...
```
Plus at `:101`, qualify the nesting sentence so the stack reads
`prompt ⊂ context ⊂ harness`, then **loop (or streaming loop)**, then graph.
Plus at `:317-320`, add `## Streaming loop` to the output template, marked
`N/A for request/response designs`.
**Test**:
```bash
grep -n '4b. Streaming loop' .claude/skills/design-system/SKILL.md
grep -c 'agent-voice' .claude/skills/design-system/SKILL.md   # expect >=1
test -f .claude/specs/agent-voice.md   # A1's pointer must not dangle — see below
```
**Done when**: §4b exists between §4 and §5; the `:101` nesting line names the streaming
variant; the output template has a `## Streaming loop` row; and the file still reads in
layer order with no forward reference to a section that doesn't exist.

> **Circular dependency with A3 — read before starting.** A1 points at `agent-voice.md`
> and A3 creates it; A3's §4b cross-reference points back here. Reordering does not fix
> this, because the dependency is genuinely mutual. **Execute A1 and A3 as one unit in
> one session**, in the order A1-body → A3 → A1-verify, and treat the `test -f` above as
> the gate. Do not close A1 while its pointer dangles — a `grep -c 'agent-voice'` hit
> proves the *reference* exists, not the *file*, and would pass against a broken link.

#### Step A2: Add the voice tier to Stage 0b defaults
**Files**: `.claude/skills/design-system/SKILL.md` — the tier table at `:69-73`, and the
latency question at `:50-51`.
**What**: Stage 0b's tier table offers Prototype / Real-but-small / Production, all keyed
on "who is watching a spinner." Voice is neither — a caller on a phone line has a
sub-second budget and no spinner. Add a voice row and qualify question 2.
**Snippet**:
```markdown
| Voice / duplex | concurrent calls, not req/day | p95 first-audio-out < 800ms; barge-in stop < 200ms | per-minute, not per-run |
```
Plus at `:50-51`, after "A human watching a spinner and a nightly batch job justify
opposite designs" — add that a caller in a live conversation is a third case where the
budget is set by conversational turn-taking, not perceived responsiveness.
**Test**: `grep -n 'Voice / duplex' .claude/skills/design-system/SKILL.md`
**Done when**: the tier table has four rows; the voice row states a first-audio-out
target, a barge-in target, and a per-minute cost basis.

#### Step A3: Write `agent-voice.md`
**Files**: `.claude/specs/agent-voice.md` (new, 150–200 lines).
**What**: The spec that owns what no existing spec does. Conventions are fixed by the
existing 13 — durable question in bold at the top, numbered `## N.` sections, status
disclaimer, `> **Conflict — flagged, not resolved.**` blocks where sources disagree,
`## Sources` at the end. Verified directly against `agent-architecture.md` and
`agent-safety.md` this session.

Required sections:
1. Cascaded (ASR→LLM→TTS) vs speech-to-speech — **present the decision tree and its
   criteria, do not hardcode the answer.** The research's own disconfirming-evidence pass
   is explicit that "cascaded" is domain reasoning for a medical booking system, not
   tooling reasoning, and that hardcoding it will mislead the next non-medical voice
   project. State the ~10× cost delta and the missing-transcript problem as *criteria*.
2. Latency budget decomposition per hop, summing to a stated end-to-end target.
3. Endpointing.
4. Barge-in and cancellation state.
5. ASR error handling — biasing, n-best, critical-slot confirmation. Cross-reference
   `agent-uncertainty.md`, which already covers the abstention case without naming voice.
6. TTS streaming.
7. Session state and lifetime.
8. Telephony and codec constraints.
9. Audio observability extension — the attribute names, cross-referencing B3.
10. One-line pointer to `agent-context.md:143`'s 5-min cache TTL as voice-hostile
    (the SKIP-with-salvage from the research).
**Snippet**:
```markdown
# Agent Voice — Conventions

**Durable question:** When audio flows both directions at once, what replaces the turn
boundary — and what is the budget for every hop between the caller speaking and hearing?

**Status (2026):** Realtime voice practice is moving fast...

---

## 1. Cascaded or speech-to-speech
...
```
**Test**:
```bash
test -f .claude/specs/agent-voice.md && wc -l .claude/specs/agent-voice.md
grep -c '^## ' .claude/specs/agent-voice.md          # expect >= 9
grep -n 'Durable question' .claude/specs/agent-voice.md
# content gate (refine 2026-08-10): no section may be a stub.
# prints any '## N.' section shorter than 8 lines; must print nothing.
awk '/^## /{if(n && c<8) print "STUB: " n " (" c " lines)"; n=$0; c=0; next} {c++}
     END{if(n && c<8) print "STUB: " n " (" c " lines)"}' .claude/specs/agent-voice.md
```
**Done when**: file exists, 150–200 lines, opens with a durable question, has ≥9 numbered
sections covering the list above, §1 presents a decision tree rather than a verdict,
`## Sources` is present, **and the stub check above prints nothing** — a section-count
gate alone passes against nine one-sentence stubs, which is why the line-depth assertion
is part of the gate rather than left to review.

#### Step A4: Index the new spec
**Files**: `CLAUDE.md:38-47` (the `## Specs` section); `.claude/specs/agent-architecture.md`
(spec index, near the tail).
**What**: `CLAUDE.md` tells readers to start with `agent-architecture.md` because it
indexes the rest. A new spec that nothing points at is invisible. Add `agent-voice.md` to
both, stating its relationship the way `agent-uncertainty.md`'s cross-cutting role is
stated at `CLAUDE.md:43-46`.
**Snippet**: in `CLAUDE.md`, after the `agent-uncertainty.md` paragraph —
`agent-voice.md` applies only to duplex/streaming designs; read it *instead of* §4 Loop
guidance, not alongside, when the design has no turn boundary.
**Test**:
```bash
grep -c 'agent-voice' CLAUDE.md .claude/specs/agent-architecture.md   # expect >=1 each
```
**Done when**: both files reference `agent-voice.md` and state when it applies.

#### Step A5: Qualify the turn-boundary definition
**Files**: `.claude/specs/agent-architecture.md` §2 "What terminates a turn" — the
`stop_reason` definition and its four bullets (verified at `:84-91`).
**What**: `:86` defines turn end by `stop_reason`. This is the single assumption the
research identifies as the root of the whole gap — eight specs inherit it. Add a
streaming-loop variant immediately after the four bullets: in a duplex stream there is no
`stop_reason`, and turn end is decided by an endpointer on the audio stream, which is a
*probabilistic* judgement rather than a protocol event. Point to `agent-voice.md §3`.
**Snippet**:
```markdown
> **Streaming variant.** The above assumes a turn that ends with a protocol event. In a
> duplex audio stream there is no `stop_reason` — turn end is *inferred* by an endpointer
> and can be wrong in both directions (cutting the user off, or waiting through silence).
> See `agent-voice.md §3`. The iteration-cap rule below still applies; the cap is on
> turns per session, not tool calls per turn.
```
**Test**: `grep -n 'Streaming variant' .claude/specs/agent-architecture.md`
**Done when**: §2 carries the variant, it is placed after the four `stop_reason` bullets,
and the max-iteration rule is explicitly preserved rather than contradicted.

> **PHASE A REVIEW BOUNDARY.** Run `/workflow-review` before Phase B. The five-layer
> model is the repo's central abstraction and every Phase B and C step inherits it —
> Key unknown #6 flags this as the most likely underestimate. If A took materially
> longer than ~3h, re-plan B and C rather than proceeding on the original sizing.

---

## Phase B — the eight spec amendments

Independent of each other; all depend on `agent-voice.md` existing. Parallelizable.
Each is a qualification plus a pointer — none is a rewrite.

#### Step B1: `agent-runtime.md` — session-scoped state
**Files**: `.claude/specs/agent-runtime.md` (209 lines), at `:68`.
**What**: `:68` asserts stateless requests, "No background tasks." A voice session is a
long-lived background task with session-scoped state. Qualify: the stateless rule holds
for tool-calling leaves; the session process itself is the exception, and it owns
connection lifetime, reconnect, and cleanup on disconnect. ~25 lines.
**Test**: `grep -n 'agent-voice' .claude/specs/agent-runtime.md`
**Done when**: `:68`'s assertion is scoped rather than deleted, and the voice exception
names what owns session cleanup.

#### Step B2: `agent-reliability.md` — supersede, don't retry
**Files**: `.claude/specs/agent-reliability.md` (223 lines), at `:110`.
**What**: `:110`'s idempotency key `run_id + step_id + tool_name` presumes a replayable
turn. A truncated utterance cannot be retried — it must be **superseded**. Add the
supersede semantic beside the retry taxonomy; the backoff and circuit-breaker guidance
transfers unchanged and should be stated as transferring. ~30 lines.
**Test**: `grep -n 'supersede' .claude/specs/agent-reliability.md`
**Done when**: supersede-vs-retry is stated with the criterion for choosing, and the
existing retry guidance is explicitly preserved for the non-streaming case.

#### Step B3: `agent-observability.md` — span shape, audio attributes, retention
**Files**: `.claude/specs/agent-observability.md` (256 lines), at `:33` and `:187-197`.
**What**: Merged from two scouts. `:33`'s tree-shaped span nesting breaks — voice needs
session→turn→{asr,llm,tts} with *overlapping* spans (TTS starts before the LLM finishes).
`:187-197` names compliance as an audit purpose but sets no retention window. Add: the
overlapping-span shape, the audio attribute extension (`latency_to_first_token`,
`turn_duration_ms`, `asr_confidence`), and a retention window for audio. ~40 lines.
This is the largest Phase B amendment.
**Test**: `grep -n 'asr_confidence' .claude/specs/agent-observability.md`
**Done when**: all three sub-changes land; the attribute names match those used in
`agent-voice.md §9` exactly (grep both, compare).

#### Step B4: `agent-eval.md` — no deterministic replay
**Files**: `.claude/specs/agent-eval.md` (214 lines), at **`:57`** (refine correction —
the plan said `:52`, which is the `## 2a.` section header; the "Reset the environment"
bullet is at `:57`).
**What**: `:57` says "Reset the environment between trials." Audio is stochastic; there is
no end-to-end deterministic replay. Add the deterministic/statistical split (components
replay; the full pipeline does not) and the **task-success-over-WER** rule — WER is a
component metric that does not predict booking success. ~30 lines.
**Test**: `grep -n 'WER' .claude/specs/agent-eval.md`
**Done when**: the split is stated, and task success is named as the primary metric with
WER explicitly demoted to component-level.

#### Step B5: `agent-memory.md` — turn-level checkpoints and erasure scope
**Files**: `.claude/specs/agent-memory.md` (301 lines), at `:54` and `:194-196`.
**What**: Merged from two scouts. `:54`'s "Checkpoint after each plan step" has no
analogue mid-utterance — checkpoint at turn boundaries, not mid-stream. `:194-196` frames
erasure as implementation rather than a GDPR Art. 17 obligation, and the erasure scope for
voice is wider than text: **audio, transcript, and derived context**. ~35 lines.
Cross-reference §7a (Step B7) rather than restating the legal basis.
**Test**: `grep -n 'derived context' .claude/specs/agent-memory.md`
**Done when**: turn-level checkpoint semantics stated; erasure scope names all three
artifacts; points to `agent-safety.md §7a`.

#### Step B6: `agent-tools.md` — latency budget for in-turn tool calls
**Files**: `.claude/specs/agent-tools.md` (195 lines).
**What**: Tool-schema, naming, and error-contract guidance transfers unchanged. What is
missing: a tool call inside a voice turn has a latency budget the text guidance never
contemplates — a 2s call is invisible in chat and fatal on a phone call. Add the rule,
plus the mitigation (acknowledge verbally while the call runs). ~20 lines.
**Test**: `grep -n 'latency budget' .claude/specs/agent-tools.md`
**Done when**: the rule states a budget, names the fill-the-silence mitigation, and does
not disturb the existing schema guidance.

#### Step B7: `agent-safety.md` §7a — regulated domains (Open Question 2)
**Files**: `.claude/specs/agent-safety.md` (336 lines) — insert at `:311`, between §7 PII
(`:291-311`) and §8 Reliability primitives (`:312`). Boundary verified this session.
**What**: New §7a per the resolved Open Question. Covers GDPR Art. 9 lawful basis for
health data, consent capture *in a voice channel* (recorded verbal consent, not a
checkbox), HDS hosting, secret médical, and AI Act Art. 50 disclosure (the caller must be
told they are talking to a machine). ~500 words. **Also** qualify `:18`'s Layer 1
("Pre-input — sanitize, detect injection, redact PII"): streaming ASR yields partial
hypotheses that revise, so there is no stable pre-input text to inspect before acting.
**Test**:
```bash
grep -n '## 7a' .claude/specs/agent-safety.md
awk '/## 7a/,/## 8/' .claude/specs/agent-safety.md | wc -w   # target <= 600
```
**Done when**: §7a sits between §7 and §8; ≤600 words (past that, revisit the extraction
decision in Open Question 2); Layer 1 at `:18` is qualified for partial hypotheses; the
13 PII types and the layered-defense model are untouched.

#### Step B8: `agent-architecture.md` streaming-loop index entry
**Files**: `.claude/specs/agent-architecture.md`.
**What**: Distinct from A5 (which adds the index line) and A4. This step indexes the
*Layer 4b concept* into the five-layer stack description so the architecture spec and
`design-system` agree on the model. ~20 lines total across both A5 and this.
**Test**: `grep -n '4b\|streaming loop' .claude/specs/agent-architecture.md`
**Done when**: the architecture spec's stack description names the streaming-loop
variant, using the same name as `design-system` §4b (grep both, compare strings).

> **PHASE B REVIEW BOUNDARY.** Run `/workflow-review` before Phase C. Specifically verify
> cross-spec consistency: B3's attribute names vs `agent-voice.md §9`, and B8's layer name
> vs A1's.

---

## Phase C — skills and ride-alongs

All depend on Phase A's model. Independent of each other.

#### Step C1: `new-agent` — the realtime routing branch
**Files**: `.claude/skills/new-agent/SKILL.md` and
`.claude/skills/new-agent/references/framework-selection.md`.
**What**: **The highest-value in-scope skill fix.** The decision tree currently routes
voice to LangGraph *by accident* — no realtime question exists, so voice falls through to
the default. Add the branch: "does this need a persistent bidirectional audio
connection?" → ADK (GCP + Gemini Live) / OpenAI Realtime (voice-first) / external voice
framework + agent graph. Add, do not rewrite — the existing tree is correct for
request/response.

> **Corrected at refine (2026-08-10) — read before starting.** Research Finding 3 claims
> ADK's `run_live()` is undocumented across the tooling and calls it the highest-leverage
> single gap. **That is false in-repo.**
> `.claude/skills/new-agent/references/cap-streaming.md:14` already states *"Google ADK |
> NATIVE | Runner yields events; `run_live()` supports bidirectional streaming."* The
> content exists; it is simply **not wired into the decision tree** —
> `framework-selection.md` returns zero hits for `realtime|bidirectional|voice|streaming`
> (verified at refine).
>
> **Consequence for this step:** C1 is a *wiring* job, not an authoring job. The realtime
> branch points at the existing `cap-streaming.md` rather than restating ADK's streaming
> story, which would fork two references that must then agree. Revised estimate **~1–2h,
> not ~4–6h.** Finding 3's framing still holds *upstream* (the template's own
> `adk-dev-guide` / `adk-scaffold` omit it) — that is unchanged and still out of scope.

**Test**:
```bash
grep -n 'bidirectional\|realtime' .claude/skills/new-agent/references/framework-selection.md
grep -n 'cap-streaming' .claude/skills/new-agent/references/framework-selection.md
```
**Done when**: a realtime question exists upstream of the LangGraph default; each of the
three outcomes names its condition; the ADK outcome **points at `cap-streaming.md` rather
than restating its content**; the request/response path is unchanged.
**Note**: galactus's copy has the same defect as the template's `framework-selection`.
Only galactus's is in scope — the template copy stays broken (Open Question 4).

#### Step C2: `design-sprint`, `scope-poc`, `project-discovery`
**Files**: `.claude/skills/design-sprint/SKILL.md`,
`.claude/skills/scope-poc/SKILL.md`, `.claude/skills/project-discovery/SKILL.md`.
**What**: Three small, mechanical adaptations. `design-sprint` inherits the Layer 4b
extension (dependency of `design-system`; small). `scope-poc` — a voice PoC's thin slice
is one complete turn *with barge-in*, not one request (~1–2h). `project-discovery` — add
one "is this realtime/duplex?" question (~30 min).
**Test**: `grep -l 'duplex\|realtime' .claude/skills/{design-sprint,scope-poc,project-discovery}/SKILL.md`
**Done when**: all three files match; `scope-poc`'s thin-slice guidance names barge-in.

#### Step C3: the three `review-*` reporters
**Files**: `.claude/skills/review-runtime/SKILL.md`,
`.claude/skills/review-silent-failure/SKILL.md`,
`.claude/skills/review-testing/SKILL.md`.
**What**: Reporter structure and finding format stay unchanged — only the checklists grow.
`review-runtime`: session-lifetime and latency-budget failure modes. `review-testing`:
"no end-to-end deterministic replay" and "task success, not WER" (must match B4's wording).
`review-silent-failure`: **the highest-value of the three** — the canonical voice silent
failures (ASR mis-hears a drug name at 0.9 confidence; barge-in drops a confirmation) are
exactly this reporter's remit and none are in its checklist. ~1–2h each.
**Required checklist entries** (refine 2026-08-10 — named verbatim so the gate asserts
specified content, not any occurrence of the word). Each reporter gains exactly these two:

| Reporter | Entry 1 | Entry 2 |
|---|---|---|
| `review-runtime` | `session lifetime` — who owns cleanup when a call drops mid-turn | `latency budget` — an in-turn tool call that exceeds its hop budget |
| `review-silent-failure` | `ASR confidence` — a mis-heard critical slot returned at high confidence | `barge-in` — an interruption that drops an unconfirmed value |
| `review-testing` | `deterministic replay` — asserting end-to-end replay that does not exist | `task success` — reporting WER in place of task completion |

**Test**:
```bash
grep -c 'session lifetime\|latency budget' .claude/skills/review-runtime/SKILL.md          # expect 2
grep -c 'ASR confidence\|barge-in' .claude/skills/review-silent-failure/SKILL.md           # expect 2
grep -c 'deterministic replay\|task success' .claude/skills/review-testing/SKILL.md        # expect 2
```
**Done when**: each of the three greps returns ≥2 against the phrases above; finding
format untouched; C3's testing wording matches B4's (grep both).

#### Step C4: REUSE-set contradiction sweep (Open Question 5)
**Files**: read-only across the 15 REUSE skills and 5 `workflow-*` skills.
**What**: The research's "0 SKIP across 30 skills" is flagged Medium-High confidence, not
High, because no deep read of the REUSE set was done. Cheap check: grep for
request/response assumptions that would contradict the new model.
**Snippet**:
```bash
grep -rn 'stop_reason\|request.response\|one request\|per request' \
  .claude/skills/ --include=SKILL.md | grep -v -e design-system -e new-agent -e scope-poc
```
**Test**: the grep above.
**Done when**: every hit is triaged as benign or filed. **If >3 genuine contradictions,
stop and re-plan** — that falsifies the REUSE verdict and is its own work item.

#### Step C5: ride-alongs — stale counts
**Files**: `DESIGN-PROCESS.md:2`.
**What**: `:2` claims "14 skills, 4 subagents, 9 hooks, and 12 specs." Verified actual
this session: 30 skills, 13 specs — and 14 specs once `agent-voice.md` lands. Fix all four
numbers; verify subagent and hook counts at execute time rather than trusting either the
doc or this plan.
**Snippet**:
```bash
ls .claude/specs/*.md | wc -l      # expect 14 after A3
ls -d .claude/skills/*/ | wc -l    # expect 30
```
**Test**: `head -3 DESIGN-PROCESS.md`
**Done when**: all four counts match a freshly-run count, not a remembered one.

---

### Test Plan

**The pytest harness is broken at baseline** (`ModuleNotFoundError: No module named
'galactus'`), and this work item ships no Python — so verification is structural, not
test-suite-based. Fixing the harness is out of scope; it must not silently become the
gate.

Per-phase gates:

| Phase | Gate |
|---|---|
| A | `agent-voice.md` is 150–200 lines with ≥9 sections; `design-system` §4b exists and both name the same layer; `CLAUDE.md` + `agent-architecture.md` both index the new spec |
| B | Each of the 8 specs greps for `agent-voice`; B3's attribute names match `agent-voice.md §9` exactly; §7a ≤600 words and sits between §7 and §8 |
| C | The 7 skills carry voice-specific content; C4's sweep returns ≤3 genuine contradictions; C5's counts match a fresh count |

Cross-cutting consistency check, run at the end of B and again at the end of C:
```bash
# the layer name must be identical in both files
grep -h '4b' .claude/skills/design-system/SKILL.md .claude/specs/agent-architecture.md
# observability attributes must match between spec and voice spec
grep -h 'asr_confidence\|latency_to_first_token\|turn_duration_ms' \
  .claude/specs/agent-observability.md .claude/specs/agent-voice.md
```

No behavioural tests exist for docs. The honest statement: **this work item's correctness
is reviewed, not tested.** `/workflow-review` at each phase boundary is the actual gate.

### Risks & Rollback

| Risk | Likelihood | Mitigation |
|---|---|---|
| `design-system` extension is wrong; every downstream skill inherits the error | Medium | Phase A is its own review boundary. Nothing in B or C starts until the model is reviewed. Research Key unknown #3 flags this as the likeliest underestimate. |
| §7a outgrows its section and should have been `agent-regulated.md` | Medium | Hard word-count gate (≤600) in B7's done-when. Extraction is cheap before C3's reporters cite it, expensive after. |
| Eight parallel spec amendments drift in vocabulary | Medium | Explicit grep-both-and-compare checks in B3/B8/C3. All eight point at one spec rather than restating it. |
| Galactus stays internally coherent while everything else routes voice wrong | **High — accepted** | Operator declined the AIT issue. Recorded in Open Question 4 so the gap is legible. Unmitigated by choice. |
| The "0 SKIP / 15 REUSE" verdict was artifactual | Low-Medium | C4's sweep, with an explicit stop-and-replan trigger at >3 hits. |
| Hardcoding "cascaded" misleads the next non-medical voice project | Medium | A3 §1 is specified as a decision tree with criteria, not a verdict. Called out in the research's own disconfirming-evidence pass. |

**Rollback**: every step is an additive doc edit on a feature branch. Revert is
`git checkout main -- <file>` per file, or abandon the branch. No migrations, no
generated artifacts, no state. The only irreversible-ish choice is §7a-vs-`agent-regulated.md`,
which is why it was decided before writing rather than during.

### Definition of Done

- [ ] `agent-voice.md` exists, 150–200 lines, ≥9 sections, §1 is a decision tree, and the
      A3 stub check prints nothing (no section under 8 lines)
- [ ] C3's six named checklist entries present verbatim (2 per reporter)
- [ ] C1's realtime branch points at `cap-streaming.md` rather than restating it
- [ ] `design-system` §4b exists; tier table has a voice row
- [ ] All 8 Phase B specs amended and referencing `agent-voice.md`
- [ ] §7a ≤600 words, between §7 and §8
- [ ] 7 skills adapted; `new-agent` no longer routes voice to LangGraph by default
- [ ] C4 sweep triaged
- [ ] `DESIGN-PROCESS.md:2` counts match a fresh count
- [ ] `CLAUDE.md` and `agent-architecture.md` index the new spec
- [ ] Reviewed at all three phase boundaries
- [ ] Out-of-scope upstream gap recorded in Open Question 4 (no issue, per operator)

_compact: 2026-08-10 16:46_

_compact: 2026-08-10 16:48_
