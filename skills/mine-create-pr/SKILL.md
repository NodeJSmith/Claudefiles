---
name: mine-create-pr
description: "Use when the user says: \"create PR\" or \"open pull request\". Reviews branch changes and creates a PR on GitHub or Azure DevOps."
user-invocable: true
---

# Create PR

Dispatches a subagent to handle the entire PR workflow: platform detection, diff analysis, PR body drafting, task archival, changelog entry + PR-number annotation, and marking ready.

## Execute

Launch one subagent (`subagent_type: standard-worker`):

> Create a PR for the current branch.
>
> Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-create-pr/worker.md` for the complete workflow. Follow every step in order. Do NOT use the Skill tool — the instructions are in worker.md, not a skill.

The subagent returns the PR URL, or an error message if something blocked it (unsupported platform, branch not pushed, PR already exists with its URL).

## Handle Review-Question Staleness

If the subagent's result contains `STALE_REVIEW_QUESTIONS:`, the branch modifies code that existing CLAUDE.md review-question files reference. Present the staleness output (everything after that marker, up to the PR URL) to the user, then ask:

```
AskUserQuestion:
  question: "This branch changes code referenced by CLAUDE.md review questions (shown above). Want to update them before marking the PR ready?"
  header: "Review Q's"
  multiSelect: false
  options:
    - label: "Update now"
      description: "Open the flagged CLAUDE.md files and update the review questions"
    - label: "Skip"
      description: "Leave the PR as-is — questions may be stale"
```

- **"Update now"**: For each flagged CLAUDE.md file, read it, read the changed code it references, and update the review questions to reflect the current code. Commit (`docs: update CLAUDE.md review questions`), push, and note the update alongside the PR URL.
- **"Skip"**: Continue.

## Present Result

Present the PR URL to the user.
