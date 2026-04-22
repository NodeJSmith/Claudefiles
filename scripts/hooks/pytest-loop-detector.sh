#!/usr/bin/env bash
# PreToolUse hook: deny pytest after 3 consecutive post-failure runs without code changes.
#
# Tracks consecutive pytest runs that follow a failure, without any intervening
# code edits (Edit/Write/MultiEdit/NotebookEdit). Denies at >= 3 and nudges
# Claude to use /mine.debug for systematic root-cause investigation.
#
# Session scoping:
#   Session UUID is written to ${CLAUDE_CODE_TMPDIR:-/tmp}/claude-pytest-loop-session.id
#   by a SessionStart hook. Counter and status files are scoped by UUID.
#
# Counter file:  ${CLAUDE_CODE_TMPDIR:-/tmp}/claude-pytest-loop-<uuid>.count
# Status file:   ${CLAUDE_CODE_TMPDIR:-/tmp}/claude-pytest-loop-<uuid>.status
#   (status file written by the PostToolUse Bash hook after each invocation)
#
# Override mechanisms:
#   CLAUDE_PYTEST_LOOP_BYPASS=1 — allow this run and reset the counter
#   pytest-loop-reset — bin script that clears the counter file
#
# Hook wiring (settings.json):
#   "PreToolUse": [{
#     "matcher": "Bash",
#     "hooks": [{
#       "type": "command",
#       "command": "${CLAUDE_HOME:-$HOME/.claude}/scripts/hooks/pytest-loop-detector.sh",
#       "timeout": 5000
#     }]
#   }]

set -euo pipefail

INPUT=$(cat)

if ! command -v jq > /dev/null 2>&1; then
  printf 'ERROR: jq is required by pytest-loop-detector.sh. Install jq or remove this hook.\n' >&2
  exit 0
fi

COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')

[ -z "$COMMAND" ] && exit 0

# --- Detect whether this command actually runs pytest ---
# Shared detection patterns (also used by pytest-loop-status.sh)
# shellcheck source=pytest-detect.sh
. "$(dirname "$0")/pytest-detect.sh"

if ! is_pytest_invocation "$COMMAND"; then
  exit 0
fi

# --- From here on, we know it's a pytest invocation ---

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
STATUS_FILE="${TMPDIR}/claude-pytest-loop-${SESSION_UUID}.status"

deny() {
  jq -cn --arg reason "$1" \
    '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":$reason}}'
  exit 0
}

reset_counter() {
  printf '%s\n' "0" > "${COUNTER_FILE}.tmp" && mv "${COUNTER_FILE}.tmp" "$COUNTER_FILE"
}

# --- Check env var bypass ---
if [ "${CLAUDE_PYTEST_LOOP_BYPASS:-}" = "1" ]; then
  reset_counter
  exit 0
fi

# --- Read previous exit code from status file ---
PREV_EXIT=0
if [ -f "$STATUS_FILE" ]; then
  PREV_EXIT=$(tr -d '[:space:]' < "$STATUS_FILE" || echo "0")
  # Default to 0 if not a number
  case "$PREV_EXIT" in
    '' | *[!0-9]*) PREV_EXIT=0 ;;
  esac
fi

# --- If previous run was successful (exit 0), reset counter and allow ---
if [ "$PREV_EXIT" = "0" ]; then
  reset_counter
  exit 0
fi

# --- Previous run failed — read and increment counter ---
COUNT=0
if [ -f "$COUNTER_FILE" ]; then
  COUNT=$(tr -d '[:space:]' < "$COUNTER_FILE" || echo "0")
  case "$COUNT" in
    '' | *[!0-9]*) COUNT=0 ;;
  esac
fi

NEW_COUNT=$((COUNT + 1))

# Write new count atomically
printf '%s\n' "$NEW_COUNT" > "${COUNTER_FILE}.tmp" && mv "${COUNTER_FILE}.tmp" "$COUNTER_FILE"
printf 'pytest-loop-detector: failure counter = %d\n' "$NEW_COUNT" >&2

# --- Deny if threshold reached ---
if [ "$NEW_COUNT" -ge 3 ]; then
  deny "DENIED: You've run pytest ${NEW_COUNT} times after a failure without making code changes. Use /mine.debug to investigate the root cause systematically. To override: set \`CLAUDE_PYTEST_LOOP_BYPASS=1\` or run \`pytest-loop-reset\`."
fi

# All checks passed — no opinion
exit 0
