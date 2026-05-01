#!/usr/bin/env bash
# PreToolUse hook: inject context window tier guidance
#
# Reads the sidecar file written by claude-context-writer (via statusLine),
# computes a behavioral tier, and emits additionalContext when the tier
# changes or on a periodic heartbeat. This prevents Claude from hallucinating
# context pressure at low usage and provides actionable guidance at higher usage.
#
# Tiers:
#   low      (<25%)  — reassurance: continue working normally
#   low-mid  (25-39%) — reassurance refresh (original low message has faded)
#   moderate (40-59%) — prefer subagents for large reads
#   high     (60-79%) — finish current task, delegate exploratory work
#   critical (80%+)   — compaction imminent, checkpoint or finish
#
# Heartbeat: even when the tier hasn't changed, re-inject the message every
# N tool calls (default 25, override via CLAUDE_CONTEXT_HEARTBEAT). This
# prevents the reassurance from scrolling out of context during long
# orchestrations, which caused Claude to fabricate context pressure and skip
# code reviews in practice.
#
# Hook wiring: add as a separate "PreToolUse" entry with matcher "*" in
# settings.json so it fires before any tool call, not just Bash.
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

# Heartbeat counter — re-inject even when tier is unchanged
heartbeat_interval="${CLAUDE_CONTEXT_HEARTBEAT:-25}"
case "$heartbeat_interval" in
  '' | *[!0-9]* | 0) heartbeat_interval=25 ;;
esac
counter_file="/tmp/claude-context-calls-${session_id}.txt"
count="$(cat "$counter_file" 2> /dev/null)" || true
count="${count:-0}"
case "$count" in *[!0-9]*) count=0 ;; esac
count=$((count + 1))

emit=false
if [ "$tier" != "$last_tier" ]; then
  emit=true
  count=0
elif [ "$count" -ge "$heartbeat_interval" ]; then
  emit=true
  count=0
fi

printf '%d' "$count" > "${counter_file}.tmp" 2> /dev/null && mv -f "${counter_file}.tmp" "$counter_file" 2> /dev/null || true

[ "$emit" = false ] && exit 0

# Tier changed or heartbeat fired — update state and emit guidance
printf '%s' "$tier" > "${tier_file}.tmp" 2> /dev/null && mv -f "${tier_file}.tmp" "$tier_file" 2> /dev/null || true
jq -cn --arg msg "$message" \
  '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":$msg}}'
