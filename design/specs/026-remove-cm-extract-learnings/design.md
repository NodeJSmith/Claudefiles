# Design: Remove cm-extract-learnings and consolidation hooks

**Date:** 2026-06-04
**Status:** archived
**Scope-mode:** hold

## Problem

The cm-extract-learnings skill mines past sessions for knowledge to persist as memories, but it was inaccurate at picking what to remember. The in-conversation auto-memory rules (already in the system prompt) do this better by deciding in context. The consolidation reminder hooks nudge users to run extract-learnings periodically, which is now unnecessary. memsearch (tracked in Dotfiles #40) replaces the proactive surfacing role. These components are dead weight.

## Goals

- Remove all cm-extract-learnings code, agents, hooks, and references from the Claudefiles repo
- Zero grep hits for `extract-learnings`, `consolidation_check`, `cm-memory-auditor`, or `cm-signal-discoverer` in any active (non-archived) file
- No breakage to the remaining claude-memory infrastructure (session capture, SQLite storage, recall, token insights, setup/context/sync hooks)

## User Scenarios

### Jessica: Claude Code user
- **Goal:** Use Claude Code without dead extract-learnings prompts or consolidation nudges
- **Context:** Every session, on any of 5 machines

#### Clean session start
1. **Start a Claude Code session**
   - Sees: no consolidation reminder in session startup
   - Then: session proceeds normally with auto-memory and memsearch handling knowledge capture

#### Run install.py
1. **Re-run the installer**
   - Sees: cm-extract-learnings no longer appears in memory bundle selection
   - Then: installer completes without creating extract-learnings directories

## Functional Requirements

- **FR#1** The `skills-memory/cm-extract-learnings/` directory does not exist
- **FR#2** The `agents/cm-memory-auditor.md` file does not exist
- **FR#3** The `agents/cm-signal-discoverer.md` file does not exist
- **FR#4** The `packages/claude-memory/src/claude_memory/hooks/consolidation_check.py` file does not exist
- **FR#5** The `packages/claude-memory/tests/test_consolidation.py` file does not exist
- **FR#6** `settings.json` contains no `Bash(cm-consolidation-check:*)` permission entry and no SessionStart consolidation-check hook
- **FR#7** `install.py` does not reference `cm-extract-learnings` in the memory bundle skills tuple
- **FR#8** `skills-memory/capabilities-memory.md` contains no extract-learnings routing row
- **FR#9** `REFERENCE.md` contains no table rows for cm-extract-learnings, cm-memory-auditor, cm-signal-discoverer, or cm-consolidation-check
- **FR#10** `ONBOARDING.md` contains no mentions of consolidation nudge or extract-learnings
- **FR#11** `packages/claude-memory/src/claude_memory/hooks/onboarding.py` contains no consolidation reminder setup logic
- **FR#12** `packages/claude-memory/src/claude_memory/hooks/write_config.py` contains no consolidation-related config args or logic
- **FR#13** `tests/test_install.py` contains no references to cm-extract-learnings, cm-memory-auditor, or cm-signal-discoverer (mkdir calls, agent list entries, symlink assertions)
- **FR#14** `packages/claude-memory/README.md` contains no extract-learnings or consolidation-check feature table entries
- **FR#15** `packages/claude-memory/src/claude_memory/db.py` contains no consolidation keys in `DEFAULT_SETTINGS` or `_CONFIG_KEYS`
- **FR#16** `packages/claude-memory/tests/test_write_config.py` contains no consolidation-related assertions or test methods
- **FR#17** `skills-memory/cm-recall-conversations/SKILL.md` and `skills-memory/cm-recall-conversations/references/lenses.md` contain no `extract-learnings` lens references
- **FR#18** `packages/merge-settings/tests/test_merge.py` has the `cm-consolidation-check` entry removed from the hardcoded hook list and the count assertion updated
- **FR#19** `packages/claude-memory/pyproject.toml` contains no `cm-consolidation-check` entrypoint
- **FR#20** All remaining claude-memory functionality (session capture, SQLite storage, cm-recall-conversations, cm-get-token-insights, setup/context/sync hooks) continues to work

## Edge Cases

- Archived design specs (019, 018, etc.) and `CHANGELOG.md` reference extract-learnings as historical record — these must NOT be modified
- The `cm-recall-conversations` skill has a routing row in `skills-memory/capabilities-memory.md` — edits must preserve it (cm-search-conversations is a CLI tool with no routing row)
- `onboarding.py` and `write_config.py` contain both consolidation and non-consolidation logic — surgical removal must not break the remaining code paths

## Acceptance Criteria

- **AC#1** `grep -r 'extract-learnings\|consolidation.check\|consolidation_reminder\|consolidation_min\|cm-memory-auditor\|cm-signal-discoverer' --include='*.py' --include='*.md' --include='*.json' --include='*.toml' . | grep -v CHANGELOG | grep -v 'design/specs/'` returns no results (FR#1-FR#19)
- **AC#2** `uv run install.py --help` runs without error (FR#7)
- **AC#3** Existing tests pass: `timeout 300 pytest tests/` and `timeout 300 pytest packages/claude-memory/tests/` and `timeout 300 pytest packages/merge-settings/tests/` (FR#20)

## Key Constraints

No feature-specific constraints identified during discovery. This is a pure deletion task.

## Dependencies and Assumptions

- memsearch setup is tracked separately in Dotfiles #40 — this PR does not add memsearch, only removes what it replaces
- The auto-memory system prompt instructions are in the user's CLAUDE.md rules, not in this repo — no changes needed there

## Architecture

Pure deletion and surgical editing. No new code.

**Deletions (5 files/directories):**
1. `skills-memory/cm-extract-learnings/` — entire directory
2. `agents/cm-memory-auditor.md`
3. `agents/cm-signal-discoverer.md`
4. `packages/claude-memory/src/claude_memory/hooks/consolidation_check.py`
5. `packages/claude-memory/tests/test_consolidation.py`

**Surgical edits (15 files):**
1. `settings.json` — remove `Bash(cm-consolidation-check:*)` from permissions, remove the consolidation-check command from the SessionStart hook's inner `hooks` array (the SessionStart entry contains multiple commands; remove only the consolidation-check element)
2. `install.py` — remove `cm-extract-learnings` from memory bundle skills tuple
3. `skills-memory/capabilities-memory.md` — remove the extract-learnings routing row from the table
4. `REFERENCE.md` — remove table rows for the 3 deleted components + the consolidation-check hook
5. `ONBOARDING.md` — remove consolidation and extract-learnings mentions
6. `packages/claude-memory/src/claude_memory/hooks/onboarding.py` — remove consolidation reminder setup
7. `packages/claude-memory/src/claude_memory/hooks/write_config.py` — remove consolidation config args and logic
8. `packages/claude-memory/src/claude_memory/db.py` — remove consolidation keys from `DEFAULT_SETTINGS` and `_CONFIG_KEYS`
9. `tests/test_install.py` — remove all references to cm-extract-learnings, cm-memory-auditor, and cm-signal-discoverer (mkdir calls, agent list entries, symlink assertions)
10. `packages/claude-memory/tests/test_write_config.py` — remove consolidation-related assertions and test methods
11. `packages/claude-memory/README.md` — remove feature table entries
12. `skills-memory/cm-recall-conversations/SKILL.md` — remove the extract-learnings lens routing row
13. `skills-memory/cm-recall-conversations/references/lenses.md` — remove extract-learnings entries from all three tables
14. `packages/merge-settings/tests/test_merge.py` — remove `cm-consolidation-check` from the hardcoded hook list and update the count assertion
15. `packages/claude-memory/pyproject.toml` — remove the `cm-consolidation-check` entrypoint from `[project.scripts]`

**Order:** Deletions first (no dependencies), then surgical edits in any order, then verification grep.

## Replacement Targets

| Target | Replaced by | Action |
|---|---|---|
| cm-extract-learnings skill | memsearch (Dotfiles #40) + in-conversation auto-memory | Delete outright |
| cm-memory-auditor agent | No direct replacement needed — memsearch handles surfacing | Delete outright |
| cm-signal-discoverer agent | No direct replacement needed — memsearch handles surfacing | Delete outright |
| consolidation_check hook | No replacement — the nudge pattern is obsolete | Delete outright |

## Test Strategy

### Existing Tests to Adapt
- `tests/test_install.py` — remove cm-extract-learnings mkdir calls from individual test methods (`test_ignores_when_already_installed`, `test_installs_when_not_present`), remove cm-memory-auditor/cm-signal-discoverer from the agent list in `_setup_full_repo` and their symlink assertions; remaining assertions must still pass
- `packages/claude-memory/tests/test_write_config.py` — remove consolidation key assertions and the `test_consolidation_min_hours_floor` test method; remaining tests must still pass
- `packages/merge-settings/tests/test_merge.py` — update the `test_real_scenario_session_start_duplicate` hook list to reflect consolidation-check removal

### New Test Coverage
None needed — this is a pure removal. AC#1 (grep verification) and AC#3 (existing tests pass) cover correctness.

### Tests to Remove
- `packages/claude-memory/tests/test_consolidation.py` — tests the deleted consolidation_check hook

## Documentation Updates

- `REFERENCE.md` — remove 4 table rows (cm-extract-learnings skill, cm-memory-auditor agent, cm-signal-discoverer agent, cm-consolidation-check hook)
- `ONBOARDING.md` — remove extract-learnings and consolidation mentions from the Memory bundle description
- `packages/claude-memory/README.md` — remove extract-learnings and consolidation-check entries from the feature table
- `skills-memory/capabilities-memory.md` — remove the extract-learnings trigger phrase routing row

## Impact

### Changed Files
- `settings.json` — shared config; affects all Claude Code sessions
- `install.py` — installer; affects fresh installs and re-runs
- `skills-memory/capabilities-memory.md` — loaded into every session via rules
- `REFERENCE.md` — documentation
- `ONBOARDING.md` — documentation
- `packages/claude-memory/src/claude_memory/hooks/onboarding.py` — session hook
- `packages/claude-memory/src/claude_memory/hooks/write_config.py` — config generation
- `packages/claude-memory/src/claude_memory/db.py` — default settings and config keys
- `tests/test_install.py` — test file
- `packages/claude-memory/tests/test_write_config.py` — test file
- `packages/claude-memory/README.md` — documentation
- `skills-memory/cm-recall-conversations/SKILL.md` — skill routing table
- `skills-memory/cm-recall-conversations/references/lenses.md` — lens definitions
- `packages/merge-settings/tests/test_merge.py` — test file
- `packages/claude-memory/pyproject.toml` — package entrypoints

### Behavioral Invariants
- cm-recall-conversations skill must continue to work (has a routing row in capabilities-memory.md)
- cm-search-conversations CLI tool must continue to work
- cm-get-token-insights skill must continue to work
- cm-memory-setup, cm-memory-context, cm-memory-sync hooks must continue to work
- Session capture and SQLite storage must be unaffected
- `install.py` must still install all other memory bundle components

### Blast Radius
Limited to the Claudefiles repo. No external consumers. The deleted skill/agents are not referenced by any other skill or hook outside the files listed above.

## Open Questions

None.
