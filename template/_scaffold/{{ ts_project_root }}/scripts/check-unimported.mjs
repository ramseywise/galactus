#!/usr/bin/env node
/**
 * Fail when a module under src/ is imported by nothing.
 *
 * Why this exists (AIT-44): four agent-support modules once shipped into every
 * TypeScript render referenced by neither the agent nor a test. Two of them
 * carried real type errors that reddened CI for two days while `npm test`
 * stayed green throughout — nothing imported the files, so only `tsc` ever saw
 * them. A module no code path touches gets its first real exercise from a type
 * checker, which is the wrong place to find out.
 *
 * Why not eslint-plugin-import's `import/no-unused-modules`: that rule cannot
 * run under ESLint 9 flat config without a legacy `.eslintrc` shim, and even
 * with the shim it silently reports nothing — a planted orphan module passes
 * clean (import-js/eslint-plugin-import#3079). A guard that always passes is
 * worse than no guard, so the import graph is built directly here.
 *
 * The check is module-level ("does any other file import this?"), not
 * export-level. Unused individual exports are a separate, noisier question; a
 * starter template legitimately ships helper functions the user has not called
 * yet. A file nobody imports at all is never legitimate.
 */

import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, resolve, dirname, relative } from "node:path";

const ROOT = resolve(dirname(new URL(import.meta.url).pathname), "..");
const SRC = join(ROOT, "src");

// Process entry points: reached by the runtime or a package.json script, not
// by an import. Anything listed here is exempt from needing an importer.
const ENTRY_POINTS = ["src/index.ts", "src/evals/run.ts"];

// Files whose imports count as "someone uses this". Tests count deliberately:
// a module exercised only by a test is wired enough to have been type-checked
// and run at least once, which is the bar this guard enforces.
//
// Since AIT-70 tests are colocated (src/<layer>/__tests__/) rather than in a
// sibling tests/ tree, so scanning src/ alone already picks them up as
// importers. They must NOT also be judged as subjects: a test file is imported
// by nothing by definition — the runner discovers it by glob — so treating one
// as a subject reports every test as an orphan.
const SCAN_DIRS = ["src"];

/** True for a test file: an importer of record, never a subject. */
const isTest = (file) => file.includes("/__tests__/") || file.endsWith(".test.ts");

function walk(dir) {
  if (!existsSync(dir)) {
    return [];
  }
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      return walk(full);
    }
    return full.endsWith(".ts") ? [full] : [];
  });
}

// Static ESM plus dynamic import(). The template's TS sources use explicit
// NodeNext specifiers ("./agent.js"), so a regex over specifiers is exact
// here — there is no bare-word or computed-path resolution to model.
const SPECIFIER = /(?:from\s*|import\s*\(?\s*)["']([^"']+)["']/g;

/** Resolve a relative specifier to a real .ts file, honouring NodeNext .js. */
function resolveSpecifier(fromFile, spec) {
  if (!spec.startsWith(".")) {
    return null;
  }
  const base = resolve(dirname(fromFile), spec);
  const candidates = [
    base.replace(/\.js$/, ".ts"),
    `${base}.ts`,
    join(base, "index.ts"),
    base,
  ];
  return candidates.find((c) => existsSync(c) && c.endsWith(".ts")) ?? null;
}

const allFiles = SCAN_DIRS.flatMap((d) => walk(join(ROOT, d)));
const imported = new Set();

for (const file of allFiles) {
  const source = readFileSync(file, "utf8");
  for (const [, spec] of source.matchAll(SPECIFIER)) {
    const target = resolveSpecifier(file, spec);
    if (target && target !== file) {
      imported.add(target);
    }
  }
}

const exempt = new Set(ENTRY_POINTS.map((p) => join(ROOT, p)));
const subjects = walk(SRC).filter((f) => !isTest(f));
const orphans = subjects
  .filter((f) => !imported.has(f) && !exempt.has(f))
  .map((f) => relative(ROOT, f))
  .sort();

if (orphans.length > 0) {
  console.error("FAIL: these modules under src/ are imported by nothing:\n");
  for (const o of orphans) {
    console.error(`  ${o}`);
  }
  console.error(
    [
      "",
      "Every module must be reached by the agent, by another module, or by a test.",
      "Fix by wiring it into a real code path, or — if it cannot be wired (e.g. it",
      "is incompatible with the streaming handler) — add a test that imports and",
      "exercises it, and say why in the module's header comment.",
      "",
      `A genuine process entry point belongs in ENTRY_POINTS in ${relative(ROOT, resolve(dirname(new URL(import.meta.url).pathname), "check-unimported.mjs"))}.`,
    ].join("\n"),
  );
  process.exit(1);
}

console.error(`OK: all ${subjects.length} modules under src/ have an importer.`);
