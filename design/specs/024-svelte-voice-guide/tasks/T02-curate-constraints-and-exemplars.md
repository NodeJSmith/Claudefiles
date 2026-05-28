---
task_id: "T02"
title: "Curate behavioral constraints and create exemplars"
status: "done"
depends_on: ["T01"]
implements: ["FR#1", "FR#3", "FR#4", "FR#9", "AC#2", "AC#4", "AC#9"]
---

## Summary
Take the raw Svelte voice analysis from T01 and distill it into behavioral constraints structured as "We always / We never / When X, do Y." Then create 3-5 before/after exemplar pairs by selecting passages from existing Hassette docs and rewriting them in the target voice, applying the constraints. The constraints and exemplars are the core intellectual work — T03 assembles them into the final file.

## Prompt
Read the analysis at `/home/jessica/source/hassette/.claude/rules/.voice-analysis.md`.

**Step 1: Distill behavioral constraints**

Convert each pattern from the analysis into a concrete behavioral rule. Structure as three categories:

- **We Always** — positive constraints (things every sentence/paragraph/section should do)
- **We Never** — forbidden patterns (specific constructions to avoid)
- **When X, Do Y** — conditional rules for different contexts (tutorials vs. reference vs. recipes)

Rules for constraint writing:
- Each constraint must be a concrete action or prohibition, not an adjective ("Start concept explanations with what the reader will do" not "be practical")
- Each constraint must be verifiable by reading the output — a reviewer can check compliance without subjective judgment
- Each constraint must cite the Svelte evidence it was derived from (passage quote or URL+section)
- Target 15-25 constraints total across the three categories
- Adapt Svelte patterns to the Hassette domain — Svelte writes about reactive UI components; Hassette writes about async Python automations. The sentence-level style transfers; the domain-specific framing does not.

**Step 2: Merge with existing voice rules**

Read the existing voice rules in the `### Voice rules` section of `/home/jessica/source/hassette/.claude/rules/doc-rules.md` (the 9 numbered rules under that heading). For each existing rule:
- If it aligns with a Svelte-derived constraint, note the alignment (no duplication needed)
- If it conflicts with a Svelte pattern, note the conflict and decide which takes precedence (prefer the Svelte-derived version unless the existing rule is Hassette-domain-specific)
- If it covers something the Svelte analysis didn't address, mark it for inclusion as-is

**Step 3: Create before/after exemplars**

Select passages from these Hassette doc files:
- Concept: `/home/jessica/source/hassette/docs/pages/core-concepts/bus/index.md` (first 30-40 lines of prose)
- Recipe: `/home/jessica/source/hassette/docs/pages/recipes/motion-lights.md` (the "How It Works" section)
- Getting-started: `/home/jessica/source/hassette/docs/pages/getting-started/first-automation.md` (Step 1 or Step 3)

For each passage:
1. Copy the original text verbatim (the "before")
2. Rewrite it applying all the behavioral constraints (the "after")
3. Note which constraints each rewrite demonstrates

The rewrites should be noticeably different from the originals — this is a significant voice shift, not a polish.

**Step 4: Write working artifacts**

Write the curated constraints to `/home/jessica/source/hassette/.claude/rules/.voice-constraints.md`
Write the exemplar pairs to `/home/jessica/source/hassette/.claude/rules/.voice-exemplars.md`

Both are dotfiles (working artifacts for T03 to assemble).

## Focus
- The existing doc-rules.md voice rules (under `### Voice rules`) are: use "you/your", lead with what it does, use concrete examples in prose, short sentences for concepts, active voice, name the benefit, don't hedge, don't over-explain, celebrate simplicity when real. Most of these will align with Svelte patterns.
- The existing anti-patterns in doc-rules.md (under `### Prose anti-patterns`) cover: copula avoidance, significance inflation, dangling -ing phrases, synonym cycling, filler hedging, abstract metaphor nouns. These overlap with Claudefiles' writing-quality.md — the voice guide should NOT duplicate them.
- The Hassette docs already use "you/your" and lead with benefits. The voice shift is about something beyond those basics — probably sentence rhythm, confidence level, information density, and rhetorical posture.
- Exemplar rewrites must be noticeably different. If the before and after read similarly, the constraints aren't capturing the voice shift.

## Verify
- [ ] FR#1: Constraints are structured as "We Always," "We Never," and "When X, Do Y" categories
- [ ] FR#3: 3-5 before/after exemplar pairs exist, each showing a Hassette passage rewritten in the target voice
- [ ] FR#4: Exemplar pairs cover concept (bus), recipe (motion lights), and getting-started (first automation) doc types
- [ ] FR#9: Each constraint is phrased as a concrete action or prohibition verifiable by reading output
- [ ] AC#2: At least 15 behavioral constraints exist across the three categories
- [ ] AC#4: Exemplar pairs cover concept, recipe, and getting-started doc types
- [ ] AC#9: Each constraint starts with a verb or names a specific construction to avoid — no constraint's primary directive is an adjective like "friendly" or "confident"
