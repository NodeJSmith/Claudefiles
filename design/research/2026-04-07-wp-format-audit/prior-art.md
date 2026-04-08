---
topic: "design-to-implementation handoff and AI task formats"
date: 2026-04-07
status: Draft
---

# Prior Art: Design-to-Implementation Handoff & AI Task Formats

## The Problem

How should design/architecture documents hand off to implementation tasks — especially when the executor is an LLM-based coding agent? The core tension: too little structure and the agent produces vague, misaligned code; too much and the spec becomes ceremony that nobody (human or AI) actually reads. Every orchestration system struggles with where to draw this line.

The question is sharpened for AI agents because they can't ask follow-up questions mid-execution, so the spec must anticipate ambiguity rather than relying on human judgment to fill gaps.

## How We Do It Today

Caliper v2 uses a three-artifact model: `spec.md` (what to build, user-facing), `design.md` (how to build it, architecture/decisions), and `WP*.md` files (executable task bundles with frontmatter metadata + structured body sections). WPs have six body sections: Objectives & Success Criteria, Subtasks, Test Strategy, Review Guidance, Visual Verification (conditional), and Activity Log. The orchestrator executes WPs sequentially with a per-WP subagent pipeline (executor → spec reviewer → test gate → visual reviewer → code reviewer → integration reviewer → verdict).

## Patterns Found

### Pattern 1: The Two-Layer Model (Project Context + Task Spec)

**Used by**: Cursor, aider, OpenAI Codex, GitHub Copilot (AGENTS.md / `.cursor/rules`); Basecamp (pitch + scope); Google (design doc + tasks)

**How it works**: Every effective system separates persistent project-level context from per-task specifications. Project context covers conventions, architecture, build commands, constraints, and rationale. Task specs are narrowly scoped and *reference* the project context rather than restating it. In the AI agent world, this manifests as AGENTS.md at the project root + a short, specific task instruction. In human engineering, it's design docs/RFCs (persistent, rationale-preserving) paired with issue trackers (per-task, execution-focused). The design doc is never duplicated into the ticket — only referenced.

**Strengths**: Avoids DRY violations in specifications. Rationale captured once, referenced many times. Project conventions don't need restating in every task.

**Weaknesses**: Requires discipline to keep the project-level context current. If it drifts, task specs that reference it become misleading.

**Example**: https://agents.md/ and https://cursor.com/blog/agent-best-practices

### Pattern 2: Shaped Work vs. Scoped Tasks (Shape Up)

**Used by**: Basecamp; teams adapting Shape Up methodology

**How it works**: Shape Up draws a hard line between "shaping" (pre-cycle, by senior people) and "scoping" (during cycle, by implementers). A pitch contains: problem, appetite, solution sketch, rabbit holes, and no-gos — explicitly NOT a task list. Tasks emerge during implementation as the team discovers "scopes" (groups of related tasks mapping to user-visible outcomes). Hill charts track "figuring out" vs. "executing" at the scope level.

**Strengths**: Prevents premature decomposition. Gives implementers ownership of task organization. Hill charts surface unknowns early.

**Weaknesses**: Requires experienced teams who can self-organize. Doesn't prescribe how scopes link back to the pitch's rationale.

**Example**: https://basecamp.com/shapeup/1.1-chapter-02

### Pattern 3: The Five-Element AI Task Spec

**Used by**: Devin (documented), Cursor (documented), aider (community convention); validated in Nature 2025 and arXiv 2025 papers

**How it works**: Five elements consistently appear in well-performing AI agent task specifications:
1. **Context** — what system/module, which files are relevant
2. **Task** — what specifically needs to happen (imperative, scoped)
3. **Constraints** — what must NOT be done (no-go zones, style rules)
4. **Edge cases** — known tricky scenarios
5. **Acceptance criteria** — how do we know it's done (concrete, test-based)

Research adds that including input/output examples and naming specific target files dramatically improves output quality. For multi-step tasks, "plan first, then execute" catches misunderstandings before code is written.

**Strengths**: Matches what AI agents actually use. Acceptance criteria enable automated verification. Constraints prevent the most common failure modes.

**Weaknesses**: Writing good acceptance criteria is hard. Edge cases require domain knowledge. Can become as long as the code (over-specification failure mode).

**Example**: https://docs.devin.ai/essential-guidelines/instructing-devin-effectively

### Pattern 4: ADR-Linked Task Metadata

**Used by**: Google, AWS, teams using adr.github.io

**How it works**: Architecture Decision Records are immutable, numbered documents capturing one decision, its context, and consequences. Tasks reference ADR IDs rather than re-stating rationale. During code review, reviewers check implementations conform to referenced ADRs. When decisions change, new ADRs supersede old ones with explicit links.

**Strengths**: Rationale survives refactors, turnover, and context compaction. Tasks stay slim. Decision log is trustworthy history.

**Weaknesses**: Requires consistent ID maintenance and linking discipline.

**Example**: https://adr.github.io/

### Pattern 5: SWE-bench Minimal Format (the baseline)

**Used by**: SWE-bench benchmark; OpenHands, SWE-agent when operating on real GitHub issues

**How it works**: A task is a GitHub issue body (free-text) plus the full codebase. No structured fields, no acceptance criteria, no file pointers. Success measured by test suite passage. ~77% solve rate on simple single-file bugs, but fails badly on multi-file/multi-session tasks (SWE-bench Pro).

**Strengths**: Zero overhead. Maps to real-world issue format.

**Weaknesses**: Performance degrades sharply on complex tasks. No traceability to design rationale.

**Example**: https://arxiv.org/pdf/2310.06770

## Anti-Patterns

- **Premature task decomposition in the design phase** — writing task lists before the design is shaped. Shape Up warns: design artifacts should describe the problem and constraints, not implementation steps. ([source](https://basecamp.com/shapeup/1.1-chapter-02))

- **Duplicating rationale into tasks** — copying design context into task descriptions causes drift from the source of truth. Reference, don't restate. ([source](https://leaddev.com/technical-decision-making/thorough-team-guide-rfcs))

- **Vague acceptance criteria** — primary failure mode for both humans (54% of project failures per IIBA) and AI agents. For LLMs, vague prompts produce vague code. ([sources](https://fabrity.com/blog/10-pitfalls-to-avoid-when-preparing-an-it-project-specification-a-guide-for-it-services-buyers/), [Devin docs](https://docs.devin.ai/essential-guidelines/instructing-devin-effectively))

- **Over-specifying implementation paths** — describing exactly how to implement reduces executor judgment and creates lock-in. Specify what to achieve and constraints, not the path. ([source](https://fabrity.com/blog/10-pitfalls-to-avoid-when-preparing-an-it-project-specification-a-guide-for-it-services-buyers/))

## Emerging Trends

- **AGENTS.md** (Linux Foundation, Dec 2025) is becoming the project-context standard — adopted by Cursor, aider, Codex, Gemini CLI, 60k+ repos. Schema-free Markdown, tool-agnostic.

- **Plan-before-execute** is now standard practice for AI agent complex tasks — both academic research (PROMST, Nature 2025) and vendor docs (Devin, Cursor) converge on this.

- **Long-horizon benchmarks driving format evolution** — SWE-bench Pro finds that single-turn issue-text-only prompts fail at scale for multi-file tasks, pushing toward richer formats with scope boundaries and milestone verification.

## Relevance to Us

Caliper v2 already implements several best practices:
- **Two-layer model**: `design.md` (persistent rationale) + `WP*.md` (per-task execution) follows the industry pattern
- **Plan-before-execute**: The orchestrator already does this (via implementer-prompt's pre-implementation questions)
- **Acceptance criteria**: `## Objectives & Success Criteria` maps directly to the Five-Element spec's acceptance criteria

Where we may diverge from best practice:
- **DRY violations**: WPs may be restating context that design.md already provides (the full design.md is passed to the executor alongside the WP — do both need the same level of detail?)
- **Over-specification risk**: Six structured body sections per WP may cross the line into ceremony, especially for simple tasks. The Granularity-to-Delegation Matching pattern suggests task detail should scale with complexity, not be uniform.
- **Dead metadata**: `Activity Log`, `plan_section` (decorative), and some design.md header metadata aren't consumed. This is pure ceremony.
- **Missing from Five-Element model**: We don't have an explicit "Edge Cases" element. Constraints are split across `Review Guidance` (what reviewers check) and `Non-Goals` (design level) — this split may reduce their visibility to the executor.

## Recommendation

The Five-Element AI Task Spec pattern is the strongest match for our use case. Our current format contains all five elements but distributes them across more sections than necessary, with some dead-weight fields. A refactor toward the five-element model — potentially collapsing `Objectives & Success Criteria` + `Review Guidance` into a tighter acceptance-criteria-plus-constraints format, dropping `Activity Log`, and making `plan_section` optional — would reduce token overhead without losing signal. The Shape Up insight about scaling task granularity to complexity (rather than uniform templates) is also worth adopting.

The research finding that "plan first, then execute" and specific file paths improve LLM output is already implemented in caliper v2 — this is a strength to preserve.

## Sources

### Reference implementations
- https://agents.md/ — AGENTS.md open standard for AI agent project context
- https://basecamp.com/shapeup — Shape Up methodology (full book)
- https://adr.github.io/ — Architecture Decision Records standard

### Blog posts & writeups
- https://www.industrialempathy.com/posts/design-docs-at-google/ — Design docs at Google
- https://blog.pragmaticengineer.com/rfcs-and-design-docs/ — Industry RFC/design doc survey
- https://jacobian.org/2024/mar/11/breaking-down-tasks/ — Task granularity and delegation matching
- https://leaddev.com/technical-decision-making/thorough-team-guide-rfcs — RFC guide
- https://fabrity.com/blog/10-pitfalls-to-avoid-when-preparing-an-it-project-specification-a-guide-for-it-services-buyers/ — Spec pitfalls
- https://aitoolsatlas.ai/blog/2026-03-20-ai-coding-agent-prompts — AI agent prompt structure
- https://cursor.com/blog/agent-best-practices — Cursor agent best practices

### Documentation & standards
- https://docs.devin.ai/essential-guidelines/instructing-devin-effectively — Devin task format
- https://developers.openai.com/codex/guides/agents-md — Codex AGENTS.md usage
- https://linear.app/docs/issue-templates — Linear issue templates

### Academic research
- https://arxiv.org/pdf/2310.06770 — SWE-bench benchmark
- https://static.scale.com/uploads/654197dc94d34f66c0f5184e/SWEAP_Eval_Scale%20(9).pdf — SWE-bench Pro (long-horizon tasks)
- https://www.nature.com/articles/s41598-025-19170-9 — LLM task flow generation (Nature 2025)
- https://arxiv.org/html/2601.13118v1 — LLM code generation prompt guidelines
- https://yongchao98.github.io/MIT-REALM-PROMST/ — PROMST multi-step task optimization
