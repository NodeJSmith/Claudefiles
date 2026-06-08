## Sources Found

### hardikpandya/stop-slop
- **URL**: https://github.com/hardikpandya/stop-slop
- **Type**: reference implementation (Claude Code skill)
- **Key takeaway**: The most popular de-slop skill (5,000+ GitHub stars). Defines banned phrases across categories (throat-clearing openers, emphasis crutches, business jargon, adverbs, vague declaratives, meta-commentary) and structural cliches (binary contrasts, negative listings, dramatic fragmentation, rhetorical setups, false agency, passive voice). Rules emphasize active voice, specificity, rhythm variation (two items instead of three), and trusting the reader.
- **Relevance**: Direct competitor/inspiration. Its SKILL.md + references/ structure (phrases to remove, structural patterns, before/after examples) is the dominant pattern for this category of skill.

### mshumer/unslop
- **URL**: https://github.com/mshumer/unslop
- **Type**: reference implementation (Claude Code skill)
- **Key takeaway**: Takes a measurement-first approach: analyzes a whole set of outputs for repeated patterns, builds a profile of model defaults, then writes a focused skill.md of what to avoid. Runs before/after comparison to verify the profile changed the result. Includes a ~200-entry taboo-phrases.md with regex patterns for detection across 24 categories.
- **Relevance**: The "measure then fix" approach is distinctive. Rather than a static banned-word list, it profiles the specific model's tendencies and tailors the suppression. The regex-pattern approach to phrase detection is more robust than string matching.

### theclaymethod/unslop
- **URL**: https://github.com/theclaymethod/unslop
- **Type**: reference implementation (agent skill)
- **Key takeaway**: Two-pass editing: diagnose what's wrong first, then reconstruct without the tells. The second pass re-reads the rewrite to catch patterns that survive the first edit (recycled transitions, lingering inflation, copula swaps). Preserves code blocks, URLs, headings, YAML frontmatter, tables, and blockquotes byte-identical.
- **Relevance**: The two-pass architecture and the "preserve technical content" rule are both important design choices. Single-pass rewrites miss patterns that only become visible after other patterns are removed.

### conorbronsdon/avoid-ai-writing
- **URL**: https://github.com/conorbronsdon/avoid-ai-writing
- **Type**: reference implementation (agent skill, multi-platform)
- **Key takeaway**: Three operational modes: rewrite (default, flags and rewrites with built-in second pass), detect (flags without rewriting, distinguishes real problems from judgment calls), and edit (minimal in-place changes, preserving passages that are already human). Includes a 109-entry word replacement table across 3 tiers, each with a specific plain alternative. Returns structured audit: identified issues with quoted text, the rewrite, change summary, and second-pass audit.
- **Relevance**: The three-mode design (rewrite / detect / edit) is the most sophisticated operational model found. The "edit" mode that preserves already-human passages and makes minimal targeted changes is exactly what a skill for PR descriptions and commit messages needs -- you want surgical fixes, not wholesale rewrites.

### lguz/humanize-writing-skill
- **URL**: https://github.com/lguz/humanize-writing-skill
- **Type**: reference implementation (Claude Code skill / plugin)
- **Key takeaway**: 3-pass editing system with 36+ banned words, 10 structural patterns, and a quality checklist. Pass 1 replaces overused AI words, Pass 2 eliminates structural patterns (parallel negation, em dash overuse), Pass 3 adds human texture (varied sentence length, contractions). Works across Claude, ChatGPT, Gemini, Cursor, Windsurf.
- **Relevance**: The three-pass architecture with distinct concerns per pass (vocabulary, structure, texture) is a clean decomposition. The "add human texture" pass is an interesting contrast to approaches that only subtract.

### tropes.fyi / tropes.md
- **URL**: https://tropes.fyi/tropes-md
- **Type**: pattern catalog / system prompt resource
- **Key takeaway**: A single Markdown file cataloging dozens of recurring LLM writing patterns across six categories: word choice, sentence structure, paragraph structure, tone, formatting, and composition. Designed to be dropped directly into system prompts. Names specific patterns like "The Serves As Dodge" (AI avoids basic copulas because repetition penalty pushes it toward fancier constructions) and "Negative Parallelism" (the "It's not X -- it's Y" pattern, identified as the single most common AI writing tell).
- **Relevance**: The most comprehensive pattern taxonomy found. The named-pattern approach (giving each tell a memorable name with an explanation of why it happens) is more useful than a flat banned-word list. Understanding the mechanism (e.g., repetition penalty causing copula avoidance) helps an editor make better judgment calls.

### Hacker News discussion of tropes.fyi
- **URL**: https://news.ycombinator.com/item?id=47088813
- **Type**: community discussion
- **Key takeaway**: Show HN post for tropes.fyi generated community discussion about AI writing patterns and approaches to fixing them.
- **Relevance**: Community validation and additional perspectives on which patterns matter most in practice.

### Wikipedia: Signs of AI writing
- **URL**: https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing
- **Type**: editorial guide / pattern catalog
- **Key takeaway**: A 15,000-word guide compiled from Wikipedia editors' experience reviewing tens of thousands of AI-generated texts. Covers linguistic patterns (excessive hedging, vocabulary rarities), formatting tells (em dash overuse, bolded-title bullet points where the bold phrase is just reworded in the sentence), and content issues (telling you something is significant instead of showing why). Notable for the caveat that not all text with these indicators is AI-generated, since LLMs are trained on human writing.
- **Relevance**: The most rigorous pattern catalog because it is based on actual editorial review of thousands of submissions, not theoretical analysis. The Wikipedia context (encyclopedic prose) differs from our target (PR descriptions, commit messages, research briefs), but the core patterns overlap heavily.

### Bloomberry AI Writing Patterns Database
- **URL**: https://www.bloomberry.ai/research/ai-writing-patterns
- **Type**: research database
- **Key takeaway**: A structured database of 7,400+ AI writing patterns from ChatGPT, Claude, Gemini, and open-source LLMs. Key finding: 82% of AI-generated posts share 4 structural fingerprints regardless of model -- hedge openers, tricolon lists, em-dash connector phrases, and resolution closers. Also describes "AI Sentence DNA": a four-part structural sequence (Opening/framing claim, Expansion/supporting evidence, Contrast/tension signal, Resolution/takeaway) that appears across all major models.
- **Relevance**: The "AI Sentence DNA" concept is a structural-level insight that goes beyond word-level detection. A skill that only catches vocabulary tells misses the deeper structural fingerprint. The 82% cross-model consistency figure confirms these patterns are worth targeting.

### Louis Bouchard: How to Clean Up AI-Generated Drafts
- **URL**: https://www.louisbouchard.ai/ai-editing/
- **Type**: blog post / practical guide
- **Key takeaway**: Practical workflow for cleaning AI drafts, including creating word avoidance lists and replacing with concrete language.
- **Relevance**: Practitioner perspective on the editing workflow, useful for understanding how humans actually use these tools.

### Stephen Turner: De-slop the text you shouldn't be writing anyway
- **URL**: https://blog.stephenturner.us/p/deslop
- **Type**: blog post / critical analysis
- **Key takeaway**: Argues that de-slopping is treating a symptom -- the real problem is generating text you don't need. Positions de-slop tools as useful for the text you do need to generate (documentation, commit messages, etc.) but questions the broader trend of generating-then-fixing.
- **Relevance**: Important counterpoint. For our use case (PR descriptions, commit messages, research briefs), the text genuinely needs to exist. But the critique is valid for avoiding over-generation.

### Nate's Newsletter: 20 Prompts to Fix AI Slop
- **URL**: https://natesnewsletter.substack.com/p/i-built-a-20-prompt-set-to-kill-ai
- **Type**: blog post / prompt engineering
- **Key takeaway**: A set of 20 specialized prompts targeting different aspects of AI writing -- each prompt addresses a specific failure mode rather than trying to fix everything at once.
- **Relevance**: The decomposed-prompt approach (one prompt per concern) contrasts with the monolithic skill approach. Could inform a multi-pass architecture where each pass has a focused concern.

### Anti-Slop Writing Workflow (Hypeflo)
- **URL**: https://www.hypeflo.ws/workflow/the-anti-slop-writing-workflow
- **Type**: workflow documentation
- **Key takeaway**: A structured workflow for applying anti-slop techniques across different AI writing tools.
- **Relevance**: Workflow-level thinking about how de-slop fits into a larger writing process.

### DEV Community: How to Fix That Robotic AI Tone
- **URL**: https://dev.to/alanwest/how-to-fix-that-robotic-ai-tone-in-your-llm-powered-features-4h5e
- **Type**: blog post / engineering guide
- **Key takeaway**: Focuses on LLM-powered product features rather than developer prose. Core advice: tell the model to stop doing the annoying things via system prompts. Make every sentence information-dense, prefer shorter words, avoid transitional filler.
- **Relevance**: The product-feature angle is relevant for our case -- PR descriptions and commit messages are consumed by teammates, so the "product UX" framing applies. Users develop "AI detector" instincts and trust text less when it reads as generated.

### HumanizerAI Agent Skills
- **URL**: https://github.com/humanizerai/agent-skills
- **Type**: reference implementation (Claude Code / Codex agent skills)
- **Key takeaway**: AI detection and text humanization as agent skills, from a company that also offers a SaaS humanizer API.
- **Relevance**: Commercial player entering the agent-skill space. Their SaaS API experience may produce more battle-tested pattern lists, but the agent skills appear to be marketing vehicles for the paid product.

### Ossama Chaib: tropes.fyi origin post
- **URL**: https://ossama.is/writing/tropes
- **Type**: blog post
- **Key takeaway**: Creator's rationale for building tropes.fyi. Frames it as a "name and shame" directory -- naming the patterns makes them easier to notice and avoid. The project is openly AI-assisted and framed as a cat-and-mouse game between prompt engineers and model defaults.
- **Relevance**: The "naming makes it visible" philosophy is sound. Our writing-quality.md already names patterns (e.g., "Copula Avoidance", "Significance Inflation") -- this validates that approach.


## Patterns Found

### Pattern 1: Banned-Word Lists with Tiered Alternatives

**Used by**: stop-slop, avoid-ai-writing, humanize-writing-skill, tropes.fyi, writing-quality.md (ours)
**How it works**: Maintain a curated list of words and phrases that are AI tells -- words like "delve," "tapestry," "leverage," "crucial," "pivotal." Each banned word maps to a plain alternative ("leverage" becomes "use," "commence" becomes "start"). Lists are typically organized into tiers or categories: vocabulary (individual words), phrases (multi-word expressions like "it's worth noting"), and structural markers (sentence-level patterns).

The more sophisticated implementations (avoid-ai-writing, mshumer/unslop) use tiered severity: some words are always wrong ("delve" in a commit message), while others are context-dependent ("robust" is fine in engineering docs describing actual robustness). The tiering prevents over-correction.

**Strengths**: Easy to implement, easy to validate, easy to extend. Catches the most obvious tells. A human can review the list and disagree with specific entries.
**Weaknesses**: Vocabulary-only detection misses structural tells entirely. A flat list without tiering over-corrects legitimate usage. Lists drift as models change -- "delve" may fade as models are fine-tuned to avoid it, while new tells emerge.
**Example**: https://github.com/conorbronsdon/avoid-ai-writing (109-entry, 3-tier table)

### Pattern 2: Multi-Pass Editing Architecture

**Used by**: theclaymethod/unslop (2-pass), avoid-ai-writing (2-pass with structured output), lguz/humanize-writing-skill (3-pass), various blog authors
**How it works**: Rather than attempting to fix everything in one pass, decompose the editing into sequential passes with distinct concerns. Common decompositions:

- **2-pass (diagnose/reconstruct)**: First pass identifies patterns and explains what is wrong. Second pass rewrites with the diagnosis in hand, then re-reads to catch patterns that survived.
- **3-pass (vocabulary/structure/texture)**: Pass 1 replaces overused words. Pass 2 fixes structural patterns (parallel negation, em dash chains, tricolon abuse). Pass 3 adds human texture (varied rhythm, contractions, sentence length variation).

The key insight is that fixing vocabulary in pass 1 can expose structural problems that were previously masked, and structural fixes in pass 2 can create new vocabulary tells. The second/third pass catches these cascading effects.

**Strengths**: Catches patterns that single-pass approaches miss. Each pass has a focused concern, making the logic easier to reason about and debug. The diagnosis step prevents blind rewriting that loses meaning.
**Weaknesses**: More expensive (multiple LLM calls for the same text). Risk of over-editing -- each pass is another opportunity to lose the author's voice. Diminishing returns past 2-3 passes.
**Example**: https://github.com/lguz/humanize-writing-skill (3-pass with distinct concerns)

### Pattern 3: Structural Pattern Detection (Beyond Words)

**Used by**: tropes.fyi, Bloomberry, Wikipedia editors, stop-slop
**How it works**: Goes beyond individual word replacement to detect sentence-level and paragraph-level structural patterns that are AI fingerprints. The major structural tells identified across sources:

- **Negative parallelism**: "It's not X -- it's Y." The single most commonly identified AI structural tell across all sources.
- **AI Sentence DNA**: A four-part arc (Opening claim, Expansion, Contrast/tension, Resolution) that appears in 82% of AI-generated posts regardless of model (Bloomberry).
- **Tricolon/Rule of Three**: AI defaults to triplets when listing anything. Two items or four items reads more human.
- **Bolded-header bullets**: Bold label followed by a colon, where the sentence after the colon restates the bold text.
- **Copula avoidance**: "Serves as," "stands as," "boasts" instead of "is" or "has" -- driven by the model's repetition penalty.
- **Resolution closers**: Wrapping paragraphs with a tidy takeaway sentence that restates what was just said.

**Strengths**: Catches the tells that survive vocabulary cleanup. Structural patterns are more stable across model versions than specific word choices. Understanding the mechanism (e.g., repetition penalty) helps make better editing decisions.
**Weaknesses**: Harder to implement as automated rules -- structural patterns require understanding sentence relationships, not just matching strings. Higher false-positive rate, since some of these structures appear in legitimate human writing too.
**Example**: https://tropes.fyi/tropes-md (named patterns with mechanisms)

### Pattern 4: Preserve-Then-Edit (Technical Content Protection)

**Used by**: theclaymethod/unslop, avoid-ai-writing, our writing-quality.md (implicitly)
**How it works**: Before editing, identify and lock regions that must not be modified: code blocks, inline code, URLs, headings, YAML frontmatter, tables, blockquotes, data tables, command examples. These regions are preserved byte-identical through all editing passes. Only prose between protected regions is eligible for rewriting.

Some implementations extend this to "already-human passages" -- text that does not trigger any AI pattern flags is left untouched rather than being rewritten for consistency. The avoid-ai-writing "edit" mode exemplifies this: minimal, targeted changes that preserve what is already good.

**Strengths**: Critical for our use case (PR descriptions, commit messages, documentation) where technical accuracy in code references, commands, and data is non-negotiable. Prevents the editor from "improving" a correct command into an incorrect one.
**Weaknesses**: Requires robust region detection. Edge cases: should a heading that uses an AI-tell word be edited? What about a code comment inside a code block?
**Example**: https://github.com/theclaymethod/unslop (byte-identical preservation rule)

### Pattern 5: Operational Modes (Rewrite vs. Detect vs. Edit)

**Used by**: avoid-ai-writing (3 modes), mshumer/unslop (profile + edit)
**How it works**: Rather than offering a single "fix it" operation, provide distinct modes for different workflows:

- **Detect/Audit**: Flag AI patterns without changing text. Returns a report of what was found, distinguishing real problems from judgment calls. Useful for reviewing text you do not want altered, or for understanding the scope before committing to edits.
- **Rewrite**: Full rewrite that restructures and replaces. Appropriate for drafts where you want maximum de-slopping and do not care about preserving the original structure.
- **Edit**: Minimal, targeted in-place changes. Preserves passages that are already human. Returns an edits-made report. Appropriate for polishing text that is mostly good but has a few tells.

For our use case, "edit" mode is the primary need (fixing a PR description that is 80% fine but has three AI tells), with "detect" mode useful as a dry-run before committing changes.

**Strengths**: Matches the tool to the situation. A commit message needs surgical edits, not a rewrite. A research brief draft might benefit from a full rewrite.
**Weaknesses**: More complex skill with more entry points. Users need to understand which mode to choose, or the skill needs to auto-select.
**Example**: https://github.com/conorbronsdon/avoid-ai-writing (rewrite / detect / edit)

### Pattern 6: Model-Specific Profiling

**Used by**: mshumer/unslop, Bloomberry (research)
**How it works**: Rather than using a static list of AI tells, analyze the specific model's output patterns and build a tailored profile. mshumer/unslop runs a batch of outputs through analysis, identifies which patterns this particular model exhibits, and generates a focused suppression profile. Bloomberry's research shows that while 82% of patterns are cross-model, each model has its own fingerprint distribution.

This matters because models change. Claude 4's tells are different from Claude 3.5's. A static list tuned for ChatGPT-4o will miss Claude-specific patterns and flag false positives for patterns Claude does not exhibit.

**Strengths**: More precise than a static list. Adapts as models change. Reduces false positives by only targeting patterns the model actually produces.
**Weaknesses**: Requires a profiling step before use. The profile itself is generated by an LLM, which may miss its own blind spots. More complex to maintain than a static list.
**Example**: https://github.com/mshumer/unslop (profile-then-edit approach)

### Pattern 7: Prevention vs. Post-Processing

**Used by**: tropes.fyi (system prompt), anti-slop-writing (system prompt), writing-quality.md (ours, rules loaded into context)
**How it works**: Rather than generating text and then fixing it, suppress AI patterns at generation time by including anti-slop rules in the system prompt or context. Our writing-quality.md is an example of this approach -- it is loaded into every conversation as a rule file, shaping generation rather than post-processing output.

The tropes.md file from tropes.fyi is designed specifically for this: drop it into your system prompt and the model avoids the cataloged patterns during generation. The anti-slop-writing project similarly provides a universal system prompt.

**Strengths**: More efficient than generate-then-fix. Avoids the information-loss problem of post-processing (the model has access to the full meaning during generation, while a post-processor only sees the surface text). No additional LLM calls.
**Weaknesses**: Does not catch everything -- models still produce tells even with anti-slop prompts. Cannot fix text generated by other tools or humans imitating AI patterns. Requires the rules to be in context for every generation, consuming context window. The cat-and-mouse dynamic means the suppression list needs regular updates.
**Example**: https://tropes.fyi/tropes-md (designed as a system prompt insert)


## Anti-Patterns

### 1. Detection-Bypass as Goal
Multiple commercial "humanizer" tools (HumanizerAI, BypassGPT, EssayDone, GPTHuman) optimize for bypassing AI detection tools like GPTZero and ZeroGPT rather than actually improving prose quality. Some resort to Unicode space character substitution or synonym cycling that makes text worse while fooling detectors. The goal should be prose that reads well to humans, not prose that fools automated classifiers.
**Sources**: https://humanizerai.com/bypass-gptzero, https://github.com/Oct4Pie/zero-zerogpt

### 2. Over-Correction into Sterile Voice
Stephen Turner's blog post makes the point: "Removing patterns is half the job. Sterile, voiceless writing is just as obvious as slop." Several skills focus entirely on subtraction (remove these words, cut these structures) without adding anything back. The result passes an AI-detection scan but reads as flat, lifeless prose -- a different kind of obvious.
**Sources**: https://blog.stephenturner.us/p/deslop, our own writing-quality.md (which explicitly calls this out under "Adding Voice")

### 3. Static Lists Without Mechanism Understanding
Flat banned-word lists without explaining why each word is a tell lead to cargo-cult editing. "Delve" is not inherently wrong -- it is a tell because LLMs use it 400% more than humans do in the same contexts. Without understanding the mechanism, editors ban words that are fine in context and miss novel tells that are not on the list.
**Sources**: https://tropes.fyi/ (explicitly names mechanisms), https://www.bloomberry.ai/research/ai-writing-patterns

### 4. Treating All Text Types Equally
A commit message, a PR description, a research brief, and a blog post have different registers and conventions. Skills that apply the same rules uniformly (e.g., banning all adverbs in technical documentation) produce awkward results. The avoid-ai-writing project's three-mode design implicitly acknowledges this, but no tool found explicitly adapts its rules to text type.
**Sources**: [no source found -- observed gap across all implementations reviewed]


## Emerging Trends

### Convergence on Named-Pattern Taxonomies
Multiple independent efforts (tropes.fyi, Wikipedia's Signs of AI writing, Bloomberry's database, stop-slop's reference files) are converging on similar pattern taxonomies with named entries. The patterns are stabilizing into a shared vocabulary: negative parallelism, tricolon abuse, copula avoidance, significance inflation, resolution closers. This suggests the field is maturing past ad-hoc word lists toward a structured understanding of AI writing tells.
**Sources**: https://tropes.fyi/, https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing, https://www.bloomberry.ai/research/ai-writing-patterns

### Agent Skills as the Primary Distribution Channel
Every major de-slop tool found is distributed as a Claude Code skill, Cursor plugin, or agent skill file -- not as a standalone application, browser extension, or API. The market has converged on "skill file dropped into your agent's context" as the delivery mechanism, reflecting that the primary consumers are developers using AI coding assistants, not general writers.
**Sources**: https://github.com/hardikpandya/stop-slop, https://github.com/conorbronsdon/avoid-ai-writing, https://github.com/mshumer/unslop

### Structural Detection Over Vocabulary Detection
The most recent and well-regarded work (Bloomberry's "AI Sentence DNA," tropes.fyi's named structural patterns) focuses on sentence and paragraph structure rather than individual words. Vocabulary tells are easy to suppress via fine-tuning or system prompts; structural patterns are more persistent across model versions and harder to mask. The 82% cross-model consistency figure for structural fingerprints (Bloomberry) suggests this is the more durable detection surface.
**Sources**: https://www.bloomberry.ai/research/ai-writing-patterns, https://tropes.fyi/tropes-md
