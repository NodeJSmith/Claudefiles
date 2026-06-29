---
name: mine-create-issue
description: "Use when the user says: 'create an issue', 'file an issue', 'open an issue', 'write an issue', 'new issue for this'. Codebase-aware issue creation — investigates the code to produce well-structured issues with acceptance criteria, affected areas, and enough detail for automated triage."
user-invocable: true
---

# Create Issue

Codebase-aware issue creation. Dispatches a subagent to investigate the code, draft a structured issue, and create it on GitHub.

To enrich an existing issue, use the `issue-refiner` agent instead.

## Arguments

$ARGUMENTS — a description of the issue to create. Can be:
- A short description: `/mine-create-issue "add retry logic to the webhook sender"`
- A bug report: `/mine-create-issue "500 error when submitting empty form"`
- Empty: ask the user what they want to file

## Classify and Gather

If $ARGUMENTS is empty, ask the user: "What do you want to create an issue for?"

Classify the issue type from the description:

| Type | Signals |
|------|---------|
| bug | "error", "broken", "crash", "fails", "wrong", "500", reproduction context |
| feature | "add", "new", "support", "enable", "implement" |
| task | "refactor", "rename", "move", "split", "clean up", "remove", "update", "upgrade" |
| chore | "deps", "CI", "config", "version bump" |

When signals overlap, prefer the type whose follow-up questions would extract the most useful detail. If genuinely ambiguous, default to task.

### Targeted follow-ups

Ask only what's missing from the description. Skip questions the user already answered. Keep this to **1-2 questions max**. The codebase investigation fills in the technical detail — don't ask the user for file paths or function names.

**Bug** — what's happening vs what should happen; how to reproduce.
**Feature** — what problem this solves; any constraints or non-goals.
**Task / Chore** — only ask if the scope is ambiguous.

## Execute

Launch one subagent (`model: sonnet`, `subagent_type: general-purpose`):

> Create an issue for this codebase.
>
> **Type:** <classified type>
> **Description:** <user's description + any follow-up answers>
>
> Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-create-issue/worker.md` for the complete workflow. Follow every step.

The subagent returns the issue URL, or an error message if something blocked it.

Present the result to the user.
