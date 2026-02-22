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
2. Otherwise, summarize the plan briefly and ask the user to confirm before starting.
3. Once confirmed, begin implementation following the plan.
4. When all work is complete, rename the plan file:
   ```bash
   mv .claude/plan.md .claude/plan.done.md
   ```
