# Writing Quality

AI-generated prose has recognizable patterns that erode trust even when the content is correct. These patterns emerge because LLM generation optimizes for surface plausibility: hedging that sounds authoritative, abstraction that sounds precise, and parallelism that sounds complete. Readers recognize the texture even when they can't name the pattern.

This applies to all non-code text: PR descriptions, commit messages, skill files, rule files, documentation, research briefs, and user-facing messages.

Removing patterns is half the job. Sterile, voiceless writing is just as obvious as slop.

## Adding Voice

- **Have opinions.** React to facts instead of neutrally listing pros and cons.
- **Vary rhythm.** Short sentences. Then longer ones that take their time.
- **Be specific.** Not "this is concerning" but "there's something unsettling about agents churning away at 3am."
- **Let some mess in.** Perfect structure feels algorithmic.
- **Acknowledge complexity.** "Impressive but also kind of unsettling" beats "impressive."

## Patterns to Detect and Fix

### AI Vocabulary

Replace with plain words: additionally, crucial, delve, enduring, enhance, fostering, garner, interplay, intricate, landscape (abstract), pivotal, showcase, tapestry (abstract), testament, underscore, vibrant. Also: utilize (use), leverage (use), facilitate (help), numerous (many), in the event that (if).

### Copula Avoidance

"Serves as", "stands as", "boasts", "features" — just say "is" or "has."

### Significance Inflation

"Pivotal moment", "testament to", "evolving landscape", "setting the stage for", "indelible mark", "deeply rooted." Cut puffery, state what happened.

### Superficial -ing Phrases

"Highlighting...", "ensuring...", "reflecting...", "showcasing...", "fostering..." — delete or expand with real content.

### Negative Parallelisms

"It's not just X, it's Y." State the point directly.

### Synonym Cycling

Protagonist, main character, central figure, hero all in one paragraph. Pick one, repeat it.

### False Ranges

"From X to Y" where X and Y aren't on a meaningful scale. List topics directly.

### Em Dash Overuse

Avoid em dashes. Use periods or commas. Em dashes are an AI tell; parentheses are the same tell in a different costume. If a thought needs separation, end the sentence.

### Colon Overuse

Colons are fine before a list or example. Not as mid-sentence connectors. "If you're coming from traditional automation: instead of registering event handlers..." adds nothing with the colon. Rewrite to let the point stand without comparison framing.

### Boldface Overuse

Don't bold every proper noun or acronym.

### Inline-Header Lists

The tell is a bold label and colon that restates the line: "**Performance:** Performance improved..." Convert to prose. A bold lead-in that names the item and is followed by genuinely new detail is fine.

### Decorative Emojis

Remove from headings and bullets.

### Rule of Three

Forcing ideas into groups of three. Use the natural number.

### Chatbot Phrases

"I hope this helps!", "Let me know if...", "Of course!", "Certainly!", "Found the smoking gun!" Remove.

### Sycophantic Tone

"Great question!", "You're absolutely right!", "Excellent point!" Respond directly.

### Filler Phrases

"In order to" becomes "To". "Due to the fact that" becomes "Because". "It is important to note that" gets deleted.

### Excessive Hedging

"Could potentially possibly be argued that it might" becomes "may."

### Abstract Metaphor Nouns

Substrate, wedge, vector, locus, vantage, nexus, primitive (as noun), harness (as metaphor), surface (as in "API surface"), bedrock, scaffolding (as metaphor), modality, paradigm. Replace with the concrete word. "Substrate" becomes "base". "Wedge in" becomes "add".

### Say the Concrete Thing

Don't wrap a simple point in abstract framing. "The database stays close at hand" describes a feeling. The fix names the mechanism: "`.toSQL()` returns the exact string sent to the database." If you can't restate a sentence as a concrete instruction, fact, or number, cut it.

### Dense Sentences

If the reader has to backtrack to parse a sentence, break it in two. One idea per sentence.

### Passive Voice

Prefer active. "Queries are validated" becomes "the compiler validates queries." Passive is fine when the actor is unknown or genuinely doesn't matter.

### Adverb Propping

"Runs quickly" becomes "is fast" or the number. "Significantly improves" becomes the measured delta. An adverb propping up a weak verb means the verb is wrong.

## Self-Audit

After writing, ask: "What makes this obviously AI-generated?" Fix whatever comes to mind.
