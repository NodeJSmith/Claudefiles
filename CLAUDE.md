# CLAUDE.md

A personal Claude Code configuration repository — skills, commands, agents, rules, and hooks that symlink into `~/.claude/`.

## Installation

```bash
./install.sh
```

Symlinks `agents/`, `skills/`, `commands/`, `scripts/hooks/`, `rules/` into `~/.claude/`, and `bin/` scripts into `~/.local/bin/`. Safe to re-run. Respects `$CLAUDE_HOME`.

### Runtime Dependencies

```bash
uv tool install -e packages/spec-helper    # WP and spec directory management
uv tool install -e packages/claude-memory  # Conversation memory hooks and CLIs
```

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

## Temp File Convention

Skills that write temp files use `get-skill-tmpdir <skill-name>` — prints a unique `/tmp/claude-*` directory. Use fixed filenames inside it (e.g., `<dir>/message.md`).

**Do NOT use `$CLAUDE_SESSION_ID`** — it doesn't propagate to subagents or Bash tool calls.

## Settings

Edit `settings.json` in this repo — **never** write directly to `~/.claude/settings.json`. Run `claude-merge-settings` to merge three layers:

1. `~/Claudefiles/settings.json`
2. `~/Dotfiles/config/claude/settings.json`
3. `~/.claude/settings.machine.json`

## Making Changes

- After adding directories under `agents/`, `skills/`, `commands/`, or `scripts/hooks/` — re-run `./install.sh`
- **Always update `README.md`** when adding, removing, or renaming skills, commands, agents, or bin/ scripts
- **Always update `rules/common/capabilities.md`** with trigger phrases for new skills
- CLI tools referenced in skills/commands/agents must exist in `bin/`, be a standard system tool, or be a well-known dev tool. No private tools outside this repo.
