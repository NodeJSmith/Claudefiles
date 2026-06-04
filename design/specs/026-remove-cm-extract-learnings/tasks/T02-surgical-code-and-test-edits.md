---
task_id: "T02"
title: "Surgical edits to code and test files"
status: "planned"
depends_on: ["T01"]
implements: ["FR#11", "FR#12", "FR#13", "FR#15", "FR#16", "FR#17", "FR#18"]
---

## Summary
Remove consolidation-related logic from the claude-memory package code files (onboarding.py, write_config.py, db.py), remove the extract-learnings lens from cm-recall-conversations, and adapt three test files to match the code changes. These files all contain a mix of consolidation and non-consolidation logic — only the consolidation parts should be removed.

## Prompt
Make these surgical edits:

**`packages/claude-memory/src/claude_memory/hooks/onboarding.py`** — Remove consolidation reminder setup logic. The file contains both consolidation and non-consolidation onboarding flows. Search for strings containing `cm-extract-learnings`, `consolidat`, and `extract-learnings` — remove only those lines. The remaining onboarding logic for session capture and memory setup must stay intact.

**`packages/claude-memory/src/claude_memory/hooks/write_config.py`** — Remove:
- The `--consolidation-reminder` argument definition (search for `add_argument` with `consolidation`)
- The `--consolidation-min-hours` and `--consolidation-min-sessions` argument definitions
- All consolidation key assignments in the config dict (search for `consolidation_reminder_enabled`, `consolidation_min_hours`, `consolidation_min_sessions` in the dict construction and conditional blocks)
The remaining config args and logic must stay intact.

**`packages/claude-memory/src/claude_memory/db.py`** — Remove consolidation keys from `DEFAULT_SETTINGS` dict (`consolidation_reminder_enabled`, `consolidation_min_hours`, `consolidation_min_sessions`) and from the `_CONFIG_KEYS` tuple/set (same three key names).

**`skills-memory/cm-recall-conversations/SKILL.md`** — Remove the extract-learnings lens routing row from the trigger table (the row containing `| "what I learned", "reflect" | extract-learnings |`).

**`skills-memory/cm-recall-conversations/references/lenses.md`** — Remove the `extract-learnings` entry from all three tables in the file (search for `extract-learnings` — appears once per table).

**`tests/test_install.py`** — Remove:
- `"cm-memory-auditor"` and `"cm-signal-discoverer"` from the agent list in `_setup_full_repo` (search for those strings in a list/tuple literal)
- The `cm-memory-auditor.md` symlink assertion (`assert (claude_dir / "agents" / "cm-memory-auditor.md").is_symlink()`)
- The `cm-memory-auditor.md` negative existence assertion (`assert not (claude_dir / "agents" / "cm-memory-auditor.md").exists()`)
- The `cm-extract-learnings` mkdir calls in `test_ignores_when_already_installed` and `test_installs_when_not_present` (search for `"cm-extract-learnings"` in those methods)
- The `for name in ("cm-memory-auditor", "cm-signal-discoverer")` loops and their bodies in those same test methods

**`packages/claude-memory/tests/test_write_config.py`** — Remove:
- Consolidation key names from the config keys assertion (the strings `"consolidation_reminder_enabled"`, `"consolidation_min_hours"`, `"consolidation_min_sessions"` in the assertion list)
- The `test_consolidation_min_hours_floor` test method (entire method)

**`packages/merge-settings/tests/test_merge.py`** — In `test_real_scenario_session_start_duplicate`:
- Remove the `cm-consolidation-check` dict entry from the `claudefiles_entry` hook list (search for `"cm-consolidation-check"`)
- Update the count assertion from `len(result[0]["hooks"]) == 6` to `== 5`
- Update the method's docstring to change both occurrences of "6 hooks" to "5 hooks"

## Focus
- `onboarding.py` is 91 lines total with only ~6 lines mentioning consolidation. Be precise — don't accidentally remove non-consolidation onboarding logic.
- `write_config.py` has consolidation args interleaved with other args in `argparse`. Remove the arg definitions AND their usage in the config dict construction.
- `db.py`'s `DEFAULT_SETTINGS` and `_CONFIG_KEYS` are used by other hooks — only remove the 3 consolidation entries, leave everything else.
- `test_install.py` has `cm-memory-auditor` in two contexts: the `_setup_full_repo` agent list (used by many tests) and standalone symlink assertions. Both need removal. `cm-signal-discoverer` only appears in the agent list and the for-loops, not in standalone assertions.
- The lenses.md file has 3 separate tables — the extract-learnings row appears once in each table.

## Verify
- [ ] FR#11: `onboarding.py` contains no consolidation reminder or extract-learnings references
- [ ] FR#12: `write_config.py` contains no consolidation-related args, keys, or logic
- [ ] FR#13: `test_install.py` contains no references to cm-extract-learnings, cm-memory-auditor, or cm-signal-discoverer
- [ ] FR#15: `db.py` contains no consolidation keys in DEFAULT_SETTINGS or _CONFIG_KEYS
- [ ] FR#16: `test_write_config.py` contains no consolidation-related assertions or test methods
- [ ] FR#17: cm-recall-conversations SKILL.md and lenses.md contain no extract-learnings lens references
- [ ] FR#18: test_merge.py has cm-consolidation-check removed from hook list and count updated
