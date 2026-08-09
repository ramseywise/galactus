# Skill Writer Reference

Technical details, frontmatter fields, discovery mechanics, and patterns.

## Table of Contents

- [Frontmatter Fields](#frontmatter-fields)
- [Discovery Mechanics](#discovery-mechanics)
- [Progressive Disclosure Architecture](#progressive-disclosure-architecture)
- [Skill Categories](#skill-categories)
- [Workflow Patterns](#workflow-patterns)
- [Instruction Writing Patterns](#instruction-writing-patterns)
- [Dynamic Content Features](#dynamic-content-features)
- [Priority and Resolution](#priority-and-resolution)

---

## Frontmatter Fields

### Required

| Field | Rules | Limit |
|-------|-------|-------|
| `name` | kebab-case, no spaces/capitals, must match folder name | 64 chars |
| `description` | What + When + Keywords, third person, single-line YAML | 1024 chars |

### Optional

| Field | Purpose | Example |
|-------|---------|---------|
| `allowed-tools` | Restrict available tools | `Read, Grep, Glob` |
| `disable-model-invocation` | Only user can invoke via `/name` | `true` |
| `user-invocable` | Only Claude can invoke (hides from `/` menu) | `false` |
| `model` | Override model when skill active | `sonnet`, `opus`, `haiku` |
| `argument-hint` | Shows expected args in autocomplete | `[file-path]` |
| `context` | Run in isolated subagent | `fork` |
| `agent` | Which subagent type (with `context: fork`) | `Explore` |
| `effort` | Reasoning effort level (Opus 4.6 only) | `low`, `medium`, `high`, `max` |
| `color` | UI accent color for skill | `red`, `blue`, `green`, `yellow`, `purple`, `orange`, `pink`, `cyan` |
| `license` | For open-source distribution | `MIT` |
| `compatibility` | Environment requirements (1-500 chars) | `Requires LibreOffice` |
| `metadata` | Custom key-value pairs | `author: Name` |

### Invocation Control Matrix

| Config | User can invoke | Claude auto-invokes | Description in context |
|--------|----------------|--------------------|-----------------------|
| (default) | Yes | Yes | Yes |
| `disable-model-invocation: true` | Yes | No | **No** |
| `user-invocable: false` | No | Yes | Yes |

**Key distinction**: `disable-model-invocation: true` removes the description from Claude's context entirely. `user-invocable: false` keeps it visible to Claude but hides the `/` command from users.

### Security Restrictions

Forbidden in frontmatter:
- XML angle brackets (`<` `>`) - could inject system prompt
- Names containing "claude" or "anthropic" (reserved)

---

## Discovery Mechanics

### How Skills Load (3 Stages)

1. **Startup**: Claude loads name + description for every skill into system prompt (~100 tokens each)
2. **Trigger**: When user query matches description, Claude reads full SKILL.md via filesystem
3. **References**: Claude navigates to linked files only when needed

### Token Budget

- **Budget**: 2% of context window (fallback: ~15,000-16,000 characters)
- **Per skill overhead**: ~109 characters + description length
- **If budget exceeded**: Skills are silently excluded from context (no warning)
- **Override**: Set `SLASH_COMMAND_TOOL_CHAR_BUDGET=30000` in environment

**Practical implications**:
- 20 skills with 200-char descriptions ≈ 6,200 chars (safe)
- 60 skills with 200-char descriptions ≈ 18,500 chars (over budget)
- For large collections: keep descriptions under 130-150 chars

### Why Skills Don't Trigger

Check in this order:
1. **Budget exceeded?** - Total descriptions exceed character budget (silent failure)
2. **YAML broken?** - Multi-line description, bad indentation, tabs instead of spaces
3. **Description too vague?** - No specific trigger keywords
4. **Name mismatch?** - Folder name doesn't match `name` field
5. **Wrong casing?** - Must be exactly `SKILL.md` (case-sensitive)

Debug: Ask Claude "When would you use the [skill-name] skill?" If it doesn't know, the skill isn't in its context.

---

## Progressive Disclosure Architecture

### Three Levels

| Level | What | Token Cost | When Loaded |
|-------|------|-----------|-------------|
| 1. Metadata | name + description | ~100 tokens/skill | Always (startup) |
| 2. SKILL.md body | Core instructions | <5k tokens | On activation |
| 3. References + scripts | Detailed docs, code | 0 until accessed | On demand |

### When to Split Content

- **SKILL.md approaching 500 lines** → move details to references/
- **Domain-specific details** → separate reference files per domain
- **Executable code** → scripts/ directory (output enters context, not source)
- **Templates and assets** → assets/ directory

### Reference File Guidelines

- **One level deep** from SKILL.md only - no reference chains
- **>100 lines**: Include table of contents at top
- **>10k words**: Include grep search patterns in SKILL.md
- **No duplication**: Info lives in SKILL.md OR references, never both

---

## Skill Categories

### Category 1: Document & Asset Creation
Skills that produce consistent output (documents, code, designs).

**Techniques**: Embedded style guides, template structures, quality checklists, verification loops.

**Example**: pdf, xlsx, pptx, frontend-design skills.

### Category 2: Workflow Automation
Multi-step processes with consistent methodology.

**Techniques**: Step-by-step workflows with validation gates, iterative refinement loops, phase-based execution.

**Example**: skill-creator, call-prep skills.

### Category 3: MCP Enhancement
Workflow guidance on top of MCP tool access.

**Techniques**: Coordinates multiple MCP calls, embeds domain expertise, provides context users would otherwise need to specify.

**Example**: sentry-code-review skill.

---

## Workflow Patterns

### Sequential Orchestration
Steps in specific order with dependencies between them.
```markdown
### Step 1: Create Account
Call: `create_customer` with name, email
### Step 2: Setup Payment
Wait for: Step 1 customer_id
Call: `setup_payment_method`
```

### Iterative Refinement
Output quality improves with iteration.
```markdown
### Draft → Validate → Refine → Re-validate
1. Generate first draft
2. Run: `scripts/validate.py`
3. Address each issue
4. Re-validate
5. Repeat until clean pass
```

### Context-Aware Selection
Same outcome, different tools depending on context.
```markdown
### Decision Tree
File type → Large (>10MB)? → Cloud storage MCP
          → Collaborative? → Notion/Docs MCP
          → Code? → GitHub MCP
```

### Verification Loop (from Anthropic's pptx skill)
```markdown
1. Generate output → Convert to inspectable format → Review
2. List issues (if none found, look again critically)
3. Fix issues
4. Re-verify affected sections
5. Repeat until full pass reveals no new issues
Do not declare success until at least one fix-and-verify cycle.
```

---

## Instruction Writing Patterns

### Imperative Voice (Universal Rule)
- ✅ "Rotate the PDF with..." / "Extract text using..."
- ❌ "The PDF can be rotated by..." / "You might want to consider..."

### Code-First Examples
Show working code immediately, explanations second (or never).

### Critical Warnings Format
```markdown
## CRITICAL: Use Formulas, Not Hardcoded Values

### ❌ WRONG
[code showing anti-pattern with inline comment explaining why]

### ✅ CORRECT
[code showing correct approach]
```

### Quick Reference Tables (Highest-Impact Format)
Map tasks to approaches in a scannable table. Used in 6/10 Anthropic skills. Empirically validated as the single most impactful pattern for AI consumption — agents treat them as lookup databases, citing specific rows. Prioritize tables over prose for any decision-mapping or option-selection content.

### Anti-Pattern Lists
Specific "what NOT to do" lists. Often more useful than positive instructions:
```markdown
NEVER use:
- Generic AI-generated aesthetics
- Overused font families (Inter, Roboto, Arial)
- Cliched color schemes
```

### Black Box Script Pattern
```markdown
**Run scripts with `--help` first.** Do NOT read source unless
a customized solution is absolutely necessary. Scripts can be
large and pollute your context window.
```

### Verification Commands
Give Claude executable validation commands it must run before completing:
```markdown
python -m markitdown output.pptx | grep -iE "lorem|ipsum|placeholder"
If grep returns results, fix before declaring success.
```

---

## Dynamic Content Features

### String Substitution (Claude Code)
- `$ARGUMENTS` - All arguments passed to skill
- `$1`, `$2` etc. - Positional arguments
- `${CLAUDE_SESSION_ID}` - Current session ID
- `${CLAUDE_PLUGIN_ROOT}` - Plugin root directory (for plugins)

### Command Execution in Skills (Claude Code)
```markdown
## Current context
- Git status: !`git status --short`
- Branch: !`git branch --show-current`
```
Commands run BEFORE skill content is sent to Claude. Output replaces placeholder.

### File References
```markdown
For detailed patterns, see [reference.md](reference.md).
@path/to/file.md  (loads file content inline - commands/legacy syntax)
```

---

## Priority and Resolution

When skills share names across scopes:

1. **Enterprise** (managed settings) - highest priority
2. **Personal** (`~/.claude/skills/`)
3. **Project** (`.claude/skills/`)
4. **Plugin** (namespaced as `plugin:skill`) - lowest priority

If a skill and legacy command share a name, the skill takes precedence.

### Nested Discovery
Claude Code discovers skills from nested `.claude/skills/` directories. Editing `packages/frontend/file.js` also loads skills from `packages/frontend/.claude/skills/`.

---

## Skill Quality Signals (From Empirical Testing)

### Tool Use Correlates With Output Quality
Agents that make 8-12 tool calls (loading skills, reading references) produce significantly better output than agents making 0-2 calls. Skill loading isn't overhead — it's quality investment. Design skills that encourage tool use (reference files, verification commands) rather than trying to front-load everything.

### Testing Methodology
- **One prompt per agent** produces cleaner data than multi-prompt. One bad result contaminates fewer data points.
- **Self-report prompts work**: Embedding "report which skills you loaded and which tools you used" gets honest, structured data from agents.
- **Blank Claude test**: Drop the skill in an empty project with no prior context. This reveals true skill quality without your knowledge polluting the assessment.

---

## Platform Differences

| Feature | Claude Code | Claude.ai | API |
|---------|------------|-----------|-----|
| Network access | Full | Varies | None |
| Package install | Local only | npm/PyPI | Pre-configured only |
| Hot-reload | Yes (CC 2.1+) | N/A | N/A |
| `context: fork` | Yes | No | No |
| Dynamic content (`!`cmd``) | Yes | No | No |
| Skill upload | File system | Settings > Skills | `/v1/skills` endpoint |

---

*Last updated: 2026-02-09*
*Sources: Anthropic skills guide, official docs, anthropics/skills repo, community research*
