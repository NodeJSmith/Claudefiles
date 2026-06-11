---
name: mine.ship
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

Follow **all steps in `mine.commit-push`** exactly (read `skills/mine.commit-push/SKILL.md` and execute its full workflow — commit quality gates included). When that phase completes successfully — changes committed and pushed — continue to Phase 2 below.

### Phase 1.5 — Clean Code Gate

After Phase 1 completes (changes committed and pushed), check for a prior clean-code run:

```bash
find /tmp -maxdepth 2 -name 'clean-code-summary.md' -path '*/claude-mine-orchestrate-*' 2>/dev/null | xargs -r ls -t 2>/dev/null | head -5
```

- For each match (most recent first), read its first line and check if it contains the current HEAD SHA (`git rev-parse --short HEAD`). If any match, skip this phase with a note: "Stylistic review already completed."
- If no files found or no SHA match, run `/mine.clean-code` on the branch diff. Note: prior-run detection only applies when mine.orchestrate ran mine.clean-code. Manual mine.clean-code runs are not detected.

When mine.clean-code presents its own next-steps prompt ("What would you like to do with these findings?"), choose "Note and move on" — this phase handles the fix/skip/stop decision.

If mine.clean-code produces findings, present:

```
AskUserQuestion:
  question: "Stylistic review found findings. What next?"
  header: "Clean code"
  multiSelect: false
  options:
    - label: "Address findings"
      description: "Apply fixes top-to-bottom, then proceed to PR creation"
    - label: "Ship anyway"
      description: "Proceed to PR creation with findings noted"
    - label: "Stop here"
      description: "Pause; I'll address findings manually"
```

- **"Address findings"**: apply fixes top-to-bottom inline (no subagent), then stage, commit (`style: address clean-code findings`), and push before proceeding to Phase 2 — mine.create-pr verifies the branch is fully pushed
- **"Ship anyway"**: proceed to Phase 2
- **"Stop here"**: stop

If mine.clean-code produces no findings, proceed to Phase 2 automatically.

If any checker subagent fails to complete, skip that checker's findings and note "unavailable" in the gate question — do not block PR creation for checker failures.

### Phase 2 — Create PR

Follow **all steps in `mine.create-pr`** exactly (read `skills/mine.create-pr/SKILL.md` and execute its full workflow — platform detection, draft PR, CHANGELOG PR-number update, ready transition). Phase 1 already committed and pushed (so create-pr's push check passes) and already archived task files (so its archival step finds nothing and skips silently). Return the PR URL it produces.
