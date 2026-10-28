---
name: vercel-ai-sdk-scaffold
description: >
  Scaffold a new Vercel AI SDK (TypeScript) agent — settings, Anthropic provider
  factory, tool registry, streamText loop, framework-agnostic HTTP handler, and
  eval smoke-test. Use when the user wants to build or extend a TS-native agent
  (e.g. "add a Vercel agent", "build me a TS agent for X", "extend the agent/ tree")
  or when the framework selection skill picks vercel_ai_sdk. Requires
  `has_typescript: true` and `ts_agent_framework: vercel_ai_sdk` in copier.yaml.
---

# Vercel AI SDK Agent Scaffolding Guide

Read `.claude/skills/framework-selection/SKILL.md` before writing any agent code if
you haven't decided a framework yet — it asks the TS-runtime question first, which is
the branch that leads here.

This skill is the TS-native counterpart to `langgraph-scaffold`. Where LangGraph gives
you a full graph with nodes, edges, and checkpointers, the Vercel AI SDK gives you a
single `streamText` + `tool()` loop — simpler control flow, TS-first, deploys on Vercel
with zero configuration. Pick this when the agent loop itself must run in the TS/Node
process; pick LangGraph (in Python, called over HTTP) if you need arbitrary graph
branching or human-in-the-loop interrupts.

---

## Step 1: Gather Requirements

Always ask before scaffolding:

1. **What problem will the agent solve?** — Core purpose and the tools it needs.
2. **Tool list** — What external APIs or data sources will it call? Each becomes a
   `tool()` entry with a Zod schema. Sketch the list; you'll implement one stub tool
   and leave the rest for the follow-up.
3. **Streaming or generate?** — Does the caller need a streamed UI response
   (`streamText`) or a single resolved string (`generateText`)? Default: `streamText`.
4. **Auth shape** — Is this a public endpoint, or does it sit behind Supabase JWT /
   another auth layer? Determines whether `middleware/auth.ts` is needed.
5. **Deployment target** — Vercel (zero-config Express deployment, no `vercel.json`
   needed unless custom routing), or standalone Node service?
6. **Max steps** — Accept the default (`TS_AGENT_MAX_STEPS=5`) or override in
   `.env.example`. There is deliberately no temperature setting: thinking-by-default
   models reject `temperature`/`top_p`/`top_k` with a 400.

---

## Step 2: Write DESIGN_SPEC.md

Present before scaffolding. Sections:

```markdown
# DESIGN_SPEC.md

## Overview
2–3 paragraphs: agent purpose, the tool-calling loop it runs, deployment home.

## Tool Registry
Each tool: name, input schema (Zod), output type, external API / side-effect.

## Example Use Cases
3–5 concrete inputs → expected tool calls → expected final answer.

## Streaming Shape
streamText (default) or generateText. If streaming: does the caller parse
text-delta chunks, or consume a full UIMessageStreamResponse?

## Auth & Middleware
Public endpoint or authenticated? If auth: middleware approach and token source.

## Constraints & Safety
Output filters, rate-limit guards, any content rules.

## Success Criteria
Measurable: latency target, tool-call accuracy on golden QA set, lint/type pass.

## Edge Cases
At least 3 scenarios (missing tool arg, provider timeout, malformed messages array).
```

---

## Step 3: Scaffold the File Set

Substitute `{AGENT_NAME}` → camelCase/slug, `{OUTPUT_DIR}` →
`{ts_project_root}/{ts_source_root}/agent/` (confirm the exact path from the project
layout — check `package.json` / `tsconfig.json` for the source root if unclear).

```
{OUTPUT_DIR}/
  agent.ts          # streamText call + tool registry + SYSTEM_PROMPT
  handler.ts        # framework-agnostic (req: Request) => Response — no Express imports here
  settings.ts       # env-var-driven config (model, temp, maxSteps, apiKey)
  clients/
    llm.ts          # getProvider() + getModel() — sole createAnthropic() call site
  tools/
    {toolName}.ts   # one file per tool: tool() + Zod schema
    index.ts        # re-exports tools record consumed by agent.ts
  eval/
    run.ts          # answer-overlap smoke eval against data/corpus/golden_qa.jsonl
```

If the project uses Express (`app.ts`), add one adapter route:
```typescript
// in app.ts — wire the framework-agnostic handler into Express
app.post("/agent/chat", async (req, res) => {
  const webReq = new Request(`http://localhost${req.path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(req.body),
  });
  const webRes = await chatHandler(webReq);
  res.status(webRes.status);
  webRes.headers.forEach((v, k) => res.setHeader(k, v));
  const body = await webRes.text();
  res.send(body);
});
```

Generation rules:

**`agent.ts`**: import `convertToModelMessages`, `stepCountIs`, `streamText`, `UIMessage`
from `"ai"`. Import `getModel` from `../../model/gateway.js`, `settings` from `./settings.js`,
`tools` from `./tools/index.js`. Export `runAgent(messages: UIMessage[])` returning
the `streamText(...)` result directly — don't `await` it; the caller (handler.ts)
decides how to consume the stream.

```typescript
export function runAgent(messages: UIMessage[]) {
  return streamText({
    model: getModel(),
    system: SYSTEM_PROMPT,
    messages: convertToModelMessages(messages),
    tools,
    // No temperature — thinking-by-default models 400 on it.
    stopWhen: stepCountIs(settings.maxSteps),
  });
}
```

**`handler.ts`**: framework-agnostic — accepts a Web API `Request`, returns a Web API
`Response`. No Express imports. Parse `messages` from the JSON body; validate shape
(return `400` if malformed or missing). Call `runAgent(messages)` and return
`.toUIMessageStreamResponse()`. This handler drops into a Next.js route handler
(`export const POST = handler`) unchanged.

**`settings.ts`**: read `process.env` here and nowhere else. Export a plain object —
no class, no singleton pattern. Match Python's `settings.py` shape: one field per
env var with a typed default.

**`model/gateway.ts`**: sole `createAnthropic()` call site. Export `getProvider()` and
`getModel()`. Never call `createAnthropic()` elsewhere in the codebase.

**`tools/{toolName}.ts`**: use `tool()` from `"ai"` + `z` from `"zod"`. Define
`parameters` as a Zod schema (input) and `execute` as an `async` function — always
async even if trivially simple, for consistency. Return plain serialisable objects.
One tool per file. Re-export from `tools/index.ts` as a named-record `tools` object.

**`eval/run.ts`**: reads `GOLDEN_QA_PATH` env var for the golden QA file path
(not hardcoded — `ts_project_root` may not be a fixed distance from the repo root).
POSTs to the running agent's `/agent/chat`. **Detect in-stream error chunks explicitly**
— the AI SDK reports provider failures as `{"type":"error",...}` chunks inside a
200-status stream; a parser that only reads `text-delta` silently produces `0.0`
overlap on auth errors. Record `answer_overlap_ratio: null` + real error message for
error rows; do not score them as `0.0`.

---

## Step 4: Update package.json

Add to `dependencies` (or verify already present from the template):
```json
"ai": "^4.x or ^5.x — match whatever is in package.json.jinja",
"@ai-sdk/anthropic": "^x.x",
"zod": "^3.x"
```

Add npm scripts if absent:
```json
"eval": "npx tsx {ts_source_root}/evals/run.ts"
```

---

## Step 5: Validate

```bash
npm install
npm run typecheck       # tsc --noEmit — must exit 0
npm run lint            # eslint — must exit 0, zero violations
npm test                # vitest — all tests pass
```

Then smoke-test the running server:
```bash
# Terminal 1
npx tsx src/index.ts

# Terminal 2 — missing messages → expect 400
curl -s -X POST http://localhost:3000/agent/chat \
  -H "content-type: application/json" \
  -d '{}' | head -c 200

# Terminal 3 — valid messages, no key → expect SSE stream + provider error in stream
curl -s -X POST http://localhost:3000/agent/chat \
  -H "content-type: application/json" \
  -d '{"messages":[{"role":"user","id":"1","parts":[{"type":"text","text":"hi"}]}]}'
```

Confirm: `400` on missing messages, SSE stream starts on valid messages (chunked
transfer, `data: {"type":"start"}`), and a real auth error from Anthropic appears in
the stream body (not a 500) when no `ANTHROPIC_API_KEY` is set — this proves the full
route → handler → agent loop → provider chain is wired.

---

## Critical Rules

- **`handler.ts` must be framework-agnostic.** No Express imports inside it — those
  go in the adapter route in `app.ts`. A Next.js route handler must be able to
  `import { handler } from "./handler"` and re-export it as `export const POST = handler`
  with zero modifications.
- **Never hardcode model strings.** All model/provider configuration lives in
  `settings.ts`, read from `process.env`. NEVER change an existing model string in
  code you're modifying unless explicitly asked.
- **`model/gateway.ts` is the sole `createAnthropic()` call site.** All other files
  call `getModel()`. Same discipline as Python's `model/gateway.py` convention, and
  the rule `.claude/hooks/sdk_lint.sh` enforces (naming.md §1 rule 2).
- **Do not `await runAgent()`.** Return the `streamText(...)` result and call
  `.toUIMessageStreamResponse()` on it in `handler.ts` — awaiting it loses the stream.
- **Detect error chunks in eval.** The AI SDK streams provider errors inside a 200
  response — check for `type: "error"` chunks and throw; don't let them score as `0.0`.
- **`stopWhen: stepCountIs(settings.maxSteps)`** must be set. Without it, a tool-heavy
  prompt can loop until token budget is exhausted.
- **No RAG wiring here.** If the agent needs retrieval, add it as a `tool()` entry
  that calls the Python RAG backend over HTTP — do not re-implement retrieval in TS.
  See the `langgraph-scaffold` skill for the Python-side RAG scaffold pattern.

---

## Eval story (TS vs Python)

The TS eval path is intentionally narrower than the Python suite:

| | Python | TS |
|---|---|---|
| Structured eval | `evals/pipelines/` (graders, metrics, calibration, sampling) | `promptfoo.config.yaml` (root of repo) |
| Smoke eval | `evals/pipelines/run.py.jinja` | `agent/eval/run.ts` |
| Retrieval grading | hit_rate / MRR via `BACKENDS` | not applicable — tool-calling agent has no retrieval step |

`promptfoo` (already in the universal `_scaffold/` root) is the TS project's structured
eval complement. `run.ts` is a lightweight answer-overlap smoke test, not a port of
Python's retrieval-grading pipeline. This is correct by design, not a gap.

---

## Scaffold as Reference

The full staged tree lives at:
`template/_scaffold/{{ ts_project_root }}/{{ ts_source_root }}/agents/{{ ts_agent_dir }}/`

Read it for canonical file shapes before generating anything new — especially
`agent.ts.jinja`, `settings.ts.jinja`, `../../model/gateway.ts.jinja`, and
`../../evals/run.ts.jinja`.
The staged tree is the ground truth; this skill is the scaffolding guide.
