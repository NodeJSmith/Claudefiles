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

TIMEOUT="${CLAUDE_SUDO_POLL_TIMEOUT:-30}"

# Read hook input from stdin
INPUT=$(cat)
COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')

# Not a sudo command — no opinion, pass through
if ! printf '%s' "$COMMAND" | grep -qw 'sudo'; then
  exit 0
fi

allow() {
  jq -cn --arg reason "$1" \
    '{"hookSpecificOutput":{"permissionDecision":"allow","permissionDecisionReason":$reason}}'
  exit 0
}

deny() {
  jq -cn --arg reason "$1" \
    '{"hookSpecificOutput":{"permissionDecision":"deny","permissionDecisionReason":$reason}}'
  exit 0
}

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
