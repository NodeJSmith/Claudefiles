#!/usr/bin/env bash
# Shared read-side check for hooks using the escalating defer/suppress
# state-file pattern (3/7/14/30 day deferral, or permanent suppression).
#
# State file format:
#   {"status": "suppressed"}
#   {"status": "deferred", "tier": <int>, "prompt_after": "<YYYY-MM-DD>"}
#   {"status": "resolved"}
#
# "resolved" is for callers whose check can be satisfied by something other
# than the user's answer to the prompt -- e.g. project-docs-check.sh writes
# it when Claude's own search finds the condition (docs already exist) was
# already true, so future sessions skip re-running that search. Skip effect
# is identical to "suppressed"; kept as a separate value so a human reading
# the state file can tell "the condition was already met" apart from "the
# user said stop asking." Same permanence caveat as "suppressed": if the
# docs this was resolved against get deleted, nothing re-checks until the
# state file is removed.
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

  case "$status" in
    suppressed | resolved) return 0 ;;
  esac

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
