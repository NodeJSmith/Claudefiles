---
description: "Use when the user says: \"end of day\", \"wrapping up\", \"eod\", \"signing off\", \"handoff for tomorrow\". Capture session state as a handoff file for morning pickup."
---

# End of Day

Write a handoff that lets someone with zero context resume this work tomorrow, without having to reconstruct what happened. Fully autonomous: no questions asked.

## Where it goes

`<git-toplevel>/.claude/handoff.md`, local to the project or worktree (`git rev-parse --show-toplevel`; create `.claude/` if needed). If not in a git repo, say "Not in a git repo — nothing to hand off." and stop. `mine-good-morning` reads this exact path and deletes the file after pickup, so a handoff left from an earlier day is replaced, not kept alongside.

## What it should say

Gather git state (branch, status, recent log, uncommitted diff stat), any tracked tasks in this session, and the tmux session if in one (`claude-tmux current`). Combine that with the conversation. When the conversation is thin, lean on git state and any design ledger (`design/specs/*/design.md`).

Write for a colleague who has never seen this session: no shorthand, no "what we discussed." Say why, not just what: the goal, the reasoning behind the approach, and what any uncommitted work is for. Use file paths. The first next step should be immediately actionable.

## Format

`mine-good-morning` reads this file and relies on the **Date:** and **Branch:** header fields and the `Uncommitted Changes`, `Open Questions`, and `Next Steps` sections, so keep those. `Uncommitted Changes` is always present; omit any other section with nothing to say. The rest is the default shape.

```markdown
# Handoff: <short description>

**Date:** <YYYY-MM-DD>
**Project:** <basename of toplevel>
**Directory:** <full toplevel path>
**Branch:** <branch name>
**Tmux:** <session name, or omit if not in tmux>

## What We Were Working On
## Approach
## Current State
### Done
### In Progress
### Not Started
## Uncommitted Changes
## Decisions Made
## Open Questions
## Key Files
## Next Steps
```

`### Done` means committed, tested, and verified. `Uncommitted Changes` is "None — all changes committed." when clean. `Key Files` entries are `` `<path>` — <role> ``. `Next Steps` is an ordered list.

## Confirm

Tell the user the handoff path. If there are uncommitted changes, add a heads-up naming the branch and suggesting they commit or stash before walking away. Otherwise say tomorrow they can open a session in `<toplevel>` and run `/mine-good-morning`.
