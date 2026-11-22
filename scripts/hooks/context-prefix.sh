#!/usr/bin/env bash
# PreToolUse hook (AskUserQuestion): prefix the first question with the real
# context-window usage, as "[Context: N%] ".
#
# The number comes from the sidecar written by claude-context-writer, so the
# user sees the measured value rather than one the model typed. Any
# "[Context: N%]" the model wrote itself is stripped from every question
# first, so a stale habit can't produce a doubled or wrong prefix. With no
# sidecar (or a garbled one), the questions pass through with only the
# model-written prefixes removed.
#
# The rewrite goes out as hookSpecificOutput.updatedInput with no
# permissionDecision, which changes the question text without touching the
# permission flow. The answer comes back keyed on the rewritten question.
#
# Sidecar reading is shared with context-tier.sh and bin/context-pct via
# lib/context-sidecar.sh.
#
# Guard clauses exit 0 with no output, which leaves the tool input untouched.

if ! command -v jq > /dev/null 2>&1; then
  exit 0
fi

input="$(cat || true)"

# Only rewrite inputs that actually carry a questions array.
printf '%s' "$input" | jq -e '.tool_input.questions | type == "array" and length > 0' > /dev/null 2>&1 || exit 0

hook_dir="$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/context-sidecar.sh
source "$hook_dir/lib/context-sidecar.sh" || exit 0

session_id="$(printf '%s' "$input" | jq -r '.session_id // empty' 2> /dev/null)" || true
percent="$(context_sidecar_pct "$session_id")"

# Strip from every question, then prefix the first one only when a valid pct
# was read; an empty $pct leaves the questions unprefixed.
printf '%s' "$input" | jq -c --arg pct "$percent" '
  def strip: sub("^\\s*\\[Context:\\s*[0-9]+%\\]\\s*"; "");
  .tool_input
  | .questions |= (map(.question |= (tostring | strip))
                   | if $pct == "" then . else .[0].question = "[Context: \($pct)%] " + .[0].question end)
  | {hookSpecificOutput: {hookEventName: "PreToolUse", updatedInput: .}}
' 2> /dev/null || exit 0
