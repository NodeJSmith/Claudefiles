---
tool: claude  # harness-only: model selection and the agent-model registry are Claude-Code-specific
---

# Model Selection

**Haiku 4.5** — Lightweight/worker agents, frequent invocation, 3x cost savings
**Sonnet 5** — Main development work, orchestration, complex coding
**Opus 4.8** — Deep reasoning, architecture decisions, research

A PreToolUse hook (`subagent-model-default.sh`) enforces model defaults on Agent dispatches. Built-in agent types (`general-purpose`, `Explore`, `Plan`, `claude`, empty) have no model frontmatter and inherit the parent model — typically Opus. The hook injects `model: sonnet` for these types when no model is specified. When the hook fires, it injects an `additionalContext` message — relay that to the user so they know the override happened. Overrides are logged to `~/.local/share/claudefiles/model-overrides.jsonl`.

## Effort Level Policy

All Sonnet agent files declare `effort: medium` in frontmatter. Sonnet 5 produces ~1.7x more output tokens than Sonnet 4.6 at the same effort level and ~2.6x more than Opus 4.6 — medium effort reduces this verbosity while preserving quality on the tasks subagents handle (review, analysis, generation). The parent session runs at `high` (set in `settings.machine.json`); subagents don't need the same depth.

**Gap:** Built-in agent types (`general-purpose`, `Explore`, `Plan`, `claude`) have no frontmatter, so they inherit the parent session's effort level (`high`). The Agent tool schema has no `effort` parameter, so the model-default hook cannot inject it. These types already get downgraded to Sonnet by the hook, which limits the cost impact.

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
- `agents/code-judo-reviewer.md` — sonnet, medium
- `agents/code-reviewer.md` — sonnet, medium (pre-commit safety gate; do not downgrade model)
- `agents/integration-reviewer.md` — sonnet, medium (pre-commit safety gate; do not downgrade model)
- `agents/lazy-checker.md` — sonnet, medium
- `agents/llm-checker.md` — sonnet, medium
- `agents/nitpicker.md` — sonnet, medium
- `agents/testing-reality-checker.md` — sonnet, medium (pre-ship safety gate; do not downgrade model)
- `agents/researcher.md` — opus
- `agents/secrets-auditor.md` — haiku
- `agents/planner.md` — sonnet, medium
- `agents/architect.md` — sonnet, medium
- `agents/qa-specialist.md` — sonnet, medium
- `agents/issue-refiner.md` — sonnet, medium
- `agents/visual-diff.md` — sonnet, medium
- `agents/wtf-reviewer.md` — sonnet, medium (pre-commit readability gate; do not downgrade model)
- `agents/fine-toothed-comb.md` — sonnet, medium
- `agents/instruction-quality-reviewer.md` — sonnet, medium
- `agents/writing-quality-reviewer.md` — sonnet, medium
- `agents/engineering-frontend-developer.md` — sonnet, medium
- `agents/engineering-backend-developer.md` — sonnet, medium
- `agents/engineering-data-engineer.md` — sonnet, medium
- `agents/engineering-technical-writer.md` — sonnet, medium
- `agents/engineering-sre.md` — sonnet, medium

**Skill files with inline model declarations** (not governed by agent frontmatter):
- `skills/mine-challenge/SKILL.md` — `model: haiku` for triage subagent, `model: sonnet` for critic and synthesis subagents
- `skills/mine-orchestrate/SKILL.md` — executor uses model from Step 4 routing (agent frontmatter, defaulting to `sonnet` for general-purpose); `model: sonnet` for reviewer subagents
- `skills/mine-orchestrate/post-execution-pipeline.md` — `model: sonnet` for the clean code check subagent
- `skills/mine-plan/SKILL.md` — `model: sonnet` for review subagent
- `skills/mine-implementation-review/SKILL.md` — `model: sonnet` for review subagent
- `skills/mine-decompose/SKILL.md` — `model: haiku` for behavioral and structural analysis subagents
- `skills/mine-issues-triage/SKILL.md` — `model: haiku` for batch triage subagents
- `skills/mine-create-pr/SKILL.md` — `model: sonnet` for PR creation worker subagent
- `skills/mine-create-issue/SKILL.md` — `model: sonnet` for investigation, drafting, and creation worker subagent
- `skills/mine-mockup/SKILL.md` — `model: sonnet` for mockup generation worker subagent
- `skills/mine-address-pr-issues/SKILL.md` — `model: sonnet` for fix subagents
- `skills/mine-brainstorm/SKILL.md` — `model: sonnet` for thinker subagents
- `skills/mine-prior-art/SKILL.md` — `model: sonnet` for web research subagent
- `skills/mine-visual-qa/SKILL.md` — `model: sonnet` for screenshotter and analysis subagents
