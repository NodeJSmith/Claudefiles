# Context: Fix post-clear detection and consolidate sidecar pipeline

## Problem & Motivation

`orchestrate-self-reset` fails to detect when Claude Code is ready after `/clear` because it greps for a banner string that no longer appears in the TUI. The fix replaces this with a SessionStart hook sentinel — authoritative, event-driven, immune to TUI changes. Separately, the sidecar pipeline (context-writer, status-writer, context-tier) is split across Dotfiles and Claudefiles with no remaining justification — all consumers that act on the data live in Claudefiles.

## Key Decisions

1. Use a SessionStart hook with `matcher: "clear"` to write a sentinel file — authoritative readiness signal, not heuristic pane scraping
2. Keep two separate sidecar files (context `.meta` and status `.meta`) — no read-modify-write race
3. Move producers and consumer to Claudefiles `scripts/hooks/` — same directory as other hooks, uses `${CLAUDE_CONFIG_DIR:-$HOME/.claude}` path convention
4. The sentinel file is keyed by tmux session name (not Claude session UUID) — `orchestrate-self-reset` knows the tmux session name
5. The sentinel hook detects its tmux session name via `tmux display-message -p '#{session_name}'`

## Constraints

- Do NOT modify `rc-send-ready` or `rc-lib-reset.sh` — those are independent
- Do NOT merge the two sidecar files into one
- Do NOT change context-tier thresholds or guidance text
- Do NOT remove `child-context-check` from Dotfiles
- The Dotfiles cleanup (T03) edits files in `~/Dotfiles`, not in this worktree — the executor must use absolute paths to the Dotfiles main checkout
- Hook registrations in `settings.json` must use the `${CLAUDE_CONFIG_DIR:-$HOME/.claude}` path pattern (matching existing hooks in this file)
- The `statusLine` config uses a bare command name on PATH — the context-writer needs an install.py entry or direct path
- All moved scripts must be executable (`chmod +x`)
