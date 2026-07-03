---
tool: claude  # harness-only: model selection and the agent-model registry are Claude-Code-specific
---

# Model Selection

**Haiku 4.5** — Lightweight/worker agents, frequent invocation, 3x cost savings
**Sonnet 4.6** — Main development work, orchestration, complex coding
**Opus 4.8** — Deep reasoning, architecture decisions, research

## Context Window (CRITICAL)

A PreToolUse hook (`context-tier.sh`, part of the personal Dotfiles setup) injects context usage tiers when they change and re-injects periodically (every 25 tool calls) to keep guidance fresh. Follow the guidance in those messages. When no tier message is present, do not invent context pressure — any unprompted claim about context usage ("building up," "getting low," suggesting compaction) is a fabrication.

A PostToolUse hook (`subagent-compaction-check.sh`) reports when a subagent auto-compacted during execution. These messages are based on observed `compact_boundary` events in the subagent's JSONL, not inference. Treat them as a data point about task scope, not an alarm requiring immediate action.

If you think a task should be split across sessions, justify it on *quality* grounds (complexity, focus), never context pressure.

## Haiku Disqualifiers

Use Sonnet instead of Haiku when any of these apply:
- Agent reads or interprets image/screenshot files (vision capability required)
- Agent's primary function is filtering false positives from ambiguous output (not agents that have some false-positive avoidance as part of a larger checklist workflow)
- Agent does the same interactive work as an existing Sonnet agent

## Agent Model Declarations

Each agent file in `agents/` declares its model in YAML frontmatter. When updating model policy, check all locations. The agent-file list below is validated against frontmatter by `bin/lint-agent-models` (pre-commit hook) — a mismatch, missing entry, or stale entry fails the commit.

**Agent files:**
- `agents/code-judo-reviewer.md` — sonnet
- `agents/code-reviewer.md` — sonnet (pre-commit safety gate; do not downgrade)
- `agents/integration-reviewer.md` — sonnet (pre-commit safety gate; do not downgrade)
- `agents/lazy-checker.md` — sonnet
- `agents/llm-checker.md` — sonnet
- `agents/nitpicker.md` — sonnet
- `agents/testing-reality-checker.md` — sonnet (pre-ship safety gate; do not downgrade)
- `agents/researcher.md` — opus
- `agents/secrets-auditor.md` — haiku
- `agents/planner.md` — sonnet
- `agents/architect.md` — sonnet
- `agents/qa-specialist.md` — sonnet
- `agents/issue-refiner.md` — sonnet
- `agents/visual-diff.md` — sonnet
- `agents/wtf-reviewer.md` — sonnet (pre-commit readability gate; do not downgrade)
- `agents/fine-toothed-comb.md` — sonnet
- `agents/engineering-frontend-developer.md` — sonnet
- `agents/engineering-backend-developer.md` — sonnet
- `agents/engineering-data-engineer.md` — sonnet
- `agents/engineering-technical-writer.md` — sonnet
- `agents/engineering-sre.md` — sonnet

**Skill files with inline model declarations** (not governed by agent frontmatter):
- `skills/mine-challenge/SKILL.md` — `model: haiku` for triage subagent, `model: sonnet` for critic and synthesis subagents
- `skills/mine-orchestrate/SKILL.md` — `model: sonnet` for executor and reviewer subagents
- `skills/mine-orchestrate/post-execution-pipeline.md` — `model: sonnet` for the clean code check subagent and the implementation fine-toothed comb subagent
- `skills/mine-plan/SKILL.md` — `model: sonnet` for review subagent
- `skills/mine-implementation-review/SKILL.md` — `model: sonnet` for review subagent
- `skills/mine-decompose/SKILL.md` — `model: haiku` for behavioral and structural analysis subagents
- `skills/mine-issues-triage/SKILL.md` — `model: haiku` for batch triage subagents
- `skills/mine-create-pr/SKILL.md` — `model: sonnet` for PR creation worker subagent
- `skills/mine-create-issue/SKILL.md` — `model: sonnet` for investigation, drafting, and creation worker subagent
- `skills/mine-mockup/SKILL.md` — `model: sonnet` for mockup generation worker subagent
- `skills/mine-review/SKILL.md` — `model: sonnet` for instruction-mode reviewers (instruction quality, writing quality)
