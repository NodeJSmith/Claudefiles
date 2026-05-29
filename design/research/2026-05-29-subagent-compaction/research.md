---
topic: "Detecting and handling subagent compaction in orchestration"
date: 2026-05-29
status: Draft
---

# Prior Art: Detecting and Handling Subagent Compaction

## The Problem

When an orchestrator spawns subagents to execute individual tasks (T01, T02, etc.), each subagent works in its own context window. If a task is too complex, the subagent's context fills up and auto-compaction fires, silently summarizing earlier work. This can degrade reasoning quality, lose file references, or signal that the task decomposition is too coarse. Today there's no way to know when this happens, how often, or which tasks trigger it.

The broader question is observability: can we detect compaction events in subagents, and what should the system do about them?

## How We Do It Today

The orchestration skill (`mine.orchestrate`) dispatches Sonnet subagents per task file with full design context. Compaction events are recorded in session JSONL as `compact_boundary` entries with pre/post token counts, but `cm-ingest-token-data` doesn't extract them. The `context-tier.sh` hook monitors the parent's context usage but has no visibility into subagent windows. The `mine.pre-compact` skill helps steer manual compaction but provides no post-compaction analytics. Subagent conversations are embedded inline in the parent's JSONL, so their compaction events (if any) would appear there, but nobody's looking.

## Patterns Found

### Pattern 1: Layered Compaction Pipeline

**Used by**: Claude Code, Hermes Agent (planned)
**How it works**: Five layers of increasing cost/lossiness run before every model call: budget reduction (cap tool output size), snip (discard oldest messages), microcompact (cache-aware tool_result editing), context collapse (create collapsed view), auto-compact (LLM summarization). Each layer exhausts cheaper options before escalating.

**Strengths**: Graceful degradation. Cache-aware layer reduces API costs. Preserves maximum information at minimum cost.
**Weaknesses**: Reactive, not proactive. Race conditions when multiple subagent results arrive simultaneously. Can't compress system prompts, leading to death spirals when they're large (documented in Claude Code issue #24677).
**Example**: https://arxiv.org/html/2604.14228v1

### Pattern 2: Context Folding (Branch and Return)

**Used by**: Context-Folding (Sun et al. 2025), AgentFold, FoldAct
**How it works**: Agents create temporary "branches" for subtasks. When the branch completes, intermediate steps are discarded and only a summary survives in the parent context. This maps directly to parent-subagent patterns: the subagent's execution IS the branch, and the returned result IS the fold. AgentFold demonstrated that proactive folding (fold when the subtask completes) significantly outperforms reactive (fold when the window fills).

**Strengths**: Natural fit for hierarchical agents. Parent context grows by summary size, not subtask complexity. 10x smaller active context in benchmarks.
**Weaknesses**: Summary quality determines information survival. The agent must choose when to branch vs. work inline.
**Example**: https://arxiv.org/abs/2510.11967

### Pattern 3: Structurally Lossless Trimming

**Used by**: CMV (Contextual Memory Virtualisation), Claude Code (budget reduction layer)
**How it works**: Remove content that exists in the environment (files on disk, tool outputs that can be re-read) and leave a pointer. Zero information loss for anything re-readable. CMV extends this with a DAG model for version-controlled context state.

**Strengths**: Zero information loss for environmental content. Very high compression ratios for tool-heavy sessions. Reversible.
**Weaknesses**: Only works for re-readable content. Conversation reasoning and decisions can't be re-read. Re-reading costs API calls.
**Example**: https://arxiv.org/pdf/2602.22402

### Pattern 4: Discrete Context Isolation

**Used by**: Manus, Claude Code (Task tool), OpenHands
**How it works**: Each subagent gets a fresh context window with only the information it needs. Parent passes task + relevant paths; subagent works in isolation. Manus principle: "Share memory by communicating, don't communicate by sharing memory." This is what we already do.

**Strengths**: Prevents context pollution. Subagents use full window for their task. Failed subagents don't corrupt parent context.
**Weaknesses**: Parent must craft sufficient task descriptions. Subagents can't access cross-task context unless explicitly passed.
**Example**: https://www.philschmid.de/context-engineering-part-2

### Pattern 5: Pre-Rot Threshold Monitoring

**Used by**: Production agent systems following Phil Schmid's guidance
**How it works**: Performance degrades before the hard context limit. For 1M windows, degradation may start around 256k. Systems monitor token usage and trigger compaction or task splitting before hitting this "pre-rot" threshold, rather than waiting for overflow. A system might use 50% for pre-rot warnings, 80% for condensation, and 95% for emergency circuit breaker.

**Strengths**: Maintains reasoning quality throughout. Proactive, not reactive. Combinable with any compaction strategy.
**Weaknesses**: Pre-rot threshold is model-specific and hard to calibrate. Research is limited. Overly conservative thresholds waste context.
**Example**: https://www.philschmid.de/context-engineering-part-2

### Pattern 6: Result Size Capping

**Used by**: Claude Code (suggested fix in issue #23463)
**How it works**: Cap subagent results at a max token size. If exceeded, write full result to a temp file, return summary + path. Prevents N subagents returning large results simultaneously from overflowing the parent.

**Strengths**: Prevents the most common overflow scenario. Full results preserved on disk. Simple to implement.
**Weaknesses**: Summary must be good enough for the parent to decide whether to read more.
**Example**: https://github.com/anthropics/claude-code/issues/23463

## Anti-Patterns

- **Reactive-only compaction**: Waiting until 95% capacity, then scrambling. Multiple concurrent results can overflow before compaction fires. (Issues #11280, #23463)
- **Unbounded parallel agent results**: N subagents completing simultaneously inject N large results into the parent, causing session death. (Issue #25714)
- **Compaction death spirals**: When system prompts are large relative to the window, compaction frees almost nothing and re-triggers immediately. 6 compactions in 3.5 minutes documented. (Issue #24677)
- **Lossy compaction destroying file references**: After compaction, the parent loses track of temp files written by subagents. Files exist on disk but the parent doesn't know about them. (Issue #23821)

## Emerging Trends

- **Context engineering as a discipline**: Multiple independent authors converged on "most agent errors are context errors, not model errors." The focus shifts from prompt engineering to context engineering.
- **Proactive over reactive**: The research trajectory (Context-Folding -> AgentFold -> FoldAct) shows a clear trend toward managing context before it fills, not after.
- **Version-controlled context**: CMV's DAG model treats context like git branches. Enables sharing compressed context across parallel sessions and rollback.

## Relevance to Us

We already use Pattern 4 (discrete context isolation) -- each task gets a fresh Sonnet subagent. This is the strongest available pattern and we're using it correctly. The question is whether our tasks are sized right for the window.

Pattern 5 (pre-rot monitoring) is directly applicable. Sonnet's 200K window may degrade before it fills. If we could observe compaction events via `compact_boundary` JSONL entries, we'd have empirical data on which tasks hit the wall.

Pattern 2 (context folding) describes what we already do conceptually -- the subagent executes a branch, returns a summary. The insight is that this is already the right architecture; the gap is observability, not mechanism.

Pattern 6 (result size capping) is relevant for the parent orchestrator, which accumulates results across all tasks. We should monitor whether the orchestrator itself compacts.

The anti-patterns are worth noting: we launch reviewers in parallel (3 agents), which could cause result-size pressure on the parent, and our system prompts are large (Claudefiles loads many rule files).

## Recommendation

The mechanism is already right (Pattern 4). The gap is observability. Two concrete next steps:

1. **Extract compaction events from JSONL**: Extend `cm-ingest-token-data` to parse `compact_boundary` entries and correlate them with subagent spans. This gives historical data: which tasks triggered compaction, how much context was lost, and how often.

2. **Post-orchestration compaction report**: After `mine.orchestrate` completes, scan the session JSONL for compaction events that occurred during task execution. Report which tasks (if any) compacted and their pre/post token counts. This is simpler and more immediately useful than the full ingest pipeline change.

If compaction turns out to be common, the response is task decomposition (split large tasks), not mechanism changes. The compaction data tells us *where* to split.

## Sources

### Reference implementations
- https://arxiv.org/html/2604.14228v1 -- Claude Code five-layer compaction pipeline analysis
- https://www.openhands.dev/blog/openhands-context-condensensation-for-more-efficient-ai-agents -- OpenHands LLM-based condensation

### Research papers
- https://arxiv.org/abs/2510.11967 -- Context-Folding: branch/return actions for sub-trajectories
- https://arxiv.org/abs/2510.24699 -- AgentFold: proactive context management for web agents
- https://arxiv.org/abs/2512.22733 -- FoldAct: stable context folding for search agents
- https://arxiv.org/pdf/2602.22402 -- CMV: version-controlled context as DAG
- https://arxiv.org/abs/2601.07190 -- ACON: failure-driven context compression
- https://arxiv.org/abs/2603.07670 -- Memory for Autonomous LLM Agents survey

### Documentation
- https://platform.claude.com/docs/en/build-with-claude/compaction -- Claude Code compaction docs
- https://platform.claude.com/cookbook/tool-use-automatic-context-compaction -- Compaction cookbook

### Blog posts & practitioner guides
- https://www.philschmid.de/context-engineering-part-2 -- Pre-rot thresholds, discrete isolation, Manus principle
- https://simonwillison.net/2026/Feb/23/agentic-engineering-patterns/ -- Agentic engineering patterns
- https://harrisonsec.com/blog/claude-code-context-engineering-compression-pipeline/ -- Five-layer pipeline deep dive
- https://dev.to/crabtalk/context-compaction-in-agent-frameworks-4ckk -- Compaction tradeoffs with concrete data
- https://www.morphllm.com/cursor-context-window -- Effective vs nominal context analysis

### Claude Code issues
- https://github.com/anthropics/claude-code/issues/23463 -- Subagent results overflow parent context
- https://github.com/anthropics/claude-code/issues/11280 -- Compaction triggers too late
- https://github.com/anthropics/claude-code/issues/23821 -- File references lost after compaction
- https://github.com/anthropics/claude-code/issues/24677 -- Compaction death spiral
- https://github.com/anthropics/claude-code/issues/25714 -- Unbounded parallel agent results
- https://github.com/anthropics/claude-code/issues/42590 -- Over-aggressive compaction on 1M windows
