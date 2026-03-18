---
name: mine.session-tools
description: "Use when managing Claude Code sessions, tmux windows, or settings. Documents claude-tmux, claude-log, claude-merge-settings — session management, log queries, settings merge."
user-invocable: false
---

# Session Management Tools

Purpose-built scripts in `~/.local/bin/`.

## claude-tmux

Tmux session helper. All commands print "Not in tmux" and exit 0 when `$TMUX` is unset.

```bash
claude-tmux rename "myproject-feature"    # rename current session
claude-tmux current                       # print current session name
claude-tmux new "myproject-feat" ~/src/myproject   # create + switch
claude-tmux list                          # list sessions (pipe-delimited)
claude-tmux panes                         # list all panes (pipe-delimited)
claude-tmux capture "myproject-feat"      # last 20 lines of active pane
claude-tmux capture "myproject-feat" 200  # last 200 lines
claude-tmux kill "old-session"            # kill one or more sessions
```

- `list` output: `name|attached|windows|last_activity`
- `panes` output: `session|window_index|command|path|pid`
- `kill` accepts multiple session names

## claude-log

Query Claude Code JSONL session logs. Pre-allowed via `Bash(claude-log:*)`.

```bash
# List / search
claude-log list --limit 10
claude-log list --project Dotfiles --since 2026-02-15
claude-log search "authentication" --since 2026-02-15 --limit 30
claude-log search "error" --project myapp --type assistant

# Show session content
claude-log show <session-id> --messages
claude-log show <session-id> --tools
claude-log show <session-id> --usage

# Stats and trends
claude-log stats <session-id>
claude-log skills --since 2026-02-01
claude-log agents --project Dotfiles

# Extract structured data
claude-log extract <session-id> --tools
claude-log extract <session-id> --bash
claude-log extract <session-id> --usage
```

| Flag | Purpose |
|------|---------|
| `--json` | JSON output |
| `--project`, `-p` | Filter by project name |
| `--since`, `-s` | Filter by date (YYYY-MM-DD) |
| `--limit`, `-l` | Max results |
| `--type` | Search filter: user, assistant, tool_use |

Show filters: `--messages` (`-m`), `--tools` (`-t`), `--user` (`-u`), `--assistant` (`-a`), `--thinking`, `--usage`

Session IDs accept full UUID, 8-char prefix, or partial match.

## claude-merge-settings

Merge Claude Code settings from three layers into `~/.claude/settings.json`.

```bash
claude-merge-settings
CLAUDE_DOTFILES_SETTINGS=/dev/null claude-merge-settings   # skip Dotfiles layer
```

Layers (later wins):
1. `~/Claudefiles/settings.json` — shared, portable
2. `~/Dotfiles/config/claude/settings.json` — private (override with `$CLAUDE_DOTFILES_SETTINGS`)
3. `~/.claude/settings.machine.json` — machine-specific

Special merge rules:
- `permissions.allow/deny` — concatenate + deduplicate
- `allowedTools` — concatenate + deduplicate
- `hooks.<type>` arrays — concatenate + deduplicate
- Everything else — deep merge, last wins
