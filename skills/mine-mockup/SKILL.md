---
name: mine-mockup
user-invocable: true
description: "Use when the user says: \"mockup this UI\", \"show me what it looks like\", \"HTML mockup\", \"UI preview\", or \"generate a mockup\". Generate self-contained HTML mockup files. Reads design/context.md if present for consistent styling."
---

# Mockup

Dispatches a subagent to generate self-contained HTML mockups. The main agent resolves design context and aesthetic direction, then hands off generation entirely.

## Arguments

$ARGUMENTS — a description of what to mockup.

## Phase 1: Resolve Design Context

Look for `design/specs/*/design.md`:
- **None found** — proceed without a design doc.
- **Exactly one** — read its **User Scenarios** section. Note the path for the subagent.
- **Multiple** — list the feature directories and ask which this mockup targets.

Look for design context in order:
- **`design/context.md`** — if found, note its path. Skip to Phase 3.
- **`.impeccable.md`** (migration fallback) — if found, note its path. Skip to Phase 3.
- **`design/direction.md`** (migration fallback) — if found, note its path. Skip to Phase 3.
- **None found** — ask:

```
AskUserQuestion:
  question: "No design context found. How should we proceed?"
  header: "Design"
  multiSelect: false
  options:
    - label: "Quick direction"
      description: "Answer a few questions about audience, content type, and aesthetic (~30 seconds)"
    - label: "Run /i-teach-impeccable"
      description: "Full design context setup first"
```

If redirect: tell the user to run `/i-teach-impeccable` and stop.

## Phase 2: Quick Direction (only if no design context)

Ask three things:

**Who is looking?** Developer understanding a system, PM seeing the big picture, team reviewing a proposal. Shapes information density.

**What type of content?** Architecture, flowchart, sequence, data flow, schema/ER, state machine, mind map, class diagram, C4, data table, timeline, dashboard, or UI mockup.

**What aesthetic?** Pick one and commit.

**Constrained aesthetics (prefer these):**
- Blueprint (technical drawing feel, deep slate/blue, monospace labels)
- Editorial (serif headlines, generous whitespace, muted earth tones or navy + gold)
- Paper/ink (warm cream `#faf7f5`, terracotta/sage accents, informal feel)
- Monochrome terminal (green/amber on near-black, monospace everything)

**Flexible aesthetics (use with caution):**
- IDE-inspired (a real, named color scheme: Dracula, Nord, Catppuccin, Solarized, Gruvbox, One Dark, Rose Pine)
- Data-dense (small type, tight spacing, maximum information, muted colors)

Pick font pairing, color palette, depth strategy. **Never pick:** Inter/Roboto/Arial/Helvetica as body font, indigo-500/violet-500 accents, or cyan+magenta+pink neon combinations.

**Good font pairings:**
- DM Sans + Fira Code (technical, precise)
- Instrument Serif + JetBrains Mono (editorial, refined)
- IBM Plex Sans + IBM Plex Mono (reliable, readable)
- Bricolage Grotesque + Fragment Mono (bold, characterful)
- Plus Jakarta Sans + Azeret Mono (rounded, approachable)

**Good accent palettes:**
- Terracotta + sage (`#c2410c`, `#65a30d`)
- Teal + slate (`#0891b2`, `#0369a1`)
- Rose + cranberry (`#be123c`, `#881337`)
- Amber + emerald (`#d97706`, `#059669`)
- Deep blue + gold (`#1e3a5f`, `#d4a73a`)

## Phase 3: Generate

Launch one subagent (`model: sonnet`, `subagent_type: general-purpose`):

> Generate an HTML mockup.
>
> **What to build:** <user's description from $ARGUMENTS>
> **Design context file:** <path to design/context.md or equivalent, or "none">
> **Design doc:** <path to design.md if found, or "none">
> **Aesthetic direction:** <if Phase 2 ran: the chosen font pairing, color palette, and depth strategy. If design context was found in Phase 1: the literal string "use design context tokens from <path>".
>
> Read `${CLAUDE_HOME:-~/.claude}/skills/mine-mockup/worker.md` for the complete workflow. Follow every step.

The subagent returns the file path of the generated HTML.

## Phase 4: Deliver

Tell the user the file path. If Phase 2 was used (quick direction, no `design/context.md`), suggest: "Want to formalize this direction? Run `/i-teach-impeccable` — it can use this mockup as input for token extraction."
