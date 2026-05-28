# Context: Svelte-Derived Voice Guide for Hassette Docs

## Problem & Motivation
Hassette's documentation reads like competent technical writing but lacks a distinctive personality. The author wants a significant voice shift toward Svelte's documentation style — opinionated, confident, conversational in a way that respects the reader's intelligence. The current voice guide uses adjective-based descriptions ("friendly, encouraging, concrete") which produce inconsistent output when Claude rewrites pages at scale. The fix is a voice guide structured as concrete behavioral constraints that Claude can apply mechanically.

## Visual Artifacts
None.

## Key Decisions
1. The voice guide lives at `.claude/rules/voice-guide.md` in the Hassette repo (`/home/jessica/source/hassette/.claude/rules/voice-guide.md`) — it auto-loads when Claude works in the repo.
2. The existing `doc-rules.md` keeps its structural rules (page types, snippets, admonitions). The new voice guide owns tone and sentence-level style only.
3. Behavioral constraints are derived from actual Svelte doc analysis, not invented. Each constraint traces back to a Svelte passage.
4. The guide uses XML tags (`<reference-voice>`, `<style-rules>`, `<examples>`) for Claude-optimized prompt structure.
5. Target under 300 lines to stay within context budget when loaded alongside doc-rules.md and writing-quality.md.
6. Svelte patterns must be adapted to the Hassette domain (Python, Home Assistant) — not copied verbatim from a JS framework context.

## Constraints & Anti-Patterns
- Do NOT duplicate structural rules from doc-rules.md (page types, snippet format, admonition usage, layering rules)
- Do NOT duplicate AI-tell detection rules from Claudefiles' `writing-quality.md` — reference them or build on them with Hassette-specific additions only
- Do NOT use adjective-based descriptions ("friendly", "approachable") — every constraint must be a concrete action or prohibition verifiable by reading the output
- Do NOT copy Svelte patterns verbatim without adapting for the Python/HA domain
- Do NOT modify doc-rules.md beyond adding a one-line pointer to voice-guide.md

## Design Doc References
- `## Architecture` — the 4-phase approach (Analyze, Extract, Exemplify, Assemble)
- `## Functional Requirements` — FR#1-FR#9, the complete specification
- `## Acceptance Criteria` — AC#1-AC#9, measurable success conditions
- `## Key Constraints` — auto-load requirement and domain adaptation
- `## Replacement Targets` — doc-rules.md Voice section partially superseded

## Convention Examples
None — no convention examples captured during discovery.
