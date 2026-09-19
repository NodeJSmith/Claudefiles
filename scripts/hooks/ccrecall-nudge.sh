#!/usr/bin/env bash
# PreToolUse hook: nudge toward `ccrecall search` when a Bash command greps
# across session transcripts instead of using ccrecall's own search.
#
# Detects: `grep -r`/`-R`/`--recursive`/`--dereference-recursive` in any flag
# token after grep (not just the one immediately following it), any `rg`
# invocation (ripgrep is recursive by default), or a `find ... *.jsonl`
# targeting the transcript directory (~/.claude/projects/ by default, or
# $CLAUDE_CONFIG_DIR/projects when that's set), as opposed to inspecting a
# single known transcript file. Non-blocking — emits additionalContext,
# never denies.
#
# Exclusions:
#   - A session working inside the ccrecall repo itself (cwd contains
#     "claude-code-recall") legitimately reads transcripts directly.
#   - CLAUDE_SKIP_CCRECALL_HINT=1 set in the environment, or prefixed on the
#     command (e.g. `CLAUDE_SKIP_CCRECALL_HINT=1 grep -rl foo ~/.claude/projects`).
#
# Known limitation, accepted: detection matches against the raw command, so
# a quoted, non-executed string with a space/operator before the trigger word
# (e.g. `echo "run grep -rl foo in ~/.claude/projects"`) can trigger a
# spurious nudge — the leading `"` only blocks a match when it sits directly
# against the word, as in `"grep ...`. Stripping quotes to avoid this was
# tried and reverted — it also erases the quoted glob argument in the
# legitimate `find ... -name "*.jsonl"` case this hook exists to catch, which
# is worse. Non-blocking hint on a solo-dev repo: an occasional unwanted
# nudge costs nothing to ignore.
#
# No set -euo pipefail — this hook is a sequence of guard clauses that each
# exit 0 on failure.
#
# Two different strings feed the checks below, deliberately:
#   - $UNQUOTED (quoted spans deleted entirely, not just unquoted — see its
#     definition) — used only for the CLAUDE_SKIP_CCRECALL_HINT escape hatch,
#     so a quoted mention of that string can't accidentally suppress the hook.
#   - $COMMAND (raw, unmodified) — used for every other check, because the
#     transcript-path and find/jsonl checks need to see text that legitimately
#     lives inside quotes (see the accepted limitation above).
#
# Hook wiring (settings.json):
#   "PreToolUse": [{
#     "matcher": "Bash",
#     "hooks": [{
#       "type": "command",
#       "command": "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/hooks/ccrecall-nudge.sh",
#       "timeout": 2000
#     }]
#   }]

if ! command -v jq > /dev/null 2>&1; then
  exit 0
fi

# Session-level escape hatch
[ "${CLAUDE_SKIP_CCRECALL_HINT:-}" = "1" ] && exit 0

INPUT="$(cat || true)"

COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2> /dev/null)" || true
[ -n "$COMMAND" ] || exit 0

CWD="$(printf '%s' "$INPUT" | jq -r '.cwd // empty' 2> /dev/null)" || true

# ccrecall's own dev session legitimately reads transcripts directly
case "$CWD" in
  *claude-code-recall*) exit 0 ;;
esac

# Per-command escape hatch: CLAUDE_SKIP_CCRECALL_HINT=1 prefixed on the command text.
# Deletes each quoted span (quotes and contents together) rather than just
# stripping the quote characters — "unquoted" describes the intent, not a
# literal unquoting.
UNQUOTED="$(printf '%s' "$COMMAND" | sed -e 's/"[^"]*"//g' -e "s/'[^']*'//g")"
if printf '%s' "$UNQUOTED" | grep -qE '(^|[;&|] *)CLAUDE_SKIP_CCRECALL_HINT=1[[:space:]]'; then
  exit 0
fi

# Must target the transcript directory, not a single known file. Matched
# against the raw command, not $UNQUOTED — a find glob like -name "*.jsonl"
# quotes its own argument on purpose, so stripping quotes here would erase
# the very text this check looks for.
#
# Transcripts live under $CLAUDE_CONFIG_DIR/projects when that's set (same
# resolution as project-docs-check.sh/project-meta-prompt.sh), not always
# literally ~/.claude/projects. Match the resolved custom path, and the
# literal env-var name followed by /projects too, in case the command
# references it unexpanded (e.g. `rg foo "$CLAUDE_CONFIG_DIR/projects"`) —
# require the /projects suffix so an unrelated config-dir reference (e.g.
# "$CLAUDE_CONFIG_DIR/settings.json") doesn't count.
CLAUDE_PROJECTS_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects"
if ! printf '%s' "$COMMAND" | grep -qE \
  -e '\.claude/projects' \
  -e "$CLAUDE_PROJECTS_DIR" \
  -e '\$\{?CLAUDE_CONFIG_DIR\}?/projects'; then
  exit 0
fi

# -[a-zA-Z]*[rR][a-zA-Z]* matches -r/-R anywhere in a bundled short-flag
# group (e.g. -rl, -Rl, -Hnr), case-insensitively (-r is --recursive, -R is
# --dereference-recursive — both count). The optional
# "([^;&|]*[[:space:]])?" lets that flag (or --recursive/
# --dereference-recursive) appear in any token after grep within the same
# command, not only the one immediately following it, e.g. `grep -n -r foo`.
GREP_RECURSIVE_RE='(^|[;&|[:space:]])grep[[:space:]]+([^;&|]*[[:space:]])?(-[a-zA-Z]*[rR][a-zA-Z]*|--recursive|--dereference-recursive)([[:space:]]|$)'

case "$COMMAND" in
  *find*.jsonl*) ;;
  *.jsonl*)
    # A specific transcript file is named directly, not the directory. rg is
    # only recursive against a directory operand — given a single file it's
    # an ordinary single-file search, same as `grep` without a recursive
    # flag — so bare `rg` doesn't count here; only an explicit recursive
    # grep flag does.
    printf '%s' "$COMMAND" | grep -qE "$GREP_RECURSIVE_RE" || exit 0
    ;;
  *)
    # No specific file named — any rg invocation counts (recursive by
    # default against the directory), alongside recursive grep.
    printf '%s' "$COMMAND" | grep -qE "(^|[;&|[:space:]])rg([[:space:]]|\$)|$GREP_RECURSIVE_RE" || exit 0
    ;;
esac

jq -cn '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"Searching across session transcripts — `ccrecall search \"<query>\"` may be faster for finding past sessions (keyword + semantic search over the same transcripts). Prefix the command with CLAUDE_SKIP_CCRECALL_HINT=1 to suppress this hint."}}'
