# Codebase Reconnaissance Protocol

**Skip this phase for trivial features.**

Before asking the user questions, silently explore the codebase for context relevant to the request. Use Grep, Glob, and Read to find:
- Existing modules, patterns, or prior art related to the feature
- Conventions the codebase already follows for similar work
- Integration points, data models, or APIs the feature would touch
- Test files covering code that will be modified or replaced — note what they test and whether they'll break
- Code or patterns being superseded if this is a migration or refactor — these become replacement targets in the design doc
- Anything that narrows the design space or resolves potential questions
- **Structural simplification opportunities** — existing complexity in the affected area that could be simplified before building on top. Bolt-on conditionals, duplicated helpers, state machines that could be data transformations. Note these for the Architecture section — the design should incorporate the simplification rather than layer new code over existing complexity.

**Principle: If a question can be answered by exploring the codebase, explore the codebase instead of asking the user.**

**Principle: Resolve conditionals now, not later.** If reconnaissance reveals something that can be determined definitively (e.g., "does file X exist?", "are there remaining consumers of Y?", "does this test reference old imports?"), state the answer as fact in the design doc — not as a conditional for the implementer to verify. "Remove `reconnectVersion` from `AppState` — zero consumers remain after migration" is better than "verify whether any consumers remain; if none, remove it."

## Code example extraction

While exploring, look for **concrete code snippets** (aim for 3-5) that represent the codebase's conventions for the kind of work this feature involves. These are real code from the repo — not prose descriptions of patterns. If the codebase has no meaningful conventions to extract (greenfield project, no similar code exists), record none and note the absence — downstream phases handle the zero-examples case.

**What to extract:**
- A function or class that follows the naming/structure conventions the new code should match
- An existing test that demonstrates the project's testing patterns (setup, assertions, fixtures)
- An error handling or validation pattern representative of how this codebase does it
- An API endpoint, CLI command, or UI component similar to what's being built (if applicable)

**Selection criteria (quality > quantity):** pick diverse examples (each a different convention, not 3 similar functions), prefer code close to where the new code will live, and keep each snippet short. Note a DO/DON'T pair when a convention has a common wrong way to do it.

Hold these snippets internally — they'll be written to the `## Convention Examples` section of `design.md` in Phase 4.

After exploring, present a brief summary to the user:

> "I found [X, Y, Z] in the codebase that's relevant to this feature. I also identified [N] code examples that demonstrate the conventions new code should follow. I'll focus my questions on decisions the code can't answer. Correct me if I'm missing something."
