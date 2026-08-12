---
topic: "OpenCode skill invocation and slash-command wrappers"
date: 2026-08-12
status: Draft
---

# Prior Art: OpenCode Skill Invocation and Slash-Command Wrappers

## The Problem

OpenCode separates reusable agent skills from user-facing slash commands. The question is whether the ecosystem normally adds a command for every skill, and, if so, what that bridge should contain.

## How We Do It Today

This repo installs native skills through OpenPackage, and `bin/opencode-sync` generates slash wrappers in the live OpenCode config during synchronization. Earlier wrappers included a Claude-path fallback that could conceal broken native registration; generated wrappers now load only the corresponding native skill.

## Patterns Found

### Pattern 1: Native agent-tool activation

**Used by**: OpenCode documentation and source; Superpowers' OpenCode integration.
**How it works**: OpenCode advertises skill metadata to the agent. The agent selects and loads a relevant skill through `skill({ name: "..." })`; users invoke the behavior through natural language or explicitly ask the agent to load a named skill.
**Strengths**: Native, portable, progressive disclosure, and no duplicate command fleet.
**Weaknesses**: No guaranteed `/skill-name` affordance; activation depends on the agent or an explicit natural-language request.
**Example**: https://opencode.ai/docs/skills/ and https://github.com/obra/superpowers/blob/main/docs/README.opencode.md

### Pattern 2: Independent custom commands

**Used by**: OpenCode's documented command system.
**How it works**: A command Markdown file is a prompt template invoked with `/name`. It may forward `$ARGUMENTS`, select an agent/model, or inject context. It is separate from skills.
**Strengths**: Discoverable, deterministic entrypoint and useful for common user operations.
**Weaknesses**: Commands do not have a native binding to skills and can duplicate workflow logic if allowed to grow.
**Example**: https://opencode.ai/docs/commands/

### Pattern 3: Thin command-to-skill bridge

**Used by**: No public OpenCode implementation found.
**How it works**: A command contains only a description, an instruction to load one named skill through the native skill tool, and forwarded arguments.
**Strengths**: Adds explicit slash UX while retaining one canonical workflow body.
**Weaknesses**: Prompt-mediated rather than guaranteed; duplicates names and metadata; a wrapper per skill adds generated surface area.
**Example**: Inferred from the official command and skill APIs; no public source found.

## Anti-Patterns

- Assuming every `SKILL.md` automatically creates `/skill-name` in OpenCode.
- Copying the skill body into the command instead of loading the canonical skill.
- Falling back to `${CLAUDE_CONFIG_DIR:-~/.claude}/skills`, which defeats proof of native OpenCode operation.
- Treating a desktop UI issue that exposed skills in command autocomplete as a stable contract.

## Emerging Trends

Agent Skills is converging on portable `SKILL.md` metadata and progressive disclosure, while invocation remains harness-specific. OpenCode uses a model-facing tool; Claude Code exposes skills directly as slash commands.

## Relevance to Us

The native skill installation is aligned with OpenCode and with mature integrations such as Superpowers. Generating wrappers for selected user-facing workflows is defensible, but generating one for every skill is not established ecosystem practice. Earlier live wrappers were thicker than necessary because they repeated the description, added explanatory ceremony, and included a Claude fallback; current generated wrappers omit those additions.

## Recommendation

Treat native skill discovery and model activation as the baseline. Generate slash wrappers only for intentionally user-invocable skills, because this repo already has that product distinction and users expect explicit workflow entrypoints. Keep each generated wrapper to one operational instruction plus `$ARGUMENTS`; omit the Claude fallback and do not copy workflow content. Add an isolated test with Claude external-skill loading disabled to prove the bridge loads the OpenCode-native skill.

## Sources

### Reference implementations

- https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/skill/index.ts - OpenCode skill discovery and tool implementation.
- https://github.com/obra/superpowers/blob/main/.opencode/plugins/superpowers.js - Mature integration registering native skills without wrappers.
- https://github.com/obra/superpowers/blob/main/docs/README.opencode.md - User invocation guidance through the native skill tool.

### Blog posts & writeups

- https://github.com/anomalyco/opencode/issues/41643 - Discussion of desktop/TUI skill-menu inconsistency.

### Documentation & standards

- https://opencode.ai/docs/skills/ - Official skill loading behavior.
- https://opencode.ai/docs/commands/ - Official slash-command behavior.
- https://opencode.ai/docs/tui/#commands - Built-in TUI slash commands.
- https://agentskills.io/specification - Portable Agent Skills format.
- https://docs.claude.com/en/docs/claude-code/slash-commands - Claude Code contrast: skills become slash commands.
