---
name: i-delight
description: 'Use when the user says: "add delight", "make it more fun", "moments of joy". Add micro-interactions and moments of delight to interfaces.'
user-invocable: true
---

Identify opportunities to add moments of joy, personality, and unexpected polish that transform functional interfaces into delightful experiences.

## MANDATORY PREPARATION

Read `${CLAUDE_HOME:-~/.claude}/skills/i-frontend-design/SKILL.md` for design principles, anti-patterns, and the **Context Gathering Protocol**. Follow the protocol before proceeding — if no design context exists yet, you MUST run /i-teach-impeccable first. Additionally gather: what's appropriate for the domain (playful vs professional vs quirky vs elegant).

---

## Assess Delight Opportunities

Identify where delight would enhance (not distract from) the experience:

1. **Find natural delight moments**:
   - **Success states**: Completed actions (save, send, publish)
   - **Empty states**: First-time experiences, onboarding
   - **Loading states**: Waiting periods that could be entertaining
   - **Achievements**: Milestones, streaks, completions
   - **Interactions**: Hover states, clicks, drags
   - **Errors**: Softening frustrating moments
   - **Easter eggs**: Hidden discoveries for curious users

2. **Understand the context**:
   - What's the brand personality? (Playful? Professional? Quirky? Elegant?)
   - Who's the audience? (Tech-savvy? Creative? Corporate?)
   - What's the emotional context? (Accomplishment? Exploration? Frustration?)
   - What's appropriate? (Banking app ≠ gaming app)

3. **Define delight strategy**:
   - **Subtle sophistication**: Refined micro-interactions (luxury brands)
   - **Playful personality**: Whimsical illustrations and copy (consumer apps)
   - **Helpful surprises**: Anticipating needs before users ask (productivity tools)
   - **Sensory richness**: Satisfying sounds, smooth animations (creative tools)

If any of these are not answered by design context (`design/context.md`, `.impeccable.md`, or `design/direction.md`), STOP and call the AskUserQuestion tool to clarify. Use the answer to inform your delight strategy. If the answer is unclear or deferred, proceed with micro-feedback only as the safe default — no personality changes.

**CRITICAL**: Delight should enhance usability, never obscure it. If users notice the delight more than accomplishing their goal, you've gone too far.

## Delight Principles

Follow these guidelines:

### Delight Amplifies, Never Blocks
- Delight moments should be quick (< 1 second)
- Never delay core functionality for delight
- Make delight skippable or subtle
- Respect user's time and task focus

### Surprise and Discovery
- Hide delightful details for users to discover
- Reward exploration and curiosity
- Don't announce every delight moment
- Let users share discoveries with others

### Appropriate to Context
- Match delight to emotional moment (celebrate success, empathize with errors)
- Respect the user's state (don't be playful during critical errors)
- Match brand personality and audience expectations
- Cultural sensitivity (what's delightful varies by culture)

### Compound Over Time
- Delight should remain fresh with repeated use
- Vary responses (not same animation every time)
- Reveal deeper layers with continued use
- Build anticipation through patterns

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

## Delight Techniques

Surfaces where delight earns its place: button press/hover feedback, loading and empty states, success confirmations, drag-and-drop lift/snap, toggle transitions, and milestone celebrations. Hidden touches (easter eggs, seasonal themes, console messages) reward the curious but are never required.

Spring physics on toggles and drops should settle with zero or near-zero overshoot — visible bounce is not permitted. Easing and motion: see /i-animate.

### Personality in Copy

**Note**: Playful error copy is appropriate only for non-blocking, easily recoverable errors (404s, empty search results) on playful brands. For serious errors (data loss, permission failures, blocking errors), empathy overrides personality — see /i-clarify.

Match copy personality to brand — banks shouldn't be wacky, but they can be warm. Examples of the right register on a playful brand:

```
"Error 404" → "This page is playing hide and seek. (And winning)"
"No messages" → "Inbox zero! You're crushing it today."
```

### Loading Messages

Write messages specific to what your product actually does:

```
- "Crunching your latest numbers..."
- "Syncing with your team's changes..."
- "Preparing your dashboard..."
```

**WARNING**: Avoid cliched loading messages like "Herding pixels", "Teaching robots to dance", "Consulting the magic 8-ball", "Counting backwards from infinity". These are AI-slop copy — instantly recognizable as machine-generated.

**NEVER**:
- Delay core functionality for delight
- Force users through delightful moments (make skippable)
- Use delight to hide poor UX
- Overdo it (less is more)
- Ignore accessibility (animate responsibly, provide alternatives)
- Make every interaction delightful (special moments should be special)
- Sacrifice performance for delight
- Be inappropriate for context (read the room)

## Verify Delight Quality

Test that delight actually delights:

- **Skippable**: Users can opt out or skip every delight moment
- **Fast**: Each moment completes in under 1 second; core functionality is never delayed
- **Performant**: No jank, no slowdown
- **Appropriate**: Matches brand and context
- **Accessible**: Honors `prefers-reduced-motion` and works with screen readers

Remember: Delight is the difference between a tool and an experience. Add personality, surprise users positively, and create moments worth sharing. But always respect usability - delight should enhance, never obstruct.

## Completion

After implementation, summarize in conversation:

1. **Changes made**: List each file changed and what was done
2. **Verification**: LLM self-check results (anti-pattern scan, consistency check). Note if Playwright was available for visual verification.
3. **Suggested next step**: Any follow-up skills that would complement this work (e.g., after /i-typeset, suggest /i-polish for a final pass)