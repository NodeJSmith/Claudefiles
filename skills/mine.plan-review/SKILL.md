---
name: mine.plan-review
description: "Use when the user says: \"review this plan\", \"check the plan\", or \"plan review\". Reviews design doc and work packages against a 9-point checklist."
user-invocable: true
---

# Plan Review

Review a design doc and its Work Packages for correctness, completeness, and design alignment before execution begins. Uses a Sonnet subagent reviewer against a 9-point checklist.

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

Launch a general-purpose subagent with `model: sonnet`. Pass this prompt (fill in the bracketed values from the files you read):

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

If the reviewer's output includes non-blocking suggestions, present "Approve with suggestions" as the first (recommended) option. If there are no suggestions (clean APPROVE), omit it and show "Approve as-is" first.

**When suggestions exist:**

```
AskUserQuestion:
  question: "Review complete. What would you like to do?"
  header: "Plan verdict"
  multiSelect: false
  options:
    - label: "Approve with suggestions (Recommended)"
      description: "Apply the reviewer's non-blocking suggestions, then proceed"
    - label: "Approve as-is"
      description: "Skip suggestions; proceed to execution"
    - label: "Revise the plan"
      description: "Blocking issues found — return to mine.draft-plan with reviewer notes"
    - label: "Abandon"
      description: "Mark the design as abandoned and stop"
```

**When no suggestions exist:**

```
AskUserQuestion:
  question: "Review complete. What would you like to do?"
  header: "Plan verdict"
  multiSelect: false
  options:
    - label: "Approve as-is"
      description: "Plan is good; proceed to execution"
    - label: "Revise the plan"
      description: "Blocking issues found — return to mine.draft-plan with reviewer notes"
    - label: "Abandon"
      description: "Mark the design as abandoned and stop"
```

### On "Approve as-is"

Update the `design.md` `**Status:**` field from `draft` to `approved`.

**If invoked inline by `mine.build`** (the user chose "Full caliper workflow" or "Accelerated"), skip the gate below and invoke `/mine.orchestrate <feature_dir>` directly — `mine.build` handles the flow.

**Otherwise**, ask:

```
AskUserQuestion:
  question: "Plan approved. Begin implementation?"
  header: "Next step"
  multiSelect: false
  options:
    - label: "Yes — start execution"
      description: "Invoke /mine.orchestrate for this feature"
    - label: "No — I'll start later"
      description: "Stop here; the plan is approved and saved"
```

If "Yes": invoke `/mine.orchestrate <feature_dir>` directly.

### On "Approve with suggestions"

Apply the reviewer's non-blocking suggestions to `design.md` and/or `WP*.md` files. Restrict WP edits to cosmetic changes (wording, clarifications, review guidance) — substantive WP changes require re-running `/mine.draft-plan`. Show the user a brief summary of what was changed (file name + one-line description per change). Update the `design.md` `**Status:**` field from `draft` to `approved`.

Then follow the same gate as "Approve as-is" above (invoke `/mine.orchestrate` on approval).

### On "Revise the plan"

Surface the reviewer's blocking issues as a numbered list.

Invoke `/mine.draft-plan <feature_dir>` directly, passing the blocking issues as context. Tell the user:
> Returning to draft-plan with the reviewer's notes to regenerate work packages.

### On "Abandon"

Update the `design.md` `**Status:**` field from `draft` to `abandoned`.

Confirm: "Design saved as abandoned at `<path>`."
