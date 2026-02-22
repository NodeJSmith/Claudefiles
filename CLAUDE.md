# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A personal Claude Code configuration repository — skills, commands, agents, rules, and hooks that symlink into `~/.claude/`. Not a typical software project; there's no build step, no tests, no application code.

## Installation

```bash
./install.sh
```

Symlinks all subdirectories into `~/.claude/`. Safe to re-run (updates existing symlinks, skips non-symlink conflicts). Respects `$CLAUDE_HOME` if set.

## Repository Structure

```
agents/          → Subagent definitions (code-reviewer, planner)
commands/        → Slash commands (*.md files, each is a prompt)
rules/
  common/        → Language-agnostic coding guidelines (auto-loaded)
  python/        → Python-specific extensions (auto-loaded)
skills/
  mine.*/        → Each skill is a directory with SKILL.md inside
scripts/
  hooks/         → PreToolUse/PostToolUse hook scripts
install.sh       → Symlink installer
```

## How the Pieces Connect

- **Skills** (`skills/mine.*/SKILL.md`) are invoked via `/mine.<name>`. Each SKILL.md is a self-contained prompt with instructions, phases, and output format. Skills can reference other skills (e.g., `/mine.ship` chains `/mine.commit-push` + `/mine.create-pr`).
- **Commands** (`commands/*.md`) are simpler slash commands — single-file prompts without the SKILL.md directory structure.
- **Agents** (`agents/*.md`) define subagent behavior for the `Task` tool. They specify model, tools, and detailed system prompts. Currently: `code-reviewer` (runs ruff/pyright/bandit/pytest) and `planner` (implementation planning).
- **Rules** (`rules/`) auto-load into Claude Code context. Python rules explicitly extend common rules (each file notes this). Rules govern coding style, testing, security, git workflow, error tracking, and agent orchestration.
- **Hooks** (`scripts/hooks/`) are JS scripts for PreToolUse/PostToolUse events. `block-git-c.js` intercepts Bash commands and rejects any containing `git -C`.

## Naming Convention

All skills and commands use the `mine.` prefix to namespace them and avoid collisions with other skill packs.

## Making Changes

When editing skills or commands:
- Skills live in `skills/mine.<name>/SKILL.md` — the directory name must match the skill reference
- Commands are flat markdown files in `commands/`
- Rules files in `python/` should reference their `common/` counterpart (pattern: "This file extends [common/foo.md]")
- After adding new directories under `agents/`, `skills/`, `commands/`, or `scripts/hooks/`, re-run `./install.sh` to create the symlink

When adding a new language to rules:
- Create `rules/<language>/` with markdown files
- The installer will symlink the entire language directory into `~/.claude/rules/<language>`
