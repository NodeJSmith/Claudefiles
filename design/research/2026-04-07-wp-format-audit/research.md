---
topic: "WP and design.md format effectiveness for LLM-based orchestration"
date: 2026-04-07
status: Draft
flexibility: Exploring
motivation: "Never audited the format before; unsure how much content agents actually use; unsure how large text volumes affect agent performance; observed quality gaps in orchestrator output"
constraints: "None — exploratory"
depth: deep
---

# Research Brief: WP and Design.md Format Effectiveness

**Initiated by**: User wants to evaluate whether the current WP and design.md artifact format is optimal for LLM-based code generation agents, given observed quality gaps in orchestrator output.

## Context

### What prompted this

The caliper v2 orchestration workflow uses two primary artifacts -- design.md (architecture reference) and WP files (executable task specs) -- to drive a multi-step code generation pipeline. These artifacts were designed organically as the workflow evolved through multiple feature iterations (001 through 013). The format has never been audited against what LLM agents actually need to produce good code, or against research on how context volume affects LLM performance.

### Current state

**The executor prompt receives approximately 4,700-8,700 tokens of injected context per WP:**

| Component | Tokens (approx) | Role |
|-----------|-----------------|------|
| WP content | 500-1,000 | Task specification |
| design.md (full) | 2,400-4,900 | Architecture reference |
| implementer-prompt.md | 2,900 | Behavioral instructions |
| tdd.md | 900 | TDD cycle reference |
| Test command | ~20 | Canonical test command |

The spec reviewer receives a similar payload (~5,600-9,600 tokens) plus the executor's output. The visual reviewer receives ~1,600 tokens of instructions plus screenshots.

**WP file sections (current schema):**
- YAML frontmatter: `work_package_id`, `title`, `lane`, `plan_section`, `depends_on`
- `## Objectives & Success Criteria`
- `## Subtasks`
- `## Test Strategy`
- `## Review Guidance`
- `## Visual Verification` (conditional)
- `## Activity Log`

**design.md sections (typical):**
- Header metadata: `**Date:**`, `**Status:**`, `**Research:**`
- `## Problem`
- `## Non-Goals`
- `## Architecture`
- `## Alternatives Considered`
- `## Test Strategy` (sometimes)
- `## Open Questions`
- `## Impact`

### Key constraints

No hard constraints. The format can be redesigned significantly if the analysis supports it.

## Findings

### 1. Consumer Chain Analysis -- What Each Agent Actually Uses

I traced every WP field and design.md section through each consumer prompt to determine what is actually referenced by name vs. received as bulk context.

#### WP fields: consumer mapping

| WP Field/Section | Executor | Spec Reviewer | Plan Reviewer | Visual Reviewer | spec-helper |
|------------------|----------|---------------|---------------|-----------------|-------------|
| `work_package_id` | Identity only | Identity only | - | - | Validated (regex) |
| `title` | Identity only | Identity only | - | - | Required non-empty |
| `lane` | Not read | Not read | Not read | - | Validated, moved |
| `plan_section` | Called "decorative" by orchestrator | Not referenced | Validated against design.md headings | - | Warning if mismatched |
| `depends_on` | Not enforced for ordering | Not referenced | Validates references exist | - | Validated (regex, existence) |
| **Objectives & Success Criteria** | Drives PASS definition | Primary pass/fail source | Checklist item | - | Not read |
| **Subtasks** | Executed sequentially | Cross-referenced with code changes | Checklist item | - | Not read |
| **Test Strategy** | Drives test writing | Coverage inventory check | Checklist item | - | Not read |
| **Review Guidance** | Constraint enforcement | Compliance check | Checklist item | - | Not read |
| **Visual Verification** | Screenshot capture plan | Plan audit only (not visual) | - | Primary evaluation source | Not read |
| **Activity Log** | **Never read** | **Never read** | **Never read** | - | **Write-only** (appended on lane moves) |

#### design.md sections: consumer mapping

| design.md Section | Executor | Spec Reviewer | Plan Reviewer | Implementation Reviewer | Challenge |
|-------------------|----------|---------------|---------------|------------------------|-----------|
| `**Date:**` header | **Not referenced** | **Not referenced** | Not referenced | Not referenced | Not referenced |
| `**Status:**` header | **Not referenced** | **Not referenced** | Updated by plan-review | Not referenced | Not referenced |
| `**Research:**` header | **Not referenced** | **Not referenced** | Not referenced | Not referenced | Not referenced |
| `## Problem` | General context | General context | Reviewed | Not specifically | General context |
| `## Non-Goals` | Scope boundary | Scope boundary | Reviewed | Not specifically | General context |
| `## Architecture` | Primary reference on ambiguity | Supplemental (defers to WP Objectives) | Primary review target | Not specifically | General context |
| `## Alternatives Considered` | **Not specifically consumed** | **Not specifically consumed** | Reviewed (but no checklist item) | Not referenced | General context |
| `## Test Strategy` | Overridden by per-WP Test Strategy | Not referenced (uses WP's) | Reviewed | Not specifically | Not referenced |
| `## Open Questions` | Not referenced | Not referenced | Reviewed | Not referenced | Not referenced |
| `## Impact` | File list reference | File list reference | Reviewed | Not specifically | Not referenced |

### 2. Dead Weight Identified

Fields/sections that exist but provide no signal to any LLM consumer:

**High-confidence dead weight (never read by any consumer):**

1. **`## Activity Log`** -- Write-only. `spec-helper` appends lane transition timestamps, but no LLM consumer ever reads it. This section grows with every lane move (avg 3-5 entries per WP by completion). In the WP01 example from 008, it had 5 entries consuming ~200 chars of context. Across a 5-WP run, that is ~1,000 chars of pure noise injected into every executor and reviewer prompt.

2. **`**Date:**` in design.md** -- Present in all design docs. Not referenced by any consumer prompt by name. Not used for staleness detection (the checkpoint uses `started_at` for that).

3. **`**Research:**` in design.md** -- Path to research brief. Not referenced by any consumer. The research brief itself is never loaded by any orchestration-stage consumer.

4. **`plan_section` in WP frontmatter** -- The orchestrator literally calls it "decorative" in Step 1 (SKILL.md line 201). spec-helper validates it against design.md headings but only as a warning. No consumer uses it for routing, ordering, or verification.

**Medium-confidence dead weight (consumed but questionable value):**

5. **`depends_on` in WP frontmatter** -- Validated by spec-helper (broken references caught). But the orchestrator executes WPs sequentially by file order, not by dependency graph. The plan reviewer checks that references exist. However, no consumer actually enforces execution ordering from this field. Its value is purely documentary.

6. **`## Alternatives Considered` in design.md** -- Not specifically consumed by name by any downstream skill. The executor is told to consult "the design doc's Architecture section" on ambiguity, not Alternatives Considered. The plan reviewer reviews it but has no specific checklist item for it. Its value is for human decision archaeology, not LLM execution.

7. **`## Impact` section in design.md** -- Contains file lists that are partially useful, but the executor and reviewers get file lists from `git diff` (Step 4.5), not from this section. Its value is pre-implementation planning, not execution.

### 3. Signal-to-Noise Analysis

**Estimated signal density by section:**

| Section | Avg chars | Signal for executor | Signal for reviewer | Overall signal density |
|---------|-----------|--------------------|--------------------|----------------------|
| Objectives & Success Criteria | 600 | HIGH -- defines PASS | HIGH -- defines FAIL | ~90% signal |
| Subtasks | 500 | HIGH -- executed sequentially | HIGH -- cross-referenced | ~85% signal |
| Test Strategy | 400 | HIGH -- drives test writing | HIGH -- coverage check | ~80% signal |
| Review Guidance | 400 | HIGH -- constraint enforcement | HIGH -- compliance check | ~80% signal |
| Visual Verification | 300 | HIGH -- screenshot plan | MEDIUM -- plan audit | ~75% signal |
| YAML frontmatter | 150 | LOW -- only identity used | LOW -- only identity used | ~30% signal |
| Activity Log | 200 | ZERO | ZERO | 0% signal |

**design.md signal density for executor context:**

| Section | Avg chars | Signal density for executor |
|---------|-----------|---------------------------|
| Architecture | 3,000-8,000 | MEDIUM -- consulted on ambiguity only |
| Problem | 500 | LOW -- general context |
| Non-Goals | 300 | MEDIUM -- scope boundary |
| Alternatives Considered | 1,000-3,000 | LOW -- not specifically consumed |
| Impact | 500-1,500 | LOW -- stale by execution time |
| Date/Research/Status headers | 100 | ZERO |
| Open Questions | 200 | LOW -- resolved before WP generation |

**The full design.md is 2,400-4,900 tokens.** For the executor, the high-signal content (Architecture + Non-Goals) is typically 1,500-3,500 tokens. The remaining 900-1,400 tokens are low-signal or zero-signal content that displaces attention.

### 4. What LLM Agents Actually Need (from research)

Research from multiple sources converges on what code generation agents need in their task specs:

**From the empirical characterization study (arxiv 2601.13118):**
The top 3 most impactful prompt elements for code generation quality are:
1. **Algorithmic details** (57% of successful optimizations) -- specific logic, not vague descriptions
2. **I/O format specification** (44%) -- concrete input/output shapes, not prose
3. **Post-conditions** (23%) -- observable outcomes, not process descriptions

This maps directly to the WP format's strengths: **Objectives & Success Criteria** (post-conditions), **Subtasks** (algorithmic details), and **Test Strategy** (I/O format via test assertions).

**From context rot research (Chroma/Morph, 2025-2026):**
- Performance degrades at every context length increment, even well below capacity
- At ~50K tokens, "significant degradation" occurs in a 200K-token model
- The signal-to-noise ratio in typical agent tasks is ~2.5% by the time tasks complete
- "The problem isn't running out of space. It's the noise that fills the space."
- Recommendation: prevent noise entry rather than compress after accumulation

**From Addy Osmani's spec guidance (2026):**
- Structured, sectioned specs outperform prose
- "What and why" before "how"
- Minimal but sufficient detail -- include necessary specifics, omit background archaeology
- Modular pieces over monolithic docs

**From the lost-in-the-middle research:**
- Models attend well to the start and end of context, poorly to the middle
- 30%+ accuracy drops for information in middle positions
- This means in a combined prompt (WP + design.md + instructions), the WP content at the top and the TDD reference at the bottom get the most attention, while the design.md in the middle gets least attention -- which is exactly where the Architecture section sits

### 5. How Other Systems Structure Task Specs

**Claude Code's built-in Task tool:**
- Minimal prompt: natural language description + specific file paths
- No formal schema -- relies on system prompt + CLAUDE.md context
- Sub-agents get focused scope, not the full project context

**SWE-Agent / OpenHands:**
- Task = GitHub issue text (title + body), typically 50-200 words
- No formal WP structure -- the agent reads the issue and explores
- Agent-Computer Interface (ACI) handles tool abstractions
- Key insight: minimal task description + good tooling > detailed spec + weak tooling

**AGENTS.md pattern (Vercel/Next.js, adopted by Codex/Cursor/Claude Code):**
- Project-level context, not per-task specs
- Captures conventions, boundaries, and patterns
- Tasks are described in natural language at invocation time

**Common pattern across all systems:**
- Task descriptions are concise (50-500 words)
- Project context is loaded separately from task specs
- File paths are explicit, not described
- Success criteria are observable (tests pass, endpoint responds)
- No "activity log" or "alternatives considered" equivalents

### 6. Verbosity vs. Quality

The research presents a nuanced picture:

**More detail helps -- up to a point:**
- Springer study: quality improved progressively from basic requirements -> basic design -> detailed design specification
- But the improvements came from *specific* additions: I/O format, exceptions, algorithmic details
- Generic context ("here is the problem background") did not contribute to measurable quality improvement

**More context actively hurts after a threshold:**
- Context rot research: every model tested showed degradation as context grew
- Lost-in-the-middle: information in middle positions suffers 30%+ accuracy drops
- For a 5-WP orchestration run with a 4,900-token design.md, the executor sees the design doc content ~5 times across the full run (once per WP). If the executor only needs the Architecture section for ambiguity resolution, it is receiving ~1,400 tokens of zero/low-signal design.md content each time.

**The "small focused context" principle:**
- Multiple sources recommend small, focused context over large comprehensive context
- Anthropic's own guidance: organize into distinct sections with strong cues
- Addy Osmani: "Minimal does not mean short -- include necessary detail, omit archaeology"

## Recommendations

### R1: Remove Activity Log from WP format (High confidence)

**What:** Remove `## Activity Log` from the WP template in `mine.draft-plan`. Stop injecting it into executor/reviewer prompts.

**Why:** Zero consumers read it. It is pure noise -- appended by spec-helper on every lane move, read by nothing. Across a 5-WP run, this wastes ~1,000 chars of executor context.

**Preserving the data:** `spec-helper wp-move` can continue appending to the file on disk for human traceability, but the content should be excluded when injecting WP content into prompts. Two approaches:
- (A) Stop generating the section in `mine.draft-plan`, have `spec-helper` append to a different section or file
- (B) Have the orchestrator strip `## Activity Log` before injecting WP content into prompts

Option (B) is simpler and preserves backward compatibility with existing WP files.

### R2: Make `plan_section` optional or remove it (High confidence)

**What:** Stop requiring `plan_section` in WP frontmatter. The orchestrator calls it "decorative."

**Why:** No consumer uses it for routing, ordering, or verification. spec-helper validates it as a warning only. It adds ~30 chars of frontmatter noise per WP and a validation step that occasionally produces false warnings when design.md headings are refactored.

**Migration:** Make it optional in `mine.draft-plan` (generate only if the mapping is unambiguous). Remove spec-helper validation for it, or downgrade to info-level.

### R3: Inject a design.md *extract* instead of the full document (High confidence)

**What:** When building the executor prompt, inject only the Architecture and Non-Goals sections of design.md, not the full document. Similarly for the spec reviewer.

**Why:** The executor prompt explicitly says to consult "the design doc's Architecture section" on ambiguity. Problem, Alternatives Considered, Open Questions (already resolved), Impact (stale file lists), and header metadata (Date, Research) are not consumed by the executor or spec reviewer.

For a typical design.md, this would reduce injected context from ~3,500 tokens to ~2,000 tokens -- a 40% reduction in design.md context with zero signal loss.

**Implementation:** In the orchestrator's Step 4 (executor launch) and Step 5 (spec reviewer launch), extract the Architecture and Non-Goals sections by heading before injecting. The full design.md continues to exist on disk and is read by mine.plan-review and mine.design, which do need the full document.

**Caveat:** The spec reviewer prompt says "use [design doc] to verify the spirit of the implementation" and "Is the implementation consistent with the architectural decisions in the design doc?" Both of these point to the Architecture section specifically. If a future spec reviewer checklist item needs Alternatives Considered or Impact, the extract can be expanded.

### R4: Strip `depends_on` from executor-injected content (Medium confidence)

**What:** When injecting WP content into the executor prompt, strip the `depends_on` frontmatter field.

**Why:** The orchestrator executes WPs sequentially by file order, not by dependency graph. The executor never reads `depends_on`. The field is useful for plan review (checking reference integrity) but not for execution.

**Keep it in the file:** `depends_on` remains in the WP file for `spec-helper wp-validate` and `mine.plan-review`. It is just not injected into the executor prompt.

### R5: Consider a structured data format for high-signal WP sections (Medium confidence, needs prototyping)

**What:** Research suggests I/O format specification (44% of successful code generation optimizations) and post-conditions (23%) are the most impactful prompt elements. The current WP format uses free-form markdown for these. Consider structured formats for the highest-signal sections.

**Example -- Objectives as structured assertions:**
```yaml
objectives:
  - "UserRepository.find_by_email() returns None for unknown users"
  - "UserRepository.find_by_email() raises UserError for database failures"
  - "test_find_by_email_unknown passes"
  - "test_find_by_email_db_error passes"
```

vs. the current prose:
```markdown
## Objectives & Success Criteria
The `UserRepository.find_by_email()` method returns `None` for unknown users
and raises `UserError` for database failures. Success: test_find_by_email_unknown
and test_find_by_email_db_error both pass.
```

**Why this might help:** Structured formats give the model "strong cues about which info is which" (Anthropic). They also align with the research finding that I/O format specification is the second most impactful optimization.

**Why this needs prototyping:** The current prose format works. Changing it has risk. The improvement is speculative -- the research was on direct code generation prompts, not multi-step orchestrated workflows. Recommend A/B testing on 2-3 WP runs before committing.

### R6: Add explicit file paths to Subtasks where missing (Medium confidence)

**What:** The `mine.draft-plan` SKILL.md already says subtasks should "Reference actual file paths" (line 186). But WPs for this repo (which has no code) often reference paths like "SKILL.md lines 213-252" rather than absolute paths. For repos with actual code, ensure subtasks contain resolved file paths, not descriptions.

**Why:** Research finding: "If you don't explicitly ask for a breakdown of work, the agent will charge ahead -- sometimes making sweeping and incorrect changes." Explicit file paths are the strongest constraint on scope. The `mine.draft-plan` Phase 2 already does codebase exploration to find exact file paths -- ensure they propagate into subtask text.

### R7: Consider removing `## Alternatives Considered` from design.md executor context (Low confidence)

**What:** Part of R3 (extract instead of full doc). Alternatives Considered is not consumed by any executor or reviewer prompt by name.

**Why this is lower confidence:** While no consumer references it by name, the section provides decision rationale that could help an executor understand *why* a particular approach was chosen. If an executor encounters ambiguity and the Architecture section doesn't resolve it, knowing why alternatives were rejected could prevent re-inventing a rejected approach. However, this scenario appears rare in practice -- the Subtasks section is usually specific enough to prevent this.

## Token Budget Summary

**Current executor prompt (typical):**

| Component | Tokens |
|-----------|--------|
| WP content (full) | ~900 |
| design.md (full) | ~3,500 |
| implementer-prompt.md | ~2,900 |
| tdd.md | ~900 |
| Test command + visual status | ~50 |
| **Total** | **~8,250** |

**After recommendations R1-R4:**

| Component | Tokens | Change |
|-----------|--------|--------|
| WP content (stripped) | ~700 | -200 (Activity Log, plan_section, depends_on) |
| design.md (extract) | ~2,100 | -1,400 (only Architecture + Non-Goals) |
| implementer-prompt.md | ~2,900 | unchanged |
| tdd.md | ~900 | unchanged |
| Test command + visual status | ~50 | unchanged |
| **Total** | **~6,650** | **-1,600 (~19% reduction)** |

The 19% reduction removes only zero-signal and low-signal content. No high-signal content is removed.

For the spec reviewer, the reduction is similar (~19%). For the visual reviewer, there is no change (it already receives only the Visual Verification table and screenshots).

## Missing Information

Things the agents might benefit from that the current format does not provide:

1. **Diff context for retries** -- On WARN/FAIL retries, the executor gets reviewer feedback but not a diff of what it changed in the prior attempt. The current `## Previous review feedback` section describes problems but not the executor's prior approach. Adding a compact diff (or the executor's "Files changed" list from the prior attempt) could prevent repeating the same mistakes.

2. **Cross-WP state** -- Each executor gets one WP in isolation. It does not know what prior WPs accomplished or what files they changed. For WPs with `depends_on`, knowing the prior WP's output (at least the file list) could help the executor understand the current state. This is a design tension: cross-WP context helps integration but increases context size.

3. **Negative examples** -- Review Guidance says what to check, but rarely includes examples of what a violation looks like. Research shows "examples" are the 9th most impactful optimization (24% application rate). Adding 1-2 negative examples per Review Guidance item could improve reviewer accuracy.

## Open Questions

- [ ] **Should the implementer-prompt.md be shortened?** At ~2,900 tokens, it is the second-largest component of the executor prompt. Much of it is behavioral instruction (deviation classification, self-review checklist, visual verification protocol) that may not apply to every WP. Could sections be conditionally included?
- [ ] **Is the full tdd.md needed for every WP?** At ~900 tokens, it provides the TDD cycle, test discovery, boundary patterns, and failure mode handling. For WPs that modify prompt files (no code), this is dead weight. Could it be conditionally included based on WP content?
- [ ] **Should design.md extraction be done by the orchestrator (prompt-time) or by mine.draft-plan (generation-time)?** Prompt-time extraction is simpler and more adaptive. Generation-time extraction could produce a per-WP "design context" that is more targeted.
- [ ] **Would A/B testing R5 (structured objectives) show measurable improvement?** The research supports it, but the caliper workflow adds layers (reviewer, retry) that may compensate for any format-level improvements.
- [ ] **What is the actual false positive rate of the spec reviewer?** If the spec reviewer is flagging issues that turn out to be non-issues (leading to WARN retries that produce the same code), the WP format may be providing too much ambiguous guidance. This would be a different kind of format problem than noise.

## Recommendation

The format is fundamentally sound -- the high-signal sections (Objectives, Subtasks, Test Strategy, Review Guidance) map well to what research says LLM agents need. The problems are additive noise, not missing structure.

**Recommended approach: trim the noise, keep the structure.**

Implement R1 (remove Activity Log from prompts), R2 (make plan_section optional), and R3 (design.md extract) first. These are low-risk, high-confidence changes that remove ~1,600 tokens of zero/low-signal content per executor invocation. They require changes to mine.orchestrate's Step 4/5 prompt construction, mine.draft-plan's WP template, and potentially spec-helper's activity log behavior.

R4 (strip depends_on from executor context) is low-risk and can go with the first batch.

R5 (structured objectives) and R6 (explicit file paths) should be prototyped on a real orchestration run before committing. The research supports them but the improvement may be marginal given the existing review/retry loop.

Before implementing, consider running `/mine.challenge` on this brief to surface any gaps.

### Suggested next steps

1. Write a design doc via `/mine.design` for R1-R4 (the high-confidence changes)
2. Prototype R5 (structured objectives) on one WP in a real orchestration run and compare executor quality
3. Instrument one orchestration run to measure: how often does the executor consult design.md content? How often does the spec reviewer reference Alternatives Considered? This would validate or refute the "dead weight" classification.

## Sources

- [Guidelines to Prompt LLMs for Code Generation: An Empirical Characterization](https://arxiv.org/html/2601.13118v1)
- [Context Rot: Why LLMs Degrade as Context Grows](https://www.morphllm.com/context-rot)
- [Prompt Length vs. Context Window: The Real Limits Behind LLM Performance](https://dev.to/superorange0707/prompt-length-vs-context-window-the-real-limits-behind-llm-performance-3h20)
- [Context Length Alone Hurts LLM Performance Despite Perfect Retrieval](https://arxiv.org/html/2510.05381v1)
- [How to Write a Good Spec for AI Agents -- Addy Osmani](https://addyosmani.com/blog/good-spec/)
- [Investigating the Relationship Between Quality and Prompt Specificity in Source Code Generation](https://link.springer.com/chapter/10.1007/978-3-031-82606-1_7)
- [Does Prompt Formatting Have Any Impact on LLM Performance?](https://arxiv.org/html/2411.10541v1)
- [Code Roulette: How Prompt Variability Affects LLM Code Generation](https://arxiv.org/html/2506.10204v2)
- [Structured AI Coding with Task Context](https://eclipsesource.com/blogs/2025/07/01/structure-ai-coding-with-task-context/)
- [GitHub Blog: Spec-driven development with AI](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/)
- [My LLM Coding Workflow Going into 2026 -- Addy Osmani](https://medium.com/@addyosmani/my-llm-coding-workflow-going-into-2026-52fe1681325e)
- [Lost in the Middle: How Language Models Use Long Contexts](https://arize.com/blog/lost-in-the-middle-how-language-models-use-long-contexts-paper-reading/)
- [OpenHands Software Agent SDK](https://arxiv.org/html/2511.03690v1)
- [Claude Prompting Best Practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
