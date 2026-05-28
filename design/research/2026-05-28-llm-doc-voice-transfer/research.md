---
topic: "LLM documentation voice transfer"
date: 2026-05-28
status: Draft
---

# Prior Art: Conditioning LLMs to Write in a Specific Documentation Voice

## The Problem

You want to rewrite Hassette's docs with a consistent voice modeled on Svelte's docs. The challenge isn't getting Claude to write *well* -- it's getting Claude to write *the same way* across 78 markdown files, and to write in a voice that's identifiably *yours* rather than default Claude prose.

LLMs can match explicit style markers (sentence length, vocabulary, structure) reliably. They struggle with implicit style -- the stuff that makes writing feel like a specific person wrote it. Documentation voice is mostly explicit markers, which puts this squarely in the territory where style transfer works.

## How We Do It Today

Hassette already has a 140-line doc rules file covering voice, page structure, example patterns, and anti-patterns. The global `writing-quality.md` adds AI-tell detection (copula avoidance, significance inflation, em-dash overuse). The existing voice is "friendly, patient, concrete -- like a friend who's already built this and wants to save you mistakes." The gap isn't having *no* voice guide -- it's that the current guide is broad enough to produce variation across long rewrites, and it describes the voice in adjectives rather than behavioral constraints.

## Patterns Found

### Pattern 1: Analyze-Extract-Encode (Use the LLM to Build the Style Guide)

**Used by**: CXL framework, Voice Analyser MCP, Nina Panickssery, Search Engine Land
**How it works**: Feed 5-10 representative Svelte doc pages to Claude and ask it to analyze the writing patterns. Not "describe the tone" but "identify concrete attributes": average sentence length, paragraph structure, how examples are introduced relative to concepts, vocabulary preferences, how the reader is addressed, what rhetorical moves appear.

A second pass reverse-engineers the prompts that could have produced each sample -- this surfaces implicit instructions the analysis missed. The output becomes a structured style guide written in language the LLM already understands.

Voice Analyser MCP automates this with 16 linguistic analysers (sentence rhythm, vocabulary frequency, burstiness, forbidden words) and produces a machine-readable guide with validation checklists.

**Strengths**: Fast to bootstrap. Catches patterns humans miss. The LLM-generated guide uses its own vocabulary, reducing interpretation gaps.
**Weaknesses**: Only as good as the reference samples. May over-index on surface features (sentence length) and miss deeper patterns (information sequencing, when examples appear).
**Example**: https://github.com/houtini-ai/voice-analyser-mcp

### Pattern 2: Few-Shot Exemplar Pairing

**Used by**: Latitude, Relevance AI, Towards AI, PromptHub
**How it works**: Include 2-5 before/after examples directly in the prompt. Each shows a passage in the source style and the same content rewritten in the target voice. The model pattern-matches against concrete transformations rather than interpreting abstract descriptions.

This transfers implicit style knowledge that no written guide can capture. "Conversational but technically precise" means different things to different people. Showing the model "this became that" transfers the knowledge directly. Examples should cover different content types: concept explanation, API reference, troubleshooting, code walkthrough.

**Strengths**: Transfers implicit style that descriptions miss. 3-5 examples generalize surprisingly well.
**Weaknesses**: Creating good before/after pairs takes manual effort. Examples consume context window space. Inconsistent examples produce inconsistent output.
**Example**: https://latitude.so/blog/how-examples-improve-llm-style-consistency

### Pattern 3: Behavioral Constraints Over Adjective Descriptions

**Used by**: CXL framework, Spencer Roberts, SingleGrain
**How it works**: Replace adjective descriptions with specific behavioral rules. "Two-sentence paragraphs" not "punchy." "Lead with what the reader will *do*, not what the feature *is*" not "practical." "Never use 'simply' before an instruction" not "respectful."

Structure as three categories: "We always" (positive constraints), "We never" (forbidden patterns), "When X, do Y" (conditional rules for tutorials vs. API docs vs. guides). This makes the voice guide actionable rather than aspirational.

**Strengths**: Specific and unambiguous. Easy to verify (grep for forbidden words, count sentences). Maps to how LLMs process instructions.
**Weaknesses**: Risk of over-specifying into robotic output. Rules alone can't capture everything about a voice -- pair with examples.
**Example**: https://cxl.com/blog/llm-tone-of-voice/

### Pattern 4: Lint-and-Fix Loop

**Used by**: Corelight (llm-styleguide-helper), Vale ecosystem
**How it works**: Define style rules as a linter config (Vale with custom rules). Run the linter on Claude's output to detect violations. Feed violations back as a fix prompt. Repeat until clean or 3 iterations with no improvement. Separates detection (deterministic) from correction (LLM-powered).

**Strengths**: Catches drift that accumulates over long documents. Deterministic validation provides hard guarantees on measurable rules.
**Weaknesses**: Only catches what you configure. Subjective qualities (rhythm, flow) are hard to lint. Fix loops can degrade other qualities while fixing flagged issues.
**Example**: https://corelight.com/blog/microsoft-style-guide-llm

### Pattern 5: Multi-Pass Separation

**Used by**: ScoutOS, general prompt engineering practice
**How it works**: Separate rewriting into distinct passes. Pass 1: restructure (headings, flow, information architecture). Pass 2: apply voice (sentence style, vocabulary, reader address). Pass 3: polish (jargon removal, clarity, examples). Each pass has a focused prompt.

**Strengths**: Each pass is simpler. Easier to debug which dimension is failing. Can iterate on one dimension without disturbing others.
**Weaknesses**: 3x the tokens. Later passes can undo earlier work. More workflow complexity.
**Example**: https://www.scoutos.com/blog/top-5-llm-prompts-for-re-writing-your-technical-documentation

### Pattern 6: Claude-Specific Structural Prompting

**Used by**: Anthropic documentation
**How it works**: For Claude, structure the prompt with reference docs at the top (20K+ tokens of Svelte pages), style guide in the middle (using XML tags: `<reference-voice>`, `<style-rules>`, `<examples>`), and the rewriting instruction plus source doc at the bottom. Anthropic's testing shows queries at the end improve quality by up to 30% with complex multi-document inputs.

**Strengths**: Leverages Claude's specific training. XML tags eliminate ambiguity about what's reference material vs. instructions.
**Weaknesses**: Claude-specific. Large reference docs eat context window.
**Example**: https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips

## Anti-Patterns

- **Adjective-only descriptions**: "Friendly, clear, approachable" gives the model too much latitude. Each generation interprets differently. Behavioral constraints are more reliable. [CXL]
- **Single-pass rewriting of long docs**: Voice drifts. The model starts strong then reverts to default. Break into sections and rewrite each independently against the same reference. [Latitude]
- **Aspirational voice guides**: Using your brand guidelines instead of analyzing your actual best writing produces output that matches what you *say* your voice is, not what it *is*. Extract from real samples. [CXL]
- **Relying on implicit transfer**: Dropping reference docs in context without explicit instructions about what to do with them. Claude can recognize style but won't automatically apply it without being told to. You need both the reference material and explicit instructions. [arXiv: "Catch Me If You Can"]

## Emerging Trends

**MCP-based voice analysis**: Voice Analyser MCP (v2.0.0) represents a shift toward automated voice extraction as a build step. Crawls a sitemap, runs 16 linguistic analysers, outputs a machine-readable style guide. Early but practical.

**Register analysis for automatic prompt construction**: Academic work decomposing "voice" into measurable linguistic dimensions (formality, interactivity, narrativity) and auto-generating style transfer prompts. Research-stage, but the decomposition framework is useful even when applied manually. [arXiv: 2505.00679]

**Lint-LLM hybrid pipelines**: Vale linting + LLM correction is emerging as the practical pattern for style enforcement at scale. Separates "what to check" (human rules) from "how to fix" (LLM generation).

## Relevance to Us

You're in a strong position. Hassette already has a doc rules file and global writing-quality rules -- you're not starting from zero. The gap is upgrading from adjective-based voice description to behavioral constraints with exemplars.

Svelte's docs are good reference material for LLM transfer because the voice is structural rather than deeply personal. It's about choices: how information is sequenced, when code appears, how the reader is addressed, how complexity is layered. These are explicit markers LLMs handle well, unlike trying to capture an individual author's quirks.

The existing `writing-quality.md` already encodes some behavioral constraints (forbidden words, anti-patterns). Extending this with Svelte-specific patterns would slot naturally into the current setup.

Your setup has a natural home for this: a doc-writing skill or rule file that combines a Svelte-derived style guide (Pattern 1), a few before/after exemplars (Pattern 2), behavioral constraints (Pattern 3), and Claude-specific prompt structure (Pattern 6). The lint loop (Pattern 4) and multi-pass approach (Pattern 5) are worth knowing about but probably overkill for a project this size.

## Recommendation

**Combine Patterns 1 + 2 + 3 + 6 into a doc-rewriting skill or rule file.** Here's the concrete sequence:

1. **Extract**: Feed 5-8 representative Svelte doc pages to Claude and ask it to analyze the voice as behavioral constraints (not adjectives). Also ask it to reverse-engineer the prompts that could have produced each page.
2. **Curate**: Take the extracted rules, merge with your existing doc-rules.md and writing-quality.md, resolve conflicts, trim to ~40-60 rules structured as "We always / We never / When X, do Y."
3. **Exemplify**: Manually create 3-5 before/after pairs showing a Hassette doc passage rewritten in the target voice. Cover different content types (concept, recipe, API reference).
4. **Encode**: Build this into a rule file or skill that structures the prompt Claude-style: reference Svelte pages at top, style guide with XML tags in middle, source doc + instructions at bottom.
5. **Test on one page**: Rewrite a single Hassette doc, compare against the Svelte voice, iterate the guide until the output sounds right.
6. **Roll out**: Apply to remaining pages, section by section (not full docs in one pass -- voice drifts).

Skip the lint loop and multi-pass approaches for now. They're worth revisiting if you find voice inconsistency across pages after the initial rewrite, but for 78 files with a good style guide, they'd be over-engineering.

## Sources

### Reference implementations
- https://github.com/houtini-ai/voice-analyser-mcp -- MCP server for automated voice extraction from doc sites

### Blog posts & writeups
- https://cxl.com/blog/llm-tone-of-voice/ -- structured framework for extracting and encoding voice as behavioral prompts
- https://latitude.so/blog/how-examples-improve-llm-style-consistency -- evidence that few-shot examples outperform abstract descriptions
- https://pub.towardsai.net/how-to-make-llms-write-stylishly-6691be12b970 -- augmented few-shot learning with reverse-engineered prompts
- https://blog.ninapanickssery.com/p/how-to-make-an-llm-write-like-someone -- practical walkthrough of LLM-assisted voice extraction
- https://www.singlegrain.com/branding-2/how-llms-interpret-brand-tone-and-voice/ -- how LLMs interpret tone as statistical patterns
- https://medium.com/@spencerjohnroberts/how-to-own-your-brand-voice-across-llm-powered-features-c1931efe6f9a -- "always/never/when-then" style brief structure
- https://searchengineland.com/guide/how-to-train-in-house-llms-on-brand-voice -- three-tier approach (prompt engineering, fine-tuning, RAG)
- https://www.scoutos.com/blog/top-5-llm-prompts-for-re-writing-your-technical-documentation -- multi-pass rewriting prompts

### Documentation & standards
- https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips -- Claude-specific prompt structuring for long context
- https://corelight.com/blog/microsoft-style-guide-llm -- lint + LLM hybrid for Microsoft Style Guide compliance (open-source tool)

### Academic papers
- https://arxiv.org/pdf/2505.00679 -- register analysis for automatic style transfer prompt construction
- https://arxiv.org/html/2509.14543v1 -- LLM limitations on implicit style imitation (sets realistic expectations)

### Community discussion
- https://github.com/sveltejs/svelte/discussions/13721 -- community characterization of what makes Svelte docs distinctive
