---
topic: "quality-review-passes-in-orchestration-workflows"
date: 2026-05-23
status: Draft
---

# Prior Art: Quality Review Passes in AI Agent Orchestration Workflows

## The Problem

Multi-step AI coding agent pipelines run per-task code reviews that see narrow diffs, missing cross-task consistency issues, style/hygiene debt, and design-doc compliance violations that only become visible when viewing the full branch. Teams discover messy code after "faithfully executing" a design doc, creating frustrating cleanup sessions that should have been caught earlier.

The core tension: per-task reviews are fast but blind to the whole picture; end-of-run reviews see everything but can't prevent error compounding. When and how should quality gates fire?

## How We Do It Today

Our orchestration pipeline (mine.orchestrate) runs **three parallel per-task reviewers** (spec reviewer, code-reviewer, integration-reviewer) plus a test gate and optional visual reviewer at Phase 2. Post-execution Phase 3 runs an implementation review against the design doc, then a cross-file integration review on the full branch diff. No style/hygiene/readability reviewer exists in the pipeline — those are user-invoked tools (mine.nitpick, mine.wtf) run ad-hoc after shipping. This creates a gap where code passes all gates but accumulates readability and naming debt.

## Patterns Found

### Pattern 1: Post-Review Code Simplifier as Final Pass

**Used by**: xiaobei930/cc-best
**How it works**: After the primary code reviewer completes and all findings are addressed, a separate `code-simplifier` agent runs as the final refinement stage. The pipeline is `tdd-guide -> code-reviewer -> code-simplifier -> commit`. The simplifier targets redundancy elimination, conditional simplification, dead code cleanup, and structural optimization. It runs with isolated subagent context to avoid the author's tunnel vision.

This is the closest analog to adding a nitpick/WTF pass to Phase 3. The key insight is **positioning**: it runs after correctness and compliance are verified, so it only concerns itself with code quality and cleanliness. It doesn't gate the pipeline — it refines before commit.

**Strengths**: Catches hygiene issues that correctness reviewers don't target. Isolated context provides fresh perspective. Positioned after primary review so it doesn't add noise to the correctness loop.
**Weaknesses**: Adds latency and cost. May suggest simplifications that break subtle invariants the correctness reviewer understood.
**Example**: https://github.com/xiaobei930/cc-best

### Pattern 2: Two-Stage Sequential Review (Spec Compliance, Then Code Quality)

**Used by**: obra/superpowers
**How it works**: After task execution, a spec reviewer checks "did you build the right thing?" and a code quality reviewer checks "did you build it well?" — but sequentially. The code quality reviewer only fires after spec compliance passes. The spec reviewer is explicitly skeptical: "The implementer finished suspiciously quickly. Their report may be incomplete, inaccurate, or optimistic."

**Strengths**: Prevents the failure mode where technically excellent code that doesn't meet requirements passes review. Forces spec compliance as a hard prerequisite.
**Weaknesses**: Sequential execution adds latency. Our current pipeline already runs spec + code + integration in parallel, which is faster.
**Example**: https://github.com/obra/superpowers

### Pattern 3: Specification-First Deterministic Gate + AI Residual

**Used by**: Proposed in arXiv 2603.25773; partially implemented by cc-best (automated Verify gate) and aider (lint-test-fix loop)
**How it works**: Split the quality pipeline into two tiers. First, deterministic verification (type checking, linting, tests, contract validation) catches everything machines can catch. Only the "residual" goes to AI review — structural coherence, architectural fit, cross-cutting concerns. AI review is expensive and noisy; deterministic checks are cheap and precise.

cc-best implements this with a 6-phase automated Verify gate (build -> type check -> lint -> test -> security scan -> git status) that blocks progression to QA. No LLM calls needed.

**Strengths**: Most cost-efficient use of AI review budget. Zero false positives from deterministic checks. AI focuses where it adds unique value.
**Weaknesses**: Requires existing lint/type-check infrastructure. Our pipeline already has a test gate but doesn't run linters.
**Example**: https://arxiv.org/pdf/2603.25773

### Pattern 4: Code Graph / AST-Aware Cross-File Review

**Used by**: CodeRabbit (Code Graph), Augment Code (Deep Code Review Context Engine)
**How it works**: Instead of reviewing only the diff, build a semantic understanding of the codebase — AST or dependency graph — and evaluate changes against it. Catches cross-file issues: a change in module A that breaks callers in module B, naming inconsistencies across files, API contract violations.

Graphite's research found a structured 2,000-token diff-with-summary outperforms a 2,500-token full-context prompt across all 8 tested models — more context causes attention dilution, not better review.

**Strengths**: Directly addresses diff blindness. Catches API misuse, naming drift, architectural violations.
**Weaknesses**: Computationally expensive. Attention dilution means more context doesn't automatically help — structure matters more than volume.
**Example**: https://www.coderabbit.ai/blog/introducing-atlas-the-first-ai-native-code-review-interface

### Pattern 5: Multi-Perspective Parallel Review Ensemble

**Used by**: zircote/.claude (6 parallel specialists), Augment Code, Cursor (three-layer)
**How it works**: Multiple specialized reviewers run in parallel — security, performance, architecture, code quality, test coverage, documentation. A synthesizer collects and deduplicates findings. zircote deploys six parallel agents; Cursor uses three layers (local agent review, automated PR review, human review).

**Strengths**: Catches diverse issues no single reviewer would find. Parallel execution bounds latency by slowest reviewer, not the sum.
**Weaknesses**: Requires structured output at agent boundaries (unstructured text is the "universal anti-pattern"). Higher total compute cost. Our pipeline already does 3-agent parallel review — the question is whether to add a 4th perspective.
**Example**: https://github.com/zircote/.claude

### Pattern 6: Pre-Existing vs New Finding Separation

**Used by**: haberlah/dotfiles-claude
**How it works**: Review findings are classified into three tiers — Important (new, must fix), Nit (new, nice to fix), Pre-existing (legacy debt, not introduced by this change). This prevents review noise from legacy code overwhelming findings about actual changes.

**Strengths**: Reduces noise. Prevents blame for inherited debt. Lets the pipeline focus on regressions.
**Weaknesses**: Requires git history analysis to classify findings. Boundary between "new" and "pre-existing" isn't always clean.
**Example**: https://github.com/haberlah/dotfiles-claude

## Anti-Patterns

- **Same-Model Self-Review**: Using the same model to review its own output. Models "converge on the same syntactically plausible but semantically wrong answers." (Source: https://plus8soft.com/blog/ai-coding-agents/)

- **Context Dumping Without Structure**: Passing full repo context to a reviewer without structuring it. Structured 2K-token summaries outperform 2.5K-token full-context dumps. (Source: https://graphite.com/guides/ai-code-review-context-full-repo-vs-diff)

- **Unbounded Review Loops**: Fix-review cycles without iteration limits. cc-best solves this with a 3-cycle circuit breaker that escalates to a Lead for architectural re-evaluation. (Source: https://github.com/xiaobei930/cc-best)

## Relevance to Us

Our pipeline already implements several of these patterns well:
- **Pattern 2**: We run spec reviewer + code reviewer + integration reviewer (though parallel, not sequential)
- **Pattern 5**: We have 3-agent parallel review per task
- **Pattern 7 (Hard vs Advisory)**: We use hard gates for spec/test failures, advisory for style concerns

The gap is **Pattern 1 (Post-Review Simplifier/Hygiene Pass)**. No reviewer in our pipeline targets the category of issues that mine.nitpick and mine.wtf catch — naming inconsistencies, dead code, API ergonomics, magic numbers, misleading naming, redundant parameters. The code-reviewer focuses on correctness; the integration-reviewer focuses on consistency and design violations. Neither has "readability debt" in their mandate.

A secondary gap is **Pattern 3 (Deterministic Gates)**. Our test gate is the only deterministic check. Adding lint/typecheck as a deterministic pre-gate before LLM review would catch some issues (like the `readonly` type inconsistency from finding #8) without LLM cost.

**Pattern 6 (Pre-existing separation)** is relevant if we add a hygiene pass — it would help filter findings from code the orchestrator didn't touch.

## Recommendation

**Add a hygiene/readability pass as Step 2.7 in Phase 3**, modeled on cc-best's code-simplifier pattern. Position it after the cross-file consistency review (Step 2.5) and before the shipping gate (Step 3). Use the `wtf-reviewer` agent on the full branch diff — it covers readability, naming, dead code, and code hygiene without redundantly re-running code-reviewer or integration-reviewer.

Make it **advisory, not a hard gate** — findings are presented alongside the shipping gate options, and the user decides what to fix. This matches the hybrid gate pattern (hard gates for correctness, advisory for style) that most mature pipelines converge on.

**Don't run it per-task** — intermediate state generates false positives (a constant scattered in T01 that T03 consolidates). The full-branch perspective in Phase 3 is the right scope.

**Consider also adding a deterministic lint/typecheck gate** in Phase 2 (alongside the test gate in Step 5.3) to catch the subset of hygiene issues that tools can find without LLM cost.

## Sources

### Reference implementations
- https://github.com/obra/superpowers — Two-stage sequential review
- https://github.com/xiaobei930/cc-best — Code simplifier, automated Verify gate, circuit breaker
- https://github.com/zircote/.claude — Six parallel specialist reviewers
- https://github.com/citypaul/.dotfiles — Mutation testing gate, TDD guardian
- https://github.com/feiskyer/claude-code-settings — Confidence-scored PR review
- https://github.com/haberlah/dotfiles-claude — Pre-existing finding classification

### Blog posts & writeups
- https://www.nxcode.io/resources/news/agentic-engineering-complete-guide-vibe-coding-ai-agents-2026 — Full multi-agent pipeline guide
- https://www.coderabbit.ai/blog/2025-was-the-year-of-ai-speed-2026-will-be-the-year-of-ai-quality — Industry shift to quality gates
- https://cognition.ai/blog/devin-review — Devin's pre-submission Critic model
- https://cursor.com/blog/agent-best-practices — Three-layer review pattern
- https://graphite.com/guides/ai-code-review-context-full-repo-vs-diff — Context vs attention dilution
- https://plus8soft.com/blog/ai-coding-agents/ — Hard gates between pipeline stages
- https://www.augmentcode.com/guides/multi-agent-orchestration-architecture-guide — Multi-perspective ensemble

### Research papers
- https://arxiv.org/pdf/2603.25773 — Specification-first deterministic gate + AI residual
- https://arxiv.org/html/2603.03823v1 — SWE-CI dual-agent verification
- https://arxiv.org/html/2307.07924v5 — ChatDev multi-role pipeline
- https://ar5iv.labs.arxiv.org/html/2308.00352 — MetaGPT document-centric communication

### Documentation
- https://aider.chat/docs/usage/lint-test.html — Per-step lint-test-fix loop
- https://openhands.dev/blog/openhands-codeact-21-an-open-state-of-the-art-software-development-agent — Self-verification steps
