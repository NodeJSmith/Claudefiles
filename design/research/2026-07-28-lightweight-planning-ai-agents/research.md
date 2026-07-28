---
topic: "lightweight-planning-ai-coding-agents"
date: 2026-07-28
status: Draft
---

# Prior Art: Lightweight Planning Workflows for AI Coding Agents

## The Problem

AI coding agents produce measurably better results when given structured task files vs working from a conversational prompt alone (+40pp success rate in the "From Plan to Action" benchmark, arXiv 2604.12147). But the process of *creating* those task files — discovery interviews, researcher dispatch, design docs, comb reviews, sign-off gates — is heavyweight ceremony that only earns its keep on genuinely complex, ambiguous features. The result: teams either run the full pipeline (ceremony tax on moderate tasks) or skip planning entirely (execution quality drops). No tool in the surveyed space has formally solved graduated ceremony — everyone offers either a binary mode switch or leaves the decision to unaudited model judgment.

## How We Do It Today

Two paths via `mine-build`: **Simple** (1-3 files, direct implementation, single code review, no task files) or **Complex** (full 6-phase caliper: define → plan → orchestrate, producing design.md, context.md, and structured T*.md task files with FR/AC traceability, spec/integration reviews, and CFL lifecycle tracking). The gap is the moderate task: multiple files, real design decisions, but well-understood territory where a formal design doc and researcher dispatch don't earn their keep. The existing `context.md` pattern already captures persistent project context once — a lever the lightweight path could use to shrink per-task ceremony.

## Patterns Found

### Pattern 1: Binary Mode Switch (light conversational vs heavy structured)

**Used by**: AWS Kiro (Vibe vs Spec), Cursor (Agent vs Plan mode), Aider (chat vs architect mode)

**How it works**: Exactly two modes — light (direct execution, no plan artifact) and heavy (fixed pipeline producing durable artifacts). The user or a simple heuristic picks one per task. Kiro is the most deliberate example, explicitly naming both modes. Cursor blurs the switch by auto-suggesting the heavier mode when it detects multi-step complexity.

**Strengths**: Simple mental model. Cheap to implement. Matches how most real work splits (either "I know exactly what to change" or "I need to think first").

**Weaknesses**: No native handling for mid-size tasks. Users either over-invoke the heavy pipeline or skip it entirely. None of the surveyed tools publish a rule for where the line sits.

**Example**: https://builder.aws.com/content/3AX80b0O3lZlJLrimxmtumlH7fJ/steering-kiro-best-practices-pitfalls-and-when-to-use-something-else

### Pattern 2: Model-Judged Escalation (agent decides ceremony from request text)

**Used by**: Claude Code (`TodoWrite`), Cursor (Plan Mode auto-suggest)

**How it works**: The system prompt tells the model to judge task complexity and decide whether to produce a structured task list. Claude Code instructs proactive `TodoWrite` for "non-trivial" work and skip for tasks under ~3 trivial steps. No schema or threshold — qualitative language interpreted by the model at runtime.

**Strengths**: Zero user friction. Small tasks never pay ceremony tax.

**Weaknesses**: Not auditable or reproducible. The same task phrased differently can trigger different ceremony. The "From Plan to Action" paper shows agents rarely produce explicit plan artifacts without deliberate structural prompting — left to model judgment, planning is under-invoked.

**Example**: https://github.com/anthropics/claude-code/issues/6968

### Pattern 3: Full Pipeline With Fixed Phases (no graduation)

**Used by**: GitHub Spec Kit, this repo's own 6-phase workflow

**How it works**: A named sequence of phases, each producing a durable artifact and gating the next. The pipeline is a complete methodology for a feature, not calibrated per-task. Smaller changes either run the full pipeline or bypass structured workflow entirely.

**Strengths**: Maximizes reviewability and traceability. Best fit for large, ambiguous, multi-session features.

**Weaknesses**: No native lighter tier. No tool in the space documents an official "small task" shortcut. Teams report skipping the tool for small tasks — the "ceremony too heavy so people bypass structure entirely" failure.

**Example**: https://github.com/github/spec-kit

### Pattern 4: Typed/Structured Task Objects Instead of Prose Checklists

**Used by**: Augment Code (Tasklist), OpenHands/Devin-style DAG execution

**How it works**: Tasks stored as structured objects (id, lifecycle state, parent/child relationships, timestamps) rather than markdown checkboxes. Dependencies expressed as a DAG. State transitions enforced, preventing an agent from silently marking something done without producing the expected artifact.

**Strengths**: The structure itself prevents drift, not just the existence of a list. Enables mid-run intervention and post-hoc auditing.

**Weaknesses**: Requires tooling investment beyond "write a markdown file." May be overkill for a deliberately minimal tier.

**Example**: https://www.augmentcode.com/blog/how-we-built-tasklist

### Pattern 5: Persistent Context File + Ephemeral Per-Task Plan

**Used by**: AWS Kiro (steering files + spec pipeline), OpenAI Codex CLI (AGENTS.md + per-session handoff files)

**How it works**: Splits planning inputs into two lifetimes. A long-lived file captures conventions, architecture, and constraints once, loaded into every task's context. A short-lived artifact captures the plan for this specific change. The durable context makes per-task artifacts shorter — they don't need to re-derive architectural context, only the delta.

**Strengths**: Reduces ceremony for small tasks because a large fraction of what a full design doc normally establishes is already available. Directly attacks why heavyweight processes exist — most of their bulk is re-establishing context a persistent file could hold once.

**Weaknesses**: Only helps with context-gathering cost, not decision-making cost. Requires the persistent file to be kept current.

**Example**: https://developers.openai.com/codex/learn/best-practices

## Anti-Patterns

- **Planning-in-band with execution** — agents that reason about *what* to do and *do it* in the same pass make execution decisions before analysis is complete, causing backtracking and orphaned code. Empirically confirmed by arXiv 2604.12147. (https://dev.to/varun_pratapbhardwaj_b13/separation-of-planning-and-execution-the-key-pattern-for-reliable-ai-coding-agents-5b53)
- **Letting the execution agent decompose itself** — quality degrades as a cliff, not a slope. Self-decomposition by the same agent that will execute is how teams stumble past that cliff. External decomposition (a separate lighter planning pass) before handoff prevents it. (https://voicetree.io/blog/complexity-threshold)
- **Vague, unauditable ceremony triggers** — "complex" / "non-trivial" in system prompts works in aggregate but isn't reproducible: identical work phrased differently gets different ceremony, with no artifact showing why planning was skipped until quality has already suffered.

## Emerging Trends

- **Structured/typed task representations displacing markdown checklists** — Augment Code's typed Tasklist is aimed at the "black box" problem. If task files are machine-consumed by an orchestrator, this is the direction the field is moving.
- **"Steering"/durable-context files shrinking per-task ceremony** — Kiro and Codex CLI are converging on persistent, always-loaded context files that reduce how much any individual plan needs to re-establish.

## Relevance to Us

We already have Pattern 5's infrastructure: `context.md` is a persistent context file loaded by every task. The full caliper chain (mine-define → mine-plan → mine-orchestrate) is Pattern 3 — a fixed pipeline with no graduation. The gap is that moderate tasks bypass it entirely (Pattern 1's failure mode), falling back to mine-build's Simple path which produces no task files at all.

The evidence strongly supports keeping task files (Pattern 4 + arXiv data). The question is not whether to produce them, but how to produce them with less ceremony. The "From Plan to Action" paper's +40pp result and the "complexity threshold" cliff argument both say a *separate* planning pass — even a minimal one — earns its keep on anything past trivially simple.

What's encouraging: the existing task file format (T*.md with frontmatter, Target Files, Prompt, Verify) and the orchestrator's consumption of them don't need to change. A lighter planning skill can write the same format with less ceremony — skip design.md, skip researcher dispatch, skip comb review, skip CFL tracking. The task files themselves are the load-bearing structure; the phases around creating them are where ceremony can be cut.

## Recommendation

No tool in the surveyed space has formally solved graduated ceremony — this would be novel. But the components are well-validated:

1. **Keep task files as the output format** — the evidence for structured task artifacts improving execution quality is strong. Don't invent a new lighter format; write the same T*.md the orchestrator already consumes.
2. **Skip the design doc** — for moderate tasks, the design decisions are few enough to capture directly in context.md + task file prompts rather than a separate design.md.
3. **Skip researcher dispatch and comb review** — inline codebase exploration (a quick read, not a subagent) is sufficient for well-understood territory.
4. **Consider graduation as a spectrum, not a third binary mode** — the number of task files and depth of each Prompt section can scale with task size without changing the format or the orchestrator.
5. **Keep the separation of planning and execution** — even at the lightest tier, the planner should not also be the executor. The planning pass writes task files; the executor (or orchestrator) consumes them.

## Sources

### Reference implementations
- https://github.com/github/spec-kit — Full spec-to-implementation pipeline (closest analog to existing workflow)
- https://docs.roocode.com/features/boomerang-tasks — Recursive task decomposition via orchestrator mode
- https://github.com/shinpr/codex-workflows — Community multi-agent workflow layered on Codex CLI

### Blog posts & writeups
- https://crabtalk.ai/blog/plans-vs-tasks-agent-design (mirror: https://openwalrus.xyz/blog/plans-vs-tasks-agent-design) — Cross-tool survey of planning in 5 production coding agents
- https://www.augmentcode.com/blog/how-we-built-tasklist — Augment Code's typed task object design
- https://spring.io/blog/2026/01/20/spring-ai-agentic-patterns-3-todowrite/ — Analysis of Claude Code's TodoWrite as lightweight task tracking
- https://dev.to/varun_pratapbhardwaj_b13/separation-of-planning-and-execution-the-key-pattern-for-reliable-ai-coding-agents-5b53 — Separation of planning and execution pattern
- https://voicetree.io/blog/complexity-threshold — Complexity threshold / quality cliff argument

### Documentation & standards
- https://claudelog.com/mechanics/plan-mode/ — Claude Code Plan Mode mechanics
- https://cursor.com/blog/plan-mode — Cursor Plan Mode
- https://aider.chat/docs/usage/modes.html — Aider Architect Mode
- https://aws.amazon.com/documentation-overview/kiro/ — AWS Kiro Vibe/Spec modes
- https://developers.openai.com/codex/learn/best-practices — Codex CLI best practices / AGENTS.md pattern

### Research papers
- https://arxiv.org/html/2604.12147v1 — "From Plan to Action: How Well Do Agents Follow the Plan?" (+40pp success with explicit plans)
- https://arxiv.org/pdf/2606.22678 — RigorBench: engineering process discipline benchmark

### Community / issues
- https://github.com/anthropics/claude-code/issues/6968 — Claude Code TodoWrite system prompt trigger language
