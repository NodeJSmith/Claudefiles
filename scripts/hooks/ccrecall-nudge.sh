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
# Known limitation, accepted: the find-pipeline check (FIND_COMMAND_RE +
# FIND_NAME_GLOB_RE below) requires a `find` token and a `-name`/`-iname`
# .jsonl glob to both appear somewhere in the command, not necessarily in
# the same pipeline segment — a `find` targeting one specific file, piped
# into an unrelated command whose own quoted argument happens to contain
# "-name ... .jsonl" text, can misfire the unconditional-nudge branch.
# Restricting the glob match to find's own segment would need real
# command-chain parsing (splitting on `;`/`&`/`|` without also splitting
# inside quotes), which isn't worth it for a non-blocking hint.
#
# No set -euo pipefail — this hook is a sequence of guard clauses that each
# exit 0 on failure.
#
# Two different strings feed the checks below, deliberately:
#   - $UNQUOTED (quoted spans deleted entirely, not just unquoted — see its
#     definition) — used for the CLAUDE_SKIP_CCRECALL_HINT escape hatch (so a
#     quoted mention of that string can't accidentally suppress the hook),
#     and for classifying "find" as a command token / ".jsonl" as a path
#     token, so a quoted rg/grep search pattern containing either word isn't
#     misread as command or path syntax.
#   - $COMMAND (raw, unmodified) — used for the transcript-path check,
#     find's own -name/-iname glob syntax, and the recursive-grep/bare-rg
#     checks, all of which need to see text that legitimately lives inside
#     quotes (see the accepted limitation above).
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
# literally ~/.claude/projects. The resolved custom path is matched as a
# fixed string (grep -F), not interpolated into the regex below — a
# CLAUDE_CONFIG_DIR containing an ERE metacharacter (e.g. /custom/a[b) would
# otherwise break the pattern (grep reports an invalid regex and the hint is
# silently lost) or match unintended text via an unescaped special char. The
# literal env-var name forms stay regexes, since they need the
# optional-brace pattern, and require the /projects suffix so an unrelated
# config-dir reference (e.g. "$CLAUDE_CONFIG_DIR/settings.json") doesn't
# count. The gate below is "exit unless at least one of the three matches" —
# De Morgan's turns that OR into the two negated-and-anded checks here (one
# grep call for the two regex alternatives, one for the fixed string).
CLAUDE_PROJECTS_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects"
if ! printf '%s' "$COMMAND" | grep -qE \
  -e '\.claude/projects' \
  -e '\$\{?CLAUDE_CONFIG_DIR\}?/projects' &&
  ! printf '%s' "$COMMAND" | grep -qF -- "$CLAUDE_PROJECTS_DIR"; then
  exit 0
fi

# -[a-zA-Z]*[rR][a-zA-Z]* matches -r/-R anywhere in a bundled short-flag
# group (e.g. -rl, -Rl, -Hnr), case-insensitively (-r is --recursive, -R is
# --dereference-recursive — both count). The optional
# "([^;&|]*[[:space:]])?" lets that flag (or --recursive/
# --dereference-recursive) appear in any token after grep within the same
# command, not only the one immediately following it, e.g. `grep -n -r foo`.
GREP_RECURSIVE_RE='(^|[;&|[:space:]])grep[[:space:]]+([^;&|]*[[:space:]])?(-[a-zA-Z]*[rR][a-zA-Z]*|--recursive|--dereference-recursive)([[:space:]]|$)'

# Classifying "targets a single known file" vs "targets the transcript
# directory" has to look at command/path tokens, not substrings of the whole
# command text — a quoted rg/grep search pattern can itself contain the
# words "find" or ".jsonl" without the command meaning either
# (`rg "find me" x.jsonl` isn't a find pipeline; `rg "mentions .jsonl" dir/`
# isn't a single-file search). $UNQUOTED (quoted spans deleted, see its
# definition above) strips those pattern texts out, leaving only text that
# is actual command/path syntax.
#
# find(1) as a command token, not a substring of a quoted search pattern.
# The boundary class includes "/" so an absolute-path invocation
# (/usr/bin/find) still counts — unlike the grep/rg checks, "find" has no
# common substring false positive to guard against by tightening this.
FIND_COMMAND_RE='(^|[;&|[:space:]/])find([[:space:]]|$)'
# find's own -name/-iname glob syntax naming *.jsonl — checked against the
# raw command, not $UNQUOTED, because this glob is itself legitimately
# quoted (-name "*.jsonl") to stop the shell from expanding it. Anchored to
# the -name/-iname flag, which isn't going to appear by coincidence inside
# an rg/grep search pattern.
FIND_NAME_GLOB_RE='-i?name[^;&|]*\.jsonl'
# A specific transcript file named as a path token in $UNQUOTED — ".jsonl"
# ends a token, not merely appears somewhere inside a quoted pattern.
JSONL_FILE_TOKEN_RE='\.jsonl([;&|[:space:]]|$)'

if printf '%s' "$UNQUOTED" | grep -qE "$FIND_COMMAND_RE" &&
  printf '%s' "$COMMAND" | grep -qE -e "$FIND_NAME_GLOB_RE"; then
  : # find ... -name "*.jsonl" pipeline — nudge unconditionally, fall through
elif printf '%s' "$UNQUOTED" | grep -qE "$JSONL_FILE_TOKEN_RE"; then
  # A specific transcript file is named directly, not the directory. rg is
  # only recursive against a directory operand — given a single file it's
  # an ordinary single-file search, same as `grep` without a recursive
  # flag — so bare `rg` doesn't count here; only an explicit recursive
  # grep flag does.
  printf '%s' "$COMMAND" | grep -qE "$GREP_RECURSIVE_RE" || exit 0
else
  # No specific file named — any rg invocation counts (recursive by
  # default against the directory), alongside recursive grep.
  printf '%s' "$COMMAND" | grep -qE "(^|[;&|[:space:]])rg([[:space:]]|\$)|$GREP_RECURSIVE_RE" || exit 0
fi

jq -cn '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"Searching across session transcripts — `ccrecall search \"<query>\"` may be faster for finding past sessions (keyword + semantic search over the same transcripts). Prefix the command with CLAUDE_SKIP_CCRECALL_HINT=1 to suppress this hint."}}'
