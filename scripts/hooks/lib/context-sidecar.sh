#!/usr/bin/env bash
# Shared reader for the per-session context-usage sidecar written by
# claude-context-writer (/tmp/claude-context-<session_id>.meta).
#
# Usage (caller sources this, then):
#   pct="$(context_sidecar_pct "$session_id")"
#
# Prints the integer pct= value, or nothing when the session id is unsafe,
# the sidecar is missing, or its pct= line is absent or not a whole number.
# Always returns 0, so callers treat empty output as "unknown".

context_sidecar_pct() {
  local sid="$1" sidecar pct
  # The id becomes part of a /tmp path; one containing '/' or '.' is not trusted.
  case "$sid" in '' | *[/.]*) return 0 ;; esac
  # Hardcodes /tmp/ to match claude-context-writer, which runs outside Claude
  # Code's sandbox and cannot use CLAUDE_CODE_TMPDIR.
  sidecar="/tmp/claude-context-${sid}.meta"
  [ -f "$sidecar" ] || return 0
  # Anchor on the pct= line: the file also carries a cwd= line whose path may
  # itself contain '='.
  pct="$(sed -n 's/^pct=//p' "$sidecar" 2> /dev/null)" || return 0
  case "$pct" in '' | *[!0-9]*) return 0 ;; esac
  printf '%s\n' "$pct"
}
