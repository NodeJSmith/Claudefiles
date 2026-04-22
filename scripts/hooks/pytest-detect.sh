#!/usr/bin/env bash
# Shared pytest detection patterns for loop-detector and loop-status hooks.
# Sourced (not executed) by sibling hooks.
#
# Provides:
#   PREFIX — regex prefix for matching command boundaries with optional env vars and runners
#   is_pytest_invocation() — returns 0 if the given command string invokes pytest

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
