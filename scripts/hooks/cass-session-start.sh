#!/usr/bin/env bash
# SessionStart hook: kicks off background cass maintenance (binary update
# check, incremental indexing) and — synchronously, hard-capped at 3s —
# injects a summary of recent session history for the current project.
#
# No `set -euo pipefail` — a hook failure must never block session start.

if ! command -v cass > /dev/null 2>&1; then
  exit 0
fi

input="$(cat)"

# Background: refresh the cass binary itself when the last check was >24h
# ago. cass-update owns its own staleness gate
# (~/.local/share/claudefiles-cass/last-update-check) so calling it
# unconditionally here is cheap and correct.
if command -v cass-update > /dev/null 2>&1; then
  nohup cass-update --if-stale < /dev/null > /dev/null 2>&1 &
fi

# Background: incremental indexing of any session files written since the
# last run. cass discovers Claude Code session JSONLs under
# ~/.claude/projects/ on its own — no path arguments needed.
nohup cass index < /dev/null > /dev/null 2>&1 &

# Synchronous context injection — best-effort, hard-capped at 3s so a slow or
# hung search never delays session start. Any failure (missing jq, timeout,
# non-zero exit, empty/unparseable results) degrades to silence, not an
# error: plain stdout is what Claude Code adds as SessionStart context, so
# printing nothing is the correct "no context" response.
if ! command -v jq > /dev/null 2>&1; then
  exit 0
fi

# The harness passes cwd on the hook's stdin JSON — prefer it over `pwd`,
# same reasoning as cass-clear-handoff.sh: it's the authoritative working
# directory for this session, not whatever directory this hook process
# happens to inherit.
cwd="$(printf '%s' "$input" | jq -r '.cwd // empty' 2> /dev/null)"
[[ -z "$cwd" ]] && cwd="$(pwd)"

results="$(timeout 3 cass search --robot --workspace "$cwd" --days 7 --limit 3 --fields minimal 2> /dev/null)"
status=$?
if [[ $status -ne 0 || -z "$results" ]]; then
  exit 0
fi

# Field extraction is deliberately lenient: cass's --fields minimal is
# documented to guarantee only source_path/line_number/agent, but a hit may
# also carry title/timestamp/snippet-style fields depending on cass version.
# Every lookup falls back gracefully so the summary degrades to whatever the
# hit actually contains instead of failing outright.
summary="$(printf '%s' "$results" | jq -r '
  (.hits // [])[] |
  ((.title // .session_id // ((.source_path // "") | split("/") | last) // "session")) as $topic |
  ((.date // .timestamp // "")) as $when |
  ((.snippet // "")) as $snippet |
  "- " + $topic
    + (if $when != "" then " (" + $when + ")" else "" end)
    + (if $snippet != "" then "\n  " + $snippet else "" end)
' 2> /dev/null)"

if [[ -z "$summary" ]]; then
  exit 0
fi

cat << EOF
## Recent session context (cass)

$summary
EOF
