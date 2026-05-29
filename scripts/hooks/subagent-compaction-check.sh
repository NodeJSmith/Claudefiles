#!/usr/bin/env bash
# PostToolUse hook: detect subagent compaction events
#
# After each Agent tool invocation, scans the subagent's JSONL file for
# compact_boundary entries. If found, injects a warning into the parent's
# context so the orchestrator knows the subagent hit its context window limit.
#
# This matters because compaction degrades reasoning quality — a subagent that
# compacted mid-task may have lost file references, prior decisions, or test
# output context. The orchestrator can then decide whether to re-run with a
# smaller scope or flag the task as potentially degraded.
#
# State file: ${CLAUDE_CODE_TMPDIR:-/tmp}/claude-subagent-compaction-<session_id>.txt
#   Tracks which subagent files have already been reported to avoid duplicate
#   warnings across multiple Agent tool calls in the same session.
#
# See also: skills/mine.orchestrate/SKILL.md "Resuming after context compaction"
#   for parent-compaction handling (a separate concern from subagent compaction).
#
# Hook wiring (settings.json):
#   "PostToolUse": [{
#     "matcher": "Agent",
#     "hooks": [{
#       "type": "command",
#       "command": "bash -c 'f=\"${CLAUDE_HOME:-$HOME/.claude}/scripts/hooks/subagent-compaction-check.sh\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
#       "timeout": 5000
#     }]
#   }]
#
# No set -euo pipefail — this hook is a sequence of guard clauses that each
# exit 0 on failure, same as context-tier.sh.

if ! command -v jq > /dev/null 2>&1; then
  exit 0
fi

input="$(cat || true)"

session_id="$(printf '%s' "$input" | jq -r '.session_id // empty' 2> /dev/null)" || true
case "$session_id" in '' | *[/.]*) exit 0 ;; esac

transcript_path="$(printf '%s' "$input" | jq -r '.transcript_path // empty' 2> /dev/null)" || true
[ -z "$transcript_path" ] && exit 0

# Claude Code transcript paths always end in .jsonl; subagent files live in a
# sibling directory named <session-uuid>/subagents/.
subagent_dir="${transcript_path%.jsonl}/subagents"
[ -d "$subagent_dir" ] || exit 0

state_dir="${CLAUDE_CODE_TMPDIR:-/tmp}"
reported_file="${state_dir}/claude-subagent-compaction-${session_id}.txt"
touch "$reported_file" 2> /dev/null || exit 0

warnings=""

for agent_file in "$subagent_dir"/agent-*.jsonl; do
  [ -f "$agent_file" ] || continue

  filename="$(basename "$agent_file")"

  grep -qF "$filename" "$reported_file" 2> /dev/null && continue

  # Python for the thousands-separator formatting ({pre:,}) that jq can't do
  stats="$(grep '"compact_boundary"' "$agent_file" 2> /dev/null | python3 -c "
import sys, json
events = []
for line in sys.stdin:
    try:
        obj = json.loads(line.strip())
        meta = obj.get('compactMetadata', {})
        pre = meta.get('preTokens', 0)
        post = meta.get('postTokens', 0)
        if pre > 0 and post > 0:
            events.append(f'{pre:,} -> {post:,} tokens ({post/pre*100:.0f}% retained)')
        elif pre > 0:
            events.append(f'{pre:,} tokens (post-compact size not recorded)')
    except (json.JSONDecodeError, ValueError):
        pass
if events:
    print(' | '.join(events))
" 2> /dev/null)" || true

  [ -z "$stats" ] && continue

  meta_file="${agent_file%.jsonl}.meta.json"
  agent_desc="$filename"
  if [ -f "$meta_file" ]; then
    desc="$(jq -r '.description // empty' "$meta_file" 2> /dev/null)" || true
    [ -n "$desc" ] && agent_desc="$desc"
  fi

  if [ -n "$warnings" ]; then
    warnings="${warnings}; ${agent_desc}: ${stats}"
  else
    warnings="${agent_desc}: ${stats}"
  fi

  printf '%s\n' "$filename" >> "$reported_file" 2> /dev/null || true
done

[ -z "$warnings" ] && exit 0

message="Subagent compaction detected — ${warnings}. This is an observed event, not inferred context pressure. The subagent may have lost file references or decision context during compaction."
jq -cn --arg msg "$message" \
  '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":$msg}}'
