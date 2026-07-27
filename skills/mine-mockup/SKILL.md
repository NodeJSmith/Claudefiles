---
name: mine-mockup
description: "Use when the user says: \"mockup this UI\", \"show me what it looks like\", \"HTML mockup\", \"UI preview\", or \"generate a mockup\". Generate self-contained HTML mockup files. Reads design/context.md if present for consistent styling."
user-invocable: true
---

# Mockup

Dispatches a subagent to generate self-contained HTML mockups. The main agent resolves design context, then hands off generation entirely.

## Arguments

$ARGUMENTS — a description of what to mockup. If empty, ask the user what they want to mockup.

## Resolve Context

Look for `design/specs/*/design.md`:
- **None found** — proceed without a design doc.
- **Exactly one** — read its **User Scenarios** section. Note the path for the subagent.
- **Multiple** — list the feature directories and ask which this mockup targets.

Look for design context (checked in order, first match wins): `design/context.md`, `.impeccable.md`, `design/direction.md`. If found, note its path. If none found, proceed without — the worker uses its default aesthetic.

## Execute

Launch one subagent (`model: sonnet`, `subagent_type: general-purpose`):

> Generate an HTML mockup.
>
> **What to build:** <user's description from $ARGUMENTS>
> **Design context file:** <path to design/context.md or equivalent, or "none">
> **Design doc:** <path to design.md if found, or "none">
>
> Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-mockup/worker.md` for the complete workflow. Follow every step. Do NOT use the Skill tool — the instructions are in worker.md, not a skill.

The subagent returns the file path of the generated HTML.

Present the file path to the user. If no `design/context.md` exists, suggest: "Want more control over styling? Run `/i-teach-impeccable` to set up design tokens."
