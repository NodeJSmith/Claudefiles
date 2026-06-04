---
task_id: "T01"
title: "Delete files and deregister from system config"
status: "planned"
depends_on: []
implements: ["FR#1", "FR#2", "FR#3", "FR#4", "FR#5", "FR#6", "FR#7", "FR#19"]
---

## Summary
Delete the 5 files/directories that comprise cm-extract-learnings and its supporting infrastructure, then remove their registrations from the system config files (settings.json, install.py, pyproject.toml). This is the foundational task — everything else depends on these components being gone.

## Prompt
Delete the following files and directories:
1. `skills-memory/cm-extract-learnings/` — entire directory (`rm -rf`)
2. `agents/cm-memory-auditor.md`
3. `agents/cm-signal-discoverer.md`
4. `packages/claude-memory/src/claude_memory/hooks/consolidation_check.py`
5. `packages/claude-memory/tests/test_consolidation.py`

Then make these surgical edits:

**`settings.json`** — Two removals:
- Remove `"Bash(cm-consolidation-check:*)"` from the `allowedTools` array (around line 28)
- In the `hooks.SessionStart` array, find the entry whose inner `hooks` array contains a command starting with `bash -c 'command -v cm-consolidation-check`. Remove that single element from the inner `hooks` array. Do NOT remove the entire SessionStart entry — it contains other commands.

**`install.py`** — Remove `"cm-extract-learnings"` from the memory bundle skills tuple (around line 137). Also remove `"cm-memory-auditor"` and `"cm-signal-discoverer"` from the agents tuple in the same bundle definition (around line 141).

**`packages/claude-memory/pyproject.toml`** — Remove the `cm-consolidation-check` line from `[project.scripts]` (line 18: `cm-consolidation-check   = "claude_memory.hooks.consolidation_check:main"`).

## Focus
- `settings.json` is shared config loaded by every Claude Code session. The SessionStart hook structure has one entry with an inner `hooks` array containing 6 commands. After this edit there should be 5 commands remaining. Do not accidentally remove sibling hook commands.
- `install.py` line 141 also lists the agents tuple for the memory bundle — both agents being deleted are there.
- The pyproject.toml entrypoint would create a broken CLI command if left in place after the source file is deleted.

## Verify
- [ ] FR#1: `skills-memory/cm-extract-learnings/` directory does not exist
- [ ] FR#2: `agents/cm-memory-auditor.md` does not exist
- [ ] FR#3: `agents/cm-signal-discoverer.md` does not exist
- [ ] FR#4: `packages/claude-memory/src/claude_memory/hooks/consolidation_check.py` does not exist
- [ ] FR#5: `packages/claude-memory/tests/test_consolidation.py` does not exist
- [ ] FR#6: `settings.json` contains no `cm-consolidation-check` permission or hook command
- [ ] FR#7: `install.py` does not reference `cm-extract-learnings`, `cm-memory-auditor`, or `cm-signal-discoverer`
- [ ] FR#19: `packages/claude-memory/pyproject.toml` contains no `cm-consolidation-check` entrypoint
