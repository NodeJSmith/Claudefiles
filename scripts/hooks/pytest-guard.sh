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

# --- Strip quoted strings to avoid false positives on arguments ---
# e.g., grep 'foo\|pytest bar' or gh-issue create --title "pytest guard"
# Only handles matched pairs; mismatched quotes pass through unchanged.
strip_quotes() {
  printf '%s' "$1" | sed "s/'[^']*'//g" | sed 's/"[^"]*"//g'
}

STRIPPED=$(strip_quotes "$COMMAND")

# --- Detect whether this command actually runs pytest ---

# Regex components — assembled by is_pytest_invocation and has_timeout:
#   BOUNDARY  — start of command or shell operator (&&, ;, |)
#   ENV_VARS  — optional KEY=val prefixes
#   RUNNER    — optional uv/poetry/pipenv/hatch run prefix
# Timeout handling differs: is_pytest_invocation makes it optional (detect
# pytest with or without timeout), has_timeout requires it.
BOUNDARY='(^|&&|;|\|)[[:space:]]*'
ENV_VARS='([A-Z_][A-Z_0-9]*=[^ ]*[[:space:]]+)*'
RUNNER='((uv|poetry|pipenv|hatch)[[:space:]]+run[[:space:]]+)?'

is_pytest_invocation() {
  local cmd="$1"
  local OPT_TIMEOUT='(timeout[[:space:]]+[^ ]+[[:space:]]+)?'

  if printf '%s' "$cmd" | grep -qE "${BOUNDARY}${ENV_VARS}${OPT_TIMEOUT}${RUNNER}pytest([[:space:]]|$)"; then
    return 0
  fi
  if printf '%s' "$cmd" | grep -qE "${BOUNDARY}${ENV_VARS}${OPT_TIMEOUT}${RUNNER}python[0-9.]* -m pytest([[:space:]]|$)"; then
    return 0
  fi
  return 1
}

if ! is_pytest_invocation "$STRIPPED"; then
  exit 0
fi

# --- From here on, we know it's a pytest invocation ---

deny() {
  jq -cn --arg reason "$1" \
    '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":$reason}}'
  exit 0
}

# Try to find per-repo config
REPO_CONFIG=""
REPO_ROOT=""

if [ -n "$CWD" ]; then
  REPO_ROOT=$(git -C "$CWD" rev-parse --show-toplevel 2> /dev/null || true)
fi

if [ -n "$REPO_ROOT" ] && [ -f "$REPO_ROOT/.claude/pytest-guard.json" ]; then
  REPO_CONFIG="$REPO_ROOT/.claude/pytest-guard.json"
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

# --- Check 1: timeout wrapper immediately before pytest? ---

has_timeout() {
  local cmd="$1"
  local REQ_TIMEOUT='timeout[[:space:]]+[^ ]+[[:space:]]+'

  if printf '%s' "$cmd" | grep -qE "${BOUNDARY}${ENV_VARS}${REQ_TIMEOUT}${RUNNER}pytest([[:space:]]|$)"; then
    return 0
  fi
  if printf '%s' "$cmd" | grep -qE "${BOUNDARY}${ENV_VARS}${REQ_TIMEOUT}${RUNNER}python[0-9.]* -m pytest([[:space:]]|$)"; then
    return 0
  fi
  return 1
}

if ! has_timeout "$STRIPPED"; then
  deny "pytest must be wrapped with timeout to prevent orphaned processes. Use: timeout 300 pytest ..."
fi

# --- Check 2: per-repo deny_flags ---
# Uses original COMMAND (not STRIPPED) — flag substrings like "-n auto"
# should match even when arguments contain quotes.

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
