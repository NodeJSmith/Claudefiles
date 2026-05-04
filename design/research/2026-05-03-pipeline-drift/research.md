---
topic: "Preventing spec-to-implementation drift in multi-agent pipelines"
date: 2026-05-03
status: Draft
---

# Prior Art: Preventing Spec-to-Implementation Drift in Multi-Agent Pipelines

## The Problem

When a design doc is decomposed into subtasks by one agent and executed by another, interpretation errors at each handoff compound into significant implementation drift. Our pipeline (design doc → WP author → WP text → executor → code) produced a 148-file UI redesign that diverged substantially from the mockup because: (1) the WP author described old patterns instead of the new design, (2) the executor dropped "secondary" requirements from correct WPs, and (3) the spec reviewer noticed missing items but rated them LOW and passed. Three layers of failure, all structural.

## How We Do It Today

The pipeline has five stages: mine.define (design doc) → mine.plan (WP generation with reviewer checklist) → mine.orchestrate (executor dispatch + spec/code/integration review per WP). The executor receives WP text + a design-extract (Architecture/Proposed Approach sections only). The spec reviewer validates executor output against WP objectives, not against the original design doc. No step validates that WPs faithfully represent the design doc's intent. No visual artifacts are passed to executors.

## Patterns Found

### Pattern 1: Spec-Anchored Development (Source of Truth Anchoring)

**Used by**: Kiro (Amazon), Tessl, spec-kit (GitHub), Martin Fowler's SDD framework

**How it works**: The original specification remains the authoritative artifact throughout the entire development lifecycle. Rather than producing intermediate artifacts that become the new "truth," all downstream agents and processes validate their work against the original spec. The spec is version-controlled alongside code and treated as a living document.

In practice: (1) the spec generates acceptance criteria before any implementation begins, (2) implementation agents receive both the task description AND the relevant section of the original spec, (3) review agents validate against the spec, not against intermediate plans, (4) the spec is updated only when requirements intentionally change.

Kiro implements this by auto-generating three linked documents (requirements, design, tasks) where each task explicitly references the requirement it satisfies. Agent Hooks validate code changes against specs automatically on file save.

**Strengths**: Eliminates the telephone game by giving every agent access to the same ground truth. Makes drift structurally visible. Scales to large projects because traceability is maintained automatically.

**Weaknesses**: Requires the spec itself to be correct and complete. Adds overhead to maintain spec-code links. Can become rigid when legitimate refinement is needed during implementation.

**Example**: https://kiro.dev/docs/specs/

---

### Pattern 2: Acceptance Criteria as Executable Gates (ATDD/BDD)

**Used by**: ATDD practitioners, BDD frameworks (Cucumber, SpecFlow), Kiro (EARS notation)

**How it works**: Before implementation begins, acceptance criteria are defined in a format that can be mechanically verified — either as automated tests, structured checklists, or binary assertions. Implementation is not complete until all criteria pass. The reviewer doesn't exercise judgment about importance — it checks each criterion.

The key insight: criteria must be agreed upon BEFORE implementation by someone who understands the intent (the spec author), not derived after-the-fact by the implementer or reviewer. This removes the calibration problem entirely for completeness checks.

**Strengths**: Eliminates reviewer judgment calls on completeness. Makes "done" unambiguous. Catches dropped items immediately.

**Weaknesses**: Not all requirements are easily binary (e.g., "UI should feel cohesive"). Upfront effort. Can lead to gaming (satisfying letter while missing spirit).

**Example**: https://agilealliance.org/glossary/atdd/

---

### Pattern 3: Ready-to-Use Prompts per Step (Flatten the Hops)

**Used by**: freekmurze/dotfiles spec-writer skill, Claude Code prompt-plan patterns

**How it works**: Instead of WPs being abstract descriptions that an executor interprets, the planning stage produces ready-to-use prompts for each implementation step. The WP IS the prompt. This eliminates the interpretation hop entirely — the executor receives exactly what to build, not a summary it must re-interpret.

freekmurze's spec-writer outputs a PROMPT_PLAN.md with implementation prompts per step that can be copy-pasted directly into a coding session. Each prompt includes full context: what files to modify, what the expected behavior is, what to verify.

**Strengths**: Zero interpretation by executor. WP author's intent is preserved exactly. Makes WP quality directly testable (is the prompt clear enough?).

**Weaknesses**: Prompts are brittle to context changes (file renames, prior WP outcomes). WP authoring takes longer. Less flexibility for executor to adapt when reality differs from plan.

**Example**: https://github.com/freekmurze/dotfiles (spec-writer skill) — GitHub issue #260

---

### Pattern 4: Per-Step Validation Against Original Artifacts (PDCA)

**Used by**: PDCA frameworks for AI coding, hallucination prevention research

**How it works**: After each subtask execution, a validation step compares the output against the ORIGINAL requirements/spec — not just against the intermediate plan. This prevents the failure mode where each step is locally correct but globally drifting.

Research on hallucination propagation explicitly warns that "early mistakes distort the agent's belief state and induce compounding failures unless explicit recovery mechanisms are present." The fix is validation BETWEEN steps, not only at the end.

**Strengths**: Catches drift early when correction cost is low. Prevents compounding. Natural checkpoints for human intervention.

**Weaknesses**: Adds latency and cost. Validator itself can be miscalibrated. Can create false security if validation is superficial.

**Example**: https://www.infoq.com/articles/PDCA-AI-code-generation/

---

### Pattern 5: Domain-Specialized Review (Separation of Concerns)

**Used by**: Cloudflare (AI code review at scale), obra/superpowers (two-stage review)

**How it works**: Instead of one reviewer checking everything, separate agents handle separate concerns. For spec compliance specifically, a dedicated agent whose ONLY job is "does implementation satisfy every spec item?" — binary pass/fail, no severity ratings, no judgment about importance.

Cloudflare's research: domain-focused agents produce 87% fewer false positives and detect 3x more issues than generalists. The superpowers repo proposed "two-stage review (spec compliance → code quality, strict ordering)" which was previously deferred in our pipeline (issue #207 analysis).

**Strengths**: Eliminates "rated LOW but actually critical." Each agent independently calibrated. Clearer rubrics.

**Weaknesses**: Coordination overhead. Can miss cross-cutting concerns. More infrastructure.

**Example**: https://blog.cloudflare.com/ai-code-review/

---

### Pattern 6: Structured Document Communication (MetaGPT SOPs)

**Used by**: MetaGPT (ICLR 2024), enterprise ADR patterns

**How it works**: Agents exchange structured artifacts — class diagrams, API specs, interface contracts — instead of natural language summaries. Structure constrains interpretation. A class diagram with method signatures leaves less room for "interpretation" than prose describing the same interface.

MetaGPT encodes SOPs into prompt sequences where each role produces specific document types with specific schemas. The key insight: when the WP author must express design in structured terms (file lists, component names, interface contracts), ambiguity is forced out.

**Strengths**: Reduces ambiguity at handoffs. Information loss becomes visible (a structured field can't be "summarized away"). Enables automated validation.

**Weaknesses**: Not all design intent is expressible structurally. Feels heavy for small changes. Requires schema design.

**Example**: https://github.com/FoundationAgents/MetaGPT

---

### Pattern 7: Traceability Matrix (Requirement-to-Implementation Mapping)

**Used by**: Safety-critical SE (DO-178C, ISO 26262), adapted in spec-driven AI tools

**How it works**: Bidirectional mapping between every requirement and its implementation artifacts. Forward traceability (spec → code) reveals unimplemented requirements. Backward traceability (code → spec) reveals scope creep.

In an AI pipeline: WP author must explicitly map each design doc requirement to a WP task. Executor annotates which requirement each code change satisfies. Reviewer checks the matrix for gaps (requirements with no implementation).

**Strengths**: Makes completeness mechanical. Reveals exactly which items were dropped. Audit trail.

**Weaknesses**: Overhead to maintain. Doesn't verify quality, only existence.

**Example**: https://abstracta.us/blog/testing-strategy/requirements-traceability-matrix-your-qa-strategy/

---

### Pattern 8: Executor Observability (Progress Protocol)

**Used by**: Proposed in GitHub issue #194

**How it works**: The executor writes structured progress markers after each subtask (DONE/SKIP/BLOCKED with rationale). The orchestrator can detect when an executor skips items or gets stuck, and intervene before the full WP is "complete" with gaps.

Currently the orchestrator goes dark during execution — no visibility into which subtasks were attempted, which were skipped, or why. A structured progress file would make "executor dropped secondary items" immediately detectable.

**Strengths**: Early detection of dropped items. Enables mid-execution intervention. Creates accountability trail.

**Weaknesses**: Executor overhead. Progress reports can themselves be inaccurate.

**Example**: GitHub issue #194 (research: executor observability via structured progress protocol)

---

## Anti-Patterns

- **Trusting intermediate artifacts as authoritative** — Each handoff produces a summary that becomes "the truth" for the next agent. The original spec is never re-consulted. This is our current failure mode. (Source: https://www.augmentcode.com/guides/multi-agent-ai-systems)

- **Severity-based gating on completeness checks** — Allowing reviewers to rate missing spec items as "LOW" conflates "Is this implemented?" (binary) with "How important is it?" (judgment). Completeness should be binary. (Source: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)

- **End-only verification for long pipelines** — Verifying only the final output of 11 sequential WPs allows drift to compound undetected. Early mistakes "distort the agent's belief state and induce compounding failures." (Source: https://arxiv.org/html/2509.18970v1)

- **Generalist reviewer judging spec compliance** — A single reviewer checking quality + compliance underperforms specialized agents by 3x. (Source: https://blog.cloudflare.com/ai-code-review/)

## Emerging Trends

**Spec-as-Source**: Tessl and SDD research (Feb 2026) push toward specs being the ONLY editable artifact. Code is generated and marked "DO NOT EDIT." Eliminates drift by making the spec the only thing that matters.

**Multi-Agent Disagreement as Signal**: Rather than single pass/fail, disagreement between specialized agents triggers human escalation. If spec-compliance agent says FAIL and code-quality agent says PASS, that disagreement is the valuable signal.

**Per-Step Recovery**: Research increasingly shows robustness "hinges less on one-shot correctness than on the ability to detect instability, revise commitments, and prevent unverified intermediate states from polluting belief and memory."

## Relevance to Us

Our pipeline already has the right structure (design → plan → execute → review). The gaps are:

1. **No spec anchoring** — executor sees WP text + design-extract, not the full design doc or visual artifacts. Spec reviewer validates against WP, not design doc.
2. **No traceability** — WPs don't explicitly map back to design doc requirements. No mechanism to verify coverage.
3. **Reviewer calibration** — spec reviewer uses judgment (PASS/WARN/FAIL) where completeness should be binary.
4. **No per-WP drift detection** — validation only at the end of each WP, not between WPs against the overall spec.
5. **Executor context is too thin** — receives design-extract (Architecture section only) + WP text, missing visual artifacts, edge cases, acceptance criteria.

Related filed issues that feed into this:
- #194: executor observability via structured progress protocol
- #193: review depth scaling per WP
- #192: WP scope limits to prevent oversized executor runs
- #199: keep docs in sync during WP execution
- #197: spec-kitty upstream changes (9-lane model, ADRs per WP)
- #260: spec-writer iterative planning (prompt-plan pattern)

## Recommendation

The highest-leverage changes, in order:

1. **Spec-anchored review** (Pattern 1 + 5): The spec reviewer should validate against the design doc, not just the WP. Cheapest fix with highest impact — it's a prompt change, not an architecture change. Make completeness binary (implemented/not), move judgment to a separate code-quality pass.

2. **Traceability in WPs** (Pattern 7): Each WP subtask should explicitly reference which design doc requirement(s) it implements (e.g., "Implements FR#16"). The reviewer can then mechanically check: "Are all FRs assigned to this WP present in the implementation?"

3. **Visual artifact injection** (Pattern 1): For frontend/UI work, the executor must receive mockup file paths and be instructed to treat them as primary reference. This is the specific fix for the hassette failure.

4. **Ready-to-use prompts for UI WPs** (Pattern 3): For frontend work where visual fidelity matters, WPs should include specific file references and line numbers from mockups rather than abstract descriptions. WP12 (post-gap-analysis) demonstrates this pattern already.

5. **Executor progress protocol** (Pattern 8, issue #194): Executor emits structured DONE/SKIP/BLOCKED per subtask. Orchestrator can detect skipped items before the review phase.

## Sources

### Research papers
- https://arxiv.org/abs/2308.00352 — MetaGPT: Multi-Agent Collaborative Framework
- https://arxiv.org/html/2307.07924v5 — ChatDev: Communicative Agents for Software Development
- https://arxiv.org/html/2602.00180v1 — Spec-Driven Development (Feb 2026)
- https://arxiv.org/html/2509.18970v1 — LLM-based Agents Suffer from Hallucinations (survey)
- https://arxiv.org/pdf/2509.25370 — Where LLM Agents Fail and How They Can Learn
- https://arxiv.org/abs/2604.14228 — Dive into Claude Code (April 2026)
- https://arxiv.org/html/2406.01304v3 — CodeR: Issue Resolving with Task Graphs

### Product documentation & reference implementations
- https://kiro.dev/docs/specs/ — Kiro spec-driven IDE
- https://github.com/FoundationAgents/MetaGPT — MetaGPT framework
- https://devin.ai/agents101 — Devin: Coding Agents 101

### Blog posts & technical articles
- https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html — Understanding Spec-Driven Development
- https://www.augmentcode.com/guides/multi-agent-ai-systems — Multi-Agent AI Systems Architecture
- https://blog.cloudflare.com/ai-code-review/ — Orchestrating AI Code Review at Scale
- https://www.infoq.com/articles/PDCA-AI-code-generation/ — PDCA Framework for AI Code Generation
- https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents — Demystifying Evals (Anthropic)

### Standards & methodologies
- https://agilealliance.org/glossary/atdd/ — Acceptance Test-Driven Development
- https://abstracta.us/blog/testing-strategy/requirements-traceability-matrix-your-qa-strategy/ — Requirements Traceability Matrix

### Internal references
- GitHub issue #194: executor observability via structured progress protocol
- GitHub issue #193: review depth scaling per WP
- GitHub issue #192: WP scope limits to prevent oversized executor runs
- GitHub issue #199: keep docs in sync during WP execution
- GitHub issue #197: spec-kitty upstream changes (9-lane model, ADRs per WP)
- GitHub issue #260: spec-writer iterative planning (prompt-plan pattern)
- GitHub issue #262: deep-research multi-agent orchestration (feiskyer)
- PR #207: superpowers-inspired review improvements (already landed)
