---
task_id: "T03"
title: "Assemble voice-guide.md and update doc-rules.md"
status: "planned"
depends_on: ["T02"]
implements: ["FR#5", "FR#6", "FR#7", "FR#8", "AC#1", "AC#5", "AC#6", "AC#7", "AC#8"]
---

## Summary
Combine the curated constraints and exemplars from T02 into the final `.claude/rules/voice-guide.md` file using the XML-tagged structure specified in the design doc. Validate against line count, duplication, and structural requirements. Add a one-line pointer in doc-rules.md. Clean up working artifacts (dotfiles).

## Prompt
Read the working artifacts:
- `/home/jessica/source/hassette/.claude/rules/.voice-constraints.md` (behavioral constraints from T02)
- `/home/jessica/source/hassette/.claude/rules/.voice-exemplars.md` (before/after pairs from T02)
- `/home/jessica/source/hassette/.claude/rules/.voice-analysis.md` (raw analysis from T01 — for the reference-voice section)

**Step 1: Write voice-guide.md**

Create `/home/jessica/source/hassette/.claude/rules/voice-guide.md` with this structure:

```markdown
# Voice Guide

<reference-voice>
[2-3 paragraph description of the target voice, synthesized from the T01 analysis.
What it sounds like. How it differs from the current Hassette voice.
Grounded in specific observations, not adjectives.]
</reference-voice>

<style-rules>
## We Always
[constraints from .voice-constraints.md, without the evidence citations — 
those stay in the analysis file for traceability]

## We Never
[forbidden patterns]

## When X, Do Y
[conditional rules]
</style-rules>

<examples>
## Before/After: Concept Page
[exemplar pair from .voice-exemplars.md]

## Before/After: Recipe Page
[exemplar pair]

## Before/After: Getting-Started Page
[exemplar pair]

[additional pairs if created]
</examples>
```

**Step 2: Validate**

Check the file against these acceptance criteria:
- Under 300 lines total (AC#7)
- Uses `<reference-voice>`, `<style-rules>`, `<examples>` XML tags (AC#5)
- No structural rules duplicated from doc-rules.md — check against the `## Page Structure`, `## Examples`, `## Layering for Skill Levels`, and `## Admonitions` sections in doc-rules.md (AC#6)
- No AI-tell detection rules duplicated from writing-quality.md — check the `## Patterns to Detect and Fix` section of `/home/jessica/Claudefiles/rules/common/writing-quality.md` (AC#8)

If over 300 lines: use 3 exemplar pairs instead of 5, trim constraint evidence citations (they live in .voice-analysis.md for traceability), shorten exemplar passages (use the most impactful section rather than full passages), or consolidate similar constraints.

**Step 3: Update doc-rules.md**

Add a one-line note at line 9 of `/home/jessica/source/hassette/.claude/rules/doc-rules.md`, immediately after the `## Voice` heading:

```
> **Voice direction lives in `voice-guide.md`.** The rules below remain for reference but voice-guide.md takes precedence for tone and sentence-level style.
```

**Step 4: Clean up intermediate artifacts**

Delete these intermediate dotfiles (their content now lives in voice-guide.md):
- `/home/jessica/source/hassette/.claude/rules/.voice-constraints.md`
- `/home/jessica/source/hassette/.claude/rules/.voice-exemplars.md`

Do NOT delete `/home/jessica/source/hassette/.claude/rules/.voice-analysis.md` — AC#3 requires that analysis artifacts are retained for traceability. It stays as a hidden dotfile.

## Focus
- The 300-line budget is real. The exemplar pairs are the biggest space consumers — each before/after pair might be 20-40 lines. With 3-5 pairs that's 60-200 lines just for examples. Budget roughly: reference-voice (15-20 lines), style-rules (80-120 lines), examples (100-150 lines).
- The XML tags are not markdown headers — they're literal `<tag>` elements that Claude recognizes as structural markers. They should appear on their own lines.
- The doc-rules.md edit is minimal — one blockquote line after the `## Voice` heading. Do not reorganize or rewrite anything else in that file.
- When checking for duplication against writing-quality.md, the key overlap areas are: copula avoidance, significance inflation, filler phrases, abstract metaphor nouns, em-dash overuse. If a constraint covers the same ground, reference writing-quality.md instead of restating.

## Verify
- [ ] FR#5: voice-guide.md uses `<reference-voice>`, `<style-rules>`, `<examples>` XML tag structure
- [ ] FR#6: File exists at `/home/jessica/source/hassette/.claude/rules/voice-guide.md`
- [ ] FR#7: No structural rules from doc-rules.md (page types, snippets, admonitions, layering) appear in voice-guide.md
- [ ] FR#8: No rule restates a rule from writing-quality.md — Hassette-specific additions only
- [ ] AC#1: File exists at the specified path
- [ ] AC#5: XML tag structure is present and correctly formed
- [ ] AC#6: Zero structural rule duplication confirmed by comparison with doc-rules.md sections: Page Structure, Examples, Layering for Skill Levels, Admonitions
- [ ] AC#7: File is under 300 lines (run `wc -l`)
- [ ] AC#8: Zero AI-tell rule duplication confirmed by comparison with writing-quality.md
