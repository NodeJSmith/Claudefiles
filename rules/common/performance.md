# Model Selection

**Haiku 4.5** — Lightweight/worker agents, frequent invocation, 3x cost savings
**Sonnet 4.6** — Main development work, orchestration, complex coding
**Opus 4.6** — Deep reasoning, architecture decisions, research

## Context Window (CRITICAL)

A PreToolUse hook (`context-tier.sh`) injects context usage tiers when they change. Follow the guidance in those messages. When no tier message is present, do not invent context pressure — any unprompted claim about context usage ("building up," "getting low," suggesting compaction) is a fabrication.

If you think a task should be split across sessions, justify it on *quality* grounds (complexity, focus), never context pressure.

## Haiku Disqualifiers

Use Sonnet instead of Haiku when any of these apply:
- Agent reads or interprets image/screenshot files (vision capability required)
- Agent's primary function is filtering false positives from ambiguous output (not agents that have some false-positive avoidance as part of a larger checklist workflow)
- Agent does the same interactive work as an existing Sonnet agent

## Agent Model Declarations

Each agent file in `agents/` declares its model in YAML frontmatter. When updating model policy, check all locations:

**Agent files:**
- `agents/code-reviewer.md` — sonnet (pre-commit safety gate; do not downgrade)
- `agents/integration-reviewer.md` — sonnet (pre-commit safety gate; do not downgrade)
- `agents/testing-reality-checker.md` — sonnet (pre-ship safety gate; do not downgrade)
- `agents/researcher.md` — opus
- `agents/planner.md` — sonnet
- `agents/architect.md` — sonnet
- `agents/qa-specialist.md` — sonnet
- `agents/issue-refiner.md` — sonnet
- `agents/visual-diff.md` — sonnet
- `agents/engineering-frontend-developer.md` — sonnet
- `agents/engineering-backend-developer.md` — sonnet
- `agents/engineering-data-engineer.md` — sonnet
- `agents/engineering-technical-writer.md` — sonnet
- `agents/engineering-sre.md` — sonnet

**Skill files with inline model declarations** (not governed by agent frontmatter):
- `skills/mine.challenge/SKILL.md` — `model: haiku` for triage subagent, `model: sonnet` for critic and synthesis subagents
- `skills/mine.orchestrate/SKILL.md` — `model: sonnet` for executor and reviewer subagents
- `skills/mine.plan/SKILL.md` — `model: sonnet` for review subagent
- `skills/mine.implementation-review/SKILL.md` — `model: sonnet` for review subagent
