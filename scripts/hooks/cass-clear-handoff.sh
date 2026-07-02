#!/usr/bin/env bash
# SessionEnd hook: writes a per-project handoff marker so /cass-resume can
# identify the prior session immediately after /clear.
#
# No `set -euo pipefail` — a hook failure must never block session end.

input="$(cat)"

STATE_DIR="${HOME}/.local/share/claudefiles-cass/clear-handoff"
mkdir -p "$STATE_DIR" 2> /dev/null || exit 0

# The harness passes cwd on the hook's stdin JSON — prefer it over `pwd`
# since it's the authoritative working directory for the session that just
# ended, not whatever directory this hook process happens to inherit.
# (CLAUDE_SESSION_ID is not set in hook subprocess environments — the
# session_id must come from stdin JSON too.)
cwd=""
session_id=""
if command -v jq > /dev/null 2>&1; then
  cwd="$(printf '%s' "$input" | jq -r '.cwd // empty' 2> /dev/null)" || true
  session_id="$(printf '%s' "$input" | jq -r '.session_id // empty' 2> /dev/null)" || true
else
  # jq missing: fall back to a plain grep/sed field pull (same technique as
  # bin/cass-update's tag_name fallback) rather than losing the fields
  # entirely.
  cwd="$(printf '%s' "$input" | grep -m1 '"cwd"' | sed -E 's/.*"cwd"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/')"
  session_id="$(printf '%s' "$input" | grep -m1 '"session_id"' | sed -E 's/.*"session_id"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/')"
fi
[[ -z "$cwd" ]] && cwd="$(pwd)"

# Project key mirrors Claude Code's own project-directory naming under
# ~/.claude/projects/ (every "/" and "." in the cwd replaced with "-"), so a
# handoff file is easy to correlate by eye with its transcript directory.
project_key="${cwd//[\/.]/-}"
handoff_file="${STATE_DIR}/${project_key}.json"

timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if command -v jq > /dev/null 2>&1; then
  jq -cn --arg session_id "$session_id" --arg timestamp "$timestamp" --arg cwd "$cwd" '
    {timestamp: $timestamp, project_path: $cwd}
    + (if $session_id != "" then {session_id: $session_id} else {} end)
  ' > "$handoff_file" 2> /dev/null
else
  # jq missing: fall back to a manual, minimally-escaped JSON write rather
  # than silently skipping the handoff entirely — backslash and
  # double-quote are the only characters a filesystem path or session UUID
  # could plausibly contain that would break JSON syntax.
  escaped_cwd="$(printf '%s' "$cwd" | sed 's/\\/\\\\/g; s/"/\\"/g')"
  if [[ -n "$session_id" ]]; then
    escaped_sid="$(printf '%s' "$session_id" | sed 's/\\/\\\\/g; s/"/\\"/g')"
    printf '{"session_id": "%s", "timestamp": "%s", "project_path": "%s"}\n' \
      "$escaped_sid" "$timestamp" "$escaped_cwd" > "$handoff_file" 2> /dev/null
  else
    printf '{"timestamp": "%s", "project_path": "%s"}\n' \
      "$timestamp" "$escaped_cwd" > "$handoff_file" 2> /dev/null
  fi
fi

exit 0
