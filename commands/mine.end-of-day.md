---
description: Capture session state as a handoff file for morning pickup.
---

# End of Day

Write a handoff document capturing everything needed to resume this work tomorrow. Fully autonomous — no questions asked.

## Step 1: Handoff Path

The handoff lives at `<git-toplevel>/.claude/handoff.md` — local to the project or worktree.

First, get the git toplevel:

```bash
git rev-parse --show-toplevel
```

If this fails: "Not in a git repo — nothing to hand off."

Then create the `.claude/` directory if needed:

```bash
mkdir -p <toplevel>/.claude
```

The handoff path is `<toplevel>/.claude/handoff.md`. The `mine.good-morning` command deletes this file after pickup.

## Step 2: Gather State

Run in parallel where possible:

### Git (Bash)
- `git branch --show-current`
- `git status --short`
- `git log --oneline -8`
- `git diff --stat` (uncommitted changes)

### Tasks (Tool + Bash)
- TaskList — any tracked tasks in this session
- `find <toplevel>/design/specs -path '*/tasks/T*.md' -print 2>/dev/null | head -20`

### Tmux (Bash)
- `claude-tmux current` — skip if not in tmux

## Step 3: Synthesize the Handoff

Reflect on the entire conversation and write each section below. Brief a colleague who has zero prior context — no shorthand, no references to "what we discussed."

1. **What We Were Working On** — the goal and why it matters. One paragraph.
2. **Approach** — how the work was structured. Key technical choices and their rationale.
3. **Current State** — what's done (committed, tested, verified) vs. in progress vs. not started. Use file paths.
4. **Uncommitted Changes** — if any, describe contents and intent. If none, say so.
5. **Decisions Made** — non-obvious choices a fresh reader wouldn't know from the code.
6. **Open Questions** — unresolved items needing attention.
7. **Key Files** — files central to the work, one-line note on each.
8. **Next Steps** — ordered list. First item should be immediately actionable.

If the conversation is thin (skill invoked early in a session), lean on git state and task files instead of narrative.

## Step 4: Write the File

Write to the path from Step 1:

```markdown
# Handoff: <short description>

**Date:** <YYYY-MM-DD>
**Project:** <basename of toplevel>
**Directory:** <full toplevel path>
**Branch:** <branch name>
**Tmux:** <session name, or omit if not in tmux>

## What We Were Working On

<narrative>

## Approach

<narrative>

## Current State

### Done
- <item>

### In Progress
- <item>

### Not Started
- <item>

## Uncommitted Changes

<summary or "None — all changes committed.">

## Decisions Made

- <decision — rationale>

## Open Questions

- <question>

## Key Files

- `<path>` — <role in context>

## Next Steps

1. <step>
2. <step>
```

Omit empty sections (e.g., skip "Decisions Made" if there were none worth recording).

## Step 5: Confirm

If uncommitted changes exist:

> Handoff written to `<path>`.
>
> **Heads up:** you have uncommitted changes on `<branch>`. Consider committing or stashing before walking away.

Otherwise:

> Handoff written to `<path>`. Tomorrow, open a session in `<toplevel>` and run `/mine.good-morning` to pick up.
