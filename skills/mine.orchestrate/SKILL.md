---
name: mine.orchestrate
description: Execute a caliper plan task-by-task with implementer + reviewer subagent loop. Handles TDD, deviation classification, and sophia CR integration.
user-invokable: true
---

# Orchestrate

Execute an approved caliper plan. Runs each task through a three-subagent loop: executor implements, spec reviewer verifies, quality reviewer grades. Gates on deviations. Integrates with sophia CR tracking if active.

## Arguments

$ARGUMENTS — path to a `plan.md` file. If empty, find the most recently modified `design/plans/*/plan.md` and confirm before proceeding.

## Phase 0: Locate the Plan

If $ARGUMENTS is provided, use it directly. If empty:

```
Glob: design/plans/*/plan.md
```

Sort by modification time, take the most recent. Confirm:

```
AskUserQuestion:
  question: "Found plan.md at <path>. Execute this plan?"
  header: "Confirm plan"
  multiSelect: false
  options:
    - label: "Yes — execute it"
    - label: "No — let me specify the path"
      description: "Tell me the correct path and I'll use that"
```

Read the plan file. Check `**Status:**` — if it is not `approved`, warn the user:
> This plan's status is `<status>`, not `approved`. It may not have passed review. Continue anyway?

## Phase 1: Optional Sophia CR Check

Check whether a `SOPHIA.yaml` file exists in the repo root.

```
Glob: SOPHIA.yaml
```

If it exists, run:

```bash
sophia cr status --json
```

Read the output. If an active CR is found:
- Surface the CR name and current phase to the user
- Note which tasks the CR marks as done vs pending
- Use this as the starting task suggestion in Phase 2

If no SOPHIA.yaml or no active CR, proceed silently.

## Phase 2: Parse Tasks and Select Start Point

### Parse the plan

Extract all `## Task N:` blocks from the plan. Build a task list:
- Task number and title
- Files field
- Verification command
- Done-when criteria

Present the task list to the user with task numbers and titles.

### Select start point

```
AskUserQuestion:
  question: "Which task should we start from?"
  header: "Resume point"
  multiSelect: false
  options:
    - label: "Task 1 — start from the beginning"
    - label: "Resume from a specific task"
      description: "Tell me the task number and I'll start there"
    - label: "Resume from sophia CR checkpoint"
      description: "Only available if a sophia CR was found in Phase 1 with a suggested start task"
```

If a sophia CR suggested a start point in Phase 1, note it in the question text: "Sophia CR suggests starting from Task N."

## Phase 3: Per-Task Execution Loop

For each task from the start point to the end of the plan:

### Step 1: Announce the task

Tell the user:
> **Task N: <title>**
> Files: `<files>`
> Verification: `<verification command>`

### Step 2: Get temp files

Make three separate Bash tool calls, each a bare `get-tmp-filename` invocation. Record the path printed by each call:
- First call → executor output path
- Second call → spec reviewer output path
- Third call → quality reviewer output path

### Step 3: Launch executor subagent

Read these files:
- `~/.claude/skills/mine.orchestrate/phase-executor-prompt.md`
- `~/.claude/skills/mine.orchestrate/implementer-prompt.md`
- `~/.claude/skills/mine.orchestrate/tdd.md`

Launch a general-purpose subagent with this prompt (fill in bracketed values):

```
You are executing a single task from a caliper implementation plan.

## Task spec
<full ## Task N: block from plan.md>

## Phase executor instructions
<full phase-executor-prompt.md content>

## Implementer instructions
<full implementer-prompt.md content>

## TDD reference
<full tdd.md content>

Write your structured result to: <executor temp file path>
```

Wait for the subagent to complete. Read the executor temp file.

### Step 4: Launch spec reviewer subagent

Read `~/.claude/skills/mine.orchestrate/spec-reviewer-prompt.md`.

Launch a general-purpose subagent:

```
You are independently verifying a completed task.

## Task spec
<full ## Task N: block from plan.md>

## Executor result
<full executor temp file content>

## Spec reviewer instructions
<full spec-reviewer-prompt.md content>

Write your structured review to: <spec reviewer temp file path>
```

Wait for the subagent to complete. Read the spec reviewer temp file.

### Step 5: Classify deviations

Compare executor result and spec reviewer verdict:

| Condition | Action |
|-----------|--------|
| Executor PASS + Spec reviewer PASS | Proceed to quality review |
| Executor auto-fix deviation noted | Log it, proceed to quality review |
| Spec reviewer WARN | Proceed to quality review; surface warning to user after quality review |
| Spec reviewer FAIL | Mark task FAIL; surface to user (gate at Step 7) |
| Executor BLOCKED (any reason) | Mark task BLOCKED; surface to user (gate at Step 7) |
| Executor BLOCKED (architectural) | Mark task BLOCKED with architectural flag; do not retry without plan change |

### Step 6: Launch quality reviewer subagent

(Run this even if spec reviewer has WARNs — still useful to have the quality pass.)

Read `~/.claude/skills/mine.orchestrate/code-quality-reviewer-prompt.md`.

Launch a general-purpose subagent:

```
You are performing a post-task code quality review.

## Task spec
<full ## Task N: block from plan.md>

## Executor result
<full executor temp file content>

## Quality reviewer instructions
<full code-quality-reviewer-prompt.md content>

Write your quality review to: <quality reviewer temp file path>
```

Wait for the subagent to complete. Read the quality reviewer temp file.

### Step 7: Present results and gate

Present a summary:

```
**Task N: <title> — <overall verdict>**

Spec review: PASS|WARN|FAIL
Quality review: PASS|NEEDS_ATTENTION

[Any deviations noted]
[Any WARN or FAIL details]
```

Then gate:

```
AskUserQuestion:
  question: "Task N complete. What next?"
  header: "Task N gate"
  multiSelect: false
  options:
    - label: "Continue to Task N+1"
      description: "Move on (only shown if verdict is PASS or WARN)"
    - label: "Fix and retry this task"
      description: "Re-run the executor with the reviewer's notes"
    - label: "Mark as blocked and skip"
      description: "Note the blocker and move to the next task"
    - label: "Stop here"
      description: "Pause execution; resume later with /mine.orchestrate"
```

If the verdict is BLOCKED (architectural), do not offer "Continue" — only "Fix and retry" or "Stop here".

### Step 8: Sophia CR update (if active)

If a sophia CR was detected in Phase 1, offer:

```
AskUserQuestion:
  question: "Mark Task N as done in the sophia CR?"
  header: "Sophia update"
  multiSelect: false
  options:
    - label: "Yes — sophia cr task done"
    - label: "No — skip sophia update"
```

If "Yes": `sophia cr task done`

### Loop to next task

After the gate, continue with the next task in sequence. Track which tasks completed (PASS), had warnings (WARN), were blocked (BLOCKED), or failed (FAIL).

## Phase 4: Post-Execution Handoff

After all tasks are processed (or user chose "Stop here"), present a summary table:

```
| Task | Title | Verdict |
|------|-------|---------|
| 1    | ...   | PASS    |
| 2    | ...   | WARN    |
...
```

Then offer:

```
AskUserQuestion:
  question: "Execution complete. Run implementation review?"
  header: "Next step"
  multiSelect: false
  options:
    - label: "Yes — run /mine.implementation-review"
      description: "Post-execution quality gate across all tasks"
    - label: "No — I'll review manually"
      description: "Stop here"
```

If "Yes": invoke `/mine.implementation-review <plan path>` directly.
