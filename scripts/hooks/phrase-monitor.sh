#!/usr/bin/env bash
# PreToolUse hook: monitor assistant messages for concerning rationalization phrases
#
# Reads the transcript to check what Claude just said, scores it against a
# weighted phrase dictionary, and logs detections. Observation mode only —
# does not intervene or inject corrections. Future versions may add blocking
# or additionalContext injection once false positive rates are understood.
#
# Categories monitored:
#   context_pressure  — fabricating context window urgency
#   minimize_changes  — avoiding work to touch fewer files
#   simplicity_excuse — choosing worse approaches for "simplicity"
#   scope_avoidance   — preemptively limiting scope
#   avoid_refactor    — explicitly avoiding needed refactoring
#   backward_compat   — citing backward compatibility to avoid proper fixes
#
# Fires every N tool calls (default 5, override via CLAUDE_PHRASE_MONITOR_INTERVAL).
# Lower than other hooks because we need to catch phrases close to when they
# appear, not 25 tool calls later.
#
# Log output: /tmp/claude-phrase-monitor.log (append-only, survives across sessions)
# Format: ISO8601<tab>session_id<tab>category<tab>score<tab>matched_phrase<tab>excerpt
#
# Notifications: pushes to ntfy when detections occur (batched per check cycle).
# Requires NTFY_TOKEN env var. Topic: claude (at ntfy.smithfamily.dev).
# Disable notifications: set CLAUDE_PHRASE_MONITOR_NOTIFY=0
#
# Hook wiring: PreToolUse with matcher "*", timeout 3000 (higher than the
# 2000ms sibling hooks due to transcript parsing + grep loops + curl)
#
# No set -euo pipefail — guard clause style, same as context-tier.sh.

umask 077

if ! command -v jq > /dev/null 2>&1; then
  exit 0
fi

input="$(cat || true)"

session_id="$(printf '%s' "$input" | jq -r '.session_id // empty' 2> /dev/null)" || true
case "$session_id" in '' | *[/.]*) exit 0 ;; esac

transcript_path="$(printf '%s' "$input" | jq -r '.transcript_path // empty' 2> /dev/null)" || true
[ -f "$transcript_path" ] || exit 0

# Heartbeat — check every N tool calls (default 5)
heartbeat_interval="${CLAUDE_PHRASE_MONITOR_INTERVAL:-5}"
case "$heartbeat_interval" in
  '' | *[!0-9]* | 0) heartbeat_interval=5 ;;
esac
counter_file="/tmp/claude-phrase-monitor-calls-${session_id}.txt"
count="$(cat "$counter_file" 2> /dev/null)" || true
count="${count:-0}"
case "$count" in *[!0-9]*) count=0 ;; esac
count=$((count + 1))

printf '%d' "$count" > "${counter_file}.tmp" 2> /dev/null && mv -f "${counter_file}.tmp" "$counter_file" 2> /dev/null || true

[ "$count" -ge "$heartbeat_interval" ] || exit 0

# Reset counter
printf '0' > "${counter_file}.tmp" 2> /dev/null && mv -f "${counter_file}.tmp" "$counter_file" 2> /dev/null || true

# Track which messages we've already scanned to avoid duplicate logs
seen_file="/tmp/claude-phrase-monitor-seen-${session_id}.txt"
seen_count="$(cat "$seen_file" 2> /dev/null)" || true
seen_count="${seen_count:-0}"
case "$seen_count" in *[!0-9]*) seen_count=0 ;; esac

# Extract assistant messages we haven't seen yet
# The transcript is JSONL — each line is a message object
total_lines="$(wc -l < "$transcript_path" 2> /dev/null)" || exit 0
# Reset if transcript was recreated (total_lines < seen_count)
[ "$total_lines" -ge "$seen_count" ] || seen_count=0
[ "$total_lines" -gt "$seen_count" ] || exit 0

# Read only new lines, filter to assistant text content
new_text="$(tail -n +"$((seen_count + 1))" "$transcript_path" 2> /dev/null |
  jq -r 'select(.type == "assistant") | .message.content[]? | select(.type == "text") | .text // empty' 2> /dev/null)" || true

[ -n "$new_text" ] || {
  printf '%d' "$total_lines" > "${seen_file}.tmp" 2> /dev/null && mv -f "${seen_file}.tmp" "$seen_file" 2> /dev/null || true
  exit 0
}

# Update seen count
printf '%d' "$total_lines" > "${seen_file}.tmp" 2> /dev/null && mv -f "${seen_file}.tmp" "$seen_file" 2> /dev/null || true

# Global, not session-scoped — intentionally accumulates across sessions for trend analysis
log_file="/tmp/claude-phrase-monitor.log"
notify_log="/tmp/claude-phrase-monitor-notify-${session_id}.txt"
now="$(date -u +%Y-%m-%dT%H:%M:%SZ 2> /dev/null)" || now="unknown"

# Notification settings
ntfy_url="${CLAUDE_PHRASE_MONITOR_NTFY_URL:-https://ntfy.smithfamily.dev/claude}"
notify_enabled="${CLAUDE_PHRASE_MONITOR_NOTIFY:-1}"
case "$notify_enabled" in 0 | false | no) notify_enabled=0 ;; *) notify_enabled=1 ;; esac

# Convert to lowercase for case-insensitive matching
lower_text="$(printf '%s' "$new_text" | tr '[:upper:]' '[:lower:]')"

# --- Phrase dictionary ---
# On match: log category, matched phrase, and a short excerpt

detection_count=0

log_match() {
  local category="$1" phrase="$2" score="$3"
  local excerpt
  excerpt="$(printf '%s' "$new_text" | grep -oi -m1 ".\{0,60\}${phrase}.\{0,60\}" 2> /dev/null | head -1)" || true
  [ -z "$excerpt" ] && excerpt="$(printf '%s' "$new_text" | head -c 120)"
  excerpt="$(printf '%s' "$excerpt" | tr '\n\t' '  ')"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$now" "$session_id" "$category" "$score" "$phrase" "$excerpt" >> "$log_file" 2> /dev/null || true
  # Accumulate for notification (skip if notifications disabled to avoid leaking tmp files)
  [ "$notify_enabled" = 1 ] && printf '%s [%s] %s\n' "$category" "$phrase" "$excerpt" >> "$notify_log" 2> /dev/null || true
  detection_count=$((detection_count + 1))
}

# Category: context_pressure (weight: 3 — near-zero false positives)
for phrase in \
  "context is getting" \
  "running low on context" \
  "context window" \
  "context is heavy" \
  "context is large" \
  "context is loaded" \
  "context is substantial" \
  "fresh context" \
  "fresh session" \
  "new context window" \
  "context for the remaining" \
  "good stopping point" \
  "natural pause" \
  "pause point" \
  "running out of context" \
  "context space"; do
  if printf '%s' "$lower_text" | grep -qF "$phrase" 2> /dev/null; then
    log_match "context_pressure" "$phrase" 3
  fi
done

# Category: minimize_changes (weight: 2 — medium false positive rate)
for phrase in \
  "but that would require" \
  "but this would require" \
  "but that means changing" \
  "less invasive" \
  "minimal change" \
  "minimal fix" \
  "avoid touching" \
  "without having to" \
  "instead of modifying"; do
  if printf '%s' "$lower_text" | grep -qF "$phrase" 2> /dev/null; then
    log_match "minimize_changes" "$phrase" 2
  fi
done

# Category: simplicity_excuse (weight: 1 — high false positive rate)
for phrase in \
  "to keep things simple" \
  "for simplicity" \
  "simpler approach" \
  "quick fix"; do
  if printf '%s' "$lower_text" | grep -qF "$phrase" 2> /dev/null; then
    log_match "simplicity_excuse" "$phrase" 1
  fi
done

# Category: scope_avoidance (weight: 1 — very high false positive rate)
for phrase in \
  "out of scope" \
  "beyond the scope" \
  "outside the scope" \
  "scope creep"; do
  if printf '%s' "$lower_text" | grep -qF "$phrase" 2> /dev/null; then
    log_match "scope_avoidance" "$phrase" 1
  fi
done

# Category: avoid_refactor (weight: 2 — lower false positive rate)
for phrase in \
  "rather than refactor" \
  "instead of refactor" \
  "avoid refactor" \
  "would require refactor" \
  "would require a refactor" \
  "more refactoring"; do
  if printf '%s' "$lower_text" | grep -qF "$phrase" 2> /dev/null; then
    log_match "avoid_refactor" "$phrase" 2
  fi
done

# Category: backward_compat (weight: 2 — check for rationalization context)
for phrase in \
  "backward compatibility" \
  "backwards compatibility" \
  "backward compat" \
  "backwards compat"; do
  if printf '%s' "$lower_text" | grep -qF "$phrase" 2> /dev/null; then
    log_match "backward_compat" "$phrase" 2
  fi
done

# Send batched notification if any detections occurred
if [ "$detection_count" -gt 0 ] && [ "$notify_enabled" = 1 ]; then
  ntfy_token="${NTFY_TOKEN:-}"
  if [ -n "$ntfy_token" ] && [ -f "$notify_log" ]; then
    notify_body="$(cat "$notify_log" 2> /dev/null)"
    hostname="$(hostname -s 2> /dev/null)" || hostname="unknown"
    cwd="$(printf '%s' "$input" | jq -r '.cwd // empty' 2> /dev/null)" || true
    curl -sf -o /dev/null \
      -H "Title: Phrase Monitor: ${detection_count} detection(s)" \
      -H "Priority: 2" \
      -H "Authorization: Bearer ${ntfy_token}" \
      -H "Tags: eyes" \
      -H "X-Markdown: 1" \
      --data-binary "${hostname} ${cwd}
${notify_body}" \
      "$ntfy_url" 2> /dev/null || true
  fi
  rm -f "$notify_log" 2> /dev/null || true
fi

exit 0
