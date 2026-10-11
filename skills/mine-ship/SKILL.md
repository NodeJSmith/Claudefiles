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

## Your task

Ship the current changes: commit, push, and open a PR. Follow each phase in order.

### Phase 1 — Commit & Push

Follow **all steps in `mine-commit-push`** exactly (read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-commit-push/SKILL.md` and execute its full workflow — commit quality gates included). When that phase completes successfully — changes committed and pushed — continue to Phase 2 below.

### Phase 1.5 — Clean Code Gate

**Skip this phase if the branch diff contains only instruction files (`.md`).** Clean-code checkers are for code, not prose. Instruction files are already covered by mine-review's instruction-mode reviewers in Phase 1.

After Phase 1 completes (changes committed and pushed), run `/mine-clean-code` on the branch diff.

When mine-clean-code presents its own next-steps prompt, choose "Note and move on" — this phase handles the fix/skip/stop decision.

If mine-clean-code produces findings, decide which are worth fixing. If none are, say so in one line and proceed to Phase 2. Otherwise fix those, top-to-bottom, inline (no subagent), re-run the tests and linter, then stage, commit (`refactor: address clean-code findings`), and push before proceeding to Phase 2 — mine-create-pr verifies the branch is fully pushed. State in one line what was fixed and what was left as not worth fixing.

Escalate instead of fixing when a fix is no longer mechanical and needs your judgment about intent: it changes a public interface or observable behavior, spreads across many files, or leaves the tests failing after one attempt. This is a major gate (clean code gate result, see `interaction.md`) — run `context-pct` and prepend the result to the question:

```
AskUserQuestion:
  question: "[Context: N%] Stylistic review found findings that need a judgment call: <which and why>. What next?"
  header: "Clean code"
  multiSelect: false
  options:
    - label: "Ship anyway"
      description: "Proceed to PR creation with findings noted"
    - label: "Stop here"
      description: "Pause; I'll address findings manually"
```

If any checker subagent fails to complete, skip that checker's findings and say "unavailable" in the summary line — do not block PR creation for checker failures.

### Phase 2 — Create PR

Follow **all steps in `mine-create-pr`** exactly (read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-create-pr/SKILL.md` and execute its full workflow — platform detection, draft PR, changelog entry + PR-number annotation, ready transition). Phase 1 already committed and pushed, so create-pr's push check passes. Return the PR URL it produces.
