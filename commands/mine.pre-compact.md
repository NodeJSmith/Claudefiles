---
description: Analyze session context and generate a focused /compact prompt that preserves what matters for the next phase.
---

# Pre-Compact Command

Generate a strategic `/compact` prompt before transitioning to the next phase of work. Keeps critical context, drops noise.

## Arguments

$ARGUMENTS — optional description of what the next phase is (e.g., "refactor", "testing", "PR creation"). If not provided, infer from conversation context.

## Step 1: Assess Current Session

Review the conversation so far and identify:

1. **What was accomplished** — decisions made, files changed, patterns established
2. **What's pending** — open tasks, unfinished work, known issues
3. **What the next phase is** — from $ARGUMENTS or inferred from context
4. **Active task list** — check TaskList for any tracked items

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

### SUMMARIZE (compress to one line each)
- Exploration and research that led to decisions
- Failed approaches and why they failed (just the lesson, not the journey)
- Debugging sessions (just the root cause and fix)

### DROP (let go)
- Tool output from reads/greps that informed decisions already made
- Intermediate draft code that was superseded
- Back-and-forth clarification that reached a conclusion
- Verbose error messages that were already resolved

## Step 3: Generate Compact Prompt

Write a compact prompt in this format and present it to the user:

```
/compact Preserve for [NEXT PHASE]: [2-4 bullet points of critical context]. Decisions: [key decisions]. Files: [paths relevant to next phase]. Drop: exploration/research output, resolved errors, superseded drafts.
```

Guidelines for the prompt:
- Keep it under 200 words — the prompt itself shouldn't bloat context
- Be specific about file paths and decisions, not vague
- Name the next phase explicitly so compact knows the frame
- Include any task list items that should survive

## Step 4: Offer to Run

After presenting the prompt, ask the user:

> Ready to compact with this prompt? You can edit it first or I can run it as-is.

Do NOT run `/compact` automatically — let the user review and adjust.

## Example

```
User: /pre-compact refactor the auth module

Claude: Here's what I'd preserve for the refactor phase:

/compact Preserve for auth module refactor: (1) Decided to extract token validation into middleware at src/auth/middleware.ts, keeping session logic in src/auth/session.ts. (2) Current tests pass — 47/47 green. (3) The RefreshToken type needs the `expiresAt` field added (discovered during debugging). (4) Task list: extract middleware, update routes, add integration tests. Files: src/auth/middleware.ts, src/auth/session.ts, src/auth/types.ts, tests/auth/. Drop: exploration of passport.js alternatives, resolved CORS debugging session, earlier draft that put everything in one file.

Ready to compact with this prompt? You can edit it first or I can run it as-is.
```

## Integration

- This command handles *what* to preserve when you compact
