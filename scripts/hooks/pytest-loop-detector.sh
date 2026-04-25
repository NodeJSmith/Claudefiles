#!/usr/bin/env bash
# PreToolUse hook: deny pytest after repeated failures.
#
# Two independent counters, both session-scoped:
#
#   1. No-edit counter (threshold: 3, default)
#      Tracks consecutive pytest failures without any intervening code edit
#      (Edit/Write/MultiEdit/NotebookEdit). Resets on edit or success.
#
#   2. Total failure counter (threshold: 8, default)
#      Tracks total pytest failures since the last success. Does NOT reset on
#      edits — only on pytest success, manual bypass, or pytest-loop-reset.
#      Catches "edit → run → fail → edit → run → fail" flailing loops.
#
# Session scoping:
#   Session UUID is written to ${CLAUDE_CODE_TMPDIR:-/tmp}/claude-pytest-loop-session.id
#   by a SessionStart hook. Counter and status files are scoped by UUID.
#
# Files:
#   Counter file:  ${CLAUDE_CODE_TMPDIR:-/tmp}/claude-pytest-loop-<uuid>.count
#   Total file:    ${CLAUDE_CODE_TMPDIR:-/tmp}/claude-pytest-loop-<uuid>.total
#   Status file:   ${CLAUDE_CODE_TMPDIR:-/tmp}/claude-pytest-loop-<uuid>.status
#     (status file written by the PostToolUse Bash hook after each invocation)
#
# Override mechanisms:
#   CLAUDE_PYTEST_LOOP_BYPASS=1 — allow this run and reset both counters
#   pytest-loop-reset — bin script that clears both counter files
#
# Env var overrides:
#   CLAUDE_PYTEST_LOOP_MAX       — no-edit counter threshold (default 3)
#   CLAUDE_PYTEST_LOOP_TOTAL_MAX — total failure threshold (default 8)
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
TOTAL_FILE="${TMPDIR}/claude-pytest-loop-${SESSION_UUID}.total"
STATUS_FILE="${TMPDIR}/claude-pytest-loop-${SESSION_UUID}.status"

# Thresholds (env var overrides, sanitized to positive integers)
NO_EDIT_MAX="${CLAUDE_PYTEST_LOOP_MAX:-3}"
case "$NO_EDIT_MAX" in
  '' | *[!0-9]*) NO_EDIT_MAX=3 ;;
esac
TOTAL_MAX="${CLAUDE_PYTEST_LOOP_TOTAL_MAX:-8}"
case "$TOTAL_MAX" in
  '' | *[!0-9]*) TOTAL_MAX=8 ;;
esac

deny() {
  jq -cn --arg reason "$1" \
    '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":$reason}}'
  exit 0
}

reset_counter() {
  printf '%s\n' "0" > "${COUNTER_FILE}.tmp" && mv "${COUNTER_FILE}.tmp" "$COUNTER_FILE"
}

reset_total() {
  printf '%s\n' "0" > "${TOTAL_FILE}.tmp" && mv "${TOTAL_FILE}.tmp" "$TOTAL_FILE"
}

# --- Check env var bypass ---
if [ "${CLAUDE_PYTEST_LOOP_BYPASS:-}" = "1" ]; then
  reset_counter
  reset_total
  exit 0
fi

# --- Read previous exit code from status file ---
PREV_EXIT=0
if [ -f "$STATUS_FILE" ]; then
  PREV_EXIT=$(tr -d '[:space:]' < "$STATUS_FILE" || echo "0")
  case "$PREV_EXIT" in
    '' | *[!0-9]*) PREV_EXIT=0 ;;
  esac
fi

# --- If previous run was successful (exit 0), reset both counters and allow ---
if [ "$PREV_EXIT" = "0" ]; then
  reset_counter
  reset_total
  exit 0
fi

# --- Previous run failed — read and increment both counters ---
COUNT=0
if [ -f "$COUNTER_FILE" ]; then
  COUNT=$(tr -d '[:space:]' < "$COUNTER_FILE" || echo "0")
  case "$COUNT" in
    '' | *[!0-9]*) COUNT=0 ;;
  esac
fi

TOTAL=0
if [ -f "$TOTAL_FILE" ]; then
  TOTAL=$(tr -d '[:space:]' < "$TOTAL_FILE" || echo "0")
  case "$TOTAL" in
    '' | *[!0-9]*) TOTAL=0 ;;
  esac
fi

NEW_COUNT=$((COUNT + 1))
NEW_TOTAL=$((TOTAL + 1))

printf 'pytest-loop-detector: no-edit=%d/%s total=%d/%s\n' "$NEW_COUNT" "$NO_EDIT_MAX" "$NEW_TOTAL" "$TOTAL_MAX" >&2

# --- Deny if either threshold reached (before writing, so denied runs don't inflate counters) ---
if [ "$NEW_COUNT" -ge "$NO_EDIT_MAX" ]; then
  deny "DENIED: You've run pytest ${NEW_COUNT} times after a failure without making code changes. Use /mine.debug to investigate the root cause systematically. To override: set \`CLAUDE_PYTEST_LOOP_BYPASS=1\` or run \`pytest-loop-reset\`."
fi

if [ "$NEW_TOTAL" -ge "$TOTAL_MAX" ]; then
  deny "DENIED: pytest has failed ${NEW_TOTAL} times in this session, even with edits between runs. The edits aren't converging on a fix. Use /mine.debug to investigate the root cause systematically. To override: set \`CLAUDE_PYTEST_LOOP_BYPASS=1\` or run \`pytest-loop-reset\`."
fi

# --- Thresholds not reached — commit the increments ---
printf '%s\n' "$NEW_COUNT" > "${COUNTER_FILE}.tmp" && mv "${COUNTER_FILE}.tmp" "$COUNTER_FILE"
printf '%s\n' "$NEW_TOTAL" > "${TOTAL_FILE}.tmp" && mv "${TOTAL_FILE}.tmp" "$TOTAL_FILE"

# All checks passed — no opinion
exit 0
