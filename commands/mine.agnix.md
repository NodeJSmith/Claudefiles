---
description: Validate agent, skill, command, and CLAUDE.md files with agnix.
---

# Validate AI Config Files

## Arguments

`$ARGUMENTS` — optional path or glob to scope validation (e.g. `agents/`, `skills/mine.foo/SKILL.md`). If omitted, validates the entire repo.

Run agnix from the repo root:

```bash
agnix .
```

Or scoped to a specific path:

```bash
agnix $ARGUMENTS
```

Report findings grouped by severity (errors first, then warnings). For each finding:
- File and line number
- Rule ID and description
- How to fix it

Summarize with total error and warning counts. If clean, say so explicitly.
