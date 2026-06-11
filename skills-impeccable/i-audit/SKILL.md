---
name: i-audit
description: 'Use when the user says: "audit this UI", "frontend quality", "full UI audit", "design audit". Comprehensive audit of interface quality across accessibility, performance, theming, and responsive design.'
user-invocable: true
---

Run systematic quality checks and generate a comprehensive audit report with prioritized issues and actionable recommendations. Don't fix issues - document them for other commands to address.

## MANDATORY PREPARATION

Read `${CLAUDE_HOME:-~/.claude}/skills/i-frontend-design/SKILL.md` for design principles and anti-patterns. Check for design context (`design/context.md`, `.impeccable.md`, or `design/direction.md`) — if found, use it to inform brand-specific judgments. If no context exists, **proceed anyway** but note in the report: "No design context found — anti-pattern checks are universal only; brand-specific judgments may not apply. Run `/i-teach-impeccable` to establish context."

Audits are read-only diagnostics — they should never be blocked by missing context.

---

## Diagnostic Scan

Scan across these dimensions. The specific checks within each are standard — work through them against the reference files rather than from a checklist here:

1. **Accessibility** — contrast, ARIA, keyboard nav, semantic HTML, alt text, form labeling. See [interaction-design.md](../i-frontend-design/reference/interaction-design.md).
2. **Performance** — layout thrashing, layout-property animations, missing lazy-load, bundle bloat, needless re-renders.
3. **Theming** — hard-coded colors vs tokens, dark-mode coverage and contrast, token consistency.
4. **Responsive** — fixed widths, sub-44px touch targets, horizontal scroll, text-scaling breakage, missing breakpoints.
5. **Anti-Patterns (CRITICAL)** — check against the [anti-patterns reference](../i-frontend-design/reference/anti-patterns.md) for AI slop tells and general design anti-patterns.

**CRITICAL**: This is an audit, not a fix. Document issues thoroughly with clear explanations of impact. Use other commands (polish, optimize, harden, etc.) to fix issues after audit.

## Generate Comprehensive Report

Create a detailed audit report with the following structure:

### Anti-Patterns Verdict
**Start here.** Pass/fail: Does this look AI-generated? List specific tells from the [anti-patterns reference](../i-frontend-design/reference/anti-patterns.md). Be brutally honest.

### Executive Summary
- Total issues found (count by severity)
- Most critical issues (top 3-5)
- Overall quality score (if applicable)
- Recommended next steps

### Detailed Findings by Severity

For each issue, document:
- **Location**: Where the issue occurs (component, file, line)
- **Severity**: Critical / High / Medium / Low
- **Category**: Accessibility / Performance / Theming / Responsive
- **Description**: What the issue is
- **Impact**: How it affects users
- **WCAG/Standard**: Which standard it violates (if applicable)
- **Recommendation**: How to fix it
- **Suggested command**: Route to the most relevant modification skill:
  - Contrast, color system, palette issues → `/i-colorize`
  - Layout, spacing, alignment, hierarchy → `/i-layout`
  - Typography, font choices, type scale → `/i-typeset`
  - Animation, motion, transition issues → `/i-animate`
  - Performance, load time, rendering → `/i-optimize`
  - Responsive, mobile, touch targets → `/i-adapt`
  - Hard-coded values, design system drift, consistency → `/i-polish`
  - Missing states, error handling, i18n, onboarding → `/i-harden`
  - Copy, labels, error messages → `/i-clarify`
  - Overall too busy/noisy → `/i-quieter`
  - Overall too generic/bland → `/i-bolder`
  - Final polish pass → `/i-polish`

Group findings under four severity tiers:
- **Critical** — blocks core functionality or violates WCAG A
- **High** — significant usability/accessibility impact, WCAG AA violations
- **Medium** — quality issues, WCAG AAA, performance concerns
- **Low** — minor inconsistencies, optimization opportunities

Then call out systemic patterns (the same defect across many components), positive findings worth keeping, and a priority-ordered fix plan that groups findings by the skill that fixes them (using the per-finding "Suggested command" routing).

**IMPORTANT**: Be thorough but actionable. Too many low-priority issues creates noise. Focus on what actually matters.

**NEVER**:
- Report issues without explaining impact (why does this matter?)
- Mix severity levels inconsistently
- Skip positive findings (celebrate what works)
- Provide generic recommendations (be specific and actionable)
- Forget to prioritize (everything can't be critical)
- Report false positives without verification

Remember: You're a quality auditor with exceptional attention to detail. Document systematically, prioritize ruthlessly, and provide clear paths to improvement. A good audit makes fixing easy.

## Completion

Run `get-skill-tmpdir i-audit` and write the audit report to `<tmpdir>/audit-YYYY-MM-DD.md`. Then summarize in conversation:

1. **Verdict**: One-line overall assessment
2. **Top findings**: The 3-5 most important issues
3. **Suggested next step**: Which modification skill to run first