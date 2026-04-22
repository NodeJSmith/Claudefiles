#!/usr/bin/env bash
# PostToolUse hook: reset the pytest failure counter after a code edit.
#
# Triggered by Edit, Write, MultiEdit, or NotebookEdit tool use.
# Reads the session UUID from the same path as pytest-loop-detector.sh and
# resets the counter to 0 atomically. Graceful no-op if session ID file or
# counter file doesn't exist.
#
# Hook wiring (settings.json):
#   "PostToolUse": [{
#     "matcher": "Edit|Write|MultiEdit|NotebookEdit",
#     "hooks": [{
#       "type": "command",
#       "command": "${CLAUDE_HOME:-$HOME/.claude}/scripts/hooks/pytest-loop-reset.sh",
#       "timeout": 2000
#     }]
#   }]

set -euo pipefail

TMPDIR="${CLAUDE_CODE_TMPDIR:-/tmp}"
SESSION_FILE="${TMPDIR}/claude-pytest-loop-session.id"

# Graceful no-op if session ID file doesn't exist
if [ ! -f "$SESSION_FILE" ]; then
  exit 0
fi

SESSION_UUID=$(tr -d '[:space:]' < "$SESSION_FILE")

if [ -z "$SESSION_UUID" ]; then
  exit 0
fi

COUNTER_FILE="${TMPDIR}/claude-pytest-loop-${SESSION_UUID}.count"

# Graceful no-op if counter file doesn't exist
if [ ! -f "$COUNTER_FILE" ]; then
  exit 0
fi

# Reset counter atomically
printf '%s\n' "0" > "${COUNTER_FILE}.tmp" && mv "${COUNTER_FILE}.tmp" "$COUNTER_FILE"

exit 0
