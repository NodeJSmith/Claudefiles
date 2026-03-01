---
description: Validate agent, skill, command, and CLAUDE.md files with agnix.
---

# Validate AI Config Files

Run agnix from the repo root:

```bash
agnix .
```

With $ARGUMENTS (optional path to scope to a file or directory):
```bash
agnix $ARGUMENTS
```

Report findings grouped by severity (errors first, then warnings). For each finding:
- File and line number
- Rule ID and description
- How to fix it

Summarize with total error and warning counts. If clean, say so explicitly.
