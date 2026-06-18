---
tool: claude  # harness-only: the claude --worktree flow and subagent isolation are Claude-Code-specific
---

# Worktree Workflow

Worktrees are created by the user via `claude --worktree <branch>`. These rules govern behavior when already inside a worktree.

## Safety Rules

When running inside a worktree:

1. **Edit only worktree files.** All file paths must resolve within the worktree directory. Never edit files in the original repository root — changes there won't be on this branch and can corrupt the main working tree.

   **Deriving the correct path:** Use `git rev-parse --show-toplevel` to get the worktree root, not any path referenced in CLAUDE.md or system context — those point to the original repo location, not the worktree.

   **Common trap:** If context gives you a path like `~/Claudefiles/rules/foo.md` and you're in a worktree at `~/Claudefiles/.claude/worktrees/my-branch/`, the correct edit path is `~/Claudefiles/.claude/worktrees/my-branch/rules/foo.md`. When in doubt, run `git rev-parse --show-toplevel` and verify your path starts with that prefix.
2. **Never run the installer** (`install.py` or any setup script that symlinks or copies files to system paths). Worktrees are isolated branches for development — installing from a worktree would overwrite symlinks/configs with the worktree's potentially in-progress state.
3. **Use `git -C <worktree-path>`** for all git commands to stay unambiguous about which working tree you're operating on.

## Subagent Isolation

When launching multiple executor subagents in parallel (agents that write files), each must run in its own worktree via `isolation: "worktree"` on the Agent tool call. A shared working directory with concurrent writers leads to destroyed changes, index corruption, and pre-commit hook race conditions.

Read-only subagents (reviewers, critics, analyzers) do not need isolation — they can safely share the working tree. See `references/common/agents.md` (Parallel Executor Isolation) for the full decision rules.
