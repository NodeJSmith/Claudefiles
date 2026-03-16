---
name: mine.implementation-review
description: "Use when the user says: \"review the implementation\" or \"post-implementation review\". Quality gate that reviews changed files against design doc and WPs using an Opus subagent."
user-invokable: true
---

# Implementation Review

Post-execution quality gate. After `/mine.orchestrate` finishes, this reviews the full implementation against the original design doc and Work Packages. Uses an Opus subagent for highest-quality judgment across 7 categories.

## Arguments

$ARGUMENTS — path to a feature directory (`design/specs/NNN-feature/`) or a `design.md` file. If empty, find the most recently modified `design/specs/*/design.md` and confirm before proceeding.

---

## Phase 1: Read the Design Doc, Work Packages, and Changed Files

### Locate the feature directory

If $ARGUMENTS points to a `design/specs/NNN-*/` directory, use it directly.

If $ARGUMENTS points to a `design.md` file, the feature directory is one level up.

If $ARGUMENTS is empty:

```
Glob: design/specs/*/design.md
```

Sort by modification time, take the most recent. The feature directory is one level up. Confirm:

```
AskUserQuestion:
  question: "Found feature at <feature_dir>. Review its implementation?"
  header: "Confirm feature"
  multiSelect: false
  options:
    - label: "Yes — review it"
    - label: "No — let me specify the path"
      description: "Tell me the correct feature directory and I'll use that"
```

### Read design doc and WPs

Read `<feature_dir>/design.md` in full.

Read all `<feature_dir>/tasks/WP*.md` files in order. If no WP files exist, proceed with design-only review and note this in the summary.

### Collect changed files

Run the git diff to find which files were changed since the branch diverged from its base. Prefer the tracking branch so this works correctly for PRs targeting non-default branches:

```bash
git diff --name-only @{upstream}...HEAD 2>/dev/null
```

If that fails or returns empty (no tracking branch set), fall back to the default branch:

```bash
git-default-branch | xargs -I {} git diff --name-only "origin/{}...HEAD" 2>/dev/null || git-default-branch | xargs -I {} git diff --name-only "{}...HEAD"
```

If still empty, fall back to:

```bash
git diff --name-only HEAD~1
```

Read each changed file. If the list is large (more than 15 files), prioritize files referenced in the WP Subtasks sections first.

---

## Phase 2: Dispatch Opus Reviewer Subagent

### Review output path

Run `get-skill-tmpdir mine-impl-review` and use `<dir>/review.md` for the review output.

### Read reviewer prompt

Read `~/.claude/skills/mine.implementation-review/reviewer-prompt.md`.

### Launch Opus subagent

Launch a general-purpose subagent using the Opus model (claude-opus-4-6). Pass this prompt (fill in bracketed values):

```
You are reviewing a completed caliper v2 feature implementation.

## Design doc
<full design.md content>

## Work packages
<full content of each WP*.md in order, separated by "--- WP<NN> ---" headers>

## Changed files
<for each changed file: filename header + full content>

## Your instructions
<full reviewer-prompt.md content>

Write your complete structured review to: <temp file path>
```

The subagent will write the review to the temp file.

---

## Phase 3: Present Findings

Read the temp file. Format the results clearly:

1. **Checklist results** — one line per item: `N. <name>: PASS|WARN|FAIL — note`
2. **Verdict** — APPROVE, REQUEST_FIXES, or ABANDON (bold, prominent)
3. **Summary** — 2-3 sentences from the subagent
4. **Blocking issues** — if verdict is REQUEST_FIXES or ABANDON
5. **Suggestions** — non-blocking notes, if any

---

## Phase 4: Gate

```
AskUserQuestion:
  question: "Implementation review complete. What would you like to do?"
  header: "Review verdict"
  multiSelect: false
  options:
    - label: "Approve — mark design as implemented"
      description: "Update design.md Status to 'implemented'"
    - label: "Request fixes"
      description: "Surface blocking issues and return to execution"
    - label: "Abandon"
      description: "Save design as abandoned and stop"
```

### On "Approve"

Update the `design.md` `**Status:**` field to `implemented`.

Confirm:
> Implementation approved. Design status updated to `implemented` at `<path>`.

### On "Request fixes"

Surface the reviewer's blocking issues as a numbered list. Tell the user:
> Address these issues and re-run `/mine.orchestrate <feature_dir>` to retry the affected WPs, then run `/mine.implementation-review <feature_dir>` again.
>
> **Blocking issues:**
> [numbered list]

### On "Abandon"

Update the `design.md` `**Status:**` field to `abandoned`.

Confirm: "Design saved as abandoned at `<path>`."
