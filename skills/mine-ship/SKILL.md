---
name: mine-ship
description: "Use when the user says: \"ship it\" or \"commit push and PR\". Commits, pushes, and creates a PR in one step."
user-invocable: true
---

## Context

- Current git status: !`git status`
- Current git diff (staged and unstaged changes): !`git diff HEAD`
- Current branch: !`git branch --show-current`
- Default branch: !`git-default-branch`
- Remote URL: !`git remote get-url origin 2>/dev/null`

## Goal

Get the current changes from the working tree to a reviewable state on the remote in one step: committed, pushed, and, where the repo calls for one, a PR. Commit, push, and PR creation are outward-facing and hard to take back, so each runs only after its gates pass.

The default flow below is a PR flow. Any rule in the user's or repo's instructions that changes how this repo ships (for example a repo that takes direct pushes to the default branch, so no PR) wins over it. Apply that rule instead of the matching default step, without asking. Skip only what is PR-specific (opening the PR, checks tied to it, returning a PR URL); everything else still runs, the changelog entry and clean-code gate included, and you report what was actually pushed in place of a PR URL. When there is no PR to review afterward, the clean-code gate has to run before the push lands, on the commits not yet on `origin/<default branch>` plus any uncommitted changes, since there is no branch diff to review once they're pushed.

## Stages

1. **Commit and push.** Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-commit-push/SKILL.md` and carry out its workflow in full, quality gates included. Continue only once the changes are committed and pushed. When no PR follows (direct push), commit but hold the push until the clean-code gate in stage 2 has passed, then push; `mine-commit-push` can't know to wait, so you do.

2. **Clean-code gate.** Skip when the change is only Markdown; clean-code checkers are for code, not prose. Otherwise run `/mine-clean-code` on the change, and when it offers its own next-steps prompt, choose "Note and move on", since this stage makes the fix/skip/stop call.

   Raw checker output doesn't decide anything. Judge which findings matter. If none do, say so in one line and move on. Fix the ones that do, inline, top to bottom (no subagent), re-run tests and linter, then commit (`refactor: address clean-code findings`) and push before the next stage, since `mine-create-pr` verifies the branch is fully pushed. State in one line what was fixed and what was left as not worth fixing.

   Escalate instead of fixing when a fix needs your judgment about intent: it changes a public interface or observable behavior, spreads across many files, or still fails the tests after one attempt. This is a major gate (see `interaction.md`): run `context-pct`, prepend `[Context: N%]` to the question, and offer the outcomes that fit what you found (ship with the findings listed in the PR body or the report, stop so the user can address them, or others the findings call for). A checker that fails to complete is reported as "unavailable" and never blocks the PR.

3. **Create the PR.** Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-create-pr/SKILL.md` and carry out its workflow in full (platform detection, changelog entry, PR creation). Stage 1 already pushed, so its push check passes. Return the PR URL it produces.
