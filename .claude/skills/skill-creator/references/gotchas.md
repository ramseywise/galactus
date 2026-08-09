# Skill Writer: Gotchas & Failure Modes

Common problems, silent failures, and how to fix them. Ordered by frequency and impact.

## Table of Contents

- [Silent Failures](#silent-failures)
- [YAML Traps](#yaml-traps)
- [Discovery Failures](#discovery-failures)
- [Instruction Compliance](#instruction-compliance)
- [Caching Issues](#caching-issues)
- [Common Misconceptions](#common-misconceptions)
- [Anti-Patterns](#anti-patterns)

---

## Silent Failures

### Token Budget Starvation (Most Dangerous)

All skill descriptions share a budget of ~15,000 characters (2% of context window). When you exceed this, skills silently disappear from Claude's context. **No warning, no error.**

**Symptoms**: Skills that worked before suddenly stop triggering after installing new skills.

**Diagnosis**: Count total characters across all skill descriptions + ~109 chars overhead per skill.

**Fix**:
- Shorten descriptions (130-150 chars for large collections)
- Set `SLASH_COMMAND_TOOL_CHAR_BUDGET=30000` environment variable
- Remove unused skills

### `disable-model-invocation: true` Removes Description from Context

This field doesn't just prevent auto-invocation - it removes the description from Claude's system prompt entirely. Claude literally cannot see the skill exists unless the user types `/skill-name`.

**When this is what you want**: Deploy, commit, send-message skills (side effects).

**When this breaks things**: If you wanted Claude to know about the skill's existence but just not auto-invoke it.

---

## YAML Traps

### Multi-Line Descriptions Break Discovery

Prettier and other auto-formatters convert single-line descriptions to multi-line YAML. This **completely breaks skill discovery**.

```yaml
# ❌ BREAKS (auto-formatted to multi-line):
description:
  Design and create Claude Skills using progressive
  disclosure principles.

# ✅ WORKS:
# prettier-ignore
description: Design and create Claude Skills using progressive disclosure principles.
```

**Prevention**: Add `# prettier-ignore` above the frontmatter, or configure `.prettierignore` for SKILL.md files.

### Common YAML Mistakes

```yaml
# ❌ Missing delimiters:
name: my-skill
description: Does things

# ❌ Unclosed quotes:
name: my-skill
description: "Does things

# ❌ Tabs instead of spaces:
name:	my-skill

# ✅ Correct:
---
name: my-skill
description: Does things.
---
```

---

## Discovery Failures

### Skill Exists But Never Triggers

Check in order:

1. **Budget exceeded?** Total descriptions over ~15k chars → skill silently excluded
2. **Multi-line YAML?** Auto-formatter broke the description
3. **Description too vague?** "Helps with projects" won't trigger - needs specific keywords
4. **Name mismatch?** Folder name must match `name` field exactly
5. **Wrong casing?** Must be `SKILL.md` (not SKILL.MD, skill.md, Skill.md)
6. **Wrong location?** Check `~/.claude/skills/` or `.claude/skills/`

**Quick debug**: Ask Claude "When would you use the [skill-name] skill?" If Claude doesn't know about it, the skill isn't in its context.

### Skill Triggers But Claude Does the Work Manually

Claude loads the skill but doesn't follow its workflow - just does the task from general knowledge.

**Fixes**:
- Make instructions more specific and imperative
- Add verification steps that force following the workflow
- Use CRITICAL: headers for must-follow rules
- Add step-by-step numbered phases that create structure

### Skill Overtriggers

Loads for unrelated queries, annoying users.

**Fixes**:
- Add negative triggers: `"Do NOT use for simple data exploration (use data-viz skill instead)."`
- Narrow scope: `"Processes PDF legal documents for contract review"` not `"Processes documents"`
- Clarify domain: `"PayFlow payment processing for e-commerce. Use specifically for online payment workflows, not general financial queries."`

---

## Instruction Compliance

### Instructions Ignored During Multi-Step Tasks

Claude reads SKILL.md, acknowledges instructions, then ignores them during complex multi-step work. Prioritizes task completion over skill patterns.

**Mitigations**:
- Put critical rules at the TOP of SKILL.md
- Use emphatic formatting: `## CRITICAL:`, `⚠️ IMPORTANT`
- Add verification commands Claude must run before completing
- Use scripts for critical validation (code is deterministic, language isn't)
- Repeat key rules in different sections if needed

### Instructions Forgotten After Context Compaction

After compaction, Claude frequently forgets skill instructions entirely.

**Mitigations**:
- Keep SKILL.md lean (compaction preserves recent + important content)
- Put persistent rules in CLAUDE.md (survives compaction better)
- For long sessions, re-invoke the skill periodically

### Instruction Framing Matters

Soft guidance gets optimized away. Positive necessity gets followed.

```markdown
# ❌ Gets skipped:
"Read these files for guidance"
"Consider checking the schema"

# ✅ Gets followed:
"Read all four files first - this ensures valid output"
"CRITICAL: Validate against schema before proceeding"
```

Frame instructions as "this helps you succeed" not "you should comply."

---

## Caching Issues

### Edits Don't Appear (Stale Cache)

Editing SKILL.md but Claude still uses old version.

**In CC 2.1+**: Hot-reload should work automatically. If it doesn't:
- Start a new session
- Delete cache: `~/.claude/plugins/cache/` and restart
- For marketplace plugins: bump version in marketplace.json

### Plugin Updates Don't Propagate

`CLAUDE_PLUGIN_ROOT` can point to stale cache directory after plugin updates.

**Fix**: Delete `~/.claude/plugins/cache/[plugin-name]/` and restart.

---

## Platform Limits (Not Fixable by Skill Writing)

### Cold-Start Discovery Without Domain Keywords (~40% Failure)
Prompts without domain-specific keywords (e.g., "I want to organize my world" without mentioning "worldbuilding" or the tool name) fail to trigger skills ~40% of the time. Broader description keywords help but can't fully solve this — it's how Claude matches prompts to descriptions at the platform level.

**Mitigation**: Front-load the most common domain keywords. Include synonyms and paraphrases. But accept that generic prompts will sometimes miss.

### Haiku Shortcuts From Knowledge Instead of Invoking
Haiku especially tends to answer from its training knowledge rather than loading and following a skill. It "knows enough to be dangerous" — produces plausible but unconstrained output.

**Mitigation**: Not description-fixable. If skill compliance matters, use sonnet or opus. For haiku agents, add explicit verification steps that force tool use.

### Plugin Visibility for Spawned Agents
Some spawned agents (via Task tool) can't see plugins at all. This is an infrastructure issue, not a content issue.

**Mitigation**: For critical agent workflows, put skills in `~/.claude/skills/` (global) rather than plugins. Global skills have more reliable visibility.

---

## Common Misconceptions

### "user-invocable: false prevents Claude from using the skill"

**Wrong.** `user-invocable` only controls the `/` menu visibility. Claude can still auto-invoke.

| Field | What it does |
|-------|-------------|
| `user-invocable: false` | Hides from `/` menu. Claude CAN still auto-invoke. |
| `disable-model-invocation: true` | Removes from context entirely. Only user can invoke. |

### "SKILL.md body is always loaded"

**Wrong.** Only frontmatter (name + description) loads at startup. The markdown body loads on-demand when Claude decides to invoke the skill. This is why "when to use" info MUST be in the description.

### "Skills are like extensions/plugins"

**Wrong.** Skills are text injected into context. No code execution, no special privileges. Scripts execute via normal Bash tool when referenced. They're closer to "onboarding guides" than "plugins."

### "More skills = more capability"

**Wrong.** Each skill costs ~100 tokens of always-loaded context. Too many skills exceed the discovery budget and silently disappear. Quality over quantity.

### "model: haiku in frontmatter overrides the model"

**Partially broken.** Known bug (Issue #17562): shorthand model names in frontmatter can cause 404 errors because they don't translate to full model IDs the way the Task tool does. Test before relying on this.

---

## Anti-Patterns

### Auxiliary Documentation Files
❌ README.md, INSTALLATION_GUIDE.md, CHANGELOG.md, QUICK_REFERENCE.md inside skill folder.

Skills are for AI agents, not humans. Only include files Claude needs to do the job.

### "When to Use" Section in Body
❌ The body loads AFTER Claude decides to activate. "When to use" info in the body is useless for triggering. Put it all in the description.

### Deeply Nested References
❌ SKILL.md → advanced.md → details.md → actual info

Claude may use `head -100` on nested files, getting incomplete info. Keep references one level deep.

### Verbose Explanations Over Examples
❌ 150 tokens explaining what PDFs are and why libraries exist.
✅ 50 tokens with direct code example.

Claude is smart. Only add context it doesn't already have.

### Too Many Options
❌ "You can use pypdf, or pdfplumber, or PyMuPDF, or pdf2image..."
✅ "Use pdfplumber for text extraction. For scanned PDFs requiring OCR, use pdf2image with pytesseract."

Pick one recommended approach. Add alternatives only for genuinely different use cases.

### Meta-Commentary
❌ "This skill was created to...", "The purpose of this skill is...", "Version history..."

Start immediately with what to do. No preamble about the skill itself.

### Permission-Seeking in Instructions
❌ "Ask the user if they want to validate..."
✅ "Validate the output. If validation fails, fix and re-validate."

Skills assume agency. Don't add confirmation steps unless the action has real side effects.

### Time Estimates
❌ "This should take about 5 minutes..."

Never include time estimates. They're unreliable and waste tokens.

### Inconsistent Terminology
❌ Mixing "API endpoint", "URL", "API route", "path" for the same concept.
✅ Pick ONE term and use it consistently throughout.

### Windows-Style Paths
❌ `scripts\helper.py`, `reference\guide.md`
✅ `scripts/helper.py`, `reference/guide.md`

Forward slashes work everywhere. Backslashes fail on Unix.

---

*Last updated: 2026-02-09*
*Sources: GitHub issues (anthropics/claude-code), community reports, empirical testing*
