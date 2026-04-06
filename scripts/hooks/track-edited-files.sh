#!/usr/bin/env bash
# PostToolUse hook: track files edited by this session.
#
# Appends the touched file path to a session-local tracking file whenever
# Write, Edit, or NotebookEdit is used. Allows any Claude Code instance to
# know which files it modified, even when multiple instances share the same
# project directory.
#
# Storage: .claude/sessions/<session-id>/files-touched.txt (gitignored)
# Format:  <ISO-8601 timestamp>\t<absolute-path>
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

# Require session ID for isolation
SESSION_ID="${CLAUDE_SESSION_ID:-}"
[ -z "$SESSION_ID" ] && exit 0

# Read tool input from stdin (JSON with tool_name, tool_input, etc.)
INPUT=$(cat)

# Extract file path from tool input
FILE_PATH="$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty' 2> /dev/null)"
[ -z "$FILE_PATH" ] && exit 0

# Find project root (git root or cwd)
PROJECT_ROOT="$(git rev-parse --show-toplevel 2> /dev/null || pwd)"

# Ensure session directory exists
SESSION_DIR="${PROJECT_ROOT}/.claude/sessions/${SESSION_ID}"
mkdir -p "$SESSION_DIR" 2> /dev/null || exit 0

TRACKING_FILE="${SESSION_DIR}/files-touched.txt"

# Append timestamp + path
printf '%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$FILE_PATH" >> "$TRACKING_FILE" 2> /dev/null || true
