# Brief: Existing Skill Improvements from pstack Patterns

Source: Claude Code Digest May 27 + Jun 1, 2026  
Branch: pstack-review  
Status: Ready for pickup

---

## Overview

Three patterns from pstack that should improve existing local skills rather than become standalone new ones. Each maps to a specific gap in something we already have.

---

## 1. `code-judo-review-lens` → Improve `mine.review`

**What pstack does:** Adds a "code judo" review dimension — actively hunting for structural reframings that preserve behavior while making implementation dramatically simpler and smaller. Specific blockers: a file growing from under 1k to over 1k lines without justification; ad-hoc conditionals inserted into unrelated flows; duplicated helpers when a canonical home exists. Reviewers are told to be ambitious, not satisfied with local cleanup.

**The gap:** The local three-reviewer model (correctness, integration, readability) identifies problems but doesn't have the specific posture of "assume a structural simplification move is always available, find it." The wtf-reviewer catches confusing code; the code-judo lens asks "what if this file or abstraction just... didn't need to exist?"

**What to do:**
- Add a fourth reviewer option to `mine.review`: the "code judo" lens
- Or add it as a mandatory pass in `mine.orchestrate`'s post-execution pipeline (Phase 3), where it has full diff context
- Agent prompt: "Assume a structural simplification exists. Look for: files that crossed 1k lines in this diff, ad-hoc conditionals inserted into unrelated flows, helpers duplicated when a canonical home exists. Be ambitious — hunt for moves that delete whole layers, not just rearrange them."
- This fits naturally alongside the existing `lazy-checker` and `llm-checker` agents

**Effort:** Low — one new agent invocation with a sharp prompt. The infrastructure is there.

---

## 2. `usage-first-design` → Improve `mine.define`

**What pstack does:** When designing APIs, libraries, or modules: write the caller's README-style usage and two or three realistic call sites first, then derive the type sketch from that usage. The usage is the spec; when types and usage diverge, reconcile types to usage — not the reverse.

**The gap:** `mine.define` produces design documents through discovery interviews and codebase analysis. It does not enforce writing the caller's perspective before defining types. The result is sometimes designs that are internally consistent but ergonomically awkward at the call site.

**What to do:**
- Add a "usage-first" gate to `mine.define` when the artifact being designed is an API, module, or public interface (as opposed to a workflow or feature)
- After the discovery interview, before writing the design doc, ask: "Write 2–3 realistic call sites first. What does the caller's code look like?"
- The design doc's interface section should then be derived from those call sites, not the reverse
- Add this as a conditional step in `skills/mine.define/SKILL.md`: if the design involves an API or module interface, insert a "caller-perspective" phase before the type definitions section

**Effort:** Low — a few lines added to the define SKILL.md for the conditional phase.

---

## 3. `subagent-lever-discipline` → Improve `mine.orchestrate` and `agents.md`

**What pstack does:** When fanning work out to subagents, encode the recipe, verification contract, and do-not-touch fences in a shared skill file that all delegates read — rather than re-explaining per prompt. Keep the skill outside the delegates' write scope so they can't quietly edit the contract. Harden the skill immediately when a delegate drifts, then re-dispatch.

**The gap:** The local `agents.md` covers parallel executor isolation (worktrees) and agent routing but says nothing about coordination discipline for multi-agent work. When `mine.orchestrate` fans out parallel executors, each agent gets a self-contained prompt — if two executors solve the same sub-problem differently, there's no shared contract to catch the drift.

**What to do:**

**Option A (light):** Add a section to `agents.md` under "Parallel Executor Isolation" called "Shared Contract Files" — when orchestrating 3+ executors on a complex task, write a `CONTRACT.md` to the worktree root with: the recipe (what done looks like), verification steps (what passes), and do-not-touch fences (files executors must not modify). Each executor prompt references this file explicitly.

**Option B (heavier):** Add a Phase 0 to `mine.orchestrate` for large-task runs that generates a `CONTRACT.md` before dispatching any executors. The post-execution pipeline checks executors against the contract rather than just running code review.

**Recommendation:** Option A first — it's a rule addition to `agents.md` and a prompt note in `mine.orchestrate`. If drift problems surface in practice, expand to Option B.

**Effort:** Low (Option A) to medium (Option B).

---

## Summary Table

| Pattern | Target | Effort | Impact |
|---|---|---|---|
| code-judo-review-lens | `mine.review` or orchestrate pipeline | Low | Medium-high |
| usage-first-design | `mine.define` | Low | Medium |
| subagent-lever-discipline | `agents.md` + `mine.orchestrate` | Low–medium | Medium |
