---
name: design-system
description: "Architect role — takes a design doc + PRD and produces two artifacts: the system design of record (tabbed HTML, diagram-led) and deep component specs (.claude/specs/). The gate before build: no execute work begins on a system whose design record does not cover it. Triggers on: 'design doc', 'system design', 'design of record', 'draw the architecture', '/design-system'."
disable-model-invocation: true
allowed-tools: Read Bash Grep Glob Write Edit AskUserQuestion Agent
---

# /design-system

Produce or update the design of record for: `$ARGUMENTS`

**The third design stage — Architect only.** Takes the design doc (from
`/design-initiative`) and the PRD (from `/design-product`) and produces two artifacts:

1. **The design of record** — `docs/<project>-system-design.html`, a tabbed HTML broadsheet
2. **Deep component specs** — `.claude/specs/platform/{agents,services,infra}/<component>.md`

There is no reference file to copy from — the spec below is the standard. A complete
plate runs figure → caption → facts table → delta links, and every plate carries an SVG
diagram. The component contract further down is normative, not illustrative.

A prior output of this skill failed by having zero diagrams, no delta anchors, and no
hash router. If an existing HTML file is present, treat it as output to be judged against
the rules below — never as a pattern to copy.

## Pipeline position

```
/design-initiative → design doc (framing, HITL — asks questions where unclear)
/design-product → PRD (deliverables, requirements, HITL — asks questions where unclear)
    ↓
/design-system (Architect) → design of record + .claude/specs/  ← YOU ARE HERE
    ↓
/design-roadmap (PM, EM, Des) → milestones, dependencies, GitHub issues
```

Every stage is interactive. Ask the user when:
- A design decision has multiple valid options and the choice affects build scope
- The working tree contradicts a source document and you're unsure which is current
- A component's responsibility boundary is ambiguous (agent vs service, shared vs owned)
- Prior art exists that might inform the design but wasn't in the inputs

## Inputs

1. **The design doc** (`.claude/docs/design/` or `.claude/specs/design-scope.md`) — the initiative framing
2. **The PRD** (`.claude/specs/design-requirements.md`) — the requirements this design must cover
3. **The working tree** — the design records what IS, not what the docs claim.
   Where a source document and the code disagree about build state, **the working
   tree is authoritative**. Grep before you claim.

   > **Greenfield case.** If the repo has no source tree yet, every component is
   > `SPECIFIED` (dashed), never `BUILT`. Do not read "no tree" as "nothing works" —
   > the project may have a running product elsewhere. Describe the *target* system
   > from the feasibility docs, and state plainly in the footer that build state could
   > not be verified against code. Re-verify on the first pass after the codebase lands.
4. **Existing specs** (`.claude/specs/`) — prior deep specs that carry requirement
   traces and decision rationale. These are input, not output to overwrite — merge
   forward, don't flatten.

### Spec coverage is a requirement, not a courtesy

**Every mechanism, rubric, threshold, taxonomy, and failure contract in `.claude/specs/`
must appear in the design record or be explicitly listed as out of scope.** The specs are
not background reading — they are the content. Before publishing, walk the spec tree
against the plates: a spec section with no plate is either a missing plate or a spec that
should be deleted.

Watch the stack refs and infra specs in particular. They are read last, or not at all, and
they hold exactly the cross-cutting content the plates most often lack — a four-rung
failure ladder sitting in a functions spec while the design record says nothing about
failure is the failure mode this rule exists to prevent. Same for idempotency rules
buried in a data-model spec, and retry/backoff policy in a gateway spec.

Report the walk: list any spec section you did not surface, and why.

## Output 1 — The design of record (HTML)

### Structure — tabbed HTML, hash-routed

| Tab | Contains |
|-----|----------|
| Overview | Why this system exists, audience cards, shared-capability inventory, TOC |
| Architecture | **C1** system context · **C2** containers · **C2.1** lifecycle & gates · **D1** data model |
| Components | **C3** one plate per named decision surface: mechanism diagram + facts table |
| Platform | The shared layer every component imports, its boundary rule, and the **semantics plate** |
| Delta | The build queue, the decision register, and the PRD coverage table |

**Every tab is built from plates.** A plate is `.plate-head` (number + title + zoom tag)
→ `.plate-sub` → `<figure>` → facts table. The numbering carries the C4 altitude, so a
reader knows whether they are looking at the whole system or one function. Sections
without plate chrome read as a blog post, not a design record.

### The Overview tab stands alone

This is the only tab a non-engineer reads, and the only one read linearly. It must work
with no other tab open: the problem in one paragraph, an audience card per actor, the
shared-capability inventory, and the TOC.

Where the PRD already frames the problem, **compress rather than restate** — cite it by
`§` and never contradict it. The PRD is the narrative artifact; this tab is its abstract,
not its replacement. A thin Overview is the most common failure of this skill: it
defaults to a tab bar with an H1 under it, and the reader who needed the framing goes
back to the PRD and never returns.

### C2.1 — the lifecycle plate is required

One plate showing the end-to-end journey as **ordered, gated stages**: what advances an
entity from each stage to the next, what gate blocks it, and who or what opens the gate.
This is consistently the single most useful figure in the document — it is the one a
reader screenshots — and it is the one most often missing, because no individual
component owns it. Draw it even when every stage is BUILT.

### The semantics plate is required

The hardest review findings are never about components — they are about **execution
semantics**, the rules that hold *between* components. A design organized
component-by-component omits them structurally, because no single component owns them.
This plate is where they live. Every row is either specified or **explicitly deferred**;
deferral is a valid answer, silence is not.

| Concern | Must state |
|---|---|
| **Lifecycle state machine** | Who may transition, from → to, guards, required approval, event written, side effects. Cross-reference the C2.1 plate |
| **Idempotency** | For every consequential command (approve, sign, send, publish, transition): the key that makes a repeat a no-op. A double-clicked Approve must not produce two state transitions |
| **Concurrency** | Whether stale writes are rejected, and how — or that it is deliberately deferred, naming the mechanism if it lands |
| **Failure taxonomy** | A row per failure: invalid output, schema violation, timeout, rate limit, provider down, auth failure, **database unavailable**, **approval unavailable**, **duplicate request**, **concurrent write**. The last four are the ones endpoint-level ladders miss |
| **Async boundary** | If the stack has a realtime/pubsub channel, state whether it is UI synchronization or a domain event bus. Say which, in one sentence |
| **Structured vs. blob** | Which data is a flexible artifact (JSON blob) and which is queryable domain state (relational). A query the product needs is the test |

**The async boundary row prevents a specific, common failure.** Where a realtime channel
exists and its role is unstated, someone eventually builds `db update → realtime event →
frontend notices → frontend calls API → API mutates` — and the business workflow now
depends on a browser tab being open. The correct direction is `command → transaction →
state + event → realtime merely informs clients`. One sentence in the design record
forecloses it.

### The trust-boundary plate — required for more than one class of principal

Where a system has more than one kind of authenticated caller, enumerate the **actors**,
not only the attacks. One row per principal — anonymous, authenticated user, staff, admin,
server function, model provider, database — with four columns: what it may **submit**,
**read**, **mutate**, and **cause**.

An attack list answers "is this specific hole closed?". This answers "what is this
principal able to do at all?", which is what surfaces the holes nobody thought to list.
The test it applies: **is there any principal whose write surface exceeds its authority?**
That question found a live hole in a prior project (diskoe) — partner orgs could advance
their own lifecycle state, making the subject of a gate its own approver.

Include the model provider as a principal. It reads whatever a prompt includes, which
makes prompt assembly a tenancy-scoped read like any other.

### The schema plate is a claim about a live database, not an instruction

Required wherever the design record draws a data model against a database that already
exists. **A migration is a claim about reality that must be verified, not an instruction
that will fail loudly if wrong.** A prior project (diskoe) learned this twice:

- `create table if not exists` **silently skipped** against a hand-built live table, so a
  `text[]` declaration sat in the repo while the real columns were `jsonb` holding JSON
  strings. Writeback would have written the wrong shape into a table with existing rows.
- `create unique index if not exists` against a same-named **non-unique** index skipped
  just as silently — recorded as applied while the invariant it declared was never in force.

Rules for the plate:

1. **`IF NOT EXISTS` guards on NAME, not definition.** Where a migration must change an
   existing object, drop-then-create is the only honest form.
2. **A migration is not done until it is pushed AND probed.** The file existing is not
   evidence that it ran. Put a drift check in the gate, and **fail on duplicate migration
   versions rather than dedupe them** — a prior project's checker keyed its map by version,
   so a second file with the same version silently evicted the first and was neither reported
   applied nor reported missing. *An instrument that disagrees with the directory and says
   nothing invalidates every row it certifies.*
3. **Every column names its reader before it is added.** A status column no query filters
   on is a trap, not documentation: it is plausible enough that the next author reaches
   for it and gets an empty set.
4. **One lifecycle column per entity**, and the plate says which one is the gate.
5. **Verify a constraint in a way that cannot be intercepted** — an undeclared trigger
   once made a passing probe meaningless. Never probe production destructively.
6. **Index the predicate the application actually filters on.**
7. **A row-level security policy is part of the plate, not an ops detail.** Enabling RLS
   with no `select` policy for the anonymous principal returns zero rows, and **reads as
   "no data" rather than "no permission"** — which is why it can survive unnoticed while
   the public surface renders empty. State the policy per table per principal, and verify
   by loading the same query as both principals.

**Mark each row `WRITTEN` or `APPLIED`, never both by implication.**

### The provenance contract — required for any system with AI-generated content

If a model generates content a human reads or approves, the design record must state
provenance as a **data-model rule, not a UI feature**. A provenance badge with no column
behind it cannot answer "where did this sentence come from?" six months later.

Distinguish four sources, and carry the distinction in the schema:

1. **Verified fact** — sourced directly from system or user data
2. **Deterministic inference** — computed by stated rules
3. **AI interpretation** — generated by a named agent
4. **Human decision** — approved, edited, or rejected by a person

Name the columns (`source_type`, `generated_by`, `model`, `model_version`,
`prompt_version`, `run_id`, `approved_by`, `approved_at`) and make the run ledger
traversable end to end:

```
agent_run → proposal → human edit → approval → state transition → external effect
```

That chain is the audit trail. Where it breaks, the system cannot explain itself.

### Design system

Confirm with the user whether the project has an existing brand palette before rendering
the first HTML. If not, use a clean default:

- **Fonts:** Inter (body), a serif for headings, a monospace for code/labels
- **Palette:** choose a primary and accent color that distinguish from generic templates
- **Radius:** `--radius: 14px` for containers, `100px` for pills
- Both light and dark section themes via CSS custom properties
- Accessibility: `prefers-reduced-motion`, `:focus-visible`, keyboard navigation, ARIA roles on tabs

### Component contract — copy these, don't reinvent them

The house style is not just tokens. These four components are what make the document a
design record rather than a styled page.

**Plate head** — carries the C4 altitude:

```html
<section class="plate" id="c1">
  <div class="plate-head">
    <span class="plate-num">C1</span>
    <h2 class="plate-title">System Context</h2>
    <span class="plate-tag">zoom: the whole system as one box</span>
  </div>
  <p class="plate-sub">One paragraph: what this plate claims, and why it matters.</p>
  <!-- figure, then facts table -->
</section>
```

```css
.plate { margin-bottom: 76px; scroll-margin-top: 92px; }
.plate-head { display: flex; align-items: baseline; gap: 16px;
              border-bottom: 1px solid var(--ink); padding-bottom: 10px; margin-bottom: 10px; }
.plate-num  { font-family: "IBM Plex Mono", monospace; font-size: 12px; font-weight: 600;
              letter-spacing: .08em; color: var(--accent); padding: 3px 8px;
              background: var(--accent-soft); border-radius: 6px; flex: none; }
h2.plate-title { font-family: var(--heading-font), Georgia, serif; font-weight: 500;
                 font-size: clamp(1.5rem, 3vw, 1.95rem); letter-spacing: -.012em;
                 margin: 0; flex: 1; }
.plate-tag  { font-family: "IBM Plex Mono", monospace; font-size: 11px;
              color: var(--ink-faint); flex: none; }
.plate-sub  { color: var(--ink-faint); font-size: .935rem; margin: 0 0 30px; max-width: 74ch; }
```

**Figure frame** — the wrapper that keeps wide diagrams legible on mobile:

```css
figure { margin: 0 0 28px; background: var(--surface); border: 1px solid var(--rule);
         border-radius: var(--radius); box-shadow: var(--shadow); overflow: hidden; }
.fig-scroll { overflow-x: auto; padding: 26px 24px 8px; }
figure svg  { display: block; width: 100%; min-width: 640px; height: auto; }
figcaption  { font-size: .875rem; color: var(--ink-soft); padding: 14px 24px 18px;
              border-top: 1px solid var(--rule-soft); background: var(--surface-alt); }
figcaption b { color: var(--ink); font-weight: 600; }
.svg-title { font-family: "Inter", sans-serif; font-size: 12.5px; font-weight: 600; fill: currentColor; }
.svg-label { font-family: "IBM Plex Mono", monospace; font-size: 11px; fill: currentColor; }
.svg-edge  { font-family: "IBM Plex Mono", monospace; font-size: 9.5px; fill: currentColor; opacity: .72; }
.svg-band  { font-family: "Inter", sans-serif; font-size: 10px; font-weight: 600;
             letter-spacing: .12em; fill: currentColor; opacity: .5; }
```

**Tab bar** — the mark names the altitude the tab covers:

```html
<nav class="tabs" role="tablist" aria-label="Sections">
  <a href="#overview"     role="tab" data-tab="overview"     aria-selected="true"><span class="tab-mark">◈</span>Overview</a>
  <a href="#architecture" role="tab" data-tab="architecture" aria-selected="false"><span class="tab-mark">C1–C2</span>Architecture</a>
  <a href="#components"   role="tab" data-tab="components"   aria-selected="false"><span class="tab-mark">C3</span>Components</a>
  <a href="#platform"     role="tab" data-tab="platform"     aria-selected="false"><span class="tab-mark">C3·6</span>Platform</a>
  <a href="#delta"        role="tab" data-tab="delta"        aria-selected="false"><span class="tab-mark">Δ</span>Delta</a>
</nav>
```

Tabs are `<a href="#...">`, not `<button>` — they must be linkable and open in a new tab.

**Hash router** — required. Without it no plate and no delta row is addressable, and the
Delta tab cannot be cited from an issue. `TAB_OF` maps every in-document anchor to its
owning tab so a deep link opens the right panel *and* scrolls:

```js
(function () {
  var TAB_OF = {
    'c1': 'architecture', 'c2': 'architecture', 'd1': 'architecture',
    /* …one entry per plate id… */
  };
  for (var i = 1; i <= 40; i++) TAB_OF['d' + i] = 'delta';   // every delta row

  var tabs = document.querySelectorAll('.tabs a[data-tab]');
  var panels = document.querySelectorAll('.tab-panel');

  function show(name) {
    panels.forEach(function (p) { p.classList.toggle('is-active', p.id === 'tab-' + name); });
    tabs.forEach(function (t) { t.setAttribute('aria-selected', String(t.dataset.tab === name)); });
  }

  function route() {
    var h = decodeURIComponent(location.hash.replace('#', ''));
    var anchor = null, tab;
    if (h && document.getElementById('tab-' + h)) { tab = h; }
    else if (h && TAB_OF[h]) { tab = TAB_OF[h]; anchor = h; }
    else { tab = 'overview'; }
    show(tab);
    if (anchor) {
      requestAnimationFrame(function () {
        var el = document.getElementById(anchor);
        if (el) el.scrollIntoView({ block: 'start' });
      });
    } else { window.scrollTo(0, 0); }
  }

  window.addEventListener('hashchange', route);
  route();
})();
```

A click handler that only toggles classes and calls `scrollTo(0,0)` is the failure mode
this replaces — it looks identical in a browser and makes the whole document uncitable.

**TOC** — closes the Overview tab, one row per plate:

```css
.toc a { display: block; padding: 10px 12px; border-radius: 8px; text-decoration: none; }
.toc a:hover, .toc a:focus-visible { background: var(--accent-soft); }
.toc .t-num  { font-family: "IBM Plex Mono", monospace; font-size: 11px; color: var(--accent); }
.toc .t-name { font-size: .9rem; font-weight: 500; }
.toc .t-desc { font-size: .78rem; color: var(--ink-faint); display: block; margin-top: 2px; }
```

### Diagram rules

**Every plate MUST contain one inline `<svg viewBox>` and one `<figcaption>`. A plate
with no figure is incomplete.** A list of box names is not a diagram — if the boxes carry
no arrows, nothing has been said about the mechanism. This is the rule most likely to be
skipped under output pressure; skipping it makes the document a styled outline. When
running low on budget, cut plates, never figures: five plates with figures beat twelve
without.

- Depict the **mechanism**, not the name: the path a request takes, what enforces
  tenancy on each side.
- **Caption the negative space** — what is deliberately NOT an arrow is often the
  design's strongest claim.
- Label every arrow; one figure, one claim; `currentColor` + theme tokens.
- Colour is semantic, never decorative: wrap a `<g>` in `color: var(--planned)` and the
  strokes, fills and text inside inherit the build state through `currentColor`.

**The `<figcaption>` carries the argument, not a description.** One bold sentence stating
the claim, then the consequence that follows from it. If the caption could be deleted
without losing information, the figure was decoration:

```html
<figcaption>
  <b>No LLM sits on the request path.</b> Enrichment, entity resolution and scene
  detection are all called <em>offline</em> by the pipeline; the serving path reads only
  precomputed attributes — which is why the p50 budget holds even though every displayed
  attribute was produced by a model.
</figcaption>
```

### SVG skeleton — copy this

Inline SVG, no libraries, no external requests. `viewBox` width 940; height to fit.

```html
<figure>
  <div class="fig-scroll">
    <svg viewBox="0 0 940 470" role="img" aria-label="<one sentence describing the whole
         figure for a screen reader — actors, dependencies, and the direction of each edge>">
      <defs>
        <marker id="ar" viewBox="0 0 10 10" refX="9" refY="5"
                markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor"/>
        </marker>
      </defs>

      <text class="svg-band" x="20" y="26">PEOPLE</text>

      <!-- A node group: colour set once on the <g>, inherited via currentColor -->
      <g color="var(--ink)">
        <rect x="20" y="40" width="176" height="66" rx="4"
              fill="var(--surface-alt)" stroke="currentColor" stroke-width="1.2"/>
        <text class="svg-title" x="108" y="66" text-anchor="middle">Actor Name</text>
        <text class="svg-label" x="108" y="86" text-anchor="middle" opacity=".7">role description</text>
      </g>

      <!-- SPECIFIED / not-yet-built nodes: state colour + dashed stroke -->
      <g color="var(--planned)">
        <rect x="704" y="370" width="216" height="62" rx="4" fill="var(--planned-bg)"
              stroke="currentColor" stroke-width="1.4" stroke-dasharray="5 3"/>
        <text class="svg-title" x="812" y="394" text-anchor="middle">Planned Component</text>
      </g>

      <!-- Edges: every one labelled -->
      <g color="var(--ink-soft)">
        <line x1="348" y1="288" x2="348" y2="370"
              stroke="currentColor" stroke-width="1.3" marker-end="url(#ar)"/>
        <text class="svg-edge" x="354" y="332">SQL under RLS</text>
      </g>
    </svg>
  </div>
  <figcaption><b>The claim.</b> The consequence.</figcaption>
</figure>
```

Rules that make this render correctly:

- **`marker` ids must be unique per figure** (`ar`, `ar2`, `ar3`...). Duplicate ids across
  figures silently resolve to the first, and later arrowheads vanish.
- `role="img"` + a full-sentence `aria-label` on every `<svg>`. The label describes the
  *relationships*, not the shapes.
- Text classes are `.svg-title` (node names), `.svg-label` (node subtitles), `.svg-edge`
  (arrow labels), `.svg-band` (zone headers). They set `fill: currentColor` — never
  hardcode a hex in a diagram.
- The `.fig-scroll` wrapper plus `figure svg { min-width: 640px }` is what keeps a wide
  diagram scrollable on mobile instead of illegibly squashed.
- Dashed stroke = not built. Solid = built. Applied consistently, the reader sees build
  state without reading a single pill.

### Build-state vocabulary — applied to every box, row, and pill

`BUILT` (code exists, tested) · `BUILT, NOT WIRED` (code exists, not connected to
live data/server) · `SPECIFIED` (designed, not written) · `GAP / BACKLOG` (named, not
designed). Never mark an intention as a plan: SPECIFIED requires a spec to point at.

**These four are the only vocabulary permitted in a State column.** No prose states — not
"Built, no tests", not "Live on Vercel", not "Partially done". Prose states cannot be
counted, cannot be filtered, and quietly reintroduce the ambiguity the four-state
vocabulary exists to remove. Nuance goes in a separate `Note` column, never in the state.

Render every state as a pill, never as an ad-hoc styled span:

```html
<span class="pill p-built">BUILT</span>
<span class="pill p-partial">BUILT, NOT WIRED</span>
<span class="pill p-planned">SPECIFIED</span>
<span class="pill p-absent">GAP</span>
```

```css
.pill {
  display: inline-block; font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 10px; font-weight: 500; letter-spacing: .05em;
  padding: 4px 10px; border-radius: 100px; white-space: nowrap;
}
.p-built   { background: var(--built-bg);   color: var(--built); }
.p-partial { background: var(--partial-bg); color: var(--partial); }
.p-planned { background: var(--planned-bg); color: var(--planned); }
.p-absent  { background: var(--absent-bg);  color: var(--absent); }
```

State tokens (light; redefine each under the dark-section selector):

```css
--built: #1B7F5C;   --built-bg: #E2F1EA;
--partial: #A34509; --partial-bg: #FDE6D2;
--planned: #1B2F79; --planned-bg: #E4E9FB;
--absent: #77818E;  --absent-bg: #E9ECEF;
```

An inline `style="font-size:11px"` repeated at each tag site is the signal this rule was
skipped — one component, four modifiers, defined once.

### The Delta tab — the document's sync point

**The delta numbers come from `.claude/specs/roadmap.md`. Never mint your own.**

That registry owns every `D{n}` and `C{n}`; the Delta tab *renders* it. Read it, render its
rows in dependency order, and carry each row's state and "needs first" through unchanged.
If a plate needs a delta row that does not exist, add the row to the registry first — then
cite it.

This rule exists because the alternative already happened in a prior project (diskoe): the
design record and the component specs each minted `D1`-`D18` independently and agreed on
**none** of them, so no number in the repo was safe to cite from an issue.

If no registry file exists, create it before the Delta tab, seeded from the plates.


This tab is the seam to `/design-roadmap`, which files GitHub issues against it. If a
delta row cannot be linked to, the next stage has nothing mechanical to cite and falls
back to re-deriving the build queue by hand. **Addressability is the requirement**, not a
polish item.

- **Stable row IDs** (D1, D2, ...) that issues and plans cite; never renumber, only append.
- **"Needs first" column** — the dependency order that makes issue-filing mechanical.
- **Cross-links both ways** — every non-BUILT pill links to its D row; every D row links to the plate.
- **Decision register** — each unratified decision names what it blocks and who decides.
- **PRD coverage table** — every PRD § with its current state and evidence.

#### Required markup

Every delta row carries an `id`, and every non-BUILT state marker anywhere in the
document carries a link back to it:

```html
<!-- In the Delta tab -->
<tr id="d7">
  <td class="dnum">D7</td>
  <td>Server-side HITL tier derivation</td>
  <td><span class="pill p-planned">SPECIFIED</span></td>
  <td>D3</td>                                    <!-- Needs first -->
  <td><a href="#c3-component">C3 · Component</a></td>    <!-- back-link to the plate -->
  <td>EM</td>
</tr>

<!-- At every use site, in any tab -->
<span class="pill p-planned">SPECIFIED</span> <a class="dnum" href="#d7">D7</a>
```

Add `tr[id] { scroll-margin-top: 92px; }` so a deep link does not land under the sticky
tab bar.

#### PRD coverage table

Last section of the Delta tab. One row per PRD `§`, so a reviewer can confirm the design
covers the requirements without reading both documents side by side. An uncovered section
is a finding, not an omission — list it with `GAP` rather than leaving the row out:

```html
<tr>
  <td>§8</td>
  <td>Responsibility matrix</td>
  <td><span class="pill p-built">COVERED</span></td>
  <td><a href="#c2">C2 · Containers</a>, <a href="#arch-matrix">Architecture · matrix</a></td>
</tr>
```

Columns: PRD §, section name, coverage state, evidence (links to the plates that cover
it). Use the same four-state vocabulary, reading COVERED / PARTIAL / SPECIFIED / GAP.

### Honesty rules

- Verify every build-state claim against the working tree at publication. **If there is
  no working tree, no component may be marked `BUILT`** — the honest state is `SPECIFIED`,
  and the footer says build state was unverifiable.
- The footer names sources and states the re-verify rule.
- A confident design for an unbuilt thing is SPECIFIED, drawn dashed.

### Altitude split — what belongs in the HTML vs the specs

The design of record and the deep specs are two artifacts at two altitudes. The
rule that decides which content goes where:

> **Does this demonstrate engineering JUDGMENT, or engineering DETAIL?**
> Judgment stays in the HTML. Detail moves to `.claude/specs/`.

**Stays in the design of record (Output 1):**

- System architecture — C1 context, C2 containers, runtime/container view
- Intelligence architecture — what each agent decides, how agents compose
- Lifecycle — the gated state machine (C2.1), who may transition, what blocks
- Data & memory as concept — entity relationships, what is structured vs blob
- Human oversight as a principle — HITL tiering rationale, the approval model
- Provenance as a concept — the audit chain from model output to external effect
- Evaluation philosophy — what is graded, why, the role of deterministic fallback
- Current build state — verified against the tree, not claimed
- Roadmap / delta — the build queue and decision register
- Key architectural decisions — condensed to the claim and its consequence

**Moves to engineering specs (Output 2):**

- Exact SQL schema — `CREATE TABLE` DDL, column types, index definitions
- Individual RLS policies — per-table `USING` / `WITH CHECK` clauses
- HTTP status codes and response shapes — `4xx` / `5xx` semantics per endpoint
- `SELECT ... FOR UPDATE` and locking semantics
- Idempotency implementation — the specific key and the specific guard
- Exact filenames and line numbers
- API payload schemas — field-by-field `{ input, output }` contracts
- Every model field — column names, types, nullability, defaults
- Detailed failure matrix — per-endpoint, per-status-code behaviour
- Exact GitHub issue numbers and milestone assignments
- Migration version numbers and file paths
- Individual test cases with input/output fixtures
- GitHub Action implementation — workflow YAML, job definitions
- MCP resource definitions — tool schemas, handler signatures
- CRM sync conflict rules — field-level merge precedence
- Plugin/extension registration contracts — hook signatures, lifecycle callbacks

**The test in practice.** These are architectural principles — they belong in the
founder-facing document:

- "AI output is a proposal, not a state change"
- "One system of record per operational capability"
- "Realtime is UI synchronization, not the domain event bus"
- "Deterministic fallback exists independently of the model"
- "Provenance follows content through model → proposal → edit → approval → action"

Their *implementations* — the exact column that stores provenance, the SQL that
enforces idempotency, the RLS policy that blocks a direct state write — belong in
the specs. Cut the implementation from the HTML when applying this rule; never cut
the principle in the name of "less technical."

**Plate numbering is not affected.** The C4-derived plate numbers (C1, C2, C3,
C3.<n>, D1-D*n*) are structural — `.plate-head` carries them and specs are
addressed as `C3.<n>`. Do not rename them. The tab bar already permits
plain-language tab *names* (the text after `<span class="tab-mark">`) — use that
for audience-friendly labels rather than changing the numbering scheme.

## Output 2 — Deep component specs (`.claude/specs/`)

### Spec home — `.claude/specs/`

Specs live in `.claude/specs/` — tracked in git, read by agents before building,
organized by architectural lane:

```
.claude/specs/
  # Root — scope + cross-cutting
  design-scope.md
  design-requirements.md
  roadmap.md

  # Stack refs (how to write code in this repo)
  stack/

  # Lane specs
  platform/
    agents/      — one per agent
    services/    — one per service
    infra/       — eval harness, model gateway, observability, orchestration
```

### Spec format — deep enough to build from, not just contract-check

For every plate in C3 and every platform module, produce a spec that carries both
the **engineering depth** (mechanism, rubrics, edge cases, decision rationale,
requirement trace) and the **build contract** (input/output types, delta rows,
test cases). A builder agent reads this single file and has everything it needs.

Write `.claude/specs/platform/{agents,services,infra}/<component>.md`:

```markdown
# <Component Name>
**Plate:** C3.<n> in docs/<project>-system-design.html
**Status:** <BUILT | BUILT NOT WIRED | SPECIFIED | GAP>
**Status note:** <one line: what exists, what doesn't, where code lives>
**PRD sections:** §<n>, §<n>

## Purpose
<What this component decides or produces. Why it exists — the problem it solves,
not just what it does. 2-3 sentences.>

## 1. <Primary mechanism>
<Deep description of how it works. The path a request takes, the algorithm,
the rubric, the taxonomy. Name the functions and files. Include findings
("the spec says X but the code does Y — carried as intentional / flagged as
divergence"). This is the section a builder reads to understand WHY the design
is shaped the way it is, not just WHAT it does.>

### <Subsection as needed>
<Tables (scoring rubrics, dimension definitions), edge cases, computed values.>

## 2. <Secondary mechanism / concern>

## Contract
- **Input:** <type name, fields, where it comes from — be specific about every field>
- **Output:** <type name, fields, where it goes>
- **Side effects:** <what it writes to the database, what it triggers>

## Rules
<The invariants — what must always be true. Include both mechanical rules and
design-intent rules.>
- <rule 1>
- <rule 2>

## HITL Tier
<Which tier and WHY — the rationale matters for future decisions.>

## Deterministic Fallback
<What happens when the model call fails. Is this a true fallback or the only path?
Name the function.>

## Dependencies
- **Imports:** <what this component uses, with file paths>
- **Imported by:** <what uses this component>
- **Data:** <tables it reads/writes, with migration references>

## Delta rows
- D<N>: <description> — <BUILT | SPECIFIED | GAP>

## Test contract
<Concrete test cases with acceptance criteria. Name the edge cases.>
- <test 1: specific input → expected output>
- <test 2: boundary case>

## Open questions
<Numbered. Each names who must answer and what it blocks.>
1. <question — *who*>

## Requirement Trace
<Full table: every requirement from prior art, where it came from, where it
landed, and whether it was carried, changed, or dropped — with rationale.>

| Old requirement | Source | Now at | Status |
|---|---|---|---|
| <requirement> | <source doc §section> | <current location> | Carried / Changed — <why> / Dropped — <why> |
```

### Spec depth rules

- **Read the code before writing the spec.** Grep for the function, read the file,
  name the line. A spec that describes code without reading it is fiction.
- **Name divergences.** When the code and a prior spec disagree, say so explicitly:
  "The spec says X; the code does Y. Carried as intentional / flagged as drift."
- **Record what was dropped and why.** A requirement that disappeared without a trace
  is a bug; one that was dropped with rationale is a decision.
- **The requirement trace is mandatory.** It is the audit trail from prior art
  to current state. Without it, the next person who reads the spec cannot distinguish
  "we decided not to do this" from "we forgot."
- **Open questions name their owner.** "TBD" is not an open question. "Should the
  intake auto-create a Business record? — PM" is.
- **One spec per component.** An agent gets one file. A service gets one file.
  Don't merge unrelated components; don't split one component across files.
- **Specs cite Delta rows.** Every open item maps to a D row in the design record.
- **Merge forward, don't flatten.** If a prior spec exists in `.claude/specs/`, read
  it and carry forward its engineering context, findings, and requirement traces.
  The new spec should be deeper than the old one, never shallower.

## HITL Gates

This skill has two mandatory pause points. Do not proceed past either without
explicit user approval.

### Gate 1 — Spec review

After writing or updating `.claude/specs/platform/{agents,services,infra}/*.md`:

1. Present a summary: which specs were created/updated, key decisions made vs deferred,
   divergences found between code and prior specs
2. List every open question from the specs (the `## Open questions` sections)
3. **Stop and ask:** "Component specs are ready for review. Check the specs in
   `.claude/specs/` and let me know what to revise — or approve to proceed to HTML."
4. Do NOT render HTML until the user approves

### Gate 2 — HTML review

After rendering Architecture + Components + Platform tabs to the HTML:

1. Run the publication checklist (diagram count, delta anchors, etc.)
2. Present the checklist results and any gaps
3. **Stop and ask:** "HTML tabs rendered. Open the file and review — or approve to
   continue to `/design-roadmap`."

The Overview tab should already exist from `/design-product`. Do not overwrite it —
only update if the PRD has changed since it was rendered.

## Process

1. **Read inputs:** design doc, PRD, existing `.claude/specs/`, and the working tree
   (migrations, src layout, api surface, CI). Grep before you claim. Also read any
   feasibility or requirements docs the project has — they carry the requirement IDs
   this design must trace to. If there is no working tree, say so and design from the docs.
2. **Ask questions** where the design has ambiguous decisions, multiple valid options,
   or contradictions between source documents. Do not guess — surface the decision
   to the user.
3. **Write deep specs** for each plate + platform module, reading the code for each.
4. **HITL Gate 1** — present specs for review. Stop until approved.
5. **Render HTML** — Architecture + Components + Platform tabs only. Do not touch the
   Overview tab (owned by `/design-product`) or the Roadmap tab (owned by
   `/design-roadmap`). If those tabs do not exist yet, leave placeholder panels.
6. **HITL Gate 2** — run publication checklist, present results, stop until approved.
7. **Verify** against the full publication checklist below before finishing.

## Publication checklist — run this, don't assume it

Each of these is grep-checkable, and each has silently failed in a real run. Check them
against the file you just wrote, not against your intent:

```bash
F="docs/<project>-system-design.html"
grep -c '<svg viewBox'  "$F"   # >= one per plate — 0 means the document has no diagrams
grep -c '<figcaption'   "$F"   # must equal the <svg viewBox> count
grep -c 'id="d'         "$F"   # >= one per delta row
grep -c 'href="#d'      "$F"   # >= one per non-BUILT marker
grep -c 'class="pill'   "$F"   # 0 means build state was rendered as ad-hoc tags
grep -c 'hashchange'    "$F"   # 1 — the router is present
grep -c 'class="toc'    "$F"   # 1 — Overview closes with a TOC
grep -c 'plate-num'     "$F"   # >= one per plate
```

Then verify by reading, not counting:

- Every build-state claim matches the working tree. Grep the file you cite; a `BUILT`
  claim with no file behind it is the one failure that discredits the whole document.
  With no tree present, confirm nothing is marked `BUILT`.
- No State column contains prose. Four states only.
- Every `<svg>` has a unique `marker` id, `role="img"`, and a full-sentence `aria-label`.
- Every figcaption states a claim, not a description of the picture.
- Every PRD `§` appears in the coverage table, including the uncovered ones.
- The footer names its sources and the re-verify rule.
- **The semantics plate has a row for every concern**, each specified or explicitly
  deferred — lifecycle, idempotency, concurrency, failure taxonomy, async boundary,
  structured-vs-blob. A missing row reads as "handled" when it means "never considered".
- **Every spec section is surfaced or listed as out of scope.** Walk `.claude/specs/`
  against the plates — stack refs and infra specs included.
- **Provenance is a data-model rule**, not a UI note, wherever a model generates content a
  human reads.
- **Every delta number in the document exists in `.claude/specs/roadmap.md`** with the same
  meaning. No number was invented, reused, or renumbered.

**If the diagram count is zero, the document is not publishable.** Go back to step 3 —
that is the deliverable, and no amount of correct tables substitutes for it.

## The gate

**No execute work begins on a system whose design record does not cover it.** A new
workstream first lands as SPECIFIED plates + D rows here; then `/design-roadmap`
cuts milestones and files issues referencing `.claude/specs/` as the build contract.

---

**Tab ownership model** — the HTML is built incrementally:

| Skill | Owns these tabs | Must not touch |
|---|---|---|
| `/design-product` | Overview | Architecture, Components, Platform, Roadmap |
| `/design-system` (this) | Architecture, Components, Platform | Overview, Roadmap |
| `/design-roadmap` | Roadmap (milestones, delta, issues) | Overview, Architecture, Components, Platform |

**Upstream:** `/design-initiative` (design doc) + `/design-product` (PRD + Overview tab).

**Next step:** `/design-roadmap` — the trio (PM, EM, Designer) takes the design record's
plates, D table, and the component specs, and plans the roadmap: milestones, dependencies,
and GitHub issues. Each issue references its `.claude/specs/platform/.../<component>.md`
as the build contract.
