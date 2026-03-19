---
name: mine.interface-design
description: Build UI with craft and consistency. For interface design (dashboards, apps, tools) — not marketing sites.
---

## Required Reading

Before writing any code, read completely:

1. Read the skill: `~/.claude/skills/mine.interface-design/SKILL.md`
2. Read the reference: `~/.claude/skills/mine.interface-design/references/principles.md`

Do not skip this. The craft knowledge is in these files.

---

## Intent First — Answer Before Building

Before touching code, answer these out loud:

**Who is this human?** Not "users." Where are they? What's on their mind?

**What must they accomplish?** Not "use the dashboard." The verb.

**What should this feel like?** In words that mean something. "Clean" means nothing.

If you cannot answer with specifics, stop and ask the user.

## Shape Before You Design

Before jumping to visual design, define what a section or screen actually *does*:

- **User flows** — What are the step-by-step interactions? (e.g., "User scans list, clicks row, sees detail, edits inline")
- **UI requirements** — What specific layouts, patterns, or components are needed?
- **Scope boundaries** — What's intentionally excluded?
- **Sample data** — Generate 5-10 realistic records with varied content and edge cases. Design against real-shaped data, not lorem ipsum. Include: long names, empty optional fields, max-length values, single items vs many, error/warning states.

This prevents designing a beautiful screen that breaks the moment real content appears. If a section hasn't been shaped, ask the user before designing it.

## Before Writing Each Component

State intent AND approach:

```
Intent: [who, what they need to do, how it should feel]
Palette: [foundation + accent — and WHY]
Depth: [borders / subtle shadows / layered — and WHY]
Surfaces: [elevation scale — and WHY this temperature]
Typography: [typeface — and WHY it fits]
Spacing: [base unit]
```

Every choice must be explainable. "It's common" or "it works" means you defaulted.

## Communication

Be invisible. Don't announce modes or narrate process. Jump into work with reasoning.

## Suggest + Ask

Lead with exploration, then confirm:

```
Domain: [concepts from this product's world]
Color world: [colors that exist in this domain]
Signature: [one element unique to this product]

Direction: [approach connecting to above]
```

Use AskUserQuestion: "Does that direction feel right?"

## Flow

1. Read the required files above (always — even if system.md exists)
2. Check if `.interface-design/system.md` exists
3. **If exists**: Apply established patterns from system.md
4. **If not**: Check for existing UI files (tsx, jsx, vue, svelte, css, scss) in the project
   - **If existing UI found**: Scan for repeated patterns (spacing values, border radius, colors, depth strategy, component patterns). Summarize what you find, then use AskUserQuestion with these options:
     - **Evolve** — Codify the existing patterns into system.md and build on them. Good when the existing UI has a reasonable foundation worth keeping.
     - **Fresh start** — Ignore existing patterns and establish a new direction. Good when the existing UI was thrown together without intention.
     - **Hybrid** — Keep what looks intentional, replace what looks accidental. Review the patterns together and decide which to keep.
   - **If no existing UI**: Assess context, suggest direction, get confirmation, build

## After Every Task

Offer to save: "Want me to save these patterns to `.interface-design/system.md`?"
