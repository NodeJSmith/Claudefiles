#!/usr/bin/env bash
# PreToolUse hook: deny-then-poll for sudo commands.
#
# When a Bash command contains "sudo":
#   1. If sudo creds are already cached → allow immediately
#   2. If not → print instructions to stderr, poll for up to 30s
#   3. If creds appear during polling → allow
#   4. If timeout → deny with instructions
#
# Requires:
#   - jq (for parsing hook input)
#   - sudoers: Defaults timestamp_type=global
#     (shares credential cache across TTYs so `sudo -v` in another pane works)
#
# Hook wiring (settings.json):
#   "PreToolUse": [{
#     "matcher": "Bash",
#     "hooks": [{
#       "type": "command",
#       "command": "${CLAUDE_HOME:-$HOME/.claude}/scripts/hooks/sudo-poll.sh",
#       "timeout": 35000
#     }]
#   }]

set -euo pipefail

# Validate timeout is a non-negative integer, capped at 30s
# (harness timeout is 35000ms — hook must finish before SIGKILL)
RAW_TIMEOUT="${CLAUDE_SUDO_POLL_TIMEOUT:-30}"
case "$RAW_TIMEOUT" in
  '' | *[!0-9]*) TIMEOUT=30 ;;
  *) TIMEOUT="$RAW_TIMEOUT" ;;
esac
if [ "$TIMEOUT" -gt 30 ]; then
  printf 'warning: CLAUDE_SUDO_POLL_TIMEOUT=%s exceeds 30s harness limit, capping to 30\n' "$TIMEOUT" >&2
  TIMEOUT=30
fi

# Read hook input from stdin
INPUT=$(cat)

# jq is required to parse hook input — fail clearly, not cryptically
if ! command -v jq > /dev/null 2>&1; then
  printf 'ERROR: jq is required by scripts/hooks/sudo-poll.sh. Install jq or remove this hook.\n' >&2
  printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"jq is required by scripts/hooks/sudo-poll.sh. Install jq or remove this hook."}}'
  exit 0
fi

COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')

# Not a sudo command — no opinion, pass through
if ! printf '%s' "$COMMAND" | grep -q 'sudo '; then
  exit 0
fi

allow() {
  jq -cn --arg reason "$1" \
    '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":$reason}}'
  exit 0
}

deny() {
  jq -cn --arg reason "$1" \
    '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":$reason}}'
  exit 0
}

# sudo must be installed for any of this to work
if ! command -v sudo > /dev/null 2>&1; then
  deny "sudo is not installed on this system."
fi

# Creds already cached — allow immediately
if sudo -n true 2> /dev/null; then
  allow "Sudo credentials cached."
fi

# Not cached — tell user and poll
printf '⏳ Sudo credentials needed. Run \047sudo -v\047 in another terminal pane...\n' >&2
trap 'deny "Sudo poll interrupted; run sudo -v and retry."' INT TERM

elapsed=0
while [ "$elapsed" -lt "$TIMEOUT" ]; do
  sleep 1
  elapsed=$((elapsed + 1))
  if sudo -n true 2> /dev/null; then
    printf '✓ Sudo credentials detected.\n' >&2
    allow "Sudo credentials cached after polling (${elapsed}s)."
  fi
done

deny "Sudo credentials not cached. Run sudo -v in another terminal and try again. (Timed out after ${TIMEOUT}s)"
