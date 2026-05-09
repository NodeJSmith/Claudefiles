#!/usr/bin/env bash
# PreToolUse hook: periodically remind Claude to check the tmux session name for drift.
#
# Fires every N tool calls (default 30, override via CLAUDE_TMUX_DRIFT_HEARTBEAT).
# Embeds the current session name in the message so Claude can judge drift without
# an extra tool call.
#
# Hook wiring: add as a "PreToolUse" entry with matcher "*" in settings.json.

[ -n "${TMUX:-}" ] || exit 0

session_id="${CLAUDE_CODE_SESSION_ID:-}"
[ -n "$session_id" ] || exit 0

heartbeat_interval="${CLAUDE_TMUX_DRIFT_HEARTBEAT:-30}"
# 0 is rejected — use CLAUDE_TMUX_DRIFT_HEARTBEAT=1 for maximum frequency; 0 would fire every call
case "$heartbeat_interval" in
  '' | *[!0-9]* | 0) heartbeat_interval=30 ;;
esac

counter_file="/tmp/claude-tmux-drift-${session_id}.txt"
count="$(cat "$counter_file" 2> /dev/null)" || true
count="${count:-0}"
case "$count" in *[!0-9]*) count=0 ;; esac
count=$((count + 1))

printf '%d' "$count" > "${counter_file}.tmp" 2> /dev/null && mv -f "${counter_file}.tmp" "$counter_file" 2> /dev/null || true

[ "$count" -ge "$heartbeat_interval" ] || exit 0

# Reset counter
printf '0' > "${counter_file}.tmp" 2> /dev/null && mv -f "${counter_file}.tmp" "$counter_file" 2> /dev/null || true

session_name="$(tmux display-message -p '#{session_name}' 2> /dev/null)" || exit 0
[ -n "$session_name" ] || exit 0

jq -cn --arg name "$session_name" \
  '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":("Session name check: current name is \($name). If the topic has shifted significantly, update it with: claude-tmux rename \"new-name\"")}}'
