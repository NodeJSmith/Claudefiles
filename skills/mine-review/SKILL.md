---
name: mine-review
description: "Use when the user says: \"review my changes\", \"run the reviewers\", \"code and integration review\", \"readability review\", \"maintainability review\", \"sniff test this\", \"WTF check\", \"code smells\", \"is this code any good\", \"fresh eyes on this branch\", \"review this directory\", \"check this module\", \"review this skill\", \"review these instructions\". Dispatches three parallel reviewers — code, integration, and a readability pass for code; consistency, instruction quality, and writing quality for instruction files — and consolidates findings into one prioritized report."
user-invocable: true
---

# Technical Review

Dispatches three parallel reviewers adapted to content type. Code: correctness, integration fit, readability. Instruction files: consistency, instruction quality, writing quality. Consolidates into a prioritized report.

## Arguments

$ARGUMENTS — optional scope. Empty for full branch diff, or a directory/file list. Path mode when files exist with no branch changes.

## Phase 1: Determine Scope

Read and execute `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-review/scope-detection.md`.

## Phase 2: Dispatch Reviewers

### Pre-compute diff (diff mode only)

1. `get-skill-tmpdir mine-review` → `<tmpdir>`
2. `git rev-parse HEAD` → `<sha>`
3. `<diff command> > <tmpdir>/diff.patch`

### Detect review mode

A file is an **instruction file** if it has a `.md` extension. If ALL files are instruction files, use **instruction mode**. Otherwise **code mode**.

### Build scope line

- **Diff mode**: `Diff at <tmpdir>/diff.patch (HEAD: <sha>). Read changed files for surrounding context. Before relying on the diff, verify HEAD matches <sha>.`
- **Path mode**: `Review these existing files (not a diff): <file list>`
- **Instruction diff mode** — append: `Read every changed file in full, not just diff hunks.`

### Code mode — dispatch all three in one message

Each agent has its own checklist and output format. Pass scope only:

- `subagent_type: "code-reviewer"` — `Review changes. <scope line>`
- `subagent_type: "integration-reviewer"` — `Review changes. <scope line>`
- `subagent_type: "wtf-reviewer"` — `Review changes. <scope line>`

### Instruction mode — dispatch all three in one message

- `subagent_type: "fine-toothed-comb"` — `Review these instruction files for consistency, accuracy, and completeness. <scope line>. Read sibling files for cross-reference context.`
- `subagent_type: "instruction-quality-reviewer"` — `Review these instruction files. <scope line>`
- `subagent_type: "writing-quality-reviewer"` — `Review these instruction files. <scope line>`

## Phase 3: Consolidate and Present

### Deduplicate

If two reviewers flagged the same issue, keep one entry and note the cross-signal: `(flagged by code-review + readability pass)`.

### Validity assessment

Apply the protocol from `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-challenge/findings-protocol.md`: findings valid by default; flagging one as likely invalid requires a concrete evidence trail.

### Present the report

Organize by severity, not by reviewer. Report header:

```markdown
## [Technical|Instruction] Review: [branch name or target path]

**Scope:** N files changed, +X/-Y lines (diff) | N files, X total lines (path)
**[Reviewer 1]:** PASS / WARN / FAIL
**[Reviewer 2]:** PASS / WARN / FAIL
**[Reviewer 3]:** X findings (N HIGH, N MEDIUM, N LOW)
**Likely-invalid:** N
```

Source labels — code mode: `Code`, `Integration`, `Readability`. Instruction mode: `Consistency`, `Instruction`, `Writing`.

Findings in severity-grouped tables (`### Critical / High`, `### Medium`, `### Low`). Each finding includes the proposed fix — the specific edit that would be applied. The user decides what to fix based on seeing both the problem and the proposed edit. Likely-invalid findings in a separate section with Claimed/Actually/Why-invalid fields.

### Next steps

```
AskUserQuestion:
  question: "What would you like to do with these findings?"
  header: "Next steps"
  multiSelect: false
  options:
    - label: "Fix all"
      description: "Apply the proposed fixes listed above, highest severity down, then re-read the modified content"
    - label: "Fix critical/high only"
      description: "Address blockers, leave medium/low for later"
    - label: "Note and move on"
      description: "Acknowledged — no fixes this session"
```

If fixing: work through findings top-down by severity, making edits directly. After fixes: "Fixes complete — run `/mine-commit-push` or proceed to commit when ready."

## What This Skill Does NOT Do

- **Deep codebase audit** — use `/mine-audit`
- **Exhaustive style sweep** — use `/mine-clean-code`
- **Automatic fixing without asking** — it diagnoses, then asks what to fix
