#!/usr/bin/env bash
# SessionStart hook: remind Claude to rename the tmux session.
# Only prints if we're inside a tmux session; silent otherwise.

if [ -n "$TMUX" ]; then
  echo "You are inside a tmux session. Rename it now with: claude-tmux rename \"<project>-<context>\""
fi
