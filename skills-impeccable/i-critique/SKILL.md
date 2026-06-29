---
name: i-critique
description: 'Use when the user says: "critique this UI", "design critique", "review this interface", "does this look AI-generated". Evaluate design effectiveness with actionable feedback.'
user-invocable: true
---

## MANDATORY PREPARATION

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/i-frontend-design/SKILL.md` for design principles and anti-patterns. Check for design context (`design/context.md`, `.impeccable.md`, or `design/direction.md`) — if found, use it to inform brand-specific judgments. If no context exists, **proceed anyway** but note: "No design context found — critique uses universal design principles only. Run `/i-teach-impeccable` to establish brand context." Additionally gather: what the interface is trying to accomplish.

Critiques are read-only diagnostics — they should never be blocked by missing context.

---

Conduct a holistic design critique, evaluating whether the interface actually works—not just technically, but as a designed experience. Think like a design director giving feedback.

## Design Critique

Evaluate the interface across these dimensions:

### 1. AI Slop Detection (CRITICAL)

**This is the most important check.** Does this look like every other AI-generated interface from 2024-2025?

Review the design against all the anti-patterns in [`../i-frontend-design/reference/anti-patterns.md`](../i-frontend-design/reference/anti-patterns.md) — they are the fingerprints of AI-generated work.

**The test**: If you showed this to someone and said "AI made this," would they believe you immediately? If yes, that's the problem.

### Remaining dimensions

Work each as a single judgment call:

- **Visual hierarchy** — can you spot the one primary action in 2 seconds, or do elements of equal weight compete?
- **Information architecture** — is the structure intuitive to a new user, or is there cognitive overload from too many choices at once?
- **Emotional resonance** — what does it evoke, is that intentional, and would the target user feel "this is for me"?
- **Discoverability & affordance** — are interactive elements obviously interactive without instructions?
- **Composition & balance** — is whitespace intentional or leftover; does asymmetry read as designed or accidental?
- **Typography as communication** — does the hierarchy signal read-order, and is body text comfortable (line length, spacing, size)?
- **Color with purpose** — does color communicate rather than decorate, and does meaning survive for colorblind users?
- **States & edge cases** — do empty/loading/error/success states guide toward action rather than dead-end?
- **Microcopy & voice** — is it clear, unambiguous, and does it sound like the right human for this brand?

## Generate Critique Report

Structure your feedback as a design director would:

### Anti-Patterns Verdict
**Start here.** Pass/fail: Does this look AI-generated? List specific tells from the [anti-patterns reference](../i-frontend-design/reference/anti-patterns.md). Be brutally honest.

### Overall Impression
A brief gut reaction—what works, what doesn't, and the single biggest opportunity.

### What's Working
Highlight 2-3 things done well. Be specific about why they work.

### Priority Issues
The 3-5 most impactful design problems, ordered by importance:

For each issue:
- **What**: Name the problem clearly
- **Why it matters**: How this hurts users or undermines goals
- **Fix**: What to do about it (be concrete)
- **Command**: Route to the most relevant modification skill (e.g., color → `/i-colorize`, layout → `/i-layout`, typography → `/i-typeset`, performance → `/i-optimize`, responsive → `/i-adapt`, consistency → `/i-polish`). Do not suggest diagnostic skills.

### Minor Observations
Quick notes on smaller issues worth addressing.

### Questions to Consider
Provocative questions that might unlock better solutions:
- "What if the primary action were more prominent?"
- "Does this need to feel this complex?"
- "What would a confident version of this look like?"

**Remember**: Be direct and specific ("the submit button," not "some elements") — name what's wrong, why it hurts users, and the concrete fix. Don't soften criticism, and prioritize ruthlessly: if everything is important, nothing is.

## Completion

Run `get-skill-tmpdir i-critique` and write the audit report to `<tmpdir>/critique-YYYY-MM-DD.md`. Then summarize in conversation:

1. **Verdict**: One-line overall assessment
2. **Top findings**: The 3-5 most important issues
3. **Suggested next step**: Which modification skill to run first