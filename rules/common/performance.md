---
tool: claude  # harness-only: model selection and the agent-model registry are Claude-Code-specific
---

# Model Selection

**Haiku 4.5** — Lightweight/worker agents, frequent invocation, 3x cost savings
**Sonnet 5** — Main development work, orchestration, complex coding
**Opus 4.8** — Deep reasoning, architecture decisions, research

A PreToolUse hook (`subagent-model-default.sh`) enforces model defaults on Agent dispatches. Built-in agent types (`general-purpose`, `Explore`, `Plan`, `claude`, empty) have no model frontmatter and inherit the parent model — typically Opus. The hook injects `model: sonnet` for these types when no model is specified. When the hook fires, it injects an `additionalContext` message — relay that to the user so they know the override happened. Overrides are logged to `~/.local/share/claudefiles/model-overrides.jsonl`.

## Effort Level Policy

Every agent file declares an explicit `effort:` in frontmatter — no agent ships without one. `lint-agent-models` enforces the declaration by rejecting any agent file whose frontmatter omits `effort:` (along with the other four required fields), but it only checks that the field is present, not that its value matches the agent's tier default below — a new agent shipped with the wrong value passes lint silently.

Sonnet agents run at `effort: medium`. Opus and Haiku agents run at `effort: high`. These are current defaults, not ceilings — match a new agent's effort to its tier's current default unless there's a specific reason to diverge. To retune a role's effort, edit that agent's frontmatter, then run `bin/lint-agent-models --write` to regenerate the list below from it.

`effort:` is the Claude Code key and stays that in source. OpenCode has no such key — its equivalent is `variant:`, and it accepts unknown agent keys silently rather than rejecting them, so an `effort:` that reached OpenCode would look configured while every agent ran at the provider default. Neither side rewrites agent files: an OpenCode plugin (`opencode/claudefiles.ts`) reads each agent's frontmatter live at OpenCode session start and resolves its Claude tier name to a model and `variant` through `opencode/config-data.json`'s `tier_map`, so raising or lowering a tier's reasoning level for OpenCode means editing that shared data file, not the agent files (`design/specs/1007-opencode-config-plugin`). `tier_map`'s per-tier `variant` values are kept matching the per-agent `effort:` defaults above.

The parent session runs at `high` (set in `settings.machine.json`).

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

Each agent file in `agents/` declares its model, effort, tools, description, and bundle membership in its own YAML frontmatter — the single source of truth for agent metadata. The list below is generated from that frontmatter by `bin/lint-agent-models`, which also generates `install.py`'s per-bundle `agents=(...)` tuples from the same source. To retune a role's model, edit that agent's frontmatter, then run `bin/lint-agent-models --write` to regenerate this list and `install.py` together — no other file needs touching. `bin/lint-agent-models` (no flags, the pre-commit hook) fails the commit if either generated artifact has drifted from frontmatter, or if any agent file is missing a required field.

The `(do not downgrade; ...)` annotations below are pulled from a trailing comment on each agent's `model:` frontmatter line — they protect the model tier (keep this agent on Sonnet, not Haiku), not the `effort` value shown next to it.

**Agent files:**
<!-- GENERATED BY bin/lint-agent-models -- DO NOT EDIT MANUALLY. Run `bin/lint-agent-models --write` to regenerate. -->
- `agents/architect.md` — sonnet, medium
- `agents/code-judo-reviewer.md` — sonnet, medium
- `agents/code-reviewer.md` — sonnet, medium (do not downgrade; pre-commit safety gate)
- `agents/engineering-backend-developer.md` — sonnet, medium
- `agents/engineering-data-engineer.md` — sonnet, medium
- `agents/engineering-frontend-developer.md` — sonnet, medium
- `agents/engineering-sre.md` — sonnet, medium
- `agents/engineering-technical-writer.md` — sonnet, medium
- `agents/fine-toothed-comb.md` — sonnet, medium
- `agents/instruction-quality-reviewer.md` — sonnet, medium
- `agents/integration-reviewer.md` — sonnet, medium (do not downgrade; pre-commit safety gate)
- `agents/issue-refiner.md` — sonnet, medium
- `agents/lazy-checker.md` — sonnet, medium
- `agents/light-worker.md` — haiku, high
- `agents/llm-checker.md` — sonnet, medium
- `agents/nitpicker.md` — sonnet, medium
- `agents/planner.md` — sonnet, medium
- `agents/qa-specialist.md` — sonnet, medium
- `agents/researcher.md` — opus, high
- `agents/secrets-auditor.md` — haiku, high
- `agents/spec-reviewer.md` — sonnet, medium
- `agents/standard-worker.md` — sonnet, medium
- `agents/testing-reality-checker.md` — sonnet, medium (do not downgrade; pre-ship safety gate)
- `agents/visual-diff.md` — sonnet, medium (vision required for screenshot comparison)
- `agents/writing-quality-reviewer.md` — sonnet, medium
- `agents/wtf-reviewer.md` — sonnet, medium (do not downgrade; pre-commit readability gate)
<!-- END GENERATED -->
