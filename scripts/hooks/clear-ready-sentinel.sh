#!/usr/bin/env bash
# SessionStart hook (matcher: "clear"): mark that /clear has fully reset the session.
#
# Fires only after /clear completes — the session is freshly reset and ready
# for input. Writes a sentinel file keyed by tmux session name so an external
# watcher (orchestrate-self-reset) can detect readiness without scraping pane
# content for a welcome-banner string that can drift or disappear across TUI
# versions.
#
# The tmux session name is the key, not the Claude session UUID — the process
# is inside a tmux pane (it was launched from one), so it can read its own
# session name via `tmux display-message`. orchestrate-self-reset knows the
# tmux session name (it was given it as an argument) but has no way to learn
# the Claude session UUID, so keying by UUID would leave it with nothing to
# poll for.
#
# Sentinel file: /tmp/claude-clear-ready-<tmux-session-name>.sentinel
#   Contents: session_id and a timestamp, for debugging only — the watcher
#   only checks for the file's existence.
#
# Hook wiring (settings.json):
#   "SessionStart": [{
#     "matcher": "clear",
#     "hooks": [{
#       "type": "command",
#       "command": "bash -c 'f=\"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/hooks/clear-ready-sentinel.sh\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
#       "timeout": 5000
#     }]
#   }]
#
# No set -euo pipefail — this hook is a sequence of guard clauses that each
# exit 0 on failure (best-effort, never disrupt the session), same style as
# the sibling SessionStart/PreToolUse hooks.

if ! command -v jq > /dev/null 2>&1; then
  exit 0
fi

[ -n "${TMUX:-}" ] || exit 0

input="$(cat || true)"

session_id="$(printf '%s' "$input" | jq -r '.session_id // empty' 2> /dev/null)" || true
case "$session_id" in '' | *[/.]*) exit 0 ;; esac

session_name="$(tmux display-message -p '#{session_name}' 2> /dev/null)" || exit 0
[ -n "$session_name" ] || exit 0
case "$session_name" in *[/.]*) exit 0 ;; esac

sentinel_file="/tmp/claude-clear-ready-${session_name}.sentinel"
timestamp="$(date +%s 2> /dev/null)" || timestamp=""

{
  printf 'session_id=%s\n' "$session_id"
  printf 'timestamp=%s\n' "$timestamp"
} > "${sentinel_file}.tmp" 2> /dev/null && mv -f "${sentinel_file}.tmp" "$sentinel_file" 2> /dev/null

exit 0
