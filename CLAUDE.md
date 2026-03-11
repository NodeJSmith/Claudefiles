# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A personal Claude Code configuration repository — skills, commands, agents, rules, and hooks that symlink into `~/.claude/`. Not a typical software project; there's no build step, no tests, no application code.

## Installation

```bash
./install.sh
```

Symlinks key configuration directories (`agents/`, `skills/`, `commands/`, `scripts/hooks/`, and per-language `rules/`) into `~/.claude/`, and helper scripts from `bin/` into `~/.local/bin/`. Safe to re-run (updates existing symlinks, skips non-symlink conflicts). Respects `$CLAUDE_HOME` if set.

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
  hooks/         → Hook scripts (PreToolUse)
bin/             → Helper scripts symlinked into ~/.local/bin
install.sh       → Symlink installer
design/
  specs/         → Feature specifications and work packages (caliper v2)
    NNN-slug/    → One directory per feature (NNN = zero-padded sequence)
      spec.md    → What to build (mine.specify)
      design.md  → How to build it (mine.design)
      tasks/
        WP01.md  → Work packages with lane state (mine.draft-plan)
        WP02.md
```

### `design/specs/` artifact convention

- `spec.md` — what to build. User-facing, technology-agnostic. Never contains tasks.
- `design.md` — how to build it. Architecture, decisions, API contracts. Never contains tasks.
- `WP*.md` — executable work packages. The **only** place tasks live. Lane state tracked in YAML frontmatter (`planned | doing | for_review | done`), updated by `spec-helper wp-move`.

Freeze gate: WPs are generated from `design.md` by `/mine.draft-plan` before `/mine.plan-review`. `/mine.plan-review` reviews `design.md` plus the existing WPs; once that review is approved, `design.md` is frozen — substantive changes require regenerating WPs via `/mine.draft-plan`.

## How the Pieces Connect

- **Skills** (`skills/mine.*/SKILL.md`) are invoked via `/mine.<name>`. Each SKILL.md is a self-contained prompt with instructions, phases, and output format. Skills can reference other skills (e.g., `/mine.ship` chains `/mine.commit-push` + `/mine.create-pr`).
- **Commands** (`commands/*.md`) are simpler slash commands — single-file prompts without the SKILL.md directory structure.
- **Agents** (`agents/*.md`) define subagent behavior for the `Task` tool. They specify model, tools, and detailed system prompts. Currently: `code-reviewer` (runs ruff/pyright/bandit/pytest) and `planner` (implementation planning).
- **Rules** (`rules/`) auto-load into Claude Code context. Python rules explicitly extend common rules (each file notes this). Rules govern coding style, testing, security, git workflow, error tracking, and agent orchestration.
- **Hooks** (`scripts/hooks/`) are Node.js scripts for hook events. Hook scripts require wiring in your `settings.json` — see [Claude Code hook configuration docs](https://docs.anthropic.com/en/docs/claude-code/hooks) for setup.

## Naming Convention

All skills and commands use the `mine.` prefix to namespace them and avoid collisions with other skill packs.

## Bash Tool Restrictions

The Bash tool wraps commands in `eval '...' < /dev/null`, which breaks certain shell patterns. **Never use these in Bash tool calls or `!` backtick template expansions:**

- **`$(...)` command substitution** — gets mangled by the eval wrapper, causing syntax errors or silent failures
- **Shell backtick command substitution** (`` `cmd` ``) — same broken code path as `$()`; this does not apply to Markdown backticks or `!` template syntax
- **Bare pipes as the final element** (sandbox mode) — data silently lost; add a trailing `;` if needed

**Workarounds:**
- Split into sequential commands: run the inner command first, then use the result in the next call
- Use `xargs -I {}` piping: `git-default-branch | xargs -I {} git log "origin/{}..HEAD"`
- For complex fallbacks: `git-default-branch | xargs -I {} git log "origin/{}..HEAD" 2>/dev/null || git-default-branch | xargs -I {} git log "{}..HEAD"`

**Wrong:** `git diff --name-only "$(git-default-branch)"` / `db=$(git-default-branch); git log "${db}..HEAD"`
**Right:** `git-default-branch | xargs -I {} git diff --name-only {}` / run `git-default-branch` first, then `git log "<result>..HEAD"`

This applies to all skills, commands, rules, and agent prompts in this repo.

## Temp File Convention

Skills that write temp files use `get-skill-tmpdir` (in `bin/`) to create a unique directory per run:

1. Run `get-skill-tmpdir <skill-name>` — prints a unique directory path (e.g., `/tmp/claude-mine-challenge-a8Kx3Q`)
2. Use fixed filenames inside that directory (e.g., `<dir>/senior.md`, `<dir>/message.md`)

This replaces the old `$CLAUDE_SESSION_ID` pattern, which failed in subagents and concurrent sessions. The helper:
- Uses `mktemp -d` for OS-guaranteed uniqueness
- Prefixes all paths with `claude-` (matches `Write(/tmp/claude-**)` allowlist)
- Respects `$CLAUDE_CODE_TMPDIR` for sandbox environments
- Is pre-allowed via `Bash(get-skill-tmpdir:*)` in settings.json

**Do NOT use `$CLAUDE_SESSION_ID` in temp file paths.** It's a SKILL.md string substitution that doesn't propagate to subagents or Bash tool calls.

## Making Changes

When editing skills or commands:
- Skills live in `skills/mine.<name>/SKILL.md` — the directory name must match the skill reference
- Commands are flat markdown files in `commands/`
- Rules files in `python/` should reference their `common/` counterpart (pattern: "This file extends [common/foo.md]")
- After adding new directories under `agents/`, `skills/`, `commands/`, or `scripts/hooks/`, re-run `./install.sh` to create the symlink
- **Always update `README.md`** when adding, removing, or renaming skills, commands, agents, rules, or bin/ scripts — the README has inventory tables with counts that must stay in sync
- **CLI tools referenced in skills/commands/agents** must be one of: a script in `bin/` (symlinked to `~/.local/bin/` by the installer), a standard system tool (`git`, `gh`, `az`, `jq`, etc.), or a well-known dev tool (`ruff`, `pyright`, `pytest`, etc.). Do not reference private tools that live outside this repo.

When adding a new language to rules:
- Create `rules/<language>/` with markdown files
- The installer will symlink the entire language directory into `~/.claude/rules/<language>`


When changing settings or permissions:
- Edit `settings.json` in this repo — **never** write directly to `~/.claude/settings.json`
- Run `claude-merge-settings` to combine three layers into `~/.claude/settings.json`:
  1. `~/Claudefiles/settings.json` (shared, portable)
  2. `~/Dotfiles/config/claude/settings.json` (private — override with `$CLAUDE_DOTFILES_SETTINGS`)
  3. `~/.claude/settings.machine.json` (machine-specific)
