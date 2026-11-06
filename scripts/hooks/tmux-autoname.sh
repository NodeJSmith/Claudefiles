#!/usr/bin/env bash
# SessionStart hook: give the tmux session a name of its own, once.
#
# Windows Terminal tabs open with `tmux new-session -A -s <project>`, which
# attaches to any session still holding that name. Renaming the session as soon
# as Claude starts frees the name, so the next tab gets a fresh session.
#
# The name is <project>-<branch>, with a random suffix if that name is taken
# (outside git or on a detached HEAD it is just <project>, which is usually the
# tab's own name, so it always gets a suffix there). A @claude_autonamed session
# option marks a renamed session; `claude-tmux rename` sets it too. Once marked,
# resume, /clear, compaction, or a second Claude pane leaves the name alone, and
# the hook only prints a hint (stdout becomes Claude's context) inviting a more
# specific name.
#
# No set -euo pipefail — this is a cosmetic hook; failure should not block session start.

# Limit for <project>-<branch>; a collision suffix adds 5 more characters.
MAX_NAME_LEN=30
MAX_COLLISION_TRIES=5

[ -n "${TMUX:-}" ] || exit 0
command -v tmux > /dev/null 2>&1 || exit 0

slug() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9-' '-' | tr -s '-' | sed 's/^-//; s/-$//'
}

hint() {
  echo "Tmux session is named \"$1\". If the task has a more specific name, rename it with: claude-tmux rename \"<project>-<context>\" (kebab-case, max ~30 chars)"
}

target=()
if [ -n "${TMUX_PANE:-}" ]; then
  target=(-t "$TMUX_PANE")
fi

info="$(tmux display-message -p "${target[@]}" '#{session_id} #{session_name}' 2> /dev/null)" || exit 0
session_id="${info%% *}"
current="${info#* }"
[ -n "$session_id" ] && [ -n "$current" ] || exit 0

if [ -n "$(tmux show-options -qv -t "$session_id" @claude_autonamed 2> /dev/null)" ]; then
  hint "$current"
  exit 0
fi

# Project is the main clone's directory name, so worktrees name after their repo.
project_dir="$PWD"
common_dir="$(git rev-parse --git-common-dir 2> /dev/null)" || common_dir=""
if [ -n "$common_dir" ]; then
  resolved="$(cd "$(dirname "$common_dir")" 2> /dev/null && pwd -P)" || resolved=""
  [ -n "$resolved" ] && project_dir="$resolved"
fi
project="$(slug "$(basename "$project_dir")")"
branch="$(slug "$(git branch --show-current 2> /dev/null)")"

desired="$project"
[ -n "$branch" ] && desired="$project-$branch"
desired="$(printf '%s' "$desired" | cut -c1-"$MAX_NAME_LEN" | sed 's/-$//')"
[ -n "$desired" ] || exit 0

# A name that extends <desired> (a suffixed copy, or a more specific name
# Claude chose) already identifies the work: keep it and mark it.
case "$current" in
  "$desired"-*)
    tmux set-option -t "$session_id" @claude_autonamed 1 2> /dev/null
    hint "$current"
    exit 0
    ;;
esac

name="$desired"
for ((try = 0; try < MAX_COLLISION_TRIES; try++)); do
  tmux has-session -t "=$name" 2> /dev/null || break
  name="$desired-$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 4)"
done

if tmux rename-session -t "$session_id" "$name" 2> /dev/null; then
  tmux set-option -t "$session_id" @claude_autonamed 1 2> /dev/null
  hint "$name"
else
  # Every candidate was taken; leave the session unmarked so the next start retries.
  hint "$current"
fi
exit 0
