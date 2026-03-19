# Research Brief: Replace interface-design and visual-explainer Skills

**Date**: 2026-03-19
**Status**: Ready for Decision
**Proposal**: Replace `mine.interface-design` and `vx.visual-explainer` with focused replacement skill(s) that produce HTML mockups with integrated design direction
**Initiated by**: User pain points -- skills are too bloated, wrong output for UI work, overlap causes routing confusion

## 1. Current State

### mine.interface-design (SKILL.md: 290 lines)

**What it does**: Design direction and craft guidelines for building real application UIs (dashboards, admin panels, SaaS tools). Phases:

1. **Intent First** -- answer who/what/feel questions before touching code
2. **Product Domain Exploration** -- domain concepts, color world, signature element, default rejection
3. **Self-Review** -- swap test, squint test, signature test, token test
4. **Craft Foundations** -- subtle layering, surface elevation, color philosophy
5. **Design Principles** -- token architecture, spacing, depth, typography, cards, controls, icons, animation, states, nav context, dark mode
6. **Workflow** -- check for `.interface-design/system.md`, suggest + ask, save patterns after

**Supporting files**:
- `references/principles.md` (113 lines) -- code-level CSS patterns, border approaches, spacing examples, typography cheat sheet
- `commands/mine.interface-design.md` (90 lines) -- command wrapper that loads skill + references, adds "Shape Before You Design" phase

**Key observation**: This skill is entirely about *design thinking and craft principles*. It does NOT generate HTML files. It produces direction/decisions that get applied when building real application code (React, Vue, Svelte, etc.). The output is UI code in the project, not standalone HTML mockups.

### vx.visual-explainer (SKILL.md: 479 lines)

**What it does**: Generate self-contained HTML files for technical visualizations. Phases:

1. **Think** -- choose audience, content type, aesthetic direction
2. **Structure** -- pick rendering approach (Mermaid, CSS Grid, tables, etc.), read templates
3. **Style** -- typography, color, surfaces, animation, anti-slop rules
4. **Deliver** -- write to `~/.claude/diagrams/`, open in browser

**Supporting files** (7,293 total lines):
- `references/css-patterns.md` (1,813 lines) -- CSS patterns, overflow protection, Mermaid zoom controls, code blocks, image containers
- `references/libraries.md` (612 lines) -- Mermaid theming, Chart.js, font pairings, anime.js
- `references/responsive-nav.md` (212 lines) -- sticky sidebar TOC + mobile nav
- `references/slide-patterns.md` (1,406 lines) -- slide deck engine, 10 slide types, presets
- `templates/architecture.html` (596 lines) -- CSS Grid card architecture template
- `templates/data-table.html` (540 lines) -- styled data table template
- `templates/mermaid-flowchart.html` (724 lines) -- Mermaid with zoom/pan controls
- `templates/slide-deck.html` (919 lines) -- full slide deck reference
- 8 command files (471 lines total) -- diff-review, fact-check, generate-slides, generate-visual-plan, generate-web-diagram, plan-review, project-recap, share
- `scripts/share.sh` -- Vercel deployment script

**Key observation**: This is a *content visualization engine*. It turns any content (architecture, diffs, plans, data) into polished HTML pages. The HTML generation infrastructure (templates, CSS patterns, Mermaid/Chart.js integration, anti-slop rules) is the valuable core. The 8 subcommands are all *consumption modes* for different content types.

### mine.human-centered-design (SKILL.md: 294 lines)

**What it does**: Empathy, accessibility, progressive enhancement, inclusive patterns. Sits **upstream** of interface-design in a declared pipeline:

1. HCD (understand the human)
2. interface-design (craft the visual system)
3. ux-antipatterns (verify the implementation)

**Supporting files**: `references/patterns.md`, `references/testing.md`

### The overlap problem

The skills serve different purposes but the user's actual workflow creates confusion:

| User intent | Current routing | Problem |
|---|---|---|
| "Design a dashboard" | `mine.interface-design` | Produces design *thinking* but no visual output to look at |
| "Show me what it looks like" | `vx.visual-explainer` | Produces HTML but has no design direction -- defaults to generic aesthetics |
| "Design this UI and show me" | ??? | Two skills needed, neither connects to the other |

The real pain: **design direction never leads to a viewable mockup**, and **mockup generation has no design process upstream**. They are two halves of one workflow that were never connected.

## 2. Cross-References

### Files that reference these skills

**Routing (capabilities.md)**:
- Line 28: `"generate a diagram", "visualize this", ...` -> `/vx.visual-explainer`
- Line 29: `"design this UI", "design this dashboard", ...` -> `/mine.interface-design`

**Skill-to-skill references**:
- `mine.human-centered-design/SKILL.md` lines 274, 292: references `mine.interface-design` as downstream in pipeline
- `mine.interface-design/SKILL.md` lines 28, 288: references `mine.human-centered-design` as upstream
- `mine.interface-design/SKILL.md` line 291: references `mine.ux-antipatterns` as downstream

**CLAUDE.md**: Lines 50, 58 mention `vx.*` prefix as example of imported skill packs

**README.md**:
- Line 33: describes `vx.` prefix convention
- Line 58: `mine.interface-design` in skills table
- Line 76: `vx.visual-explainer` in skills table (with full subcommand list)
- Line 85: `mine.interface-design` in commands table
- Lines 93-100: all 8 vx subcommands in commands table

**Top-level command aliases** (8 files in `commands/`):
- `vx.diff-review.md`, `vx.fact-check.md`, `vx.generate-slides.md`, `vx.generate-visual-plan.md`, `vx.generate-web-diagram.md`, `vx.plan-review.md`, `vx.project-recap.md`, `vx.share.md`

**No references from**: agents/, settings.json, personal capabilities.md, frontend-workflow.md, ux-antipatterns skill

## 3. What's Worth Salvaging

### From mine.interface-design -- KEEP (for mockup design direction)

- **Intent First questions** (lines 26-36): who/what/feel -- concise, effective
- **Product Domain Exploration** (lines 62-74): domain, color world, signature, defaults -- the anti-generic-output framework
- **Self-Review checks** (lines 79-87): swap test, squint test, signature test, token test
- **Component Checkpoint** (lines 129-141): intent/palette/depth/surfaces/typography/spacing declaration
- **Design Principles section** (lines 145-212): token architecture, spacing, depth, typography, controls, animation, states -- these are the "how to not look generic" rules
- **Avoid list** (lines 216-230): concrete anti-patterns

**NOT worth keeping for mockups**:
- `.interface-design/system.md` persistence workflow -- this is for real app codebases, not standalone mockups
- The references/principles.md CSS values -- too specific to real app development, vx has better CSS patterns

### From vx.visual-explainer -- KEEP (for HTML generation)

**Core infrastructure (essential)**:
- HTML file structure pattern (lines 346-365)
- Delivery workflow: write to `~/.claude/diagrams/`, open in browser (lines 197-205)
- Anti-slop rules (lines 412-479) -- forbidden fonts, colors, patterns
- Quality checks (lines 401-410) -- squint test, swap test, overflow, themes

**CSS/template references (essential for quality)**:
- `references/css-patterns.md` (1,813 lines) -- this IS the HTML generation engine
- `references/libraries.md` (612 lines) -- Mermaid theming, Chart.js, font pairings
- `references/responsive-nav.md` (212 lines) -- section navigation patterns
- `templates/architecture.html` -- CSS Grid card layout reference
- `templates/data-table.html` -- styled table reference
- `templates/mermaid-flowchart.html` -- Mermaid with zoom/pan controls

**NOT worth keeping (user wants these tossed)**:
- All 8 subcommands and their command files
- `references/slide-patterns.md` (1,406 lines) -- slides subcommand
- `templates/slide-deck.html` (919 lines) -- slides template
- `scripts/share.sh` -- Vercel deployment
- surf-cli AI image generation workflow
- Proactive table rendering behavior (auto-HTML for ASCII tables)

### From mine.interface-design references/principles.md -- PARTIAL

- Typography cheat sheet (lines 99-113) -- useful, overlaps with vx's `libraries.md` font pairings but approaches it from a different angle (vibes vs specific pairings). Could merge the best of both.
- Surface elevation practice (lines 7-18) -- useful for mockups
- Border approaches (lines 20-37) -- useful for mockups

## 4. Options

### Option A: Single skill -- `mine.mockup`

**How it works**: One skill that combines design direction (Phase 1) with HTML mockup generation (Phase 2). The design direction is a mandatory gate before any HTML is written -- you cannot skip to "just generate HTML" without answering the intent questions.

Phase 1 (Design Direction): adapted from interface-design's Intent First, Domain Exploration, and Component Checkpoint. Produces a design brief in the conversation (not a file). Asks user to confirm direction.

Phase 2 (HTML Generation): adapted from vx.visual-explainer's structure/style/deliver workflow, stripped of all subcommands, slides, and non-mockup content types. Uses the same templates and CSS patterns references.

Phase 3 (Deliver + Review): write HTML to `~/.claude/diagrams/`, open in browser, run self-review checks (combining both skills' checklists).

**File structure**:
```
skills/mine.mockup/
  SKILL.md                      (~300-350 lines, merged from both)
  references/
    css-patterns.md             (kept from vx, trimmed of slide-specific content)
    libraries.md                (kept from vx)
    responsive-nav.md           (kept from vx)
    principles.md               (kept from interface-design, slimmed)
  templates/
    architecture.html           (kept from vx)
    data-table.html             (kept from vx)
    mermaid-flowchart.html      (kept from vx)
commands/mine.mockup.md         (~40-50 lines)
```

**Pros**:
- Single invocation point -- no routing confusion
- Design direction is always applied -- prevents generic HTML output
- User's stated preference: "design direction integrated into the mockup skill"
- Simplest mental model: "I want a UI mockup" -> `/mine.mockup`
- Removes 8 subcommands and their routing entries

**Cons**:
- Design direction phase adds friction when user already knows what they want
- Loses the ability to use interface-design for real app code (not mockups) -- but the user said design direction "always leads to building UI" so this may not matter
- Large skill file if not careful (both source skills are 290 + 479 lines)

**Effort estimate**: Medium -- the content exists in both skills, this is primarily a merge and trim exercise. The references/ and templates/ files are mostly kept as-is (minus slide content).

**Dependencies**: None new. Drops vx.visual-explainer's optional surf-cli and vercel dependencies.

### Option B: Two skills -- `mine.design-direction` + `mine.mockup`

**How it works**: Lightweight `mine.design-direction` outputs a design brief (intent, palette, typography, spacing decisions). Separate `mine.mockup` consumes that brief and generates HTML. The design-direction skill could also feed into real app code work (the original interface-design use case).

**Pros**:
- Preserves design direction as a reusable standalone step
- mockup skill stays focused on HTML generation
- Design direction can feed into `mine.build` for real app code too

**Cons**:
- Two invocations required for the common case ("design and show me a mockup")
- Passing state between skills is fragile (write brief to file? embed in conversation?)
- User explicitly said they want design direction *integrated into* the mockup skill
- More files to maintain

**Effort estimate**: Medium -- same merge work plus the state-passing mechanism design.

**Dependencies**: None new.

### Option C: Slim down mine.interface-design + extract mine.mockup from vx

**How it works**: Keep `mine.interface-design` but strip it to ~100 lines of pure design direction (no craft foundations, no extensive principles). Create `mine.mockup` from vx.visual-explainer's core, but have it auto-invoke interface-design's direction phase internally.

**Pros**:
- Preserves interface-design as a named concept
- HCD pipeline reference (`HCD -> interface-design -> ux-antipatterns`) stays intact
- Less disruptive to existing skill references

**Cons**:
- Still two skills that are tightly coupled
- The "auto-invoke" mechanism doesn't really exist -- skills are prompt templates, not callable functions
- Maintaining two skills for what is effectively one workflow adds overhead
- User's stated preference is to toss the current approach, not preserve it

**Effort estimate**: Medium-Large -- more careful surgery to preserve the right pieces in the right places, and the auto-invoke pattern needs design.

**Dependencies**: None new.

### Option D: Do less -- just delete vx, slim interface-design, add HTML output

**How it works**: Delete all of vx.visual-explainer. Slim down interface-design to add an "HTML Mockup Output" phase at the end that writes a self-contained HTML file. Pull in just the essential CSS patterns from vx.

**Pros**:
- Minimal new files
- Preserves the interface-design name and HCD pipeline
- Smallest change footprint

**Cons**:
- Loses vx's extensive template library and CSS patterns (the best part of vx)
- interface-design would need to grow to include HTML generation guidance, making it bloated again
- The skill name "interface-design" doesn't clearly signal "generates HTML mockups"
- Trying to preserve the old structure while changing the behavior

**Effort estimate**: Small-Medium -- but the output quality would be lower without vx's infrastructure.

**Dependencies**: None new.

## 5. Recommended Approach

**Option A: Single `mine.mockup` skill.**

Rationale:
1. The user explicitly said design direction should be *integrated into* the mockup skill, not standalone
2. The user said design direction "always leads to building UI" -- there is no standalone use case they care about
3. The overlap problem is fundamentally that two skills exist for one workflow. One skill solves it.
4. vx.visual-explainer's HTML generation infrastructure is excellent and should be preserved, but the 8 subcommands and slide engine are bloat
5. interface-design's design thinking framework is excellent and should be preserved, but the `.interface-design/system.md` persistence and real-app-code focus are not needed for mockups

The merge is natural: interface-design's Phase 1 (direction) feeds directly into vx's Phase 2-3 (structure/style/deliver). They were always two halves of one skill.

### What about HCD?

`mine.human-centered-design` currently references `mine.interface-design` as downstream. Update it to reference `mine.mockup` instead. The pipeline becomes: `HCD -> mockup -> ux-antipatterns`. This is actually better -- HCD's empathy work now directly produces a viewable artifact instead of abstract design tokens.

### What about real app UI work?

The design direction principles (intent-first, domain exploration, anti-defaults) are universally valuable. They should live in `mine.mockup`'s Phase 1 but the principles are also useful when building real app code via `mine.build`. Consider extracting the core design-direction questions into a lightweight reference file that both `mine.mockup` and `mine.build` can point to. But this is a future optimization, not a blocker.

## 6. Cleanup Manifest

### Files to CREATE

| File | Source | Notes |
|---|---|---|
| `skills/mine.mockup/SKILL.md` | Merge of interface-design + vx core | ~300-350 lines |
| `commands/mine.mockup.md` | New, adapted from `commands/mine.interface-design.md` | ~40-50 lines |

### Files to MOVE (keep from vx.visual-explainer)

| From | To |
|---|---|
| `skills/vx.visual-explainer/references/css-patterns.md` | `skills/mine.mockup/references/css-patterns.md` |
| `skills/vx.visual-explainer/references/libraries.md` | `skills/mine.mockup/references/libraries.md` |
| `skills/vx.visual-explainer/references/responsive-nav.md` | `skills/mine.mockup/references/responsive-nav.md` |
| `skills/vx.visual-explainer/templates/architecture.html` | `skills/mine.mockup/templates/architecture.html` |
| `skills/vx.visual-explainer/templates/data-table.html` | `skills/mine.mockup/templates/data-table.html` |
| `skills/vx.visual-explainer/templates/mermaid-flowchart.html` | `skills/mine.mockup/templates/mermaid-flowchart.html` |

### Files to DELETE

| File | Reason |
|---|---|
| `skills/vx.visual-explainer/SKILL.md` | Replaced by mine.mockup |
| `skills/vx.visual-explainer/references/slide-patterns.md` | Slides subcommand tossed |
| `skills/vx.visual-explainer/templates/slide-deck.html` | Slides subcommand tossed |
| `skills/vx.visual-explainer/commands/diff-review.md` | Subcommand tossed |
| `skills/vx.visual-explainer/commands/fact-check.md` | Subcommand tossed |
| `skills/vx.visual-explainer/commands/generate-slides.md` | Subcommand tossed |
| `skills/vx.visual-explainer/commands/generate-visual-plan.md` | Subcommand tossed |
| `skills/vx.visual-explainer/commands/generate-web-diagram.md` | Subcommand tossed |
| `skills/vx.visual-explainer/commands/plan-review.md` | Subcommand tossed |
| `skills/vx.visual-explainer/commands/project-recap.md` | Subcommand tossed |
| `skills/vx.visual-explainer/commands/share.md` | Subcommand tossed |
| `skills/vx.visual-explainer/scripts/share.sh` | Share feature tossed |
| `skills/mine.interface-design/SKILL.md` | Replaced by mine.mockup |
| `skills/mine.interface-design/references/principles.md` | Merged into mockup refs |
| `commands/mine.interface-design.md` | Replaced by mine.mockup command |
| `commands/vx.diff-review.md` | Subcommand tossed |
| `commands/vx.fact-check.md` | Subcommand tossed |
| `commands/vx.generate-slides.md` | Subcommand tossed |
| `commands/vx.generate-visual-plan.md` | Subcommand tossed |
| `commands/vx.generate-web-diagram.md` | Subcommand tossed |
| `commands/vx.plan-review.md` | Subcommand tossed |
| `commands/vx.project-recap.md` | Subcommand tossed |
| `commands/vx.share.md` | Subcommand tossed |

**Total: 24 files deleted, 6 files moved, 2 files created**

### Files to MODIFY

| File | Change |
|---|---|
| `rules/common/capabilities.md` | Remove vx.visual-explainer routing (line 28), replace interface-design routing (line 29) with `mine.mockup`. Add trigger phrases: "mockup this", "show me what it looks like", "design this UI", "design this dashboard", "craft the interface" |
| `skills/mine.human-centered-design/SKILL.md` | Update 2 references: `mine.interface-design` -> `mine.mockup` (lines 274, 292) |
| `README.md` | Remove vx.visual-explainer entry + all 8 subcommand entries from skills and commands tables. Remove mine.interface-design entries. Add mine.mockup entries. Update prefix convention text (line 33). Update skill/command counts. |
| `CLAUDE.md` | Update lines 50, 58 that reference `vx.*` prefix as example -- either remove the example or use a different one |
| `CHANGELOG.md` | Add entry for the replacement |
| `skills/mine.mockup/references/css-patterns.md` | Trim slide-specific content from the moved file (~200-300 lines of slide patterns can be removed) |

## 7. Open Questions

- [ ] **Skill name**: Is `mine.mockup` the right name? Alternatives: `mine.ui-mockup`, `mine.design`, `mine.prototype`. "Mockup" is clear but slightly narrow -- this skill could also produce visual design explorations, not just screen mockups.
- [ ] **Proactive table rendering**: vx.visual-explainer auto-generates HTML tables when it would otherwise render ASCII. Should this behavior carry over to mine.mockup, or is it out of scope (mockups only)?
- [ ] **Diagram generation**: Should mine.mockup also handle "generate an architecture diagram" requests, or should those be handled differently now that vx is gone? Currently capabilities.md routes "generate a diagram" to vx. Without vx, that routing is orphaned.
- [ ] **HCD pipeline preservation**: The current pipeline is HCD -> interface-design -> ux-antipatterns. Updating to HCD -> mockup -> ux-antipatterns changes the semantics slightly (HCD leads to a *mockup* rather than *design direction*). Is that the right flow, or should HCD just stand alone?
- [ ] **CSS patterns trimming**: The `css-patterns.md` file is 1,813 lines. How aggressively should slide-specific and subcommand-specific content be removed? A lighter trim preserves patterns that might be useful for mockup pages; an aggressive trim keeps the file focused.
- [ ] **Design direction for mine.build**: Should the core design-direction questions (intent, domain, signature, defaults rejection) be extracted into a shared reference that `mine.mockup` and `mine.build` can both use? Or is duplication acceptable given they serve different contexts?
