---
topic: "Single-source-of-truth structure for spec/design docs reviewed by LLM consistency checkers"
date: 2026-09-29
status: Draft
---

# Prior Art: One fact, one home in design docs

## The Problem

mine-define's design.md enumerates the same behaviors in several parallel places: Goals, User Scenarios, Functional Requirements (FR#), Edge Cases, Acceptance Criteria (AC#, mapped to FRs), Test Strategy > New Test Coverage (mapped to FRs), plus any inventory table in Architecture. Impact > Changed Files also overlaps Architecture and Replacement Targets. The fine-toothed comb checks cross-section consistency, so every restatement is a live invariant it can find broken. In hassette spec 115 (408 lines, 24 FRs), three comb passes each found a new pair of lists that disagreed. Fleet-wide, 77% of comb runs since 2026-08-01 report blocking findings (289/373).

## How We Do It Today

The template descends from GitHub Spec Kit (FR IDs, the `[NEEDS CLARIFICATION]` convention, now banned). The pre-#223 split between spec.md and design.md was merged into one document, and both layers were kept. The result has Spec Kit's User Stories and FRs, plus a separate top-level AC# list and a Test Strategy that maps to FRs a third time. Downstream, mine-plan parses the FR#/AC# lists, Impact > Changed Files, Behavioral Invariants, and the four Test Strategy subsections. Task `implements`/Verify fields cite FR#/AC# IDs. The comb gate offers "Fix and finish" from run 3 onward. It has no trend check.

## Patterns Found

### Pattern 1: Scenario-under-requirement (the requirement owns its test)
**Used by**: OpenSpec (`#### Scenario:` Given/When/Then nested under each `### Requirement:`), Kiro (EARS `WHEN … THE SYSTEM SHALL …` is both requirement and acceptance criterion), Spec Kit (acceptance scenarios nested under the user story).
**How it works**: There is one enumeration. Verification is a child block of the requirement, not a parallel numbered list. The reviewer's check becomes local ("does each requirement have a scenario?") rather than a cross-list comparison.
**Strengths**: Removes the FR↔AC↔test drift class by construction.
**Weaknesses**: Aggregate test concerns (layers, infrastructure, tests to adapt or remove) still need their own section. The template needs a restructure, not just added cross-references.
**Example**: https://openspec.dev/docs/core-concepts ; https://kiro.dev/docs/specs/feature-specs/requirements-first/

### Pattern 2: Link, don't copy
**Used by**: Google-style design docs; Spec Kit ("Independent Test" cites FR IDs); traceability practice (inline IDs over a separate matrix).
**How it works**: A fact with a canonical home is referenced by ID or link everywhere else and never paraphrased.
**Strengths**: Easy to retrofit.
**Weaknesses**: An ID plus a paraphrase can still drift. Cross-references alone only partly fix the problem.
**Example**: https://www.industrialempathy.com/posts/design-doc-a-design-doc/ ; https://www.drdobbs.com/dont-enter-the-matrix/184415807

### Pattern 3: Delta-only specs
**Used by**: OpenSpec (ADDED/MODIFIED/REMOVED blocks merged into the canonical spec).
**Relevance**: This addresses duplication across proposals over time, not within one document. Low relevance here.

### Pattern 4: Non-convergence is a stop signal, not a budget to exhaust
**Used by**: The Contrast Security writeup on AI reviewers that disagree; the "More Rounds, More Noise" paper (arXiv 2603.16244, abstract only, not verified).
**How it works**: Track blocking-finding count and category across rounds. If the count is flat or rising, stop re-running. Fix the structural cause or escalate to a human.
**Weaknesses**: Needs finding history persisted across runs. `cfl gate` already records blocking/minor counts.
**Example**: https://www.contrastsecurity.com/security-influencers/when-ai-reviewers-cannot-agree

## Anti-Patterns
- Parallel top-level enumerations of the same facts with no ownership hierarchy. None of the surveyed formats keeps three.
- Re-running the same reviewer until the round budget runs out, then calling that convergence.

## Relevance to Us

Our template matches the anti-pattern exactly: FR, AC, and New Test Coverage are three parallel lists. Pattern 1 fits best, but mine-plan and task files depend on AC# IDs, so the restructure has to keep IDs stable (for example, ACs nested under their FR, or FRs that carry their own Verify line). Pattern 2 is the cheap companion: when a design has an inventory table, FRs and tests point at the table instead of re-listing it. The hassette session invented that fix by hand. Pattern 4 maps onto the comb gate's existing iteration counter.

## Recommendation

1. Restructure the template so verification nests under each FR. Drop the standalone AC list, or keep AC# IDs as children of FRs. Reduce Test Strategy to aggregate concerns only: required layers, tests to adapt, tests to remove.
2. Add a "one fact, one home" content rule. An enumeration lives in one place, and other sections cite it by ID or table name.
3. Make the comb's cross-section mismatches point to a structural fix: delete the restatement rather than syncing it. Add a trend-based exit to comb-gate.md.

Coverage caveat: the OpenSpec rationale and the arXiv paper came from search snippets or abstracts, not full text.

## Sources

### Reference implementations
- https://github.com/github/spec-kit/blob/main/templates/spec-template.md — Spec Kit spec template
- https://www.mintlify.com/github/spec-kit/commands/analyze — Spec Kit /analyze (flags duplication; remediation gated on the user)
- https://openspec.dev/docs/core-concepts — OpenSpec requirement/scenario format and deltas
- https://kiro.dev/docs/specs/feature-specs/requirements-first/ — Kiro EARS acceptance criteria
- https://github.com/ResourcefulAI/bmad-method — BMAD (sharding; not relevant to this question)

### Blog posts & writeups
- https://www.industrialempathy.com/posts/design-doc-a-design-doc/ — link, don't copy
- https://www.contrastsecurity.com/security-influencers/when-ai-reviewers-cannot-agree — non-convergent AI review
- https://www.drdobbs.com/dont-enter-the-matrix/184415807 — critique of separate traceability matrices

### Documentation & standards
- https://en.wikipedia.org/wiki/Easy_Approach_to_Requirements_Syntax — EARS
- https://arxiv.org/pdf/2603.16244 — "More Rounds, More Noise" (not verified)

Note: URLs were not live-verified.
