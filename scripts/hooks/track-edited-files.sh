#!/usr/bin/env bash
# PostToolUse hook: track files edited by this session.
#
# Appends the touched file path to a session-local tracking file whenever
# Write, Edit, or NotebookEdit is used. Allows any Claude Code instance to
# know which files it modified, even when multiple instances share the same
# project directory.
#
# Storage: $CLAUDE_HOME/file-tracking/<project-slug>/<session-id>/files-touched.txt
# Format:  <ISO-8601 timestamp>\t<absolute-path>
# Dedup:   The same path may appear multiple times (one entry per tool invocation).
#          Consumers that want unique files should deduplicate on read:
#            cut -f2 | sort -u                 # unique paths only
#            awk -F'\t' '!seen[$2]++'          # unique paths, first-seen order
#          Timestamps are preserved for consumers needing temporal ordering.
#
# Consumed by: (planned — see issue tracking consumer work)
#
# Wiring (settings.json):
#   "PostToolUse": [{ "matcher": "Write|Edit|NotebookEdit", ... }]
#
# CLAUDE_SESSION_ID note: The CLAUDE.md warning about this variable applies to
# SKILL.md template substitution (which doesn't propagate to subagents or Bash
# tool calls). Hooks run as subprocesses of the Claude Code process, which sets
# CLAUDE_SESSION_ID as an environment variable — it is reliably available here.
#
# No set -euo pipefail — this is a tracking hook; failure must not block edits.

# Require jq for JSON parsing — silently exit to avoid noisy warnings on every hook run
command -v jq > /dev/null 2>&1 || exit 0

# Require session ID for isolation
SESSION_ID="${CLAUDE_SESSION_ID:-}"
[ -z "$SESSION_ID" ] && exit 0

# Sanitize session ID — only allow alphanumeric, hyphens, underscores
SESSION_ID="${SESSION_ID//[^a-zA-Z0-9_-]/_}"

# Read tool input from stdin (JSON with tool_name, tool_input, etc.)
INPUT=$(cat)

# Extract file path from tool input (file_path for Write/Edit, notebook_path for NotebookEdit)
FILE_PATH="$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty' 2> /dev/null)"
[ -z "$FILE_PATH" ] && exit 0

# Normalize to absolute path when the parent directory exists.
# If it does not exist yet (e.g., Write to a new nested path), keep the
# original path rather than fabricating a bogus absolute path like "/<basename>".
case "$FILE_PATH" in
  /*) ;;
  *)
    FILE_DIR="$(dirname "$FILE_PATH")"
    if [ -d "$FILE_DIR" ]; then
      ABS_DIR="$(cd "$FILE_DIR" 2> /dev/null && pwd)"
      [ -n "$ABS_DIR" ] && FILE_PATH="${ABS_DIR}/$(basename "$FILE_PATH")"
    fi
    ;;
esac

# Derive project root from the file being edited, not from hook cwd
PROJECT_ROOT="$(git -C "$(dirname "$FILE_PATH")" rev-parse --show-toplevel 2> /dev/null || dirname "$FILE_PATH")"
PROJECT_SLUG="$(basename "$PROJECT_ROOT")"

# Store tracking data centrally under CLAUDE_HOME
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
SESSION_DIR="${CLAUDE_HOME}/file-tracking/${PROJECT_SLUG}/${SESSION_ID}"
mkdir -p "$SESSION_DIR" 2> /dev/null || {
  printf 'track-edited-files: warning: could not create %s — tracking disabled for this session\n' "$SESSION_DIR" >&2
  exit 0
}

TRACKING_FILE="${SESSION_DIR}/files-touched.txt"

# Append timestamp + path
printf '%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$FILE_PATH" >> "$TRACKING_FILE" 2> /dev/null || true
