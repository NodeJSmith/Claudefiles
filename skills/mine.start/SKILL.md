---
name: mine.start
description: Read a plan handoff from a previous Claude session and begin implementation. Use when opening a new Claude session in a worktree that has a prepared plan.
user-invokable: true
---

## Context

- Plan: !`cat .claude/plan.md 2>/dev/null || echo "NO_PLAN_FOUND"`
- Current branch: !`git branch --show-current`
- Git status: !`git status --short`

## Your task

1. If the plan context above shows `NO_PLAN_FOUND`, tell the user no plan was found and ask what they'd like to work on.
2. Otherwise, summarize the plan briefly.
3. Rename the tmux session based on the plan title. Derive `<project>-<context>` from the working directory name and plan subject (kebab-case, ~30 chars max). E.g., plan "Fix URL quote parsing" in myapp → `claude-tmux rename "myapp-url-quote-fix"`.
4. Ask the user to confirm before starting.
5. Once confirmed, begin implementation following the plan.
6. When all work is complete, rename the plan file:
   ```bash
   mv .claude/plan.md .claude/plan.done.md
   ```
