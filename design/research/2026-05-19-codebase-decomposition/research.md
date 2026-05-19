---
topic: "codebase decomposition analysis"
date: 2026-05-19
status: Draft
---

# Prior Art: Codebase Decomposition Analysis

## The Problem

Large files, god classes, and mixed-abstraction modules accumulate naturally as features are added. Teams need tools that identify *where* to split code and *how* to split it — not just "this file is too long." The challenge is producing actionable decomposition suggestions (concrete split points, proposed module boundaries, refactoring sequence) rather than just flagging metrics that exceed thresholds.

## How We Do It Today

The Claudefiles repo has strong structural *problem detection* but no dedicated decomposition tool. `mine.audit` identifies god modules, tight coupling clusters, and high-churn files. `mine.wtf` flags readability and abstraction inconsistencies. `code-reviewer` flags functions over 50 lines or nesting over 4 levels. Rules in `coding-style.md` set file size limits (200-400 typical, 800 max) and function length limits (<50 lines). None of these prescribe *how* to split — the "where to cut" decision is left to the developer.

## Patterns Found

### Pattern 1: Behavioral-Static Hybrid Analysis (CodeScene Model)

**Used by**: CodeScene, teams following Adam Tornhill's "Your Code as a Crime Scene" methodology
**How it works**: Combines static code metrics (complexity, nesting, code health) with behavioral signals mined from Git history. Three key behavioral signals: (1) **change frequency** — high-complexity code that nobody touches is low-priority; moderate-complexity code changing weekly is high-priority; (2) **change coupling** — functions that consistently change in the same commit reveal hidden dependencies invisible to static analysis; (3) **developer dispersion** — many developers touching one file amplifies risk. CodeScene's X-Ray drills into hotspot files at function level, showing which methods are change-coupled (should stay together) vs independent (safe to extract separately). Decomposition suggestions are prioritized by business impact (change frequency x code health deficit) rather than worst-code-first.
**Strengths**: Captures real-world development patterns that pure static analysis misses. Prioritizes by ROI. Change coupling is empirically one of the strongest defect predictors.
**Weaknesses**: Requires meaningful Git history (6+ months). Squash-merge workflows lose granular change data. Large reformatting commits skew the behavioral model.
**Example**: https://docs.enterprise.codescene.io/latest/guides/technical/xray.html

### Pattern 2: Hybrid LLM + Static Analysis (EM-Assist / MANTRA Model)

**Used by**: JetBrains (EM-Assist IntelliJ plugin), MANTRA research framework
**How it works**: LLMs generate creative decomposition suggestions, then IDE-grade static analysis validates safety. Workflow: (1) LLM proposes candidate extractions with start/end lines and names; (2) AST-based static analysis filters candidates that would break compilation or semantics; (3) program slicing expands/trims extraction boundaries for complete data-flow slices; (4) ranking by cohesion improvement and size balance. MANTRA extends this with multi-agent orchestration (separate analysis, generation, validation agents) and Context-Aware RAG to ground suggestions in the codebase's existing patterns. **Critical finding**: naive LLM prompting achieves 8.7% success; MANTRA's structured orchestration achieves 82.8%.
**Strengths**: Dramatically outperforms both pure-LLM and pure-static approaches. LLM brings semantic understanding of coherent responsibilities; static analysis ensures correctness.
**Weaknesses**: Currently limited to method-level (Extract Method) refactoring — cross-class and cross-module decomposition remains out of reach. Requires IDE integration for static validation.
**Example**: https://arxiv.org/abs/2405.20551 (EM-Assist), https://arxiv.org/abs/2503.14340 (MANTRA)

### Pattern 3: Graph-Based Semantic Clustering for Class Decomposition

**Used by**: Academic research (god class detection literature), CodeMR
**How it works**: Models a class as a graph — methods are nodes, edges represent structural similarity (shared attributes, call relationships) and semantic similarity (identifier/comment NLP analysis). The graph is clustered into responsibility groups, each becoming a candidate extracted class. LCOM4 metric provides a direct signal: if LCOM4 > 1, the class has that many disconnected components (natural split candidates). Advanced approaches use variational graph auto-encoders to learn latent representations capturing both structural and semantic relationships.
**Strengths**: Produces concrete "these N methods become Class A, those M become Class B" recommendations. Dual structural+semantic signal avoids false positives (shared attribute, different purpose) and false negatives (same purpose, no shared attributes).
**Weaknesses**: Sensitive to identifier naming quality. Clustering thresholds can produce unnatural groupings. Significant implementation effort vs simpler heuristics.
**Example**: https://arxiv.org/pdf/1204.1967

### Pattern 4: Multi-Signal Decomposition Metrics

**Used by**: SonarQube, CodeMR, NDepend, general practice
**How it works**: Combines multiple orthogonal signals: (1) cognitive complexity (control flow difficulty, threshold 15); (2) LCOM4 (disconnected components = number of resulting classes); (3) afferent/efferent coupling (high Ca = too many responsibilities, high Ce = too many dependencies); (4) connascence locality (connascent elements far apart = misplaced responsibilities); (5) parameter count (many params = combined responsibilities). Power is in combining: a class with LCOM4=3, high Ca, and cognitive complexity >15 is a strong candidate with clear split guidance.
**Strengths**: Well-understood, decades of validation, cheap to compute. Each metric points at a different decomposition problem.
**Weaknesses**: Metrics can conflict (improving LCOM4 may increase coupling). Thresholds are context-dependent. No domain semantics — treats all code as abstract structure.
**Example**: https://devopedia.org/cohesion-vs-coupling

### Pattern 5: Codebase-Aware "Show Don't Tell" (CodeScene)

**Used by**: CodeScene
**How it works**: When presenting refactoring recommendations, searches the team's own codebase for past solutions to the same type of code health issue. Shows concrete before/after examples from related files, ranked by readability and health improvement. Each suggestion comes with evidence from code the developer already knows.
**Strengths**: Dramatically increases developer trust and adoption. Eliminates "but our codebase is different" objection. Suggestions automatically match team style.
**Weaknesses**: Bootstrapping problem for consistently low-quality codebases. May reinforce suboptimal existing patterns.
**Example**: https://codescene.com/use-cases/refactoring-targets

## Anti-Patterns

- **Decomposition without cohesion improvement**: Splitting large files into smaller files that are still tightly coupled and must change together. Result is higher coupling with same effective complexity spread across files. A tool must verify proposed splits improve cohesion and don't increase coupling. ([source](https://hewi.blog/software-architecture-the-hard-partschapter-3-architectural-decomposition-patterns))
- **Over-reliance on LOC thresholds**: Using lines of code as the primary signal leads to arbitrary splits at line boundaries rather than responsibility boundaries. A 300-line function doing one coherent thing is better than three 100-line tangled functions. LOC should be secondary to cohesion/coupling. ([source](https://www.sonarsource.com/blog/5-clean-code-tips-for-reducing-cognitive-complexity))
- **Naive LLM prompting**: Sending code to an LLM with "refactor this" produces 8.7% success. Without structured orchestration, LLM suggestions frequently break compilation or produce cosmetic changes. ([source](https://arxiv.org/abs/2503.14340))
- **Functional decomposition in OOP contexts**: Breaking a class into stateless procedures based on control flow rather than domain responsibilities. Produces "manager" classes orchestrating tiny functions, destroying encapsulation.

## Emerging Trends

- **Agentic multi-file refactoring (2025-2026)**: The shift from single-method to autonomous multi-file agents. MANTRA's multi-agent architecture (separate analysis, generation, validation agents) is the leading pattern. Cross-class architectural refactoring remains the frontier challenge.
- **Hybrid LLM + static analysis as consensus architecture**: Pure LLM and pure static analysis both have significant limitations. The emerging pattern is LLMs for semantic understanding + static analysis for correctness guarantees.
- **Behavioral signals becoming standard**: CodeScene's Git-history-based signals (change coupling, developer dispersion) are spreading. "What changes together should live together" is more actionable than any static metric alone.

## Relevance to Us

Our existing skill ecosystem is well-positioned for a decomposition skill. `mine.audit` already identifies god modules, high-churn files, and coupling clusters — a decomposition skill can build on those findings rather than re-detecting them. The MANTRA research validates our existing multi-agent orchestration pattern (separate agents for analysis, generation, validation) — we already do this in `mine.orchestrate` and `mine.challenge`.

**Key insight for our context**: We operate as an LLM agent without IDE-grade static analysis (no IntelliJ refactoring engine). This means Pattern 2's safety-validation step needs a substitute — likely AST-based checks via Python's `ast` module or tree-sitter, combined with test execution as the ultimate safety net. Our strength is the LLM's ability to understand domain semantics and propose meaningful names and boundaries.

**Git behavioral signals** (Pattern 1) are cheap to compute and we have full Git access. Change coupling and hotspot analysis could be the primary prioritization mechanism — "here's what to decompose *first*" — while the LLM handles the "here's *how* to decompose it" part.

**Convention alignment**: Our `coding-style.md` already sets thresholds (200-400 lines typical, 800 max, functions <50 lines, nesting <4). A decomposition skill should reference these as triggers but use cohesion/coupling analysis for the actual split recommendations.

## Recommendation

Build a **two-phase skill**: (1) a metrics/behavioral scan that identifies and prioritizes decomposition candidates (combining CodeScene-style Git signals with multi-signal metrics), then (2) an LLM-driven suggestion phase that proposes concrete splits with before/after sketches, validated by running the test suite. This maps naturally to our existing multi-agent patterns.

The strongest patterns to borrow:
- **Change coupling from Git history** (Pattern 1) — cheap, actionable, and uniquely available to us
- **Multi-signal metrics** (Pattern 4) — LCOM4 for class splits, cognitive complexity for method extraction, coupling for module boundaries
- **Structured LLM orchestration** (Pattern 2) — the MANTRA finding that naive prompting fails at 8.7% directly argues against a simple "analyze and suggest" prompt; multi-step analysis→generation→validation is essential
- **Show don't tell** (Pattern 5) — reference existing good examples from the same codebase when suggesting splits

## Sources

### Reference implementations
- https://docs.enterprise.codescene.io/latest/guides/technical/xray.html — CodeScene X-Ray function-level decomposition
- https://codescene.com/use-cases/refactoring-targets — CodeScene refactoring targets with codebase examples
- https://docs.sourcery.ai/References/Sourcery-Rules/Python/Default-Rules/extract-method/ — Sourcery Extract Method rule

### Academic papers
- https://arxiv.org/abs/2405.20551 — EM-Assist: Safe Automated Extract Method with LLMs (FSE 2024)
- https://arxiv.org/abs/2503.14340 — MANTRA: Multi-Agent LLM Refactoring with RAG (2025)
- https://arxiv.org/pdf/2603.04177 — CodeTaste: Can LLMs Generate Human-Level Refactorings? (2026)
- https://arxiv.org/pdf/1506.06086 — JExtract: Eclipse Extract Method recommendations
- https://arxiv.org/pdf/1204.1967 — God Class Detection via Semantic Clustering
- https://arxiv.org/pdf/2203.08787 — Extract Class via Variational Graph Auto-Encoders

### Blog posts & writeups
- https://codescene.com/blog/benchmarking-code-health-refactoring-roi — CodeScene refactoring ROI benchmarking
- https://www.sonarsource.com/blog/5-clean-code-tips-for-reducing-cognitive-complexity — SonarQube cognitive complexity
- https://www.sourcery.ai/blog/five-refactoring-tips/ — Sourcery Python refactoring tips
- https://khalilstemmler.com/wiki/coupling-cohesion-connascence/ — Connascence framework
- https://hewi.blog/software-architecture-the-hard-partschapter-3-architectural-decomposition-patterns — Decomposition anti-patterns
- https://www.augmentcode.com/tools/ai-code-refactoring-tools-tactics-and-best-practices — AI refactoring landscape (2025-2026)

### Documentation & standards
- https://devopedia.org/cohesion-vs-coupling — LCOM4, coupling metrics reference
- https://www.ibm.com/think/topics/ai-code-refactoring — IBM AI code refactoring overview
- https://www.emergentmind.com/topics/llm-driven-refactoring — LLM-driven refactoring topic overview
