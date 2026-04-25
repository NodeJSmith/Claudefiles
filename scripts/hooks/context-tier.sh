#!/usr/bin/env bash
# PreToolUse hook: inject context window tier guidance
#
# Reads the sidecar file written by claude-context-writer (via statusLine),
# computes a behavioral tier, and emits additionalContext only when the tier
# changes. This prevents Claude from hallucinating context pressure at low
# usage and provides actionable guidance at higher usage.
#
# Tiers:
#   low      (<25%)  — reassurance: continue working normally
#   low-mid  (25-39%) — reassurance refresh (original low message has faded)
#   moderate (40-59%) — prefer subagents for large reads
#   high     (60-79%) — finish current task, delegate exploratory work
#   critical (80%+)   — compaction imminent, checkpoint or finish
#
# Hook wiring: append to the existing "PreToolUse" > "Bash" hooks array
# in settings.json (alongside sudo-poll, pytest-guard, pytest-loop-detector).
#
# No set -euo pipefail — this hook is a sequence of guard clauses that each
# exit 0 on failure. Every operation has an explicit failure path; adding -e
# then sprinkling || true everywhere is noisier for no correctness gain.

if ! command -v jq > /dev/null 2>&1; then
  exit 0
fi

input="$(cat || true)"

session_id="$(printf '%s' "$input" | jq -r '.session_id // empty' 2> /dev/null)" || true
case "$session_id" in '' | *[/.]*) exit 0 ;; esac

# Hardcodes /tmp/ to match claude-context-writer, which runs outside Claude
# Code's sandbox and cannot use CLAUDE_CODE_TMPDIR.
sidecar="/tmp/claude-context-${session_id}.txt"
[ -f "$sidecar" ] || exit 0

percent="$(cat "$sidecar" 2> /dev/null)" || exit 0
[ -z "$percent" ] && exit 0

# Validate numeric
case "$percent" in
  *[!0-9]*) exit 0 ;;
esac

if [ "$percent" -lt 25 ]; then
  tier="low"
  message="Context: low usage (${percent}%). Continue working normally."
elif [ "$percent" -lt 40 ]; then
  tier="low-mid"
  message="Context: low usage (${percent}%). Plenty of room — continue working normally."
elif [ "$percent" -lt 60 ]; then
  tier="moderate"
  message="Context: moderate usage (${percent}%). Prefer subagents for large file reads."
elif [ "$percent" -lt 80 ]; then
  tier="high"
  message="Context: high usage (${percent}%). Finish current task, delegate exploratory work to subagents."
else
  tier="critical"
  message="Context: critical usage (${percent}%). Compaction imminent — checkpoint or finish up."
fi

tier_file="/tmp/claude-context-tier-${session_id}.txt"
last_tier="$(cat "$tier_file" 2> /dev/null)" || true

[ "$tier" = "$last_tier" ] && exit 0

# Tier changed — update state and emit guidance
printf '%s' "$tier" > "$tier_file" 2> /dev/null || true
printf '%s\n' "$message"
