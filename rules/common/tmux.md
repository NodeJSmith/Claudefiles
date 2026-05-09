# Tmux Session Naming

## Convention

At conversation start, rename the session to reflect the current work:

```bash
claude-tmux rename "<name>"
```

If the output says **"Not in tmux"**, you are not inside a tmux session — do NOT attempt any further tmux commands for the rest of this conversation. No retries, no drift detection, no renaming.

## Name Format

`<project>-<context>`, kebab-case, max ~30 chars.

- **project**: derived from the working directory name (e.g., `dotfiles`, `myapp`, `claudefiles`)
- **context**: branch name, issue number, task description — whatever best identifies the work

Examples:
- `dotfiles-main` — general work on main branch
- `myapp-238-url-fix` — issue worktree
- `claudefiles-pr3` — PR review
- `dotfiles-tmux-naming` — feature work

Rules:
- Truncate intelligently (don't cut mid-word)
- No spaces or special characters beyond hyphens
- Prefer branch name if it's already descriptive

## Terminal Tab Title (Bedrock Only)

On Bedrock, Claude Code's auto-title generation is broken (output_config rejected by Bedrock API). The workaround is in `tmux.conf`: when `CLAUDE_CODE_USE_BEDROCK=1`, `set-titles-string` uses `#{session_name}` instead of `#{pane_title}`. Claude Code's spinner constantly overwrites the pane title but never touches the session name, so the tab always reflects the session name set by `claude-tmux rename`. No sidecar files or extra hooks needed — just renaming the session is sufficient.

## Drift Detection

When the conversation topic shifts significantly (e.g., pivoting from one feature to another), update the session name to match the new focus.

A `PreToolUse` hook (`tmux-drift-check.sh`) fires every ~30 tool calls inside tmux sessions, reporting the current session name and prompting a rename if the topic has shifted. The interval is configurable via `CLAUDE_TMUX_DRIFT_HEARTBEAT`.

## Cross-Pane Monitoring

Claude Code can read output from other tmux panes. When a dev server, build process, or test runner is running in another pane, use `claude-tmux capture` to grab its output:

```bash
claude-tmux capture "session-name"       # last 20 lines
claude-tmux capture "session-name" 200   # last 200 lines (build logs, stack traces)
```

Use `claude-tmux panes` to discover what's running in other panes (command, path, PID) before capturing.
