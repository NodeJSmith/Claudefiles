#!/usr/bin/env bash
# PostToolUse hook: write subagent telemetry stats for cfl dispatch correlation
#
# After each Agent tool invocation, extracts token usage from the hook input
# and compaction count from the subagent's JSONL, then writes a stats file
# keyed by cfl_dispatch_id (extracted from the subagent prompt).
#
# Stats file: ${CLAUDE_CODE_TMPDIR:-/tmp}/cfl-dispatch-stats/<dispatch_id>.json
#
# Non-orchestrate Agent calls (no cfl_dispatch_id in prompt) are silently skipped.
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

# Extract all fields in one jq invocation (tab-separated)
_fields="$(printf '%s' "$input" | jq -r '[
  (.tool_use_id // ""),
  (.tool_response.usage.input_tokens // 0 | tostring),
  (.tool_response.usage.output_tokens // 0 | tostring),
  (.tool_response.agentId // ""),
  (.transcript_path // ""),
  ((.tool_input.prompt // "") | capture("cfl_dispatch_id: (?<id>[0-9]+)") // {} | .id // "")
] | join("\t")' 2> /dev/null)" || exit 0

IFS=$'\t' read -r tool_use_id tokens_in tokens_out agent_id transcript_path dispatch_id <<< "$_fields"
[ -z "$dispatch_id" ] && exit 0

compactions=0
jsonl_path=""

if [ -n "$agent_id" ] && [ -n "$transcript_path" ]; then
  subagent_dir="${transcript_path%.jsonl}/subagents"
  candidate="$subagent_dir/agent-${agent_id}.jsonl"
  if [ -f "$candidate" ]; then
    jsonl_path="$candidate"
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

# Write stats file keyed by dispatch_id (reap stale files >1h old)
stats_dir="${CLAUDE_CODE_TMPDIR:-/tmp}/cfl-dispatch-stats"
mkdir -p "$stats_dir" 2> /dev/null || exit 0
find "$stats_dir" -name "*.json" -mmin +60 -delete 2> /dev/null || true

stats_file="$stats_dir/${dispatch_id}.json"
tmp_file="$stats_dir/.tmp-${dispatch_id}.json"
jq -cn \
  --arg tool_use_id "$tool_use_id" \
  --argjson tokens_in "${tokens_in:-0}" \
  --argjson tokens_out "${tokens_out:-0}" \
  --argjson compactions "$compactions" \
  --arg jsonl_path "$jsonl_path" \
  '{
    tool_use_id: (if $tool_use_id == "" then null else $tool_use_id end),
    tokens_in: $tokens_in,
    tokens_out: $tokens_out,
    compactions: $compactions,
    jsonl_path: $jsonl_path
  }' > "$tmp_file" 2> /dev/null && mv "$tmp_file" "$stats_file" 2> /dev/null || exit 0

exit 0
