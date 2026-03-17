---
description: Deep-dive one or more issues by key, or scan and pick if no keys given.
---

# Issues Command

Deep-dive specific issues by key, or fall through to scanning if no keys are provided. Supports GitHub (`gh`) and Jira (`jira`) via the `$ISSUE_TRACKER` env var.

## Arguments

$ARGUMENTS — zero or more issue keys. GitHub: `123 456`. Jira: `PROJ-123 PROJ-456`. If none provided, falls through to the scan flow.

## Phase 1: Tool Detection

Read `$ISSUE_TRACKER`.

- If **unset or empty**: tell the user `$ISSUE_TRACKER is not configured. Set it to "gh" or "jira" in your context var file.` and **stop**.
- If set to something other than `gh` or `jira`: tell the user `Unsupported ISSUE_TRACKER value: "$ISSUE_TRACKER". Expected "gh" or "jira".` and **stop**.

## Phase 2: Route

- **No arguments provided**: Run the full scan flow — behave exactly as `/mine.issues-scan` would (list, classify, pick, then deep-dive the chosen issue). Follow the same phases described in `mine.issues-scan.md`.
- **Arguments provided**: Continue to Phase 3 (Deep Dive).

## Phase 3: Deep Dive (Subagent)

For **each** issue key in the arguments, launch a **Task subagent** (`subagent_type: Explore`, `model: haiku`) with this prompt:

> **If `$ISSUE_TRACKER` is `gh`:**
> Run `gh-issue view <N> --json title,body,comments,labels,assignees,milestone` to get the full issue.
>
> **If `$ISSUE_TRACKER` is `jira`:**
> Run `jira issue view <KEY> --comments 5 --plain` to get the full issue.
>
> Then scan the codebase for files and areas mentioned in or related to the issue (grep for keywords, check referenced file paths, look at relevant modules).
>
> Return this structured summary and nothing else:
>
> ```
> ## Issue <KEY> — Title
> - **Description**: [condensed from body, 2-3 sentences max]
> - **Key comments**: [relevant discussion points, or "None" if no useful comments]
> - **Affected areas**: [files/modules identified from codebase scan]
> - **Estimated scope**: [small/medium/large with brief reasoning]
> - **Suggested approach**: [1-2 sentences]
> ```

Launch subagents **in parallel** when multiple keys are provided. Display all structured summaries.

## Phase 4: Next Step (Main Context)

Use `AskUserQuestion` to ask the user what they'd like to do next:

- **Create a plan** — Launch the planner to design an implementation approach for this issue
- **Just explore** — Continue researching the codebase without committing to a plan yet
- **Skip** — Done for now, I'll come back to this later

If the user picks "Create a plan":
1. **Branch naming reminder**: Check `git branch --show-current`. If the current branch name does not contain the issue number, remind the user:
   > "When you create your working branch, include the issue number so the PR links back automatically — e.g., `git checkout -b 123-short-description` or `claude --worktree 123-short-description`."
2. Launch the Agent tool with `subagent_type: "Planner"`, passing the issue context. Present the plan to the user via `AskUserQuestion` for approval.

Otherwise, follow their choice.
