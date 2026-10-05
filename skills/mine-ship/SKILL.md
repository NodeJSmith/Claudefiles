---
name: mine-ship
description: "Use when the user says: \"ship it\" or \"commit push and PR\". Commits, pushes, and creates a PR in one step."
user-invocable: true
opencode-command: true
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

If mine-clean-code produces findings, decide which are worth fixing. If none are, say so in one
line and proceed to Phase 2. Otherwise present the gate below, naming those findings and why. This is a
major gate (clean code gate result, see `interaction.md`) — run `context-pct` and prepend the
result to the question:

```
AskUserQuestion:
  question: "[Context: N%] Stylistic review found findings. <Which are worth fixing and why.> What next?"
  header: "Clean code"
  multiSelect: false
  options:
    - label: "Address findings (Recommended)"
      description: "Fix the ones worth fixing, then proceed to PR creation"
    - label: "Ship anyway"
      description: "Proceed to PR creation with findings noted"
    - label: "Stop here"
      description: "Pause; I'll address findings manually"
```

- **"Address findings"**: fix the findings you called worth fixing, top-to-bottom, inline (no subagent), then stage, commit (`refactor: address clean-code findings`), and push before proceeding to Phase 2 — mine-create-pr verifies the branch is fully pushed
- **"Ship anyway"**: proceed to Phase 2
- **"Stop here"**: stop

If mine-clean-code produces no findings, proceed to Phase 2 automatically.

If any checker subagent fails to complete, skip that checker's findings and note "unavailable" in the gate question — do not block PR creation for checker failures.

### Phase 2 — Create PR

Follow **all steps in `mine-create-pr`** exactly (read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-create-pr/SKILL.md` and execute its full workflow — platform detection, draft PR, changelog entry + PR-number annotation, ready transition). Phase 1 already committed and pushed, so create-pr's push check passes. Return the PR URL it produces.
