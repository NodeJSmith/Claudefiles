# Design: Replace interface-design + visual-explainer with look-and-feel, mockup, and build update

**Date:** 2026-03-19
**Status:** archived
**Issue:** #104
**Prior research:** `design/research/2026-03-19-replace-skills/research.md`, `design/research/2026-03-19-replace-skills/design-direction-research.md`
**Critique:** `design/critiques/2026-03-19-replace-skills/critique.md`, `design/critiques/2026-03-19-replace-skills/design-doc-critique.md`

## Problem

Two skills serve disconnected halves of one workflow. `mine.interface-design` produces design thinking (tokens, intent, principles) but no viewable output. `vx.visual-explainer` produces polished HTML but with no design process — it defaults to generic aesthetics. The user's actual need ("plan the UI feel, then show me what it looks like") requires invoking both skills manually, and neither feeds the other.

Additionally, there is no design-direction planning step before writing real frontend code. When `mine.build` touches UI, it has no awareness of design decisions — each session starts from scratch.

The existing skills are also bloated: interface-design is 290 lines of mixed philosophy and implementation guidance, visual-explainer is 480 lines plus 7K lines of references/templates/commands, most of which (slides, diff-review, fact-check, share) are unused.

## Non-Goals

- **No diagram generation.** "Generate an architecture diagram" is dropped as a routed capability. The templates (Mermaid, CSS Grid) survive in mine.mockup for use in UI mockups, but there is no standalone diagram skill.
- **No subcommand replacement.** diff-review, fact-check, plan-review, project-recap, generate-slides, share — all confirmed dead by the user. No migration path needed.
- **No multi-prefix convention.** The `vx.*` prefix system is removed entirely. All skills use `mine.*`.
- **No HCD/ux-antipatterns updates.** Both already removed in PR #105.

## Architecture

### Three skills with `direction.md` as the shared artifact

```
mine.look-and-feel             mine.mockup               mine.build (updated)
        │                           │                          │
        │  writes                   │  reads                   │  reads
        ▼                           ▼                          ▼
   design/direction.md ──────────────────────────────────────────
   (persists across sessions)
```

**`design/direction.md`** is the persistence layer. It lives at the project root under `design/`, alongside `specs/`, `research/`, and `critiques/`. Written by mine.look-and-feel, consumed by mine.mockup and mine.build.

**Scoped directions:** The default file is `design/direction.md`. For projects with multiple visual contexts (admin panel, marketing site, docs), use `design/direction-{scope}.md` (e.g., `design/direction-admin.md`). When multiple direction files exist, mine.mockup and mine.build ask which applies. mine.look-and-feel asks whether to create a new scoped file or update an existing one.

### Skill 1: mine.look-and-feel

**Purpose:** Plan UI design direction before writing code. Produces `design/direction.md` (or `design/direction-{scope}.md`).

**Source material:** Interface-design's Intent First, Domain Exploration, Component Checkpoint, Self-Review. Design-direction research's document template, closed token layer principle, style tiles methodology.

**Workflow:**

1. **Check for existing direction files** — Look for `design/direction*.md`. If found, read and ask: "Direction exists. Update it, start fresh, or create a scoped variant (e.g., direction-admin.md)?"
2. **Gather intent** — Who is this person? What are they doing? What should it feel like? (from interface-design's Intent First, but tighter — 3 focused questions, not open-ended philosophy)
3. **Collect references** — Ask for 2-3 apps/sites whose *feel* matches intent. If none provided, suggest options based on domain. This is the style tiles step — visual references before token decisions.
4. **Domain exploration** — Run the four-part exploration: domain concepts (5+), color world (5+ colors), signature element (1 unique thing), defaults to reject (3 obvious choices named and rejected). Adapted from interface-design lines 62-74.
5. **Propose direction** — Present concrete token decisions: color palette with hex values and semantic names, typography with specific fonts and scale, spacing base unit and scale, depth strategy (one of: borders-only, subtle shadows, layered shadows, surface tints), border radius scale, motion parameters. Every value must be justified against intent and domain ("WHY" requirement from interface-design line 40).
6. **Self-review** — Run swap test, squint test, signature test, token test (from interface-design lines 82-87) on the proposed direction. If any fail, iterate before presenting.
7. **Confirm and save** — Write `design/direction.md` (or scoped variant). Format defined below. Include `completeness: full` in frontmatter.
8. **Hand off to mockup** — After saving, offer: "Direction saved. Want to see what it looks like? I can generate a mockup with `/mine.mockup`." This closes the gap where direction-setting produces no viewable output.

**Estimated size:** ~150-200 lines for SKILL.md, plus a ~100-line reference file containing the direction.md template and guidance.

**File structure:**
```
skills/mine.look-and-feel/
  SKILL.md
  references/
    direction-template.md    # The direction.md format + writing guidance
```

**What NOT to include:**
- Implementation guidance (that's mine.build's job)
- HTML generation (that's mine.mockup's job)
- Craft Foundations philosophical content (interface-design lines 91-126 — too abstract, the token decisions are what matter)
- The `.interface-design/system.md` persistence workflow (replaced by `design/direction.md`)

### direction.md format

The format must be specific enough for mine.mockup and mine.build to consume, yet readable as a standalone design document. Based on the design-direction research's recommended template:

```markdown
# Design Direction: [Product/Feature Name]

**Date:** YYYY-MM-DD
**Updated:** YYYY-MM-DD
**Completeness:** full | lightweight

## Intent
- **Who**: [specific person in specific context — not "users"]
- **Task**: [the verb — not "use the app"]
- **Feel**: [specific aesthetic language — not "clean and modern"]

## References
- [App/site name]: [what to take from it — e.g., "the density and monospace feel"]
- [App/site name]: [what to take from it]

## Domain
- **Concepts**: [5+ domain-specific concepts]
- **Color world**: [colors that exist naturally in this domain]
- **Signature**: [one element unique to THIS product]
- **Rejected defaults**: [obvious choices and why they're wrong for this]

## Tokens

### Color
| Token | Value | Role |
|-------|-------|------|
| `--bg` | #... | Page background |
| `--surface` | #... | Card/panel background |
| `--border` | rgba(...) | Separation |
| `--text` | #... | Primary text |
| `--text-dim` | #... | Secondary text |
| `--accent` | #... | Primary action/emphasis |
| `--accent-dim` | #... | Accent backgrounds |
| `--destructive` | #... | Error/danger |
| `--success` | #... | Positive/complete |
| `--warning` | #... | Caution |

Dark mode values in a second table (same token names, different values).

**Rationale**: [how colors connect to domain and intent]

### Typography
- **Primary**: [font name] — [why]
- **Mono**: [font name] — [for code/data]
- **Scale**: [specific sizes: xs, sm, base, lg, xl, 2xl, 3xl]
- **Weights**: [which weights, for what purpose]

### Spacing
- **Base**: [value, e.g., 4px or 0.25rem]
- **Scale**: micro (1×), sm (2×), md (4×), lg (8×), xl (12×), 2xl (16×)

### Depth
- **Strategy**: [borders-only | subtle shadows | layered | surface tints]
- **Why**: [connection to intent and feel]
- **Levels**: [specific values for each elevation tier]

### Border Radius
- **Scale**: sm (inputs/buttons), md (cards), lg (modals)
- **Character**: [sharp=technical, round=friendly — where on the spectrum]

### Motion
- **Micro**: [~150ms, easing]
- **Transition**: [200-250ms, easing]
- **Entrance**: [if applicable]

## Anti-patterns
- [Specific things to avoid for THIS product — not generic advice]

## Component Notes
- [Any component-specific decisions from exploration]
```

**The closed token layer constraint:** Every CSS value in code generated by mine.mockup or mine.build must reference a token from this document. No raw hex values, no magic numbers. This is the primary anti-drift mechanism.

### Skill 2: mine.mockup

**Purpose:** Generate self-contained HTML mockup files. Reads `design/direction.md` if present.

**Source material:** vx.visual-explainer's Think/Structure/Style/Deliver workflow, stripped of subcommands, slides, surf-cli, share, and proactive table rendering.

**Workflow:**

1. **Check for direction files** — Look for `design/direction*.md` in the project.
   - **If one found**: Read it, use tokens and direction for styling. Skip to step 3.
   - **If multiple found**: Ask which applies to this mockup. Read the selected one. Skip to step 3.
   - **If none found**: Ask the user: "No design direction found. Run a quick inline direction phase, or run /mine.look-and-feel first?"
     - If inline: run a lightweight Think phase (audience, content type, aesthetic — adapted from vx lines 35-66).
     - If redirect: tell user to run `/mine.look-and-feel` and stop.
2. **Quick direction** (only if no direction.md and user chose inline) — audience, content type, aesthetic. Pick font pairing, color palette, depth strategy. ~30 seconds, not the full look-and-feel workflow.
3. **Structure** — Choose rendering approach based on content type. Read reference material before generating:
   - Architecture overviews: read `templates/architecture.html`
   - Flowcharts/diagrams: read `templates/mermaid-flowchart.html`
   - Data tables: read `templates/data-table.html`
   - Multi-section pages: also read `references/responsive-nav.md`
   - Always read `references/css-patterns.md` for layout patterns
   - Always read `references/libraries.md` for font pairings and Mermaid/Chart.js theming
4. **Style** — Apply direction.md tokens (or inline direction) to the HTML. Typography, color, surfaces, animation. Anti-slop rules from vx lines 412-479 (forbidden fonts, colors, patterns).
5. **Quality checks** — Squint test, swap test, both themes, overflow check, information completeness (from vx lines 401-410).
6. **Deliver** — Write to `~/.claude/diagrams/`, open in browser (`xdg-open` on Linux, `open` on macOS). Tell the user the file path.
7. **Offer to persist** (only if step 2 was used) — After delivering the mockup, offer: "Save this direction to `design/direction.md` so future mockups and builds use it?" If yes, write a lightweight direction.md from the inline choices with `completeness: lightweight` in frontmatter. mine.build can then distinguish full vs. lightweight directions and suggest running `/mine.look-and-feel` for the full treatment when appropriate.

**Estimated size:** ~250-300 lines for SKILL.md.

**File structure:**
```
skills/mine.mockup/
  SKILL.md
  references/
    css-patterns.md         # Moved from vx, trimmed of slide-specific content
    libraries.md            # Moved from vx, trimmed of slide preset references
    responsive-nav.md       # Moved from vx, unchanged
  templates/
    architecture.html       # Moved from vx, unchanged
    data-table.html         # Moved from vx, unchanged
    mermaid-flowchart.html  # Moved from vx, unchanged
```

**What NOT to include:**
- Design direction philosophy (that's mine.look-and-feel)
- Subcommands (diff-review, fact-check, etc. — all dead)
- Slide deck mode and slide-patterns.md
- surf-cli AI image generation
- Vercel share/deploy
- Proactive table rendering ("render ASCII tables as HTML automatically")
- The `commands/` directory (no subcommands)
- `scripts/share.sh`

**What to preserve from vx:**
- The HTML file structure pattern (single self-contained .html)
- The delivery workflow (write to `~/.claude/diagrams/`, open in browser)
- Anti-slop rules (forbidden fonts, colors, patterns, the slop test)
- Quality checks
- Mermaid theming, container, scaling, and CSS class collision rules
- Chart.js and anime.js CDN patterns
- All aesthetic directions (Blueprint, Editorial, Paper/ink, Monochrome terminal, IDE-inspired)
- The rendering approach decision table (content type → Mermaid vs CSS Grid vs table)

### Skill 3: mine.build update

**Purpose:** Teach mine.build to detect and use `design/direction.md` when doing UI work.

**Change location:** `skills/mine.build/SKILL.md`, Phase 1 (Understand the Request) — so it applies to all paths (Simple, Complex, Accelerated).

**What to add:**

At the end of Phase 1, after paraphrasing the request, add a direction.md detection step:

> **Before writing UI code**, check for `design/direction*.md` in the project. If found and the work touches frontend (CSS, components, layouts, styles):
> - Read the applicable direction file (ask which if multiple exist)
> - State which design tokens and decisions apply to this change
> - Apply the closed token layer: every CSS value must reference a token from direction.md
>
> If not found and the work involves non-trivial UI (new pages, new components, visual redesign), suggest: "No design direction found. Consider running `/mine.look-and-feel` first for consistent results."

**Token compliance via code-reviewer:** When direction.md exists and the diff touches CSS/styles, the code-reviewer agent should check for raw hex values (`#[0-9a-f]{3,8}`), raw px values not matching the spacing scale, and font names not listed in direction.md. Surface violations as HIGH findings: "Found raw value `#333` in component.css:42 — should this reference a direction.md token?" This leverages the existing review loop (code-reviewer runs after implementation, fixes are applied, re-review until clean) rather than adding a separate enforcement step. **Note:** This is implemented as guidance in mine.build's SKILL.md, not as a change to `agents/code-reviewer.md`. The code-reviewer already reads project context and flags style inconsistencies; the mine.build note makes it aware of direction.md as a reference. If this proves insufficient in practice, a dedicated code-reviewer update can follow.

This is additive — mine.build's existing workflow is unchanged for non-UI work.

### Routing (capabilities.md)

Replace the two current routing entries:

**Remove:**
```
| "generate a diagram", "visualize this", "architecture diagram", "diff review", "visual plan", "slide deck", "project recap", "fact check a doc" | `/vx.visual-explainer` |
| "design this UI", "design this dashboard", "craft the interface" | `/mine.interface-design` |
```

**Add:**
```
| "design this UI", "design this dashboard", "look and feel", "establish design tokens", "plan the look and feel", "UI planning", "design system for this project", "craft the interface" | `/mine.look-and-feel` |
| "mockup this UI", "show me what it looks like", "HTML mockup", "UI preview", "generate a mockup" | `/mine.mockup` |
```

**No collision with mine.design:** `mine.design` handles "design this change" / "write a design doc" (caliper v2 architecture docs). `mine.look-and-feel` handles "design this UI" / "plan the look and feel" (visual design planning). The skill names are completely distinct — no shared prefix ambiguity. The trigger phrase "design this UI" routes to mine.look-and-feel because it's about visual direction, not architecture.

**Disambiguation comment** in capabilities.md: Add a note like the existing spec/design comments: `<!-- NOTE: "design this UI" = visual direction (look-and-feel); "design this change" = architecture doc (design) -->`

**Diagram routing explicitly dropped:** "Generate a diagram", "visualize this", and "architecture diagram" are intentionally removed from routing. The Mermaid templates survive in mine.mockup for use in mockups, but there is no standalone diagram skill. Users who want a quick diagram can invoke `/mine.mockup` directly.

### Evals (intent-to-skill-design-ux.yaml)

Rewrite 6 test cases:
- 3 `mine.interface-design` cases → update to expect `mine.look-and-feel`
- 3 `vx.visual-explainer` cases → update to expect `mine.mockup`

Add 5+ boundary test cases to validate the mine.design vs mine.look-and-feel boundary:
- "design this change" → must route to `mine.design` (NOT mine.look-and-feel)
- "plan the look and feel for this dashboard" → must route to `mine.look-and-feel`
- "design this UI" → must route to `mine.look-and-feel` (NOT mine.design)
- "write a design doc for the auth feature" → must route to `mine.design`
- "design the dashboard" → must route to `mine.look-and-feel` (visual, not architecture)
- "what should this app look like" → must route to `mine.look-and-feel`

### css-patterns.md trimming

Conservative trim: remove only content explicitly gated by "slide deck", "--slides", or `slide-patterns.md` references. Estimated removal: ~200 lines. Everything else stays — better to have unused patterns than to accidentally remove something a mockup needs.

### README.md and CLAUDE.md updates

**README.md:**
- Remove `mine.interface-design` from skills table and commands table
- Remove `vx.visual-explainer` from skills table (all subcommand entries already removed by PR #105)
- Add `mine.look-and-feel` and `mine.mockup` to skills table
- Add `mine.look-and-feel` command entry
- Remove "About skill prefixes" section (or rewrite: "All skills use the `mine.*` prefix")
- Update skill and command counts

**CLAUDE.md:**
- Remove `vx.*` prefix references (lines 50, 58)
- Update "Naming Convention" section: all skills use `mine.*`, no multi-prefix system

## Alternatives Considered

### Single mine.mockup with inline direction (original research recommendation)

Fold design direction into mine.mockup as a mandatory Phase 1. No separate planning skill, no mine.build update.

**Rejected because:**
- No persistence across sessions — critique finding #4
- Design direction principles locked inside a mockup-only skill — can't be used for real app code
- User explicitly decided on the three-skill split after challenge review

### Two skills without mine.build update

Create mine.look-and-feel and mine.mockup, but don't touch mine.build.

**Rejected because:**
- The user's primary use case is real app code, not standalone mockups
- Without mine.build awareness, direction.md is only useful for mockups — wastes the planning work
- Adding direction.md detection to mine.build is a ~10-line change with high value

## Open Questions

*Must be empty before plan approval.*

- [x] **css-patterns.md slide content boundaries**: Conservative trim — grep for "slide" and remove only explicitly slide-gated content. ~200 lines. Implementation detail, not a design question.
- [x] **interface-design principles.md useful content**: Merge into mine.look-and-feel's `references/direction-template.md`. Typography cheat sheet and surface elevation examples inform direction decisions, not mockup generation.

## Impact

### Files created (6)
- `skills/mine.look-and-feel/SKILL.md` (~150-200 lines)
- `skills/mine.look-and-feel/references/direction-template.md` (~100 lines)
- `commands/mine.look-and-feel.md` (~30-40 lines)
- `skills/mine.mockup/SKILL.md` (~250-300 lines)
- `commands/mine.mockup.md` (~30-40 lines)
- `design/specs/005-replace-skills/design.md` (this file)

### Files moved (6)
- `vx.visual-explainer/references/css-patterns.md` → `mine.mockup/references/css-patterns.md` (trimmed)
- `vx.visual-explainer/references/libraries.md` → `mine.mockup/references/libraries.md` (minor trim)
- `vx.visual-explainer/references/responsive-nav.md` → `mine.mockup/references/responsive-nav.md`
- `vx.visual-explainer/templates/architecture.html` → `mine.mockup/templates/architecture.html`
- `vx.visual-explainer/templates/data-table.html` → `mine.mockup/templates/data-table.html`
- `vx.visual-explainer/templates/mermaid-flowchart.html` → `mine.mockup/templates/mermaid-flowchart.html`

### Files deleted (19)
- `skills/vx.visual-explainer/` — entire directory (SKILL.md, references/slide-patterns.md, templates/slide-deck.html, 8 command files, scripts/share.sh)
- `skills/mine.interface-design/` — entire directory (SKILL.md, references/principles.md)
- `commands/mine.interface-design.md`

### Files modified (6)
- `rules/common/capabilities.md` — routing table
- `evals/compliance/routing/intent-to-skill-design-ux.yaml` — 6 updated + 5-6 new boundary test cases
- `skills/mine.build/SKILL.md` — direction.md detection (~10 lines added)
- `README.md` — inventory tables, counts, prefix section
- `CLAUDE.md` — remove vx.* prefix references
- `CHANGELOG.md` — new entry
