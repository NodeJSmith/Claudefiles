---
task_id: "T03"
title: "Update documentation and verify completeness"
status: "done"
depends_on: ["T02"]
implements: ["FR#8", "FR#9", "FR#10", "FR#14", "FR#20", "AC#1", "AC#2", "AC#3"]
---

## Summary
Update all documentation files to remove references to the deleted components, then run the full verification suite to confirm zero remaining references and no test breakage. This is the final task — it verifies that T01 and T02 left no orphaned references.

## Prompt
Make these documentation edits:

**`skills-memory/capabilities-memory.md`** — Remove the extract-learnings routing row from the Intent Routing table (the row with triggers "extract learnings", "save this for next time", etc.).

**`REFERENCE.md`** — Remove these 4 table rows:
- The `cm-extract-learnings` row in the Skills table
- The `cm-memory-auditor` row in the Agents table
- The `cm-signal-discoverer` row in the Agents table
- The `cm-consolidation-check` row in the Hooks table

**`ONBOARDING.md`** — Remove extract-learnings and consolidation mentions from the Memory bundle description (the sentence containing "nudges you to consolidate" and "/cm-extract-learnings"). Keep the `/cm-recall-conversations` mention.

**`packages/claude-memory/README.md`** — Remove:
- The consolidation reminders question in the onboarding section (the numbered item mentioning "Consolidation reminders")
- The `cm-consolidation-check` row from the hooks feature table (search for `cm-consolidation-check` in a markdown table)
- The `/cm-extract-learnings` row from the skills feature table (search for `cm-extract-learnings` in a markdown table)
- The consolidation config keys from the JSON example (`consolidation_reminder_enabled`, `consolidation_min_hours`, `consolidation_min_sessions`)
- The `cm-consolidation-check` lines from the architecture diagram (the indented lines mentioning `cm-consolidation-check` and `extract-learnings`)

After all edits, run the verification:

1. **AC#1 grep**: `grep -r 'extract-learnings\|consolidation.check\|consolidation_reminder\|consolidation_min\|cm-memory-auditor\|cm-signal-discoverer' --include='*.py' --include='*.md' --include='*.json' --include='*.toml' . | grep -v CHANGELOG | grep -v 'design/specs/'` — must return no results.

2. **AC#2 installer check**: `uv run install.py --help` — must run without error.

3. **AC#3 test suites**: Run `timeout 300 pytest tests/`, `timeout 300 pytest packages/claude-memory/tests/`, and `timeout 300 pytest packages/merge-settings/tests/` — all must pass.

## Focus
- `capabilities-memory.md` has 3 routing rows. Only the extract-learnings row should be removed. The cm-recall-conversations and cm-get-token-insights rows must stay.
- `ONBOARDING.md` line 59 is a long sentence that mixes extract-learnings and recall-conversations descriptions. Rewrite to keep only the recall part.
- `README.md` has consolidation references scattered across multiple sections (onboarding, hooks table, skills table, config example, architecture diagram). Check all sections.
- The AC#1 grep uses `consolidation.check` (dot = any char) to catch both underscore and hyphen forms. It also includes `consolidation_reminder` and `consolidation_min` to catch db.py-style keys.

## Verify
- [ ] FR#8: `capabilities-memory.md` contains no extract-learnings routing row
- [ ] FR#9: `REFERENCE.md` contains no rows for cm-extract-learnings, cm-memory-auditor, cm-signal-discoverer, or cm-consolidation-check
- [ ] FR#10: `ONBOARDING.md` contains no mentions of consolidation or extract-learnings
- [ ] FR#14: `packages/claude-memory/README.md` contains no extract-learnings or consolidation references
- [ ] FR#20: Remaining claude-memory functionality works (session capture, recall, token insights, hooks)
- [ ] AC#1: Verification grep returns no results
- [ ] AC#2: `uv run install.py --help` runs without error
- [ ] AC#3: All three test suites pass
