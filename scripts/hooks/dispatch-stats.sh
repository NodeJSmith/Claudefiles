#!/usr/bin/env bash
# PostToolUse hook: write subagent telemetry stats for cfl dispatch correlation
#
# After each Agent tool invocation, extracts token usage from the hook input
# and compaction count from the subagent's JSONL, then writes a stats file
# that `cfl dispatch end --tool-use-id` picks up automatically.
#
# Stats file: ${CLAUDE_CODE_TMPDIR:-/tmp}/cfl-dispatch-stats/<session_id>-<tool_use_id>.json
#
# Hook wiring (settings.json):
#   "PostToolUse": [{
#     "matcher": "Agent",
#     "hooks": [{
#       "type": "command",
#       "command": "bash -c 'f=\"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/hooks/dispatch-stats.sh\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
#       "timeout": 5000
#     }]
#   }]

if ! command -v jq > /dev/null 2>&1; then
  exit 0
fi

input="$(cat || true)"

session_id="$(printf '%s' "$input" | jq -r '.session_id // empty' 2> /dev/null)" || true
[ -z "$session_id" ] && exit 0

tool_use_id="$(printf '%s' "$input" | jq -r '.tool_use_id // empty' 2> /dev/null)" || true
[ -z "$tool_use_id" ] && exit 0

# Extract token usage from tool_response.usage (already computed by Claude Code)
tokens_in="$(printf '%s' "$input" | jq -r '.tool_response.usage.input_tokens // 0' 2> /dev/null)" || true
tokens_out="$(printf '%s' "$input" | jq -r '.tool_response.usage.output_tokens // 0' 2> /dev/null)" || true

# Find the subagent JSONL via agentId
agent_id="$(printf '%s' "$input" | jq -r '.tool_response.agentId // empty' 2> /dev/null)" || true
transcript_path="$(printf '%s' "$input" | jq -r '.transcript_path // empty' 2> /dev/null)" || true

compactions=0
jsonl_path=""

if [ -n "$agent_id" ] && [ -n "$transcript_path" ]; then
  subagent_dir="${transcript_path%.jsonl}/subagents"
  candidate="$subagent_dir/agent-${agent_id}.jsonl"
  if [ -f "$candidate" ]; then
    jsonl_path="$candidate"
    # Count real compact_boundary events (same validation as subagent-compaction-check.sh)
    compactions="$(grep '"compact_boundary"' "$candidate" 2> /dev/null | python3 -c "
import sys, json
count = 0
for line in sys.stdin:
    try:
        obj = json.loads(line.strip())
        if obj.get('compactMetadata', {}).get('preTokens', 0) > 0:
            count += 1
    except (json.JSONDecodeError, ValueError):
        pass
print(count)
" 2> /dev/null)" || compactions=0
  fi
fi

# Write stats file (reap stale files >1h old on each invocation)
stats_dir="${CLAUDE_CODE_TMPDIR:-/tmp}/cfl-dispatch-stats"
mkdir -p "$stats_dir" 2> /dev/null || exit 0
find "$stats_dir" -name "*.json" -mmin +60 -delete 2> /dev/null || true

stats_file="$stats_dir/${session_id}-${tool_use_id}.json"

jq -cn \
  --argjson tokens_in "${tokens_in:-0}" \
  --argjson tokens_out "${tokens_out:-0}" \
  --argjson compactions "$compactions" \
  --arg jsonl_path "$jsonl_path" \
  '{
    tokens_in: $tokens_in,
    tokens_out: $tokens_out,
    compactions: $compactions,
    jsonl_path: $jsonl_path
  }' > "$stats_file" 2> /dev/null || exit 0

exit 0
