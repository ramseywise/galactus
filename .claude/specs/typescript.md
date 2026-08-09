# TypeScript Conventions

- Strict mode always (`"strict": true` in tsconfig)
- `npm` as package manager for TS projects — never uv/pip
- ESLint + TypeScript strict mode; Prettier for formatting
- Prefer `fetch` over axios for HTTP; use `Response` streaming for agent output
- No `any` — use `unknown` + type narrowing
- Env vars server-side only — never `NEXT_PUBLIC_` or `VITE_` prefix for secrets/API keys
- Agent state (ADK session, conversation history) → Supabase, not in-memory
- Error boundaries at route level in Next.js/React

## Don'ts (akira-scan checks these as findings, not just prose)

- No API keys in client bundles — Vercel Functions / Next.js API routes only
- No `console.log` in production paths — use structured logging or remove
- No `require()` in new code — ESM imports only
- No implicit `any` via `as any` casts
- No unhandled promise rejections — `await` in try/catch or `.catch()` every promise
- No non-null `!` assertion to silence the compiler — narrow the type instead
- No fetch without a timeout / `AbortSignal` on server paths
