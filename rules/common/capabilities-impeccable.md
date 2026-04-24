# Impeccable Design Skills

**BLOCKING REQUIREMENT**: When a user request matches a trigger phrase below, you MUST invoke the corresponding skill **before** responding. Do NOT perform the task directly — dispatch to the skill. This applies even if you could answer inline.

## Intent Routing

<!-- NOTE: "design this UI" = visual direction (i-teach-impeccable); "design this change" = architecture doc (mine.define) -->

| User says something like... | Invoke |
|---|---|
| "audit this UI", "frontend quality", "full UI audit", "design audit" | `/i-audit` |
| "critique this UI", "design critique", "review this interface", "does this look AI-generated" | `/i-critique` |
| "fix the typography", "improve the type", "font choices" | `/i-typeset` |
| "fix the colors", "color system", "palette needs work" | `/i-colorize` |
| "fix the layout", "arrange this", "visual hierarchy", "spacing issues", "crowded UI" | `/i-layout` |
| "too busy", "too noisy", "reduce visual clutter" | `/i-quieter` |
| "make it bolder", "more distinctive", "too generic" | `/i-bolder` |
| "polish this UI", "final pass", "pixel-perfect", "normalize the design", "make it consistent", "align with design system" | `/i-polish` |
| "add animations", "motion design", "transitions" | `/i-animate` |
| "responsive design", "make it mobile-friendly", "adapt for mobile" | `/i-adapt` |
| "improve the copy", "error messages are confusing", "UX writing" | `/i-clarify` |
| "add delight", "make it more fun", "moments of joy" | `/i-delight` |
| "too complex", "simplify this UI", "strip it down" | `/i-distill` |
| "production hardening", "handle edge cases in UI", "make it resilient", "improve onboarding", "empty states", "first-run experience" | `/i-harden` |
| "optimize frontend performance", "improve load time", "fix rendering" | `/i-optimize` |
| "design this UI", "design this dashboard", "look and feel", "establish design tokens", "plan the look and feel", "UI planning", "design system for this project", "craft the interface" | `/i-teach-impeccable` |
| "setup impeccable", "design context setup", "teach impeccable" | `/i-teach-impeccable` |
| "shape this feature", "plan the UX", "design brief", "UX planning" | `/i-shape` |
| "go all out", "make it extraordinary", "overdrive", "wow factor", "push the limits" | `/i-overdrive` |
