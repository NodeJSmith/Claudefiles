---
description: Generate a /compact prompt that preserves what matters for the next phase.
---

# Pre-Compact

Generate a strategic `/compact` prompt before transitioning to the next phase of work. Keeps critical context, drops noise.

## Arguments

$ARGUMENTS — optional description of what the next phase is (e.g., "refactor", "testing", "PR creation"). If not provided, infer from conversation context.

## Step 1: Assess Current Session

Review the conversation so far and identify:

1. **What was accomplished** — decisions made, files changed, patterns established
2. **What's pending** — open tasks, unfinished work, known issues
3. **What the next phase is** — from $ARGUMENTS or inferred from context
4. **Active task list** — check TaskList for any tracked items
5. **Tmux session name** — run `claude-tmux current` and check whether the name still reflects the current work. If it no longer matches (topic drifted), update it with `claude-tmux rename "<new-name>"` before generating the compact prompt.

Do NOT use subagents for this — you already have full conversation context.

## Step 2: Classify Context

Sort everything in the session into three buckets:

### PRESERVE (carry forward)
- Final decisions and their rationale (not the deliberation)
- Implementation plan or approach for the next phase
- File paths and specific locations that will be touched next
- Architectural constraints or patterns established
- Active task list items and their status
- Any gotchas, edge cases, or warnings discovered
- Test results or build state that affects next steps
- Current tmux session name (if in tmux)

### SUMMARIZE (compress to one line each)
- Exploration and research that led to decisions
- Failed approaches and why they failed (just the lesson, not the journey)
- Debugging sessions (just the root cause and fix)

### DROP (let go)
- Tool output from reads/greps that informed decisions already made
- Intermediate draft code that was superseded
- Back-and-forth clarification that reached a conclusion
- Verbose error messages that were already resolved

## Step 3: Output

Output ONLY the ready-to-paste `/compact` command. No preamble, no explanation, no "here's what I came up with", no offer to edit. Just the command.

Format:

```
/compact Preserve for [NEXT PHASE]: [2-4 bullet points of critical context]. Decisions: [key decisions]. Files: [paths relevant to next phase]. Drop: exploration/research output, resolved errors, superseded drafts.
```

Guidelines:
- Keep it under 200 words
- Be specific about file paths and decisions, not vague
- Name the next phase explicitly so compact knows the frame
- Include any task list items that should survive
