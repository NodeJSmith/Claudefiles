---
name: mine.ux-antipatterns
description: "Use when the user says: \"UX anti-patterns scan\". Detects UX anti-patterns in frontend code — layout shifts, missing feedback, broken forms, race conditions, accessibility gaps."
user-invocable: true
---

# UX Anti-Pattern Detection

Scan frontend code for patterns that cause user frustration.

## Core Axioms

| # | Axiom | Rule |
|---|-------|------|
| 1 | **Acknowledge every action** | Visible feedback within 100ms, even if the result takes seconds. |
| 2 | **Never destroy user input** | Not on error, not on navigation, not on timeout, not on refresh. |
| 3 | **State survives the unexpected** | Refresh, double-clicks, network loss — handle edge cases. |
| 4 | **Most recent intent wins** | Stale responses must never overwrite a newer user action. |
| 5 | **Explain every constraint** | Disabled? Say why. Failed? Say how to fix it. Succeeded? Say what happened. |
| 6 | **Don't fight the platform** | Browser conventions, OS gestures, native controls, and a11y APIs encode billions of hours of UX research. |

## When NOT to Use

- Backend-only code with no UI layer
- CLI tools or non-visual interfaces
- Design system tokens/docs without implementation code
- Pure API or data-layer reviews

## Anti-Pattern Categories

| # | Category | User Harm |
|---|----------|-----------|
| 1 | Layout Stability | Click target moves; wrong thing clicked. |
| 2 | Feedback & Responsiveness | Action feels ignored; user retries or loses trust. |
| 3 | Error Handling & Recovery | User stuck with no way forward; input destroyed. |
| 4 | Forms & Input Interference | Platform fights typing; data mangled, editing broken. |
| 5 | Focus | UI yanks user elsewhere mid-typing. |
| 6 | Notifications & Dialogs | Flow broken; attention taxed by noise; ambiguous choices. |
| 7 | Navigation & State Persistence | Can't go back; context evaporates on refresh. |
| 8 | Scroll & Viewport | Content unreachable or unstable. |
| 9 | Timing & Race Conditions | Actions fire twice, responses arrive stale, sessions expire mid-task. |
| 10 | Accessibility as UX | Keyboard users can't navigate, touch users locked out. |
| 11 | Visual Layering | Elements overlap, clip, or hide each other. |
| 12 | Mobile & Viewport-Specific | Keyboard covers input, layout jumps, tap targets unresponsive. |
| 13 | Cumulative Decay | App degrades over time; preferences lost, performance rots. |

## Quick Reference: Symptom -> Category

| User complaint | Cat |
|---|---|
| "Button does nothing when I click it" | 2 |
| "I clicked the wrong thing — it moved" | 1 |
| "I lost my form data" | 4 |
| "Something went wrong with no explanation" | 3 |
| "The page jumped while I was typing" | 5 |
| "I got the same notification 5 times" | 6 |
| "I logged in and it forgot where I was going" | 7 |
| "I scrolled back and lost my place" | 8 |
| "My order was placed twice" | 9 |
| "I can't use this with my keyboard" | 10 |
| "The dropdown is hidden behind the modal" | 11 |
| "The keyboard covers the input on my phone" | 12 |
| "The app gets slower over time" | 13 |

## Workflow

1. Read `references/antipatterns.md` to load detection heuristics.
2. Scan the code under review against each applicable category.
3. Report findings grouped by anti-pattern, citing file:line locations.
4. For each finding: state the anti-pattern name, the user harm, and a concrete fix.
5. If no anti-patterns found, say the code is clean. Don't manufacture findings.

## Common Mistakes

- **Flagging style preferences as anti-patterns.** A non-standard button shape is a design choice, not a UX violation. Only flag patterns that cause measurable user harm.
- **Ignoring context.** A disabled button inside a wizard step IS explained by the wizard's flow. Check for nearby explanatory elements before reporting.
- **Suggesting fixes that break accessibility.** A fix that adds a visual indicator but removes keyboard access trades one violation for another.
- **Over-reporting handled edge cases.** If the code already has an AbortController, don't flag race conditions. Read the implementation first.
- **Reporting framework internals.** React's `key` prop remounts, Next.js loading states, SvelteKit form actions may handle anti-patterns at the framework level.
