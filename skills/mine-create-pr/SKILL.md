---
name: mine-create-pr
description: "Use when the user says: \"create PR\" or \"open pull request\". Reviews branch changes and creates a PR on GitHub or Azure DevOps."
user-invocable: true
---

# Create PR

Dispatches a subagent to handle the entire PR workflow: platform detection, diff analysis, PR body drafting, task archival, changelog entry + PR-number annotation, and marking ready.

## Execute

Launch one subagent (`model: sonnet`, `subagent_type: general-purpose`):

> Create a PR for the current branch.
>
> Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-create-pr/worker.md` for the complete workflow. Follow every step in order.

The subagent returns the PR URL, or an error message if something blocked it (unsupported platform, branch not pushed, PR already exists with its URL).

Present the result to the user.
