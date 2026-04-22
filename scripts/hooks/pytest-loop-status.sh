#!/usr/bin/env bash
# PostToolUse hook: record the Bash tool exit code for the pytest loop detector.
#
# After each Bash tool invocation, writes the exit code to a session-scoped
# status file. The pytest-loop-detector.sh PreToolUse hook reads this file to
# determine whether the previous pytest run succeeded or failed.
#
# Status file: ${CLAUDE_CODE_TMPDIR:-/tmp}/claude-pytest-loop-<uuid>.status
#
# Hook wiring (settings.json):
#   "PostToolUse": [{
#     "matcher": "Bash",
#     "hooks": [{
#       "type": "command",
#       "command": "${CLAUDE_HOME:-$HOME/.claude}/scripts/hooks/pytest-loop-status.sh",
#       "timeout": 2000
#     }]
#   }]

set -euo pipefail

INPUT=$(cat)

if ! command -v jq > /dev/null 2>&1; then
  printf 'pytest-loop-status: jq not found, skipping status write\n' >&2
  exit 0
fi

COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')

[ -z "$COMMAND" ] && exit 0

# Only record status for pytest invocations — non-pytest Bash commands must not
# overwrite the status file, or an intervening `ls` / `git` after a failed pytest
# would reset the failure signal and defeat loop detection.
# shellcheck source=pytest-detect.sh
. "$(dirname "$0")/pytest-detect.sh"

if ! is_pytest_invocation "$COMMAND"; then
  exit 0
fi

TMPDIR="${CLAUDE_CODE_TMPDIR:-/tmp}"
SESSION_FILE="${TMPDIR}/claude-pytest-loop-session.id"

if [ ! -f "$SESSION_FILE" ]; then
  exit 0
fi

SESSION_UUID=$(tr -d '[:space:]' < "$SESSION_FILE")

if [ -z "$SESSION_UUID" ]; then
  exit 0
fi

STATUS_FILE="${TMPDIR}/claude-pytest-loop-${SESSION_UUID}.status"

RAW=$(printf '%s' "$INPUT" | jq -r '.tool_response.exit_code // 0' 2> /dev/null || echo "0")
EXIT_CODE=0
case "$RAW" in
  '' | *[!0-9]*) EXIT_CODE=0 ;;
  *) EXIT_CODE="$RAW" ;;
esac

# Write status atomically
printf '%s\n' "$EXIT_CODE" > "${STATUS_FILE}.tmp" && mv "${STATUS_FILE}.tmp" "$STATUS_FILE"

exit 0
