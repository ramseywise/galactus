# `cap-*.md` reuse triage

Date: 2026-08-08
Source: `/Users/wiseer/.claude/skills/new-agent/references/`
Scope: Step 2 of `job-system/.claude/docs/plans/2026-08-08-ml6-genai-prototyping-loop.md`

These specs inform the **solution** (guardrails, vision ingest, observability), not the
prototyping workflow. Four of the 18 `cap-*.md` files have a plausible claim on a
deterministic DAG architecture; they are assessed individually below. The remaining 14 are
skipped by category (one line at the end).

## Verdicts

| File | Verdict | Destination | Reason |
|---|---|---|---|
| `cap-guardrails.md` | **REUSE (adapt)** | Step 4 (validator), Step 7 (grounding) | Layer 4 post-generate structural check is the layout-contract validator, restated. Its grounding rule — every claim traceable to a retrieved passage, else `cannot_verify` — is exactly the gate F2's hybrid ingest exists to enable. Highest-value file in the set. |
| `cap-vision.md` | **REUSE (adapt)** | Step 7 (vision ingest path) | `image_to_message()` + `resize_and_encode()` are directly liftable for sending PDF page images. Provider-branching shape matches the Step 6 LLM port. |
| `cap-observability.md` | **REUSE (adapt)** | Step 9 (traces, R2) | `AgentSpan` dataclass is a portable, OTel-GenAI-conformant span contract with token/cache accounting. `configure_structlog()` is liftable as-is. |
| `cap-genai.md` | **SKIP (registry); salvage one helper** | — (helper → Step 9 evals, optional) | Confirmed as predicted. No tool-calling loop exists in this architecture, so the registry mechanism has nothing to dispatch. Its own spec note (line 16) concedes the schema builder regexes docstrings incorrectly and emits Anthropic-only `input_schema`. See note below on `summarize_table`. |

## Adaptation notes

### `cap-guardrails.md` → Step 4 / Step 7

Take the **shape**, not the code. The scaffold is agent-loop-shaped (five sequential layers
around a model turn); this pipeline needs only Layer 4, and needs it as a *pure function
returning violations*, not as an exception-raising gate.

- **Divergence that matters**: `GuardrailViolation` raises and carries a `reason` string.
  Step 4's `Violation` must *return* (many per draft, all reported at once) and carry
  structured fields (`field`, `constraint`, `actual`, `limit`, `repair_hint`) — because the
  repair loop needs machine-readable violations to build a repair prompt, not a human
  message. A raise-on-first-failure design would only ever surface one violation per
  round-trip, multiplying LLM calls.
- **Reusable directly**: the "guardrails must be fast (<5ms), semantic grading belongs in
  the offline eval pipeline" rule (line 7). This is the validator/eval split of Steps 4 and 9.
- **Layer 4 grounding → Step 7**: the `cannot_verify` response instead of a hallucination is
  the disposition for a claim that fails span-matching. Note the reference implementation
  only warns rather than blocking (lines 247–250) — the prototype should block, since
  "factually correct" is a stated case requirement.
- Layers 1/2/3/5 are out of scope: no untrusted user text at the injection boundary, no
  retrieval scoring, no human handoff.

### `cap-vision.md` → Step 7

- Lift `encode_image_base64()`, `image_to_message()`, `resize_and_encode()`.
- `VisionInput`'s path-existence validator is useful; the file itself flags (line 16) that
  its two `@field_validator("image_path")` decorators both run and should be collapsed —
  do that when lifting.
- Size ceilings are verified 2026-07-20: 5 MB, 2576 px long edge. For PDF page images,
  pass `max_dimension=1568` unless table extraction demonstrably needs the fidelity — it is
  ~3× the image tokens, and F8 says input tokens are essentially the whole cost model.
- Pillow becomes a dependency only if resizing is actually needed; PDF page rasterization
  comes from `pymupdf` (Step 7) which can emit at a chosen DPI directly.

### `cap-observability.md` → Step 9

- `AgentSpan` + `configure_structlog()` cover R2's structured-logging and trace
  requirements without an OTel collector. Instantiate spans, call `.log()`, skip
  `OTelExporter` unless a collector materializes (it degrades gracefully with
  `tracer_provider=None`).
- Semconv pin: `opentelemetry-semantic-conventions-ai>=0.4.0` — `gen_ai.usage.input_tokens`,
  not `prompt_tokens`. Only relevant if the exporter is wired up.
- **Extension needed for Step 9**: `AgentSpan` has no field for pipeline-stage identity or
  repair-attempt count. The eval metrics (contract pass rate, repair convergence, fallback
  rate, grounding rate) need `metadata` entries for `stage`, `repair_attempts`, and
  `used_fallback`. The `metadata: dict` field absorbs these without touching the dataclass.
- "Every LLM call gets a span; do not aggregate" (line 20) applies directly to the repair
  loop — attempt 1 and attempt 2 are separate spans, which is what makes repair convergence
  measurable at all.

### `cap-genai.md` → skip, with one salvage

The registry is correctly skipped. One thing in the file is worth noting rather than
discarding: `shared_tools.py`'s `summarize_table()` (lines 321–359) formats a list of dicts
as a compact markdown table, and is pure, dependency-free, and unrelated to the registry —
the file's own agnostic contract (line 7) says the domain utilities "are not part of the
registry mechanism." It may be useful for rendering eval results in Step 9. Copy the
function if wanted; do not import the module (it imports `registry` at line 206 and
executes decorators on import).

`parse_date_range()` and `format_currency()` have no use here.

## The other 14 — skipped by category

`cap-a2a`, `cap-batch`, `cap-cluster`, `cap-compaction`, `cap-finetune`, `cap-forecast`,
`cap-hitl`, `cap-kg`, `cap-langchain`, `cap-mcp`, `cap-rag`, `cap-rlhf`, `cap-search`,
`cap-streaming` — skipped by category: this architecture has no tool-calling loop, no
retrieval infrastructure (F3), no multi-agent coordination, no MCP (F5), no
training/tuning, and no streaming surface. If Step 4, 7, or 9 turns up a need one of them
covers, read it then.
