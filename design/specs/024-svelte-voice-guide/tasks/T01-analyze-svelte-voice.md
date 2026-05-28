---
task_id: "T01"
title: "Analyze Svelte docs and extract voice patterns"
status: "done"
depends_on: []
implements: ["FR#2", "AC#3"]
---

## Summary
Fetch 5-8 representative pages from Svelte's documentation spanning different content types (tutorial, API reference, guide). Analyze them to extract concrete voice patterns — sentence structure, reader address, information sequencing, rhetorical moves, vocabulary. Also reverse-engineer: "what system prompt would produce this writing?" The output is a raw analysis document that T02 will distill into behavioral constraints.

## Prompt
Fetch pages from svelte.dev/docs using WebFetch. Target 5-8 pages across these content types:

- Tutorial/getting-started content (e.g., introduction, basic concepts)
- API reference (e.g., component lifecycle, reactivity)
- Guide/concept page (e.g., stores, transitions, actions)
- Migration or "what's new" content (if available)

For each page, extract and document:

1. **Sentence-level patterns** — average sentence length, paragraph structure (how many sentences per paragraph), how sentences open (imperative? declarative? question?), use of fragments
2. **Reader address patterns** — use of "you/your", imperative mood frequency, where the reader is directly addressed vs. where the writing is impersonal
3. **Information sequencing** — does code appear before or after explanation? How is complexity layered? Where do caveats and limitations appear relative to the main point?
4. **Rhetorical moves** — how are new concepts introduced? How are limitations disclosed? How are alternatives presented? How does the writing handle "you might expect X but actually Y"?
5. **Vocabulary patterns** — preferred verbs (short anglo-saxon vs. latinate?), forbidden constructions (passive voice? nominalization?), formality level, technical jargon handling
6. **Distinctive qualities** — what makes this writing recognizably "Svelte docs" vs. generic technical writing?

Then reverse-engineer: "What system prompt would you write to produce this exact documentation style? Be specific about sentence construction, not just adjectives."

Write the complete analysis to `/home/jessica/source/hassette/.claude/rules/.voice-analysis.md` (dotfile — working artifact, not the final guide). Include the URLs analyzed and specific passage quotes as evidence for each pattern identified.

## Focus
- Svelte's docs are at svelte.dev/docs — the Svelte 5 docs specifically
- The analysis must produce concrete, quotable evidence — not impressionistic descriptions. Every pattern claim needs a specific passage quote from the docs
- The reverse-engineered system prompt is a key artifact — it will inform the final voice guide's `<reference-voice>` section
- This is a working document (dotfile prefix) — it doesn't need to be polished, but it needs to be complete and well-evidenced

## Verify
- [ ] FR#2: Analysis contains specific Svelte doc passage quotes as evidence for each pattern identified
- [ ] AC#3: Analysis document exists at `/home/jessica/source/hassette/.claude/rules/.voice-analysis.md` with URLs of analyzed pages and traceable evidence
