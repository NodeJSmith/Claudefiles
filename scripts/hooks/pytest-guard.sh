#!/usr/bin/env bash
# PreToolUse hook: require timeout on pytest invocations.
#
# Denies Bash commands that invoke pytest without a `timeout` wrapper.
# Optionally reads per-repo config from <repo-root>/.claude/pytest-guard.json
# for additional restrictions (e.g., denying -n auto).
#
# Global behavior (always on):
#   - Bare pytest without timeout → deny with instructions
#
# Per-repo config (.claude/pytest-guard.json):
#   {
#     "timeout": 300,
#     "deny_flags": ["-n auto"],
#     "deny_reason": "Use -n 2 instead of -n auto"
#   }
#
# To block ALL pytest invocations in a repo (e.g., "use nox instead"):
#   {
#     "deny_all": true,
#     "deny_reason": "Use nox instead of pytest directly"
#   }
#   Note: deny_flags uses substring matching — use multi-word values
#   (e.g., "-n auto") to avoid false matches on short flags.
#
# Env var override:
#   CLAUDE_PYTEST_TIMEOUT — overrides default and per-repo timeout value
#
# Escape hatch (mirrors serena-guard.sh): prefix the command with a
# reason-bearing env var to opt out of every check below when you genuinely need
# to run pytest without a timeout wrapper (or past a per-repo deny):
#   PYTEST_GUARD_OFF="running under a debugger that owns process lifetime" pytest ...
# The reason must be non-empty; it's echoed to stderr so the override stays a
# conscious, auditable choice.
#
# Requires:
#   - jq (for parsing hook input and per-repo config)
#   - git (for finding repo root)
#
# Hook wiring (settings.json):
#   "PreToolUse": [{
#     "matcher": "Bash",
#     "hooks": [{
#       "type": "command",
#       "command": "${CLAUDE_HOME:-$HOME/.claude}/scripts/hooks/pytest-guard.sh",
#       "timeout": 5000
#     }]
#   }]

set -euo pipefail

INPUT=$(cat)

if ! command -v jq > /dev/null 2>&1; then
  printf 'ERROR: jq is required by pytest-guard.sh. Install jq or remove this hook.\n' >&2
  exit 0
fi

COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty')

[ -z "$COMMAND" ] && exit 0

# --- OVERRIDE: a PYTEST_GUARD_OFF="reason" prefix opts out of every check below ---
# Mirrors serena-guard.sh. The opt-out is deliberately a conscious choice — a
# real, non-empty reason is required:
#   - anchored to the start of the command (the documented prefix form), so it
#     can't be triggered from inside a later argument, heredoc, or string.
#   - the three regex branches accept a double-quoted, single-quoted, or bare-word
#     value; an empty value (PYTEST_GUARD_OFF= / "" / '') matches none of them.
#   - the captured value is unquoted and trimmed, then a bare <reason> placeholder
#     (the literal from the hint text) is rejected.
# Pipeline: grep -o prints the whole match (KEY=VALUE), so cut strips the "KEY="
# prefix; sed then strips surrounding quotes and whitespace. The '\'' sequences
# are a literal single-quote inside a single-quoted string. grep exits 1 on no
# match; the trailing || true keeps that (or any pipe-stage failure) from aborting
# under set -e — it just leaves OVERRIDE_REASON empty.
OVERRIDE_REASON=$(printf '%s' "$COMMAND" |
  grep -oE '^[[:space:]]*PYTEST_GUARD_OFF=("[^"]+"|'\''[^'\'']+'\''|[^[:space:]"'\'']+)' |
  head -n1 | cut -d= -f2- |
  sed -e 's/^["'\'']//' -e 's/["'\'']$//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' || true)
if [ -n "$OVERRIDE_REASON" ] && [ "$OVERRIDE_REASON" != "<reason>" ]; then
  printf 'pytest-guard.sh: override honored — %s\n' "$OVERRIDE_REASON" >&2
  exit 0
fi

# --- Detect whether this command actually runs pytest ---

# Prefix pattern: optional env vars, optional runner (uv run, poetry run, etc.)
# Anchors at command boundaries (^, &&, ;, |) to find each pytest invocation.
# Each pytest segment in a chained command needs its own timeout wrapper.
PREFIX='(^|&&|;|\|)[[:space:]]*([A-Z_][A-Z_0-9]*=[^ ]*[[:space:]]+)*((uv|poetry|pipenv|hatch)[[:space:]]+run[[:space:]]+)?'

is_pytest_invocation() {
  local cmd="$1"

  if printf '%s' "$cmd" | grep -qE "${PREFIX}(timeout[[:space:]]+[^ ]+[[:space:]]+)?pytest([[:space:]]|$)"; then
    return 0
  fi
  if printf '%s' "$cmd" | grep -qE "${PREFIX}(timeout[[:space:]]+[^ ]+[[:space:]]+)?python[0-9.]* -m pytest([[:space:]]|$)"; then
    return 0
  fi
  return 1
}

if ! is_pytest_invocation "$COMMAND"; then
  exit 0
fi

# --- From here on, we know it's a pytest invocation ---

# Shown only on the global timeout denial below — not on per-repo deny_all/
# deny_flags, whose configured reasons reflect a deliberate repo policy we don't
# undercut by advertising the bypass.
OVERRIDE_HINT='To run without the timeout wrapper, prefix the command with PYTEST_GUARD_OFF="<your reason>".'

deny() {
  jq -cn --arg reason "$1" \
    '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":$reason}}'
  exit 0
}

# Resolve timeout value: env var > repo config > default (300s)
DEFAULT_TIMEOUT=300

# Try to find per-repo config
REPO_CONFIG=""
REPO_TIMEOUT=""
REPO_ROOT=""

if [ -n "$CWD" ]; then
  REPO_ROOT=$(git -C "$CWD" rev-parse --show-toplevel 2> /dev/null || true)
fi

if [ -n "$REPO_ROOT" ] && [ -f "$REPO_ROOT/.claude/pytest-guard.json" ]; then
  REPO_CONFIG="$REPO_ROOT/.claude/pytest-guard.json"
  REPO_TIMEOUT=$(jq -r '.timeout // empty' "$REPO_CONFIG" 2> /dev/null || true)
  if [ -n "$REPO_TIMEOUT" ]; then
    case "$REPO_TIMEOUT" in
      '' | *[!0-9]*)
        printf 'warning: .claude/pytest-guard.json timeout=%s is not a valid integer, ignoring\n' "$REPO_TIMEOUT" >&2
        REPO_TIMEOUT=""
        ;;
    esac
  fi
fi

# --- Check 0: deny_all — block ALL pytest invocations for this repo ---
if [ -n "$REPO_CONFIG" ]; then
  DENY_ALL=$(jq -r 'if .deny_all == true then "true" else "false" end' "$REPO_CONFIG" 2> /dev/null || echo "false")
  if [ "$DENY_ALL" = "true" ]; then
    DENY_REASON=$(jq -r '.deny_reason // "pytest is not allowed in this repository"' "$REPO_CONFIG" 2> /dev/null || true)
    [ -z "$DENY_REASON" ] && DENY_REASON="pytest is not allowed in this repository"
    deny "$DENY_REASON"
  fi
fi

# Final timeout: env var wins, then repo config, then default
RAW_TIMEOUT="${CLAUDE_PYTEST_TIMEOUT:-}"
if [ -n "$RAW_TIMEOUT" ]; then
  case "$RAW_TIMEOUT" in
    '' | *[!0-9]*)
      printf 'warning: CLAUDE_PYTEST_TIMEOUT=%s is not a valid integer, using default\n' "$RAW_TIMEOUT" >&2
      TIMEOUT="$DEFAULT_TIMEOUT"
      ;;
    *) TIMEOUT="$RAW_TIMEOUT" ;;
  esac
elif [ -n "$REPO_TIMEOUT" ]; then
  TIMEOUT="$REPO_TIMEOUT"
else
  TIMEOUT="$DEFAULT_TIMEOUT"
fi

# --- Check 1: timeout wrapper immediately before pytest? ---

has_timeout() {
  local cmd="$1"

  # timeout must immediately precede pytest (not just appear anywhere)
  if printf '%s' "$cmd" | grep -qE "${PREFIX}timeout[[:space:]]+[^ ]+[[:space:]]+pytest([[:space:]]|$)"; then
    return 0
  fi
  if printf '%s' "$cmd" | grep -qE "${PREFIX}timeout[[:space:]]+[^ ]+[[:space:]]+python[0-9.]* -m pytest([[:space:]]|$)"; then
    return 0
  fi
  return 1
}

if ! has_timeout "$COMMAND"; then
  deny "pytest must be wrapped with timeout to prevent orphaned processes. Use: timeout ${TIMEOUT} pytest ... (or set CLAUDE_PYTEST_TIMEOUT to adjust the limit). ${OVERRIDE_HINT}"
fi

# --- Check 2: per-repo deny_flags ---

if [ -n "$REPO_CONFIG" ]; then
  DENY_FLAGS=$(jq -r '.deny_flags[]? // empty' "$REPO_CONFIG" 2> /dev/null || true)
  DENY_REASON=$(jq -r '.deny_reason // "Denied by per-repo pytest-guard config"' "$REPO_CONFIG" 2> /dev/null || true)

  if [ -n "$DENY_FLAGS" ]; then
    while IFS= read -r flag; do
      [ -z "$flag" ] && continue
      if printf '%s' "$COMMAND" | grep -qF -- "$flag"; then
        deny "${DENY_REASON} (matched: ${flag})"
      fi
    done <<< "$DENY_FLAGS"
  fi
fi

# All checks passed — no opinion
exit 0
