---
name: mine.plan-review
description: Review a design doc and work packages with an Opus subagent against a 6-point checklist, then gate on approve/revise/abandon.
user-invokable: true
---

# Plan Review

Review a design doc and its Work Packages for correctness, completeness, and design alignment before execution begins. Uses a subagent reviewer against a 6-point checklist.

## Arguments

$ARGUMENTS — path to a `design.md` file or a feature directory (`design/specs/NNN-feature/`). If empty, find the most recently modified `design/specs/*/design.md` and confirm with the user before proceeding.

## Phase 1: Read the Design Doc and Work Packages

### Locate the design doc

If $ARGUMENTS points to a feature directory (`design/specs/NNN-*/`), read `design.md` from that directory.

If $ARGUMENTS is a direct path to a `design.md`, use it directly. In this case, `<feature_dir>` is the parent directory of the file (e.g., `design/specs/NNN-feature/` when the path is `design/specs/NNN-feature/design.md`).

If $ARGUMENTS is empty:

```
Glob: design/specs/*/design.md
```

Sort by modification time, take the most recent. Then confirm:

```
AskUserQuestion:
  question: "Found design.md at <path>. Review this?"
  header: "Confirm design doc"
  multiSelect: false
  options:
    - label: "Yes — review it"
    - label: "No — let me specify the path"
      description: "Tell me the correct path and I'll use that"
```

### Read the design doc and work packages

Read the `design.md` in full.

Also read all `WP*.md` files from `<feature_dir>/tasks/` if they exist — these are what the reviewer will evaluate for feasibility, completeness, and design alignment.

If no WP files exist yet, proceed with a design-only review and note in the summary that WP files were not yet generated.

## Phase 2: Dispatch Reviewer Subagent

### Review output path

Run `get-skill-tmpdir mine-plan-review` and use `<dir>/review.md` for the review output.

### Read reviewer prompt

Read `~/.claude/skills/mine.plan-review/reviewer-prompt.md` to get the checklist content.

### Launch subagent

Launch a general-purpose subagent using the Opus model (claude-opus-4-6) for highest-quality review judgment. Pass this prompt (fill in the bracketed values from the files you read):

```
You are reviewing an implementation design and its work packages.

## Design doc content
<full design.md content>

## Work package files
<full content of each WP*.md, in order, separated by file headers>

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
      description: "Hand off to /mine.orchestrate to begin implementation"
    - label: "Request revisions"
      description: "Return to mine.draft-plan with the reviewer's notes"
    - label: "Abandon"
      description: "Save the plan as draft and stop"
```

### On "Approve"

Update the `design.md` `**Status:**` field from `draft` to `approved`.

Tell the user:
> Design approved. Run `/mine.orchestrate <feature_dir>` to begin implementation.

### On "Request revisions"

Surface the reviewer's blocking issues as a numbered list. Write them to the conversation so the user can copy them, then tell the user:
> Run `/mine.draft-plan <feature_dir>` and paste the following reviewer notes so the skill can incorporate them:
>
> [blocking issues list]

### On "Abandon"

Update the `design.md` `**Status:**` field from `draft` to `abandoned`.

Confirm: "Design saved as abandoned at `<path>`."
