---
name: mine.agent-patterns
description: Agent orchestration patterns — parallel execution, model selection, context passing, subagent types, temp files, foreground/background, multi-perspective analysis.
user-invokable: false
---

# Agent Patterns

Detailed guidance for writing skills and commands that launch subagents.

> **Note:** Some older SKILL.md files may still refer to parallelism as "Task calls". These map to the same underlying `Agent` subagent mechanism described here — there is no separate "Task" tool.

## Parallel Agent Execution

Multiple `Agent` tool calls in a **single message** = parallel execution. Claude Code launches them concurrently and returns all results before you continue.

```markdown
# GOOD: Three Agent calls in one message → parallel
Agent(description="Audit auth module", prompt="...")
Agent(description="Review cache layer", prompt="...")
Agent(description="Check API types", prompt="...")

# BAD: Three separate messages → sequential
```

Always launch independent agents in a single message. Only sequentialize when one agent's output feeds another's input.

## Choosing a Subagent Type

| Need | `subagent_type` | Why |
|------|----------------|-----|
| Read code, search files, analyze patterns | `Explore` | Fast (Haiku), read-only tools, cheap. Default for research. |
| Full autonomy (write files, run commands, web search) | `general-purpose` | All tools available. |
| Domain-specific review with a specialized prompt | Named agent — e.g., `code-reviewer`, `qa-specialist` | Tailored system prompt + tool restrictions. |

**Rule of thumb**: use `Explore` unless the subagent needs to write files, run commands, or search the web.

## Model Inheritance

Top-level agents inherit the parent session's model by default. `Explore` always uses Haiku. Skill-specific agents (under `skills/mine.*/agents/`) may pin a model for cost control.

To override: pass `model: "sonnet"` (or `"opus"`, `"haiku"`) in the Agent tool call. Useful for cost control on high-volume patterns (10+ parallel graders on Haiku instead of Opus).

## Collecting Results: Inline vs Temp Files

**Inline returns** (default) — subagent's final message comes back to your context:
- Use when each subagent returns a focused summary (< ~2K tokens)
- Examples: `mine.research` subagents, `mine.audit` per-directory scouts

**Temp file output** — subagent writes to a file, main instance reads it:
- Use when subagents produce large or structured output
- Create the temp dir first with `get-skill-tmpdir <skill-name>`, then pass fixed filenames
- Examples: `mine.brainstorm` thinkers, `mine.challenge` critics

## Foreground vs Background

**Foreground** (default) — blocks until complete:
- Use when you need the result before continuing (most cases)
- Parallel foreground agents all run concurrently

**Background** (`run_in_background: true`) — runs while you keep working:
- Background agents **cannot** ask user questions (auto-denied)
- Background agents **cannot** get new permission approvals
- Use for fire-and-forget tasks (test suite while editing another file)

## Passing Context to Subagents

Subagents start with a **fresh context** — they don't inherit your conversation.

| Context type | How to pass |
|-------------|-------------|
| Small code excerpts (< 200 lines) | Embed directly in the prompt |
| Larger files or multiple files | Pass file paths — subagent reads them |
| Agent behavior instructions | Read the agent definition file, embed its content |
| Shared constraints | Embed directly in the prompt |
| Output destination (temp files) | Pass the exact file path as a literal string |

**Never assume a subagent knows what you're working on.** Be explicit about: what to investigate, what to produce, and where to write it.

## Standard Phrasing for Skills

When writing SKILL.md files that launch parallel agents:

```markdown
Launch **parallel subagents** (`subagent_type: <type>`). Each receives:
- [what context is passed]
- [what output is expected]
- [where to write results, if temp files]
```

## Multi-Perspective Analysis

For complex problems, use split-role subagents with the same context but different personas:
- Factual reviewer
- Senior engineer
- Security expert
- Consistency reviewer
- Redundancy checker

Give each persona **specific instructions** — not just a role title. Include: what to look for, what to ignore, what format to return, and shared rules all personas must follow.
