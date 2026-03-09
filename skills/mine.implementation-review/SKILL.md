---
name: mine.implementation-review
description: Post-execution quality gate for a completed caliper plan. Reviews all changed files against the plan and design doc using an Opus subagent. 7-category checklist with approve/fix/abandon verdict.
user-invokable: true
---

# Implementation Review

Post-execution quality gate. After `/mine.orchestrate` finishes, this reviews the full implementation against the original plan and design doc. Uses an Opus subagent for highest-quality judgment across 7 categories.

## Arguments

$ARGUMENTS — path to a `plan.md` file. If empty, find the most recently modified `design/plans/*/plan.md` and confirm before proceeding.

## Phase 1: Read the Plan, Design Doc, and Changed Files

### Locate the plan

If $ARGUMENTS is provided, use it directly. If empty:

```
Glob: design/plans/*/plan.md
```

Sort by modification time, take the most recent. Confirm:

```
AskUserQuestion:
  question: "Found plan.md at <path>. Review its implementation?"
  header: "Confirm plan"
  multiSelect: false
  options:
    - label: "Yes — review it"
    - label: "No — let me specify the path"
      description: "Tell me the correct path and I'll use that"
```

### Read the plan and design doc

Read the plan.md. From the `**Design doc:**` field, read the design doc as well.

If the design doc is missing or not found, proceed with plan-only review and automatically set checklist item 7 (test coverage) to WARN with the note "no design doc available for cross-reference."

### Collect changed files

Run the git diff to find which files were changed since the branch diverged from the default branch:

```bash
git-default-branch | xargs -I {} git diff --name-only {}
```

If the output is empty (no diverged commits), fall back to:

```bash
git diff --name-only HEAD~1
```

Read each changed file. If the list is large (more than 15 files), read the files listed in the plan's `files` fields first, then read any remaining changed files that aren't in the plan.

## Phase 2: Dispatch Opus Reviewer Subagent

### Prepare temp file

```bash
get-tmp-filename
```

Use the path printed by the command exactly — do not construct it manually.

### Read reviewer prompt

Read `~/.claude/skills/mine.implementation-review/reviewer-prompt.md`.

### Launch Opus subagent

Launch a general-purpose subagent using the Opus model (claude-opus-4-6). Pass this prompt (fill in bracketed values):

```
You are reviewing a completed caliper plan implementation.

## Plan content
<full plan.md content>

## Design doc content
<full design.md content, or "Not available" if missing>

## Changed files
<for each changed file: filename + full content>

## Your instructions
<full reviewer-prompt.md content>

Write your complete structured review to: <temp file path>
```

The subagent will write the review to the temp file.

## Phase 3: Present Findings

Read the temp file. Format the results clearly:

1. **Checklist results** — one line per item: `N. <name>: PASS|WARN|FAIL — note`
2. **Verdict** — APPROVE, REQUEST_FIXES, or ABANDON (bold, prominent)
3. **Summary** — 2-3 sentences from the subagent
4. **Blocking issues** — if verdict is REQUEST_FIXES or ABANDON
5. **Suggestions** — non-blocking notes, if any

## Phase 4: Gate

```
AskUserQuestion:
  question: "Implementation review complete. What would you like to do?"
  header: "Review verdict"
  multiSelect: false
  options:
    - label: "Approve — mark plan as implemented"
      description: "Update plan.md Status to 'implemented'"
    - label: "Request fixes"
      description: "Surface blocking issues and return to execution"
    - label: "Abandon"
      description: "Save plan as abandoned and stop"
```

### On "Approve"

Update the plan.md `**Status:**` field to `implemented`.

Confirm:
> Implementation approved. Plan status updated to `implemented` at `<path>`.

Check whether `SOPHIA.yaml` exists in the repo root:

```
Glob: SOPHIA.yaml
```

If found, offer:
> Run `sophia cr close` to close the CR.

### On "Request fixes"

Surface the reviewer's blocking issues as a numbered list. Tell the user:
> Address these issues and re-run `/mine.orchestrate <plan path>` to retry the affected tasks, then run `/mine.implementation-review <plan path>` again.
>
> **Blocking issues:**
> [numbered list]

### On "Abandon"

Update the plan.md `**Status:**` field to `abandoned`.

Confirm: "Plan saved as abandoned at `<path>`."
