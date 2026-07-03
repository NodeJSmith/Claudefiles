# CLAUDE.md

A personal Claude Code configuration repository — skills, commands, agents, rules, and hooks that symlink into `$CLAUDE_CONFIG_DIR` (defaults to `~/.claude/`).

## Installation

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
uv run install.py
```

Interactive wizard that symlinks skills, agents, hooks, rules, commands, and bin scripts into `$CLAUDE_CONFIG_DIR` (default: `~/.claude/`). Installs selected packages via `uv tool install -e`. Safe to re-run — loads saved config and only prompts for new items.

Use `--reconfigure` to change selections, `--uninstall` to remove everything.

## Naming Conventions

- `mine-*` — personal skills and commands
- `i-*` — [Impeccable](https://impeccable.style/) frontend design skills
- `cli-*` — CLI design skills
- `cass-*` — conversation memory skills (recall, context, resume) backed by the `cass` binary

## Bash Tool State

Command substitution (`$(...)`), backticks, and pipes work normally in the Bash tool — use them freely within a single call. The one limit: shell state (env vars, variables, `cd`) does **not** persist across separate Bash tool calls, since each call is a fresh shell. When you need a value in a later command, either inline the substitution in one call (`git diff "$(git-branch-base)"...HEAD`) or write it to a file.

## Path References in Skills

When referencing installed skill, agent, or persona files from within a SKILL.md or agent file, always use `${CLAUDE_CONFIG_DIR:-~/.claude}` — never hardcode `~/.claude`. This ensures paths resolve correctly when `$CLAUDE_CONFIG_DIR` is set to a non-default location.

**Right:** `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-challenge/findings-protocol.md`
**Wrong:** `~/.claude/skills/mine-challenge/findings-protocol.md`

## Temp File Convention

Skills that write temp files use `get-skill-tmpdir <skill-name>` — prints a unique `/tmp/claude-*` directory. Use fixed filenames inside it (e.g., `<dir>/message.md`).

**Do NOT use `$CLAUDE_SESSION_ID`** — it doesn't propagate to subagents or Bash tool calls.

## Settings

Edit `settings.json` in this repo — **never** write directly to `$CLAUDE_CONFIG_DIR/settings.json`. Run `claude-merge-settings` to merge three layers:

1. `~/Claudefiles/settings.json`
2. `~/Dotfiles/config/claude/settings.json`
3. `$CLAUDE_CONFIG_DIR/settings.machine.json`

## Making Changes

- After adding directories under `agents/`, `skills/`, `skills-impeccable/`, `skills-cli/`, `commands/`, or `scripts/hooks/` — re-run `uv run install.py`
- **Always update `REFERENCE.md`** when adding, removing, or renaming skills, commands, agents, or bin/ scripts — it holds the full component tables
- **Always update `ONBOARDING.md`** when adding a capability a new adopter should know about (new bundle, significant new skill, workflow change)
- **Always update the appropriate capabilities file** with trigger phrases for new skills: `rules/common/capabilities-core.md` for mine-* and cass-*, `skills-impeccable/capabilities-impeccable.md` for i-*, `skills-cli/capabilities-cli.md` for cli-*
- **When bundling a new plugin:** add its marketplace to `extraKnownMarketplaces` and enable it in `enabledPlugins` in `settings.json`, then document it in the Plugins table in `REFERENCE.md` and the relevant path in `ONBOARDING.md`
- **When adding a rule to `rules/common/`** — set its `tool:` frontmatter. Portable rules get `tool: claude, codex, antigravity`; Claude-Code-harness-specific rules get `tool: claude  # harness-only: <reason>`. Omitting `tool:` is fail-closed (the rule reaches Claude only, never Codex). `codex-rules-sync` reads this to build `~/.codex/AGENTS.md`.
- CLI tools referenced in skills/commands/agents must exist in `bin/`, be a standard system tool, or be a well-known dev tool. No private tools outside this repo.
- **CodeRabbit reviews are manual.** Auto-review is disabled (`.coderabbit.yaml`). After the full PR workflow is complete (commit, push, PR created and marked ready), comment `@coderabbitai review` on the PR to trigger a review.
