---
name: mine-create-pr
description: "Use when the user says: \"create PR\" or \"open pull request\". Reviews branch changes and creates a PR on GitHub or Azure DevOps."
user-invocable: true
---

# Create PR

## Step 1: Review-Question Staleness Check

Before creating the PR, run `check-review-questions` (no arguments). If it produces output, present it to the user and ask:

```
AskUserQuestion:
  question: "This branch changes code referenced by REVIEW.md review questions (shown above). Want to update them before creating the PR?"
  header: "Review Q's"
  multiSelect: false
  options:
    - label: "Update now"
      description: "Open the flagged REVIEW.md files and update the review questions"
    - label: "Skip"
      description: "Create the PR without updating — questions may be stale"
```

- **"Update now"**: For each flagged `REVIEW.md` file, read it, read the changed code it references, and update the review questions to reflect the current code. Commit (`docs: update REVIEW.md review questions`) and push.
- **"Skip"**: Continue.

If `check-review-questions` produces no output, skip silently.

## Step 2: Create PR

Launch one subagent (`subagent_type: standard-worker`):

> Create a PR for the current branch.
>
> Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-create-pr/worker.md` for the complete workflow. Follow every step in order. Do NOT use the Skill tool — the instructions are in worker.md, not a skill.

The subagent returns the PR URL, or an error message if something blocked it (unsupported platform, branch not pushed, PR already exists with its URL).

## Step 3: Present Result

Present the PR URL to the user.
