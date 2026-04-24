# CLAUDE.md

A personal Claude Code configuration repository — skills, commands, agents, rules, and hooks that symlink into `~/.claude/`.

## Installation

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
uv run install.py
```

Interactive wizard that symlinks skills, agents, hooks, rules, commands, and bin scripts into `~/.claude/`. Installs selected packages via `uv tool install -e`. Safe to re-run — loads saved config and only prompts for new items. Respects `$CLAUDE_HOME`.

Use `--reconfigure` to change selections, `--uninstall` to remove everything.

## Naming Conventions

- `mine.*` — personal skills and commands
- `i-*` — [Impeccable](https://impeccable.style/) frontend design skills
- `cm-*` — claude-memory skills, agents, and CLI entry points

## Bash Tool Restrictions

The Bash tool wraps commands in `eval '...' < /dev/null`. **Never use:**

- **`$(...)` command substitution** — silently fails or errors
- **Backtick substitution** — same broken code path
- **Bare pipes as the final element** (sandbox mode) — data silently lost

**Workarounds:**
- Split into sequential calls: run the inner command first, use result in next call
- `xargs -I {}` piping: `git-default-branch | xargs -I {} git log "origin/{}..HEAD"`

**Wrong:** `git diff --name-only "$(git-default-branch)"`
**Right:** `git-default-branch | xargs -I {} git diff --name-only {}`

## Path References in Skills

When referencing installed skill, agent, or persona files from within a SKILL.md or agent file, always use `${CLAUDE_HOME:-~/.claude}` — never hardcode `~/.claude`. This ensures paths resolve correctly when `$CLAUDE_HOME` is set to a non-default location.

**Right:** `${CLAUDE_HOME:-~/.claude}/skills/mine.challenge/findings-protocol.md`
**Wrong:** `~/.claude/skills/mine.challenge/findings-protocol.md`

## Temp File Convention

Skills that write temp files use `get-skill-tmpdir <skill-name>` — prints a unique `/tmp/claude-*` directory. Use fixed filenames inside it (e.g., `<dir>/message.md`).

**Do NOT use `$CLAUDE_SESSION_ID`** — it doesn't propagate to subagents or Bash tool calls.

## Settings

Edit `settings.json` in this repo — **never** write directly to `~/.claude/settings.json`. Run `claude-merge-settings` to merge three layers:

1. `~/Claudefiles/settings.json`
2. `~/Dotfiles/config/claude/settings.json`
3. `~/.claude/settings.machine.json`

## Making Changes

- After adding directories under `agents/`, `skills/`, `skills-impeccable/`, `skills-memory/`, `commands/`, or `scripts/hooks/` — re-run `uv run install.py`
- **Always update `README.md`** when adding, removing, or renaming skills, commands, agents, or bin/ scripts
- **Always update the appropriate `rules/common/capabilities-*.md`** file with trigger phrases for new skills (`capabilities-core.md` for mine.*, `capabilities-impeccable.md` for i-*, `capabilities-memory.md` for cm-*)
- CLI tools referenced in skills/commands/agents must exist in `bin/`, be a standard system tool, or be a well-known dev tool. No private tools outside this repo.
