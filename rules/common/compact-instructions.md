# Compact Instructions

When compacting (auto or manual), preserve what the next step needs and drop the rest.

**Preserve:**
- Final decisions and their rationale, not the deliberation
- File paths and locations that will be touched next
- Architectural constraints and gotchas discovered
- Active task list items and their status
- Test or build state that affects next steps
- Current branch and worktree path (not the main clone's)

**Summarize to one line:** exploration that led to decisions, failed approaches (the lesson only), debugging (root cause and fix).

**Drop:** tool output from reads and greps already acted on, superseded drafts, resolved errors, clarification back-and-forth.
