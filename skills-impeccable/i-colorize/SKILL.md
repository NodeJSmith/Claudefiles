---
name: i-colorize
description: 'Use when the user says: "fix the colors", "color system", "palette needs work". Improve color palettes, contrast, and theming.'
user-invocable: true
---

Strategically introduce color to designs that are too monochromatic, gray, or lacking in visual warmth and personality.

## MANDATORY PREPARATION

Read `${CLAUDE_HOME:-~/.claude}/skills/i-frontend-design/SKILL.md` for design principles, anti-patterns, and the **Context Gathering Protocol**. Follow the protocol before proceeding — if no design context exists yet, you MUST run /i-teach-impeccable first. Additionally gather: existing brand colors.

---

## Assess Color Opportunity

Analyze the current state and identify opportunities:

1. **Understand current state**:
   - **Color absence**: Pure grayscale? Limited neutrals? One timid accent?
   - **Missed opportunities**: Where could color add meaning, hierarchy, or delight?
   - **Context**: What's appropriate for this domain and audience?
   - **Brand**: Are there existing brand colors we should use?

2. **Identify where color adds value**:
   - **Semantic meaning**: Success (green), error (red), warning (yellow/orange), info (blue)
   - **Hierarchy**: Drawing attention to important elements
   - **Categorization**: Different sections, types, or states
   - **Emotional tone**: Warmth, energy, trust, creativity
   - **Wayfinding**: Helping users navigate and understand structure
   - **Delight**: Moments of visual interest and personality

If any of these are not answered by design context (`design/context.md`, `.impeccable.md`, or `design/direction.md`), STOP and call the AskUserQuestion tool to clarify. Use the answer to inform your color strategy. If the answer is unclear or deferred, proceed using the existing palette with no changes without explicit confirmation.

**CRITICAL**: More color ≠ better. Strategic color beats rainbow vomit every time. Every color should have a purpose.

## Plan Color Strategy

Create a purposeful color introduction plan:

- **Color palette**: What colors match the brand/context? (Choose 2-4 colors max beyond neutrals)
- **Dominant color**: Which color owns 60% of colored elements?
- **Accent colors**: Which colors provide contrast and highlights? (30% and 10%)
- **Application strategy**: Where does each color appear and why?

**IMPORTANT**: Color should enhance hierarchy and meaning, not create chaos. Less is more when it matters more.

---

## Propose Changes

After analyzing the current state, present your proposed changes to the user:

1. **Assessment**: What's wrong and why (your domain analysis above)
2. **Proposed changes**: Specific changes ranked by impact, with rationale
3. **Verification plan**: What to check after implementation (LLM self-check items + Playwright verification if available)

Then STOP and confirm before implementing:

```
AskUserQuestion:
  question: "Here's what I propose. How would you like to proceed?"
  header: "Confirm"
  options:
    - label: "Implement"
      description: "Looks good — go ahead and make these changes."
    - label: "Refine scope"
      description: "I want to adjust what's included before you start."
    - label: "Challenge this first"
      description: "I'll run /mine.challenge against your proposal before we proceed."
    - label: "Stop here"
      description: "Don't implement anything. The proposal is in this conversation only."
```

If "Implement" → proceed to implementation below.
If "Refine scope" → ask what to change, update proposal, re-confirm.
<!-- CHALLENGE-CALLER -->
If "Challenge this first" → invoke `/mine.challenge` inline against the proposal, read findings, revise proposal, re-present this gate.
If "Stop here" → end the skill.

---

## Introduce Color Strategically

You already know the standard semantic mappings (success=green, error=red, warning=amber, info=blue) and the obvious surfaces for accent color — primary CTAs, links, status badges, charts, accent borders, focus rings. Apply them with restraint per the 60/30/10 split from your plan. The load-bearing specifics:

**Tinted neutrals**: replace pure gray (`#f5f5f5`) with a warm or cool tint — `oklch(97% 0.01 60)` (warm) or `oklch(97% 0.01 250)` (cool). Never pure gray for neutrals, and never pure black (`#000`) or pure white (`#fff`) for large areas.

**Use OKLCH**: perceptually uniform, so equal lightness steps *look* equal — ideal for generating harmonious scales.

## Balance & Refinement

Ensure color addition improves rather than overwhelms:

- **Accessibility**: meet WCAG contrast (4.5:1 text, 3:1 UI components), never rely on color alone, verify red/green works for colorblind users.
- **Cohesion**: pull from the defined palette only, keep meanings consistent (green always = success), keep temperature consistent (warm stays warm).

**NEVER**:
- Use every color in the rainbow (choose 2-4 colors beyond neutrals)
- Apply color randomly without semantic meaning
- Put gray text on colored backgrounds—it looks washed out; use a darker shade of the background color or transparency instead
- Use pure gray for neutrals—add subtle color tint (warm or cool) for sophistication
- Use pure black (`#000`) or pure white (`#fff`) for large areas
- Violate WCAG contrast requirements
- Use color as the only indicator (accessibility issue)
- Make everything colorful (defeats the purpose)
- Use any pattern listed in the [anti-patterns reference](../i-frontend-design/reference/anti-patterns.md) — especially the AI color palette (cyan-on-dark, purple-to-blue gradients, gradient text)

## Verify Color Addition

Test that colorization improves the experience:

- **Better hierarchy**: Does color guide attention appropriately?
- **Clearer meaning**: Does color help users understand states/categories?
- **More engaging**: Does the interface feel warmer and more inviting?
- **Still accessible**: Do all color combinations meet WCAG standards?
- **Not overwhelming**: Is color balanced and purposeful?

Remember: Color is emotional and powerful. Use it to create warmth, guide attention, communicate meaning, and express personality. But restraint and strategy matter more than saturation and variety. Be colorful, but be intentional.

## Completion

After implementation, summarize in conversation:

1. **Changes made**: List each file changed and what was done
2. **Verification**: LLM self-check results (anti-pattern scan, consistency check). Note if Playwright was available for visual verification.
3. **Suggested next step**: Any follow-up skills that would complement this work (e.g., after /i-typeset, suggest /i-polish for a final pass)