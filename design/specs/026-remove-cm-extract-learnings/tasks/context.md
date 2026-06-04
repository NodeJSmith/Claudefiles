# Context: Remove cm-extract-learnings and consolidation hooks

## Problem & Motivation
The cm-extract-learnings skill mined past sessions to persist knowledge as memories, but it was inaccurate at deciding what to remember. The in-conversation auto-memory rules already handle this better by deciding in context. The consolidation reminder hooks nudge users to run extract-learnings periodically, which is now unnecessary since memsearch (Dotfiles #40) replaces the proactive surfacing role. All these components are dead weight that should be removed.

## Visual Artifacts
None.

## Key Decisions
1. Pure deletion — no replacement code in this repo. memsearch is tracked separately in Dotfiles #40.
2. The `extract-learnings` lens in cm-recall-conversations is being removed (it was conceptually tied to the deleted skill).
3. Archived design specs (018, 019, 023, etc.) and CHANGELOG.md must NOT be modified — they are historical records.
4. The SessionStart hook in settings.json has multiple commands in an inner array — remove only the consolidation-check element, not the entire hook entry.

## Constraints & Anti-Patterns
- Do NOT modify any file under `design/specs/` (archived historical records).
- Do NOT modify `CHANGELOG.md`.
- Do NOT break cm-recall-conversations, cm-search-conversations, cm-get-token-insights, or any of the setup/context/sync hooks.
- When editing `capabilities-memory.md`, preserve the cm-recall-conversations and cm-get-token-insights routing rows.
- When editing `onboarding.py` and `write_config.py`, these files contain both consolidation and non-consolidation logic — remove only consolidation-related code.

## Design Doc References
- `## Architecture` — lists all 5 deletions and 15 surgical edits with specific file paths and what to change in each
- `## Test Strategy` — lists 3 test files to adapt and 1 to remove
- `## Edge Cases` — archived specs, shared capabilities file, mixed-concern files
- `## Acceptance Criteria` — verification grep command, installer check, test suite runs

## Convention Examples
None — no convention examples captured during discovery.
