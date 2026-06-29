---
task_id: "T09"
title: "Migrate peripheral skills and rules to cfl"
status: "planned"
depends_on: ["T03", "T07"]
implements: ["FR#27"]
---

## Summary

Replace all `spec-helper` references in skills outside mine-orchestrate: mine-plan, mine-define, mine-grill, mine-commit-push, mine-create-pr, mine-write-skill, and git-workflow.md. These are lower-complexity replacements — mostly `spec-helper init` → `cfl spec init`, `spec-helper validate` → `cfl spec validate`, and `spec-helper archive` → `cfl archive`.

## Target Files

- modify: `skills/mine-plan/SKILL.md`
- modify: `skills/mine-define/SKILL.md`
- modify: `skills/mine-grill/SKILL.md`
- modify: `skills/mine-commit-push/SKILL.md`
- modify: `skills/mine-create-pr/worker.md`
- modify: `skills/mine-write-skill/REFERENCE.md`
- modify: `rules/common/git-workflow.md`
- read: `design/specs/035-sqlite-orchestration-store/cli-design.md`

## Prompt

Replace spec-helper references in each file:

### skills/mine-plan/SKILL.md

Find `spec-helper validate <feature>` → replace with `cfl spec validate [--spec NNN]`. The cfl version auto-resolves the spec from CWD, so the explicit feature argument is no longer needed. If the skill passes a feature name, replace it with `--spec NNN` only if disambiguation is needed.

### skills/mine-define/SKILL.md

Find `spec-helper init <slug> --json` → replace with `cfl spec init <slug>`. Output JSON format changes: cfl adds `spec_id` field. Update any field name references.

### skills/mine-grill/SKILL.md (line 79)

Find `spec-helper init <slug> --json` → replace with `cfl spec init <slug>`.

### skills/mine-commit-push/SKILL.md (line 27)

The Task File Archival step currently runs:
```
spec-helper archive --all --dry-run --json
spec-helper archive --all
```

Replace with:
```
cfl archive --dry-run
cfl archive
```

Note: cfl has no `--all` flag — it auto-resolves to the current spec. The `--json` flag is gone (JSON is default).

### skills/mine-create-pr/worker.md (line 34)

Same archive pattern as mine-commit-push. Replace `spec-helper archive --all --dry-run --json` → `cfl archive --dry-run` and `spec-helper archive --all` → `cfl archive`.

Also update the error message from "spec-helper archive failed" to "cfl archive failed".

### skills/mine-write-skill/REFERENCE.md (line 44)

Replace the reference to spec-helper with cfl: "Use `cfl`, `get-skill-tmpdir`, and other `bin/` helpers where appropriate".

### rules/common/git-workflow.md (Task File Cleanup section)

The current section references `spec-helper archive --all --dry-run --json` and `spec-helper archive --all`. Replace with `cfl archive --dry-run` and `cfl archive`. Update the `find` command and the conditional logic to use cfl's output format.

The `spec-helper` availability check (`spec-helper` is available) should become a `cfl` availability check.

## Focus

- Each replacement is straightforward but the output JSON format differs. cfl doesn't need `--json` (it's the default) or `--all` (auto-resolves).
- git-workflow.md is loaded into context for every conversation — this is a high-visibility file. Keep the replacement clean and concise.
- mine-commit-push and mine-create-pr have nearly identical archive patterns — make sure both are updated consistently.
- Read each file before editing to understand the full context of the spec-helper call, not just the line.

## Verify

- [ ] FR#27: Zero references to `spec-helper` remain in mine-plan, mine-define, mine-grill, mine-commit-push, mine-create-pr, mine-write-skill, or git-workflow.md
