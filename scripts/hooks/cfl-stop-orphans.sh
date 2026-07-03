#!/usr/bin/env bash
# SessionStart hook: stop orphaned cfl runs whose working directory no longer exists.
#
# No `set -euo pipefail` — a hook failure must never block session start.

if ! command -v cfl > /dev/null 2>&1; then
  exit 0
fi

result="$(cfl stop-orphans 2> /dev/null)" || exit 0

if command -v jq > /dev/null 2>&1; then
  count="$(printf '%s' "$result" | jq -r '.count // 0' 2> /dev/null)" || count=0
else
  count="$(printf '%s' "$result" | grep -o '"count": *[0-9]*' | grep -o '[0-9]*')" || count=0
fi

if [ "${count:-0}" -gt 0 ]; then
  echo "cfl: stopped $count orphaned run(s) — working directory no longer exists"
fi

exit 0
