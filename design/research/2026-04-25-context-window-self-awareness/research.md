---
topic: "LLM agent context window self-awareness"
date: 2026-04-25
status: Draft
---

# Prior Art: LLM Agent Context Window Self-Awareness

## The Problem

LLM coding agents (Claude Code, Cursor, Aider, etc.) have no visibility into their own context window consumption. Without concrete data, they fabricate estimates — Claude undershoots actual usage by ~35% across 230+ sessions (Issue #26340). This manifests as both premature urgency ("context is building up" at 35% of a 1M window) and missed exhaustion (running out mid-task without warning).

The BATS paper (arXiv 2511.17006) provides the strongest evidence this matters: budget-unaware agents hit a performance ceiling regardless of how much budget they're given. Budget-aware agents achieve 31.3% lower cost while maintaining accuracy.

## How We Do It Today

The `starship-claude` status line script already computes everything — `CLAUDE_PERCENT_RAW`, token counts, cache stats, context size — from the JSON payload Claude Code pipes to it. But this data flows outward to the terminal only. Claude (the model) never sees it. A checked-in rule (`rules/common/performance.md`) tells Claude to never claim context awareness since it doesn't have it.

## Patterns Found

### Pattern 1: Per-Turn Budget Status Injection

**Used by**: BATS paper (Budget Tracker), Claude Code Issue #26340 proposal, Agno framework
**How it works**: After each turn, a status block is appended to the agent's context: `[Context: 142,387 / 200,000 tokens (71.2%)]`. The BATS paper maps budget levels to behavioral tiers — high (>=70% remaining) allows broad exploration, medium (30-70%) requires focused queries, low (10-30%) allows one focused action, critical (<10%) means minimal tool use. The key finding: without this injection, agents cannot utilize additional budget effectively.
**Strengths**: Empirically proven (31.3% cost reduction). Models adapt strategy in real-time.
**Weaknesses**: Adds tokens every turn. Requires the model to actually change behavior based on the data.
**Example**: https://arxiv.org/html/2511.17006v1

### Pattern 2: Out-of-Band Logging with Threshold Alerts

**Used by**: Claude Code Issue #34879 proposal, Agno session metrics
**How it works**: A hook writes token usage to a JSONL file every turn (zero context cost). The agent never sees this data automatically — a threshold trigger injects a single-line alert only at crossings (e.g., 50%, 75%). The log survives compaction since it lives on disk.
**Strengths**: Near-zero ambient token cost. Log survives compaction. Decouples collection from consumption.
**Weaknesses**: Requires hooks to expose token metadata — Claude Code hooks do not currently expose this. Agent must know to read the log.
**Example**: https://github.com/anthropics/claude-code/issues/34879

### Pattern 3: Sidecar File from Status Line (feasible today)

**Used by**: No known implementation — proposed in this conversation
**How it works**: The existing `starship-claude` status line command already receives the full JSON payload with token data on every status update. Adding one line (`printf '%s' "$percent_used" > /tmp/claude-context-latest.txt`) makes the data readable by Claude via the Read tool or by a hook that injects it as additionalContext. No Claude Code changes required.
**Strengths**: Works today with zero infrastructure changes. Leverages existing starship-claude parsing. Can be consumed on-demand (Read) or injected automatically (hook).
**Weaknesses**: Status line updates are controlled by Claude Code — timing may not align with when Claude needs the data. Relies on the status line command being configured and running. The file is a snapshot, not a stream.
**Example**: [no source found — novel combination of existing mechanisms]

### Pattern 4: Observation Masking over Summarization

**Used by**: SWE-agent, JetBrains research (NeurIPS 2025)
**How it works**: Replace old tool outputs with placeholders instead of LLM-summarizing them. JetBrains found masking is 52% cheaper and equally effective — summarization actually makes agents run 13-15% longer by hiding stop signals.
**Strengths**: Simpler, cheaper, equally effective. No model cooperation needed.
**Weaknesses**: Agent has no say in what gets masked. Doesn't address the root self-awareness problem.
**Example**: https://blog.jetbrains.com/research/2025/12/efficient-context-management/

### Pattern 5: Progressive Context Disclosure

**Used by**: Aider (repo map with token budget), Cursor (MCP tool name-only loading — 46.9% token reduction), Claude Code (deferred tool schemas)
**How it works**: Load minimal metadata upfront, full content on demand. Prevent bloat at the source rather than monitoring it at runtime. Complementary to self-awareness — keeps the baseline lean.
**Strengths**: Prevents the problem rather than reacting to it. Significant savings.
**Weaknesses**: Doesn't help when the agent legitimately needs large data loads.
**Example**: https://cursor.com/blog/dynamic-context-discovery

## Anti-Patterns

- **Reading context to measure context**: A user in Issue #34879 had Claude read its entire message history to calculate token usage — consuming significant context to measure context. Self-monitoring must be out-of-band.
- **Hallucinated budget estimates**: Across 230+ sessions, Claude undershoots actual context usage by ~35%. Without data, it fabricates optimistic estimates that lead to mid-task exhaustion. ([Source](https://github.com/anthropics/claude-code/issues/26340))
- **Budget-unaware scaling**: The BATS paper shows giving an unaware agent 100 tool calls produces worse results than a budget-aware agent with 10. More resources without awareness = waste. ([Source](https://arxiv.org/html/2511.17006v1))

## Emerging Trends

Three independent Claude Code issues (#34879, #26340, #10388) converged on the same conclusion: token metadata should be agent-accessible. All were closed as not planned, indicating an unsolved gap. The BATS paper's tiered behavioral policies (not just raw numbers, but actionable guidance per budget level) are being adopted beyond research contexts.

## Relevance to Us

The sidecar file approach (Pattern 3) is uniquely feasible in this setup because `starship-claude` already does all the parsing. The implementation is roughly:

1. Add one `printf` line to `starship-claude` writing context % to a known file
2. A PreToolUse hook reads the file and injects it as `additionalContext` (maybe only at threshold crossings to minimize noise)
3. The rule in `performance.md` shifts from "you can't see context" to "here's how to read your context usage, and here's what to do at each level"

The BATS tiered approach maps well: instead of telling Claude "never mention context" (current rule), tell it what to do at each level — which at 35% of a 1M window is "proceed normally, don't mention context."

Key constraint: Claude Code hooks do NOT receive token metadata in their environment (Issues #34879, #34340 requested this, both closed). The sidecar file from the status line is a workaround for this gap.

## Recommendation

The sidecar file + threshold hook approach is worth building. It's low-effort (one line in starship-claude + a small hook), works today without Claude Code changes, and addresses a documented problem (35% underestimation). The BATS paper provides empirical backing that budget awareness materially improves agent behavior.

However — the current rule change (prohibiting context claims entirely) is the right immediate fix. The sidecar injection is an enhancement that could replace the prohibition with accurate awareness, but it needs testing to confirm the model actually changes behavior based on injected data rather than ignoring it.

**Suggested approach**: Ship the prohibition rule now. Build the sidecar + hook as a follow-up experiment.

## Sources

### Academic research
- https://arxiv.org/html/2511.17006v1 — BATS: budget-aware tool-use with tiered behavioral policies
- https://blog.jetbrains.com/research/2025/12/efficient-context-management/ — JetBrains NeurIPS 2025: observation masking vs summarization

### Claude Code issues & docs
- https://github.com/anthropics/claude-code/issues/34879 — Expose context metrics via hooks (closed: not planned)
- https://github.com/anthropics/claude-code/issues/26340 — Token usage summary readable by Claude (closed: not planned)
- https://github.com/anthropics/claude-code/issues/10388 — Agent token usage API (closed: not planned)
- https://code.claude.com/docs/en/context-window — Context window documentation

### Official guides & frameworks
- https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents — Anthropic context engineering guide
- https://docs.langchain.com/oss/python/langchain/context-engineering — LangChain middleware-based context management
- https://www.agno.com/blog/handling-context-window-limits-in-agno-token-tracking-preventing-overflow — Agno token tracking

### Product approaches
- https://cursor.com/blog/dynamic-context-discovery — Cursor: file-based tool output, 46.9% MCP token reduction
- https://windsurf.com/changelog — Windsurf: user-facing token display
- https://aider.chat/docs/repomap.html — Aider: budget-aware repo map construction

### Experience reports
- https://dev.to/sasha_podles/claude-code-using-hooks-for-guaranteed-context-injection-2jg — Hook-based context injection patterns
- https://www.mindstudio.ai/blog/ai-agent-token-budget-management-claude-code — Claude Code budget management analysis
