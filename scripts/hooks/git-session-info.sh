#!/usr/bin/env bash
# SessionStart hook: display git repository context.
# Override the default branch with CLAUDE_GIT_DEFAULT_BRANCH.
# No set -euo pipefail — failure should not block session start.

git rev-parse --git-dir > /dev/null 2>&1 || exit 0

parts=()

# Linked worktrees have a .git file (gitdir pointer), not a directory
toplevel=$(git rev-parse --show-toplevel 2> /dev/null) || exit 0
if [ -f "$toplevel/.git" ]; then
  parts+=("worktree: $(basename "$toplevel")")
fi

branch=$(git branch --show-current 2> /dev/null) || branch=""
[ -z "$branch" ] && branch="(detached)"
parts+=("branch: $branch")

default="${CLAUDE_GIT_DEFAULT_BRANCH:-}"
if [ -z "$default" ]; then
  default=$(git-default-branch --no-network 2> /dev/null) || default=""
fi
[ -n "$default" ] && parts+=("default: $default")

# git-branch-ahead/behind exit 10 when ahead/behind > 0 — no || here,
# since that would wipe the captured output on the interesting case.
if [ -n "$default" ]; then
  ahead_json=$(git-branch-ahead --no-fetch --json 2> /dev/null)
  behind_json=$(git-branch-behind --no-fetch --json 2> /dev/null)

  ahead=""
  behind=""
  [ -n "$ahead_json" ] && ahead=$(printf '%s' "$ahead_json" | grep -o '"ahead":[0-9]*' | grep -o '[0-9]*')
  [ -n "$behind_json" ] && behind=$(printf '%s' "$behind_json" | grep -o '"behind":[0-9]*' | grep -o '[0-9]*')

  if [ -n "$ahead" ] && [ -n "$behind" ]; then
    if [ "$ahead" -eq 0 ] && [ "$behind" -eq 0 ]; then
      parts+=("up to date")
    else
      status=""
      [ "$ahead" -gt 0 ] && status="${ahead} ahead"
      [ "$behind" -gt 0 ] && {
        [ -n "$status" ] && status="$status, "
        status="${status}${behind} behind"
      }
      parts+=("$status")
    fi
  fi
fi

printf '%s' "${parts[0]}"
for ((i = 1; i < ${#parts[@]}; i++)); do
  printf ' · %s' "${parts[$i]}"
done
printf '\n'
