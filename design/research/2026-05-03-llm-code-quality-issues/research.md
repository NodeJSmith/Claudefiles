---
topic: "LLM-generated code quality issues and review patterns"
date: 2026-05-03
status: Draft
---

# Prior Art: LLM-Generated Code Quality Issues

## The Problem

LLM-generated code compiles, passes basic tests, and looks structurally sound — but degrades codebases over time through patterns that traditional code review doesn't screen for. Research shows AI-generated PRs produce 1.7x more issues per PR than human-written code, with logic errors up 75% and security vulnerabilities rising 1.5-2x. The core challenge: developers trust AI output more than warranted (the confidence-competence gap), and existing review processes check for human failure modes, not AI failure modes.

## How We Do It Today

We have `code-reviewer` (correctness, security, performance) and `integration-reviewer` (duplication, convention drift, misplacement) that run on every commit. `mine.audit` does deep codebase health checks. None of these explicitly screen for LLM-specific antipatterns: overengineering, happy-path-only code, hallucinated APIs, context amnesia, or the readability debt that comes from code that's "compact but complex."

## Patterns Found

### Pattern 1: The Happy Path Assumption

**Used by**: AlterSquare (codebase rescue), research teams studying LLM bugs
**How it works**: LLM-generated code systematically assumes ideal conditions. External services respond instantly, database queries return expected results, network calls never hang, inputs are well-formed. In a review of 50 AI PRs: 82% had catch blocks that failed to distinguish error types, 76% omitted network timeouts, 44% introduced N+1 queries. The code looks correct — the issue is what's absent.

**Strengths**: Checklistable (timeout? error differentiation? connection pooling? retry logic?)
**Weaknesses**: Requires domain knowledge to know which unhappy paths matter
**Example**: https://altersquare.medium.com/ai-generated-code-looks-clean-heres-why-your-next-refactor-will-prove-it-isn-t-c928033b60b1

### Pattern 2: Verbose Overengineering

**Used by**: Teams using Claude/Cursor/Copilot; documented by Nathan Onn, Karpathy, HackerNoon 40K-line study
**How it works**: LLMs pattern-match to "production-ready" training examples. Simple features get factory patterns, strategy patterns, repository layers. Specific manifestations: excessive error handling for impossible cases, duplicated logic instead of refactoring, bloated tests with unnecessary mocking, architectural patterns applied where they don't belong, merging dissimilar components into "universal" abstractions filled with conditionals.

**Strengths**: Most actionable — addressable with negative constraints and review rules
**Weaknesses**: The line between appropriate abstraction and overengineering is context-dependent
**Example**: https://www.nathanonn.com/how-to-stop-claude-code-from-overengineering-everything/

### Pattern 3: Package and API Hallucination

**Used by**: USENIX Security researchers, supply chain security teams
**How it works**: Of 2.23M code samples, 440K referenced hallucinated packages. 43% of hallucinated names repeat consistently across runs (predictable attack surface — "slopsquatting"). Extends beyond packages to API methods, parameters, and return types that don't exist in the library version being used.

**Strengths**: Fully automatable (dependency resolution catches phantom packages)
**Weaknesses**: API-level hallucinations require runtime or type-checking to catch
**Example**: https://www.usenix.org/publications/loginonline/we-have-package-you-comprehensive-analysis-package-hallucinations-code

### Pattern 4: Context Amnesia (Ignoring Existing Codebase Patterns)

**Used by**: ISSTA 2025 researchers, AlterSquare
**How it works**: LLMs generate code that's internally consistent but ignores established conventions. Implements Repository pattern in a direct-access project, creates new error handling alongside an existing strategy, duplicates existing utility helpers. ISSTA 2025 calls this "Project Context Conflicts."

**Strengths**: Integration reviewers can catch by comparing new code against existing patterns
**Weaknesses**: Requires whole-codebase awareness
**Example**: https://dl.acm.org/doi/pdf/10.1145/3728894

### Pattern 5: The Confidence-Competence Gap

**Used by**: Devoteam, nilenso, RCT productivity study
**How it works**: Developers using AI produce less secure code while reporting greater confidence. In an RCT, seasoned contributors using AI experienced 19% net slowdown while believing they worked 20% faster. Teams adopting AI without review infrastructure see 35-40% bug density increase within 6 months.

**Strengths**: Addressable with process changes (mandatory review, AI-specific checklists)
**Weaknesses**: Cultural resistance — teams adopt AI for speed and resist review overhead
**Example**: https://www.devoteam.com/expert-view/a-software-architects-guide-to-ai-slop/

### Pattern 6: Self-Correcting Guardrail Loops

**Used by**: Datadog, Claude Code (hooks), coding agent architectures
**How it works**: Embed static analysis, linting, and type checking in the agent's generation loop. Agent generates → runs linters → sees errors → fixes before human review. CI/CD as second layer.

**Strengths**: Catches mechanical errors without human effort
**Weaknesses**: Cannot catch semantic issues (wrong algorithm, architectural mismatch)
**Example**: https://www.datadoghq.com/blog/delivery-guardrails-for-ai-generated-code/

### Pattern 7: Risk-Tiered Review

**Used by**: Practical code review checklists
**How it works**: Score changes on risk dimensions before deciding review depth. Config/tests = low risk; auth/payments/migrations = high risk. AI's risk profile differs from humans — more likely to introduce subtle security issues in auth code and N+1 queries in data access.

**Strengths**: Focuses limited review bandwidth where it matters most
**Weaknesses**: Requires maintaining a risk taxonomy
**Example**: https://dev.to/sathish_daggula/cursor-claude-my-ai-code-review-checklist-hm5

## Anti-Patterns

- **Vibe Coding Without Guardrails**: Accepting AI code because "it compiles and runs." 35-40% bug density increase within 6 months without review infrastructure. (Source: https://www.wits.ac.za/news/latest-news/opinion/2026/2026-03/securing-vibe-coding-the-hidden-risks-behind-ai-generated-code.html)
- **Treating AI as Senior Instead of Junior**: AI doesn't say "I'm not sure." The correct model is a fast but unreliable junior whose output always needs review. (Source: https://dev.to/techstratos/i-let-ai-rewrite-40-of-my-codebase-heres-what-actually-happened-1jd6)
- **Lengthy Instruction Files That Get Ignored**: More rules ≠ fewer problems. Concise negative constraints ("do NOT...") outperform verbose positive instructions. (Source: https://www.nathanonn.com/how-to-stop-claude-code-from-overengineering-everything/)
- **AI Slop PRs**: Low-quality AI-generated contributions overwhelm maintainers. Projects like tldraw and curl have restricted contributions. (Source: https://www.devoteam.com/expert-view/a-software-architects-guide-to-ai-slop/)

## Emerging Trends

- **AI-specific SAST becoming standard** — every major vendor (Semgrep, Snyk, SonarQube, CodeRabbit) positioning for AI code review
- **Agent self-correction loops** — embedding linters/type checkers inside the generation loop rather than only post-generation
- **"More code, not better code"** — LOC/developer grew from 4,450 to 7,839; median PR size up 33%; review capacity gap projected at 40% by 2026
- **Economic pressure toward quality** — competition may drive AI models toward simpler code, but not yet realized

## Relevance to Us

Our existing setup already addresses several of these patterns partially:
- **Context Amnesia** → `integration-reviewer` catches convention drift and duplication, but doesn't explicitly screen for "LLM ignored existing patterns"
- **Guardrail Loops** → pre-commit hooks run code-reviewer + integration-reviewer automatically
- **CLAUDE.md constraints** → our rules already include negative constraints (no `Optional[X]`, no lazy imports, immutability)

The gaps map cleanly to what a WTF skill should cover:
- **Happy Path Assumption** → neither reviewer explicitly checks for missing error differentiation, timeouts, or N+1 patterns at the semantic level
- **Verbose Overengineering** → code-reviewer flags >50 line functions and >4 nesting, but doesn't catch unnecessary abstraction layers, premature patterns, or "universal" components with conditional bloat
- **Hallucinated APIs** → type checkers catch some of this, but string-referenced APIs, config keys, and CSS custom properties slip through
- **Readability debt** → no reviewer asks "will a human understand this in a month?" — nested ternaries, bespoke state tracking, fragile heuristics, type assertions that defeat safety

## Recommendation

The research strongly validates the three-part approach (enhance existing reviewers + standalone WTF skill):

1. **Add LLM-specific smell checks to existing reviewers** — happy path assumptions, overengineering signals, hallucination markers. These are cheap additions to agents that already run on every commit.
2. **Build a standalone WTF skill** with the "readability in a month" framing — the comprehensive sniff test for code that works but will confuse future developers.
3. **The empirical bug taxonomy** (arxiv 2403.08937) provides a concrete checklist: Misinterpretation, Silly Mistake, Prompt-biased Code, Missing Corner Case, Hallucinated Object, Wrong Attribute, Incomplete Generation, Non-Prompted Consideration. Several of these map directly to review categories.

The strongest signal across all sources: AI code quality scales with review discipline. The WTF skill is exactly the kind of "review infrastructure" that prevents the 35-40% bug density increase.

## Sources

### Research papers
- https://arxiv.org/html/2403.08937v2 — 10 bug patterns from 333 LLM-generated bugs
- https://dl.acm.org/doi/pdf/10.1145/3728894 — LLM hallucinations in code generation (ISSTA 2025)
- https://www.usenix.org/publications/loginonline/we-have-package-you-comprehensive-analysis-package-hallucinations-code — Package hallucination at scale (USENIX 2025)
- https://arxiv.org/html/2511.10271v1 — Non-functional quality characteristics of LLM code
- https://arxiv.org/html/2502.01853v2 — Multi-language, multi-model security analysis

### Blog posts & experience reports
- https://hackernoon.com/can-llms-generate-quality-code-a-40000-line-experiment — 40K-line quality experiment
- https://altersquare.medium.com/ai-generated-code-looks-clean-heres-why-your-next-refactor-will-prove-it-isn-t-c928033b60b1 — 50 AI PRs reviewed
- https://www.devoteam.com/expert-view/a-software-architects-guide-to-ai-slop/ — Architect's guide to AI slop
- https://blog.nilenso.com/blog/2025/05/29/ai-assisted-coding/ — AI-assisted coding for serious teams
- https://www.datadoghq.com/blog/delivery-guardrails-for-ai-generated-code/ — Datadog delivery guardrails
- https://www.nathanonn.com/how-to-stop-claude-code-from-overengineering-everything/ — Stopping Claude overengineering
- https://dev.to/techstratos/i-let-ai-rewrite-40-of-my-codebase-heres-what-actually-happened-1jd6 — 40% codebase rewrite experience
- https://dev.to/sathish_daggula/cursor-claude-my-ai-code-review-checklist-hm5 — AI code review checklist
- https://stackoverflow.blog/2026/01/23/ai-can-10x-developers-in-creating-tech-debt/ — AI and tech debt
- https://www.greptile.com/blog/ai-slopware-future — Slop is not necessarily the future
- https://dev.solita.fi/2026/02/20/code-quality-in-the-ai-era.html — Code quality in the AI era
- https://explainx.ai/blog/karpathy-claude-code-guidelines-andrej-karpathy-skills — Karpathy-inspired Claude guidelines

### Reference
- https://en.wikipedia.org/wiki/Slopsquatting — Slopsquatting definition
