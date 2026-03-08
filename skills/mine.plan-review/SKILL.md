---
name: mine.plan-review
description: Review a caliper plan with an Opus subagent against a 6-point checklist, then gate on approve/revise/abandon.
user-invokable: true
---

# Plan Review

Review a caliper implementation plan for correctness, completeness, and design alignment before execution begins. Uses a subagent reviewer against a 6-point checklist.

## Arguments

$ARGUMENTS — path to a `plan.md` file. If empty, find the most recently modified `design/plans/*/plan.md` and confirm with the user before proceeding.

## Phase 1: Read the Plan and Design Doc

### Locate the plan

If $ARGUMENTS is provided, use it directly. If empty:

```
Glob: design/plans/*/plan.md
```

Sort by modification time, take the most recent. Then confirm:

```
AskUserQuestion:
  question: "Found plan.md at <path>. Review this?"
  header: "Confirm plan"
  multiSelect: false
  options:
    - label: "Yes — review it"
    - label: "No — let me specify the path"
      description: "Tell me the correct path and I'll use that"
```

### Read both documents

Read the plan.md. From the plan header, extract the **Design doc:** path. Read that design doc too. Both are required — do not proceed without both.

If the design doc path is not in the plan header or the file doesn't exist, note it as a structural issue (automatic WARN on checklist item 3 — design alignment).

## Phase 2: Dispatch Reviewer Subagent

### Prepare temp file

Get a temp file path for the review output:

```bash
get-tmp-filename
```

The path printed is `${CLAUDE_CODE_TMPDIR:-/tmp}/claude-cmd-<random>.txt`. Use this exact path — do not construct it manually.

### Read reviewer prompt

Read `~/.claude/skills/mine.plan-review/reviewer-prompt.md` to get the checklist content.

### Launch subagent

Launch a general-purpose subagent with this prompt (fill in the bracketed values from the files you read):

```
You are reviewing a caliper implementation plan.

## Plan content
<full plan.md content>

## Design doc content
<full design.md content>

## Your instructions
<full reviewer-prompt.md content>

Write your complete structured review to: <temp file path>
```

The subagent will write the review to the temp file.

## Phase 3: Present Findings

Read the temp file. Format the results clearly:

1. **Checklist results** — one line per item: `N. <name>: PASS|WARN|FAIL — note`
2. **Verdict** — APPROVE, REQUEST_REVISIONS, or ABANDON (bold, prominent)
3. **Summary** — 2-3 sentences from the subagent
4. **Blocking issues** — if verdict is REQUEST_REVISIONS or ABANDON
5. **Suggestions** — non-blocking notes, if any

## Phase 4: Gate

```
AskUserQuestion:
  question: "Review complete. What would you like to do?"
  header: "Plan review verdict"
  multiSelect: false
  options:
    - label: "Approve — begin execution"
      description: "Hand off to /mine.sophia to create a CR and start tracking"
    - label: "Request revisions"
      description: "Return to mine.draft-plan with the reviewer's notes"
    - label: "Abandon"
      description: "Save the plan as draft and stop"
```

### On "Approve"

Update the plan.md `**Status:**` field from `draft` to `approved`.

Tell the user:
> Plan approved. To begin execution, run `/mine.sophia create "<topic>"` and reference `<plan path>` in the CR contract.

### On "Request revisions"

Surface the reviewer's blocking issues as a numbered list. Tell the user:
> Run `/mine.draft-plan <design doc path>` with the following reviewer notes:
> [blocking issues list]

### On "Abandon"

Update the plan.md `**Status:**` field from `draft` to `abandoned`.

Confirm: "Plan saved as abandoned at `<path>`."
