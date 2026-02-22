---
description: Scan open issues, classify by effort, and pick one to deep-dive.
---

# Issues Scan Command

Browse and classify open issues, then hand off to `/mine.issues` for deep-dive. Supports GitHub (`gh`) and Jira (`jira`) via the `$ISSUE_TRACKER` env var.

## Arguments

$ARGUMENTS — optional filters passed through to the underlying CLI tool.

## Phase 1: Tool Detection

Read `$ISSUE_TRACKER`.

- If **unset or empty**: tell the user `$ISSUE_TRACKER is not configured. Set it to "gh" or "jira" in your context var file.` and **stop**.
- If set to something other than `gh` or `jira`: tell the user `Unsupported ISSUE_TRACKER value: "$ISSUE_TRACKER". Expected "gh" or "jira".` and **stop**.

## Phase 2: Scan (Subagent)

Launch a **Task subagent** (`subagent_type: general-purpose`, `model: haiku`) with this prompt:

> **If `$ISSUE_TRACKER` is `gh`:**
> Run `gh issue list --state open --limit <N> --sort created --order asc --json number,title,labels,assignees,createdAt` where N is a random number between 30 and 75. Pass through any user-provided filters: $ARGUMENTS
>
> **If `$ISSUE_TRACKER` is `jira`:**
> Run `jira issue list --plain --no-truncate` with any user-provided filters passed through: $ARGUMENTS
>
> If the CLI tool fails (not installed, not authenticated, no issues, etc.), return the error message and stop.
>
> Do NOT write scripts (Python, jq, or otherwise) — use your own reasoning to classify and format the output.
>
> From the results, classify each issue by estimated effort using only the title and labels (do NOT fetch bodies). Use these heuristics:
> - Labels like `good first issue`, `bug`, `typo`, `docs` → small
> - Labels like `enhancement`, `feature` → medium
> - Labels like `epic`, `architecture`, `breaking` → large
> - No clear signals → use title keywords as best guess
>
> Randomly select up to 10 issues from the full results and return them as a markdown table in that random order:
>
> ```
> | Key | Title | Labels | Assignee | Est. Effort |
> ```
>
> For GitHub, the Key column is the issue number. For Jira, it's the issue key (e.g. PROJ-123).
>
> Return ONLY the table (or error message). No commentary.

Display the table from the subagent result.

## Phase 3: Pick (Main Context)

Use `AskUserQuestion` with issue titles as options (single-select, max 4 options from the top of the table). If more than 4 issues, pick the top 4 and let the user type "Other" for a different key.

If Phase 2 returned an error or no issues, display the message and stop.

## Phase 4: Handoff

Tell the user to run `/mine.issues <key>` with their chosen issue key(s) to deep-dive, or run it directly on their behalf.
