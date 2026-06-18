---
name: i-polish
description: 'Use when the user says: "polish this UI", "final pass", "pixel-perfect", "normalize the design", "make it consistent", "align with design system". Final quality pass for alignment, spacing, consistency, and design system alignment.'
user-invocable: true
---

## MANDATORY PREPARATION

Read `${CLAUDE_HOME:-~/.claude}/skills/i-frontend-design/SKILL.md` for design principles, anti-patterns, and the **Context Gathering Protocol**. Follow the protocol before proceeding — if no design context exists yet, you MUST run /i-teach-impeccable first. Additionally gather: quality bar (MVP vs flagship).

---

Perform a meticulous final pass to catch all the small details that separate good work from great work. The difference between shipped and polished.

## Design System Discovery

Before polishing, understand the system you are polishing toward:

1. **Find the design system**: Search for design system documentation, component libraries, style guides, or token definitions. Study the core patterns: color tokens, spacing scale, typography styles, component API.
2. **Note the conventions**: How are shared components imported? What spacing scale is used? Which colors come from tokens vs hard-coded values? What motion and interaction patterns are established?
3. **Identify drift**: Where does the target feature deviate from the system? Hard-coded values that should be tokens, custom components that duplicate shared ones, spacing that doesn't match the scale.

If a design system exists, polish should align the feature with it. If none exists, polish against the conventions visible in the codebase.

## Pre-Polish Assessment

Understand the current state and goals:

1. **Review completeness**:
   - Is it functionally complete?
   - Are there known issues to preserve (mark with TODOs)?
   - What's the quality bar? (MVP vs flagship feature?)
   - When does it ship? (How much time for polish?)

2. **Identify polish areas**:
   - Visual inconsistencies
   - Spacing and alignment issues
   - Interaction state gaps
   - Copy inconsistencies
   - Edge cases and error states
   - Loading and transition smoothness

**CRITICAL**: Polish is the last step, not the first. Don't polish work that's not functionally complete.

---

## Propose Changes

After analyzing the current state, present your proposed changes to the user:

1. **Assessment**: What's wrong and why (your domain analysis above)
2. **Proposed changes**: Specific changes ranked by impact, with rationale
3. **Verification plan**: What to check after implementation (LLM self-check items + Playwright verification if available)

Then STOP and confirm before implementing:

```
AskUserQuestion:
  question: "Here's what I'll check and fix in this polish pass. Proceed?"
  header: "Confirm"
  options:
    - label: "Implement"
      description: "Looks good — go ahead and make these changes."
    - label: "Refine scope"
      description: "I want to adjust what's included before you start."
    - label: "Challenge this first"
      description: "I'll run /mine-challenge against your proposal before we proceed."
    - label: "Stop here"
      description: "Don't implement anything. The proposal is in this conversation only."
```

If "Implement" → proceed to implementation below.
If "Refine scope" → ask what to change, update proposal, re-confirm.
<!-- CHALLENGE-CALLER -->
If "Challenge this first" → invoke `/mine-challenge` inline against the proposal, read findings, revise proposal, re-present this gate.
If "Stop here" → end the skill.

---

## Polish Systematically

Work through these dimensions methodically. The standard checks (grid alignment, WCAG contrast, 44px touch targets, removing console.logs/dead code, alt text, no layout shift) you already know — apply them. The items below are the ones worth spelling out:

- **Spacing**: All gaps use the spacing scale — no random 13px values. Optical alignment over mathematical (icons may need an offset to look centered).
- **Typography**: Body line length 45-75 characters. Same elements use same size/weight throughout.
- **Color**: No hard-coded colors — all from tokens. Tinted neutrals, never pure gray or pure black (~0.01 chroma tint). Gray on colored backgrounds: see /i-colorize. Also check the [anti-patterns reference](../i-frontend-design/reference/anti-patterns.md).
- **Interaction states**: Every interactive element needs its full set of states. See [interaction-design.md](../i-frontend-design/reference/interaction-design.md) for the canonical eight-states table. Missing states create broken experiences.
- **Transitions**: 150-300ms. Easing: see /i-animate — never bounce/elastic. Animate only transform and opacity. Respect `prefers-reduced-motion`.
- **Copy**: Consistent terminology and capitalization throughout. Punctuation consistent (periods on sentences, not on labels).
- **Forms**: Consistent validation timing (on blur vs on submit), logical tab order.
- **Edge cases**: Loading, empty, error, and success states all present. Handles very long content and missing data gracefully.

**IMPORTANT**: Polish is about details. Zoom in. Squint at it. Use it yourself. The little things add up.

**NEVER**:
- Polish before it's functionally complete
- Spend hours on polish if it ships in 30 minutes (triage)
- Introduce bugs while polishing (test thoroughly)
- Ignore systematic issues (if spacing is off everywhere, fix the system)
- Perfect one thing while leaving others rough (consistent quality level)
- Create new one-off components when design system equivalents exist
- Hard-code values that should use design tokens

## Final Verification

Before marking as done:

- **Use it yourself**: Actually interact with the feature
- **Test on real devices**: Not just browser DevTools
- **Ask someone else to review**: Fresh eyes catch things
- **Compare to design**: Match intended design
- **Check all states**: Don't just test happy path

Remember: You have impeccable attention to detail and exquisite taste. Polish until it feels effortless, looks intentional, and works flawlessly. Sweat the details - they matter.

## Clean Up

After polishing, ensure code quality:

- **Replace custom implementations**: If the design system provides a component you reimplemented, switch to the shared version.
- **Remove orphaned code**: Delete unused styles, components, or files made obsolete by polish.
- **Consolidate tokens**: If you introduced new values, check whether they should be tokens.
- **Verify DRYness**: Look for duplication introduced during polishing and consolidate.

## Completion

After implementation, summarize in conversation:

1. **Changes made**: List each file changed and what was done
2. **Verification**: LLM self-check results (anti-pattern scan, consistency check). Note if Playwright was available for visual verification.
3. **Suggested next step**: Any follow-up skills that would complement this work (e.g., after /i-typeset, suggest /i-polish for a final pass)