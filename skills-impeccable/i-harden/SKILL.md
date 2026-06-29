---
name: i-harden
description: 'Use when the user says: "production hardening", "handle edge cases in UI", "make it resilient", "improve onboarding", "empty states", "first-run experience". Improve interface resilience, error states, onboarding flows, and edge cases.'
user-invocable: true
---

Strengthen interfaces against edge cases, errors, internationalization issues, and real-world usage scenarios that break idealized designs.

## MANDATORY PREPARATION

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/i-frontend-design/SKILL.md` for design principles, anti-patterns, and the **Context Gathering Protocol**. Follow the protocol before proceeding — if no design context exists yet, you MUST run /i-teach-impeccable first.

---

## Assess Hardening Needs

Identify weaknesses and edge cases:

1. **Test with extreme inputs**:
   - Very long text (names, descriptions, titles)
   - Very short text (empty, single character)
   - Special characters (emoji, RTL text, accents)
   - Large numbers (millions, billions)
   - Many items (1000+ list items, 50+ options)
   - No data (empty states)

2. **Test error scenarios**:
   - Network failures (offline, slow, timeout)
   - API errors (400, 401, 403, 404, 500)
   - Validation errors
   - Permission errors
   - Rate limiting
   - Concurrent operations

3. **Test internationalization**:
   - Long translations (German is often 30% longer than English)
   - RTL languages (Arabic, Hebrew)
   - Character sets (Chinese, Japanese, Korean, emoji)
   - Date/time formats
   - Number formats (1,000 vs 1.000)
   - Currency symbols

**CRITICAL**: Designs that only work with perfect data aren't production-ready. Harden against reality.

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

## Hardening Dimensions

You already know the standard recipes — ellipsis/line-clamp truncation, `Intl.DateTimeFormat`/`Intl.NumberFormat` for locale formatting, debounce/throttle, proper-plural i18n libraries, status-code handling (400 validate, 401 login, 403 permission, 404 not-found, 429 rate-limit, 500 generic+support), retry buttons, skeleton screens, listener/timer cleanup on unmount. Apply them. The non-obvious ones worth spelling out:

**Flex/grid overflow**: a flex or grid child overflowing its container is almost always a missing `min-width: 0` — the default `min-width: auto` refuses to shrink below content size.
```css
.flex-item { min-width: 0; overflow: hidden; }
.grid-item { min-width: 0; min-height: 0; }
```

**RTL**: use logical properties so layout flips automatically, instead of physical left/right.
```css
margin-inline-start: 1rem;   /* not margin-left */
padding-inline: 1rem;        /* not padding-left/right */
border-inline-end: 1px solid;/* not border-right */
[dir="rtl"] .arrow { transform: scaleX(-1); }
```

**Text expansion**: translations run longer than English (German ~30%) — see [ux-writing.md](../i-frontend-design/reference/ux-writing.md) for the per-language budget. Never use fixed widths on text containers; let flex/grid adapt to content.

**Concurrent operations**: disable submit while in-flight to prevent double-submission; optimistic updates need a rollback path. Abort pending requests on unmount.

### Onboarding & First-Run Experience

Production-ready features work for first-time users, not just power users. Design the paths that get new users to value:

**Empty states**: Every zero-data screen needs:
- What will appear here (description or illustration)
- Why it matters to the user
- Clear CTA to create the first item or start from a template
- Visual interest (not just blank space with "No items yet")

Empty state types to handle:
- **First use**: emphasize value, provide templates
- **User cleared**: light touch, easy to recreate
- **No results**: suggest a different query, offer to clear filters
- **No permissions**: explain why, how to get access

**First-run experience**: Get users to their "aha moment" as quickly as possible.
- Show, don't tell -- working examples over descriptions
- Progressive disclosure -- teach one thing at a time, not everything upfront
- Make onboarding optional -- let experienced users skip
- Provide smart defaults so required setup is minimal

**Feature discovery**: Teach features when users need them, not upfront.
- Contextual tooltips at point of use (brief, dismissable, one-time)
- Badges or indicators on new or unused features
- Celebrate activation events quietly (a toast, not a modal)

### Input, Accessibility & Performance Resilience

Standard practice applies — client-side validation with clear `maxlength`/`pattern` constraints (backend validates independently), keyboard-accessible everything with logical tab order and modal focus management, ARIA live regions for dynamic changes, never color alone, skeleton screens on slow connections. One concrete snippet worth keeping is the reduced-motion reset:
```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

## Testing Strategies

Test with extreme data (very long, very short, empty), different languages, offline, throttled-to-3G connections, screen readers, keyboard-only, and old browsers. Automated coverage is out of scope — use your project's testing conventions.

**IMPORTANT**: Hardening is about expecting the unexpected. Real users will do things you never imagined.

**NEVER**:
- Assume perfect input (validate everything)
- Ignore internationalization (design for global)
- Leave error messages generic ("Error occurred")
- Forget offline scenarios
- Trust client-side validation alone
- Use fixed widths for text; assume English-length text
- Block the entire interface when one component errors
- Force long onboarding before users can touch the product
- Show the same tooltip repeatedly (track and respect dismissals)
- Block the entire UI during a guided tour, or build tutorial modes disconnected from the real product
- Design empty states that just say "No items" with no next action

## Verify Hardening

Test thoroughly with edge cases:

- **Long text**: Try names with 100+ characters
- **Emoji**: Use emoji in all text fields
- **RTL**: Test with Arabic or Hebrew
- **CJK**: Test with Chinese/Japanese/Korean
- **Network issues**: Disable internet, throttle connection
- **Large datasets**: Test with 1000+ items
- **Concurrent actions**: Click submit 10 times rapidly
- **Errors**: Force API errors, test all error states
- **Empty**: Remove all data, test empty states

Remember: You're hardening for production reality, not demo perfection. Expect users to input weird data, lose connection mid-flow, and use your product in unexpected ways. Build resilience into every component.

## Completion

After implementation, summarize in conversation:

1. **Changes made**: List each file changed and what was done
2. **Verification**: LLM self-check results (anti-pattern scan, consistency check). Note if Playwright was available for visual verification.
3. **Suggested next step**: Any follow-up skills that would complement this work (e.g., after /i-typeset, suggest /i-polish for a final pass)