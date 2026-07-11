#!/usr/bin/env bash
# PreToolUse hook: enforce model defaults on Agent dispatches
#
# Agent types with model: in their .md frontmatter resolve correctly.
# Built-in types (general-purpose, Explore, Plan, claude) have no
# frontmatter, so they inherit the parent session's model — typically
# Opus. This hook catches those and injects model: sonnet.
#
# Requires: jq (silently passes through if unavailable — no override,
# no log entry, no error). Verify jq is installed if overrides stop
# appearing in the log.
#
# Log: ~/.local/share/claudefiles/model-overrides.jsonl
# Emits additionalContext so the orchestrating LLM can relay the
# override to the user.
#
# Hook wiring (settings.json):
#   "PreToolUse": [{
#     "matcher": "Agent",
#     "hooks": [{
#       "type": "command",
#       "command": "bash -c 'f=\"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/hooks/subagent-model-default.sh\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
#       "timeout": 2000
#     }]
#   }]

if ! command -v jq > /dev/null 2>&1; then
  exit 0
fi

input="$(cat || true)"
[ -z "$input" ] && exit 0

model="$(printf '%s' "$input" | jq -r '.tool_input.model // empty' 2> /dev/null)" || true
[ -n "$model" ] && exit 0

agent_type="$(printf '%s' "$input" | jq -r '.tool_input.subagent_type // empty' 2> /dev/null)" || true
desc="$(printf '%s' "$input" | jq -r '.tool_input.description // empty' 2> /dev/null)" || true

# Built-in agent types that have no .md frontmatter declaring model:.
# When no model is specified, these inherit the parent — typically Opus.
# Keep in sync with Claude Code's built-in agent types.
# Empty string = no subagent_type specified, defaults to general-purpose.
case "$agent_type" in
  general-purpose | Explore | Plan | claude | "") ;;
  *)
    exit 0
    ;;
esac

default_model="sonnet"
label="${agent_type:-default}"

original_input="$(printf '%s' "$input" | jq -c '.tool_input' 2> /dev/null)" || true
updated="$(printf '%s' "$original_input" | jq -c --arg m "$default_model" '. + {model: $m}' 2> /dev/null)" || true

if [ -z "$updated" ] || [ "$updated" = "null" ]; then
  exit 0
fi

log_dir="$HOME/.local/share/claudefiles"
log_file="$log_dir/model-overrides.jsonl"
mkdir -p "$log_dir"

session_id="$(printf '%s' "$input" | jq -r '.session_id // empty' 2> /dev/null)" || true
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

printf '%s\n' "$(jq -cn \
  --arg ts "$ts" \
  --arg session "$session_id" \
  --arg agent_type "$label" \
  --arg desc "$desc" \
  --arg model "$default_model" \
  '{timestamp: $ts, session: $session, agent_type: $agent_type, description: $desc, injected_model: $model}')" \
  >> "$log_file" 2> /dev/null

ctx="Model override: ${label} dispatch defaulted to ${default_model} (desc: ${desc})"

jq -cn \
  --arg ctx "$ctx" \
  --argjson updated "$updated" \
  '{hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "allow",
    permissionDecisionReason: "Injected default model for built-in agent type",
    additionalContext: $ctx,
    updatedInput: $updated
  }}'
