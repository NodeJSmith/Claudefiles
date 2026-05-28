# Design: Svelte-Derived Voice Guide for Hassette Docs

**Date:** 2026-05-28
**Status:** approved
**Scope-mode:** hold
**Research:** design/research/2026-05-28-llm-doc-voice-transfer/research.md

## Problem

Hassette's documentation needs a noticeably different voice. The current docs are friendly and technically accurate, but they read like competent technical writing — not like docs with a distinctive personality. Svelte's docs have the feel the author wants: opinionated, confident, conversational in a way that respects the reader's intelligence. The gap isn't quality — it's character.

The current voice guide in `doc-rules.md` describes tone with adjectives ("friendly, encouraging, concrete") and includes some behavioral rules, but adjective-based descriptions produce inconsistent output across long LLM-assisted rewrites. When Claude rewrites 77 pages, the voice drifts unless the guide is structured as concrete behavioral constraints that the model can apply mechanically.

## Goals

- A voice guide artifact that makes Claude produce consistent, Svelte-flavored prose across all 77 Hassette doc pages without per-page prompt tuning. Success metric: pages rewritten with the guide are distinguishable from pages rewritten without it in a blind comparison, and the author approves the voice (no voice-related edits needed) on first pass for >80% of pages
- Behavioral constraints ("we always / we never / when X, do Y") derived from actual Svelte doc analysis, not aspirational descriptions
- Before/after exemplars covering the major doc types (concept, recipe, getting-started, API reference) that transfer implicit style the rules can't capture
- Clear separation from the existing doc-rules.md: the voice guide owns tone and sentence-level style; doc-rules.md owns page structure, snippets, and admonitions

## Non-Goals

- Rewriting the actual Hassette docs (separate follow-up project)
- Building a reusable multi-project skill (this is Hassette-specific)
- Lint rules or automated enforcement (can be added later if voice drift is a problem)
- Modifying the existing doc-rules.md (it keeps its structural rules unchanged)

## User Scenarios

### Doc author: Hassette maintainer
- **Goal:** rewrite a Hassette doc page in the target voice using Claude
- **Context:** sitting in the Hassette repo, about to ask Claude to rewrite a page

#### Rewrite a concept page

1. **Opens a doc page for rewriting**
   - Sees: the existing page content
   - Decides: this page needs the voice update
   - Then: asks Claude to rewrite it

2. **Claude loads the voice guide automatically** (via .claude/rules/)
   - Sees: Claude's rewrite in the new voice
   - Decides: whether the output matches the target feel
   - Then: accepts, revises, or asks for another pass

3. **Reviews the rewrite against exemplars**
   - Sees: the before/after pairs for that doc type
   - Decides: whether the rewrite captures the right qualities
   - Then: commits or iterates

## Functional Requirements

- **FR#1** The voice guide contains behavioral constraints structured as "We always," "We never," and "When X, do Y" categories
- **FR#2** Behavioral constraints are derived from analysis of actual Svelte documentation pages, not invented or aspirational
- **FR#3** The voice guide contains 3-5 before/after exemplar pairs, each showing a Hassette doc passage rewritten in the target voice
- **FR#4** Exemplar pairs cover at least three distinct doc types: concept explanation, recipe, and getting-started content
- **FR#5** The voice guide is structured with XML tags for Claude consumption: `<reference-voice>`, `<style-rules>`, `<examples>` sections
- **FR#6** The voice guide lives at `.claude/rules/voice-guide.md` in the Hassette repo, alongside the existing `doc-rules.md`
- **FR#7** The voice guide does not duplicate structural rules already in doc-rules.md (page types, snippet format, admonition usage, layering rules)
- **FR#8** The voice guide does not duplicate AI-tell detection rules already in Claudefiles' writing-quality.md — it references them or builds on them with Hassette-specific additions
- **FR#9** Constraints are specific enough to be verifiable: a reviewer can check compliance by reading the output, not by subjective judgment

## Edge Cases

- A constraint from Svelte analysis conflicts with an existing doc-rules.md voice rule — the voice guide should note the conflict and state which takes precedence
- A Svelte pattern doesn't translate to technical documentation about a Python framework (Svelte docs are about a JS UI framework) — the guide should adapt patterns to the Hassette domain rather than copy them verbatim
- The voice guide is too long and exceeds practical context window budget when combined with other rules — target under 300 lines to stay within the budget when loaded alongside doc-rules.md and writing-quality.md

## Acceptance Criteria

- **AC#1** The voice guide file exists at `.claude/rules/voice-guide.md` in the Hassette repo (maps to FR#6)
- **AC#2** The file contains at least 15 behavioral constraints across the three categories (maps to FR#1, FR#9)
- **AC#3** Constraints trace to specific Svelte doc passages that were analyzed — the analysis artifacts are retained (maps to FR#2)
- **AC#4** The file contains 3-5 before/after exemplar pairs covering concept, recipe, and getting-started doc types (maps to FR#3, FR#4)
- **AC#5** The file uses XML tag structure for Claude consumption (maps to FR#5)
- **AC#6** No structural rules from doc-rules.md are duplicated in the voice guide (maps to FR#7)
- **AC#7** The file is under 300 lines (maps to edge case on context budget)
- **AC#8** No rule in the voice guide restates a rule from writing-quality.md — Hassette-specific additions are allowed, duplicates are not (maps to FR#8)
- **AC#9** Each behavioral constraint is phrased as a concrete action or prohibition, not an adjective or subjective quality — a reviewer can check compliance by reading the output without needing to judge "feel" (maps to FR#9)

## Key Constraints

- The voice guide must work as a `.claude/rules/` file that loads automatically — it cannot require manual prompt construction or special invocation
- Svelte's docs are for a JavaScript UI framework; Hassette is a Python Home Assistant automation framework. Voice patterns must be adapted, not copied verbatim. "Playful touches" that work for a trendy JS framework may not work for home automation infrastructure docs.

## Dependencies and Assumptions

- Access to Svelte's documentation at svelte.dev/docs for analysis (web fetch required)
- The existing doc-rules.md remains unchanged and continues to govern page structure
- The Claudefiles writing-quality.md continues to provide base AI-tell detection
- Assumes Claude Code loads all `.claude/rules/*.md` files into context when working in the Hassette repo

## Architecture

### Phase 1: Analyze Svelte Voice

Fetch 5-8 representative pages from svelte.dev/docs spanning different content types (tutorial, API reference, guide, migration). Feed them to Claude with a structured analysis prompt that extracts:

- Sentence-level patterns (length distribution, paragraph structure, how sentences open)
- Reader address patterns (pronouns, imperative vs. declarative, where "you" appears)
- Information sequencing (code-first vs. explanation-first, how complexity layers)
- Rhetorical moves (how concepts are introduced, how limitations are disclosed, how alternatives are presented)
- Vocabulary patterns (preferred verbs, forbidden constructions, formality level)

Also reverse-engineer: "what system prompt would produce this writing?"

### Phase 2: Extract and Curate Constraints

Take the raw analysis and distill into behavioral constraints structured as:

```
## We Always
- [rule] — [evidence from Svelte analysis]

## We Never  
- [rule] — [evidence from Svelte analysis]

## When X, Do Y
- When [context], [rule] — [evidence from Svelte analysis]
```

Merge with relevant voice rules from the existing doc-rules.md (lines 29-38) — keep what aligns with the Svelte analysis, flag conflicts. Adapt Svelte-specific patterns to the Hassette domain.

Target: 15-25 constraints across the three categories. Each must be specific enough that compliance is verifiable by reading the output.

### Phase 3: Create Exemplars

Select 3-5 passages from existing Hassette docs that represent different doc types. For each:
1. The original passage (as-is from the current docs)
2. The same content rewritten in the target voice, applying the constraints from Phase 2

Exemplar sources:
- Bus overview page (concept — `/docs/pages/core-concepts/bus/index.md`)
- Motion lights recipe (recipe — `/docs/pages/recipes/motion-lights.md`)
- First automation tutorial (getting-started — `/docs/pages/getting-started/first-automation.md`)
- Optionally: CLI commands reference, migration guide

### Phase 4: Assemble Voice Guide

Write the final `.claude/rules/voice-guide.md` file with this structure:

```markdown
# Voice Guide

<reference-voice>
[2-3 paragraph description of the target voice, grounded in the Svelte analysis — 
what it sounds like, how it differs from the current Hassette voice]
</reference-voice>

<style-rules>
## We Always
[behavioral constraints]

## We Never
[forbidden patterns]

## When X, Do Y
[conditional rules]
</style-rules>

<examples>
## Before/After: Concept Page
[exemplar pair]

## Before/After: Recipe Page
[exemplar pair]

## Before/After: Getting-Started Page
[exemplar pair]
</examples>
```

### What Changes

- **New file:** `.claude/rules/voice-guide.md` in the Hassette repo
- **Existing doc-rules.md:** The Voice section (lines 9-55) becomes partially redundant. The voice guide supersedes it for tone; the structural rules remain. A note should be added to doc-rules.md pointing to voice-guide.md for voice direction.

## Replacement Targets

The Voice section of doc-rules.md (lines 9-55) is partially superseded by the new voice guide. The new guide takes precedence for tone and sentence-level style. However, doc-rules.md is not being modified in this scope — a one-line note directing readers to voice-guide.md is the only change needed there.

## Documentation Updates

- Add a one-line note to the top of doc-rules.md's Voice section: reference voice-guide.md as the authoritative voice direction
- No other documentation updates required — the voice guide is itself a documentation artifact

## Alternatives Considered

### Overwrite doc-rules.md entirely
Merge voice and structural rules into one file. Rejected because: doc-rules.md is well-established and the structural rules (page types, snippets, admonitions) are orthogonal to voice. Keeping them separate allows updating voice independently and keeps each file focused.

### Build a Claudefiles skill
A reusable `/mine.write-like-svelte` skill that could be pointed at any project. Rejected because: the voice guide needs to be Hassette-specific (adapted patterns, domain-specific exemplars). A generic skill would either be too abstract or require per-project configuration that makes it no easier than a direct rule file.

### Use Voice Analyser MCP
Automate voice extraction via the Voice Analyser MCP tool. Rejected for now because: adding an MCP dependency for a one-time analysis is over-engineering. The manual analysis approach (fetch pages, prompt Claude) achieves the same result with tools already available. Worth revisiting if voice guides become a recurring need across projects.

## Test Strategy

N/A — no test infrastructure applies to a rule file. Verification is qualitative: feed the voice guide to Claude alongside a Hassette doc page and check whether the rewrite matches the target voice. This verification happens during the exemplar creation phase (Phase 3) and serves as the functional test.

## Impact

### Changed Files
- **New:** `.claude/rules/voice-guide.md` in the Hassette repo (~200-300 lines)
- **Modified:** `.claude/rules/doc-rules.md` — one-line addition pointing to voice-guide.md

### Behavioral Invariants
- doc-rules.md structural rules (page types, snippet format, admonition usage) must continue working unchanged
- The voice guide must not conflict with writing-quality.md's AI-tell detection rules

### Blast Radius
Narrow. The voice guide is a new file that only affects future doc rewrites. No existing behavior changes until someone actively uses it to rewrite pages.

## Open Questions

None — all decisions resolved during discovery.
