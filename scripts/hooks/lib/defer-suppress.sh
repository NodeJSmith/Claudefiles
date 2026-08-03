#!/usr/bin/env bash
# Shared read-side check for hooks using the escalating defer/suppress
# state-file pattern (3/7/14/30 day deferral, or permanent suppression).
#
# State file format:
#   {"status": "suppressed"}
#   {"status": "deferred", "tier": <int>, "prompt_after": "<YYYY-MM-DD>"}
#
# Usage (caller sources this, then):
#   defer_suppress_should_skip "$state_file" && exit 0
#
# Requires python3 on PATH — callers already guard this before reaching
# the check, so it isn't re-checked here.
#
# The write side (choosing a tier, computing the next prompt_after, writing
# suppressed) is done by Claude itself at runtime per each hook's embedded
# AskUserQuestion instructions, not by this script.

defer_suppress_should_skip() {
  local state_file="$1"
  [ -f "$state_file" ] || return 1

  local status prompt_after
  read -r status prompt_after < <(python3 -c "
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    print(d.get('status', ''), d.get('prompt_after', ''))
except (OSError, json.JSONDecodeError):
    print('', '')
" "$state_file" 2> /dev/null)

  [ "$status" = "suppressed" ] && return 0

  if [ "$status" = "deferred" ]; then
    local today
    today=$(date +%Y-%m-%d)
    # Lexicographic comparison works because YYYY-MM-DD is zero-padded
    if [ -n "$prompt_after" ] && [[ "$today" < "$prompt_after" ]]; then
      return 0
    fi
  fi

  return 1
}
