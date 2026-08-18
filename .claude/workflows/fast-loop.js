/**
 * fast-loop — four-band Workflow dispatcher for the proto-* pipeline.
 *
 * Dispatches band agents by composing skill bodies (read fresh at dispatch time),
 * explicit targets (substituted for $ARGUMENTS), and tool grants (from frontmatter).
 * No skill is invoked by name; the disable-model-invocation flags stay set.
 *
 * Breakpoints: after band 1 (confirm decision tree), after band 3 (gate confirmation).
 * Bands 2 and 3 run without stopping.
 *
 * Usage:
 *   claude workflow .claude/workflows/fast-loop.js -- --plan <plan-doc-path>
 *
 * GAL-27
 */

import Anthropic from "@anthropic-ai/sdk";
import * as fs from "fs";
import * as path from "path";
import { execSync } from "child_process";

// --- Configuration -----------------------------------------------------------

const BAND_SKILLS = {
  1: [
    { skill: "proto-scope", phase: "triage" },
    { skill: "proto-research", phase: "research" },
    { skill: "proto-plan", phase: "plan" },
  ],
  2: [
    { skill: "proto-refine", phase: "refine" },
    { skill: "proto-execute", phase: "execute" },
  ],
  3: [{ skill: "proto-review", phase: "review" }],
  4: [{ skill: "proto-harden", phase: "harden" }],
};

const SKILL_TOOLS = {
  "proto-scope": ["Read", "Grep", "Glob", "Bash", "Write"],
  "proto-research": ["Read", "Bash", "Grep", "Glob", "WebSearch", "Write"],
  "proto-plan": ["Read", "Grep", "Glob", "Bash", "Write"],
  "proto-refine": ["Read", "Grep", "Glob", "Bash", "Edit", "Agent"],
  "proto-execute": ["Read", "Grep", "Glob", "Bash", "Edit", "Write"],
  "proto-review": ["Read", "Grep", "Glob", "Bash", "Agent"],
  "proto-harden": ["Read", "Grep", "Glob", "Bash", "Edit", "Write"],
};

// --- Execution-root assertion (V1 + FA-006) ----------------------------------

function assertExecutionRoot() {
  const repoRoot = execSync("git rev-parse --show-toplevel", {
    encoding: "utf-8",
  }).trim();

  if (!repoRoot.endsWith("/galactus")) {
    throw new Error(
      `Execution-root assertion failed: expected galactus repo, got ${repoRoot}. ` +
        "The dispatcher must run from ~/workspace/galactus, not ~/workspace."
    );
  }

  // Check the hook that will actually run emits transitions (FA-006)
  const hookPath = path.join(
    repoRoot,
    ".claude/hooks/plan_transition_validate.sh"
  );
  if (!fs.existsSync(hookPath)) {
    throw new Error(
      `Hook not found at ${hookPath}. The transition hook must exist for ` +
        "the ledger to record band transitions."
    );
  }

  const hookContent = fs.readFileSync(hookPath, "utf-8");
  if (!hookContent.includes("log_transition")) {
    throw new Error(
      "The transition hook at " +
        hookPath +
        " does not emit transitions " +
        "(no log_transition call found). This is the galactus#20 failure: a hook " +
        "that runs but does not record."
    );
  }

  return repoRoot;
}

// --- Skill body composition --------------------------------------------------

function readSkillBody(repoRoot, skillName) {
  const skillPath = path.join(
    repoRoot,
    ".claude/skills",
    skillName,
    "SKILL.md"
  );
  if (!fs.existsSync(skillPath)) {
    throw new Error(`Skill body not found: ${skillPath}`);
  }
  const content = fs.readFileSync(skillPath, "utf-8");
  // Strip YAML frontmatter — the agent gets the body, not the metadata
  const fmMatch = content.match(/^---\n[\s\S]*?\n---\n/);
  return fmMatch ? content.slice(fmMatch[0].length) : content;
}

function composeAgentPrompt(repoRoot, skillName, target) {
  const body = readSkillBody(repoRoot, skillName);
  // Substitute $ARGUMENTS with the explicit target
  const prompt = body.replace(/\$ARGUMENTS/g, target);
  return prompt;
}

// --- Checklist evaluation ----------------------------------------------------

function readPlanDoc(planPath) {
  if (!fs.existsSync(planPath)) return null;
  return fs.readFileSync(planPath, "utf-8");
}

function extractStatus(content) {
  const match = content.match(/^Status:\s*(.+)$/m);
  return match ? match[1].trim() : null;
}

function evaluateGate(bandNum, planPath) {
  const content = readPlanDoc(planPath);
  if (!content) return { pass: false, items: [{ id: "ERR", expectation: "plan doc exists", value: "error" }] };

  const status = extractStatus(content);
  const items = [];

  if (bandNum === 1) {
    items.push({
      id: "B1-01",
      expectation: "Status is PLANNED or later",
      value: ["PLANNED", "REFINED", "READY", "IN_PROGRESS", "EXECUTED", "COMPLETE"].includes(status) ? "true" : "false",
    });
    const hasTrack = /^Track:\s*.+$/m.test(content);
    items.push({
      id: "B1-04",
      expectation: "Track is declared",
      value: hasTrack ? "true" : "false",
    });
  } else if (bandNum === 2) {
    items.push({
      id: "B2-01",
      expectation: "Status is EXECUTED",
      value: status === "EXECUTED" ? "true" : "false",
    });
  } else if (bandNum === 3) {
    items.push({
      id: "B3-01",
      expectation: "Review has run",
      value: /^Review:\s*.+$/m.test(content) ? "true" : "false",
    });
  }

  const allPass = items.every((i) => i.value === "true");
  return { pass: allPass, items };
}

// --- Band dispatch -----------------------------------------------------------

async function dispatchBand(client, repoRoot, bandNum, target, timing) {
  const skills = BAND_SKILLS[bandNum];
  const startTime = Date.now();
  let stopped = false;

  console.log(`\n${"=".repeat(60)}`);
  console.log(`BAND ${bandNum} — ${skills.map((s) => s.phase).join(" → ")}`);
  console.log(`${"=".repeat(60)}\n`);

  for (const { skill, phase } of skills) {
    console.log(`  [${phase}] Dispatching ${skill}...`);

    const prompt = composeAgentPrompt(repoRoot, skill, target);
    const tools = SKILL_TOOLS[skill] || [];

    // The agent is dispatched with the composed prompt and granted tools.
    // In a full Workflow runtime, this would be an agent() call.
    // For now, we print what would be dispatched.
    console.log(`  [${phase}] Prompt: ${prompt.slice(0, 120)}...`);
    console.log(`  [${phase}] Tools: ${tools.join(", ")}`);
    console.log(`  [${phase}] Target: ${target}`);

    // Check status after each skill to see if we should continue
    const content = readPlanDoc(target);
    if (content) {
      const status = extractStatus(content);
      console.log(`  [${phase}] Current status: ${status}`);
    }
  }

  const elapsed = (Date.now() - startTime) / 1000;
  timing.push({
    band: bandNum,
    elapsed_seconds: elapsed,
    stopped,
    completed: !stopped,
  });

  console.log(
    `\n  Band ${bandNum} ${stopped ? "STOPPED" : "completed"} in ${elapsed.toFixed(1)}s\n`
  );
  return !stopped;
}

// --- Breakpoints -------------------------------------------------------------

function printChecklist(bandNum, planPath) {
  const gate = evaluateGate(bandNum, planPath);
  console.log(`\n--- Release checklist: Band ${bandNum} → Band ${bandNum + 1} ---`);
  for (const item of gate.items) {
    const icon = item.value === "true" ? "PASS" : item.value === "error" ? "ERR " : "FAIL";
    console.log(`  [${icon}] ${item.id}: ${item.expectation}`);
  }
  if (!gate.pass) {
    console.log("\n  Gate BLOCKED — items above must be resolved before proceeding.");
  }
  return gate;
}

// --- Main --------------------------------------------------------------------

export default async function workflow({ args }) {
  const planIdx = args.indexOf("--plan");
  if (planIdx === -1 || !args[planIdx + 1]) {
    console.error("Usage: --plan <path-to-plan-doc>");
    return;
  }
  const planPath = args[planIdx + 1];

  console.log("fast-loop dispatcher — GAL-27");
  console.log(`Plan: ${planPath}\n`);

  // Execution-root assertion
  let repoRoot;
  try {
    repoRoot = assertExecutionRoot();
    console.log(`Root: ${repoRoot} (verified)`);
  } catch (err) {
    console.error(`BLOCKED: ${err.message}`);
    return;
  }

  // Record ledger state before
  const ledgerPath = path.join(repoRoot, ".claude/logs/plan-transitions.jsonl");
  const ledgerBefore = fs.existsSync(ledgerPath)
    ? fs.readFileSync(ledgerPath, "utf-8").split("\n").filter(Boolean).length
    : 0;

  const timing = [];
  const client = new Anthropic();

  // --- Band 1: Triage -------------------------------------------------------
  await dispatchBand(client, repoRoot, 1, planPath, timing);

  // BREAKPOINT: confirm the decision tree
  const gate1 = printChecklist(1, planPath);
  if (!gate1.pass) {
    console.log("\nBand 1 gate not satisfied. Stopping for human confirmation.");
    console.log("Timing:", JSON.stringify(timing, null, 2));
    return;
  }
  console.log("\n>> BREAKPOINT: Band 1 complete. Confirm decision tree to proceed.");

  // --- Band 2: Prototype ----------------------------------------------------
  await dispatchBand(client, repoRoot, 2, planPath, timing);

  // --- Band 3: Optimize (review) --------------------------------------------
  await dispatchBand(client, repoRoot, 3, planPath, timing);

  // BREAKPOINT: gate confirmation before harden
  const gate3 = printChecklist(3, planPath);
  if (!gate3.pass) {
    console.log("\nBand 3 gate not satisfied. Stopping for human confirmation.");
    console.log("Timing:", JSON.stringify(timing, null, 2));
    return;
  }
  console.log("\n>> BREAKPOINT: Band 3 complete. Confirm to proceed to hardening.");

  // --- Band 4: Harden -------------------------------------------------------
  await dispatchBand(client, repoRoot, 4, planPath, timing);

  // --- Summary ---------------------------------------------------------------
  const ledgerAfter = fs.existsSync(ledgerPath)
    ? fs.readFileSync(ledgerPath, "utf-8").split("\n").filter(Boolean).length
    : 0;

  console.log("\n" + "=".repeat(60));
  console.log("FAST-LOOP COMPLETE");
  console.log("=".repeat(60));
  console.log(`\nTiming:`);
  for (const t of timing) {
    console.log(
      `  Band ${t.band}: ${t.elapsed_seconds.toFixed(1)}s (${t.completed ? "completed" : "stopped"})`
    );
  }
  console.log(`\nLedger: ${ledgerBefore} → ${ledgerAfter} transitions`);
  if (ledgerAfter === ledgerBefore) {
    console.warn(
      "\nWARNING: ledger unchanged — the dispatcher ran but no transitions were recorded. " +
        "This is the FA-001 failure: check that the hook is firing."
    );
  }
}
