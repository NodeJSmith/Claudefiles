---
name: mine-create-issue
description: "Use when the user says: 'create an issue', 'file an issue', 'open an issue', 'write an issue', 'new issue for this'. Codebase-aware issue creation — investigates the code to produce well-structured issues with acceptance criteria, affected areas, and enough detail for automated triage."
user-invocable: true
---

# Create Issue

Codebase-aware issue creation. Dispatches a subagent to investigate the code and draft a structured issue, then handles preview and creation interactively.

To enrich an existing issue, use the `issue-refiner` agent instead.

## Arguments

$ARGUMENTS — a description of the issue to create. Can be:
- A short description: `/mine-create-issue "add retry logic to the webhook sender"`
- A bug report: `/mine-create-issue "500 error when submitting empty form"`
- Empty: ask the user what they want to file

## Phase 1: Classify and Gather

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

## Phase 2: Investigate and Draft

Launch one subagent (`model: sonnet`, `subagent_type: general-purpose`) to investigate the codebase and draft the issue:

> Investigate and draft an issue for this codebase.
>
> **Type:** <classified type>
> **Description:** <user's description + any follow-up answers>
>
> Read `${CLAUDE_HOME:-~/.claude}/skills/mine-create-issue/worker.md` for the complete workflow. Follow every step.

Parse the subagent's response to extract the title and body (formatted as `TITLE:` and `BODY:` sections).

## Phase 3: Preview

Display the full issue (title + body) to the user, then:

```
AskUserQuestion:
  question: "How does this look?"
  header: "Preview"
  multiSelect: false
  options:
    - label: "Create it"
      description: "File the issue on GitHub"
    - label: "Edit first"
      description: "I want to adjust something before creating"
    - label: "Cancel"
      description: "Don't create the issue"
```

If **"Edit first"**: ask what to change, revise, and re-preview. Repeat until the user selects "Create it" or "Cancel".

## Phase 4: Create

Run `gh-issue overview` once to see available labels and milestones.

**Labels:** Match the issue type to existing labels:
- bug → "bug" label (if it exists)
- feature → "enhancement" label (if it exists)
- task/chore → no default label unless the repo has one

**Milestones:** If >50% of recent issues have milestones, pick the milestone that fits the work's scope.

Create the issue:

1. Run `get-skill-tmpdir mine-create-issue` — note the path
2. Write the issue body to `<tmpdir>/issue-body.md`
3. Run:

```bash
gh-issue create --title "<title>" --body-file <tmpdir>/issue-body.md [--label "<label>"] [--milestone "<name>"]
```

Display the issue URL and number.

### Offer next action

```
AskUserQuestion:
  question: "Issue created. What next?"
  header: "Next"
  multiSelect: false
  options:
    - label: "Create another"
      description: "File another issue"
    - label: "Start working on it"
      description: "Run /mine-build to implement this issue"
    - label: "Done"
      description: "Stop here"
```

If **"Create another"**: restart from Phase 1.
If **"Start working on it"**: run `/mine-build` with the issue context.
