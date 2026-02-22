---
description: Quick mid-session pattern capture. When you just solved something non-trivial, grab the reusable insight as a skill file before moving on.
---

# Capture Lesson

Extract a reusable pattern from something you just solved and save it as a skill file. Use this mid-session when the insight is fresh — don't wait until the end.

## Arguments

$ARGUMENTS — optional description of what to capture. If omitted, infer from conversation context.

## What to Extract

Look for:

1. **Error Resolution Patterns** — what broke, root cause, what fixed it
2. **Debugging Techniques** — non-obvious steps, tool combinations that worked
3. **Workarounds** — library quirks, API limitations, version-specific fixes
4. **Project-Specific Patterns** — conventions discovered, architecture decisions, integration patterns

Do NOT extract:
- Trivial fixes (typos, simple syntax errors)
- One-time issues (specific API outages, transient failures)
- Patterns that won't save time in future sessions

## Process

1. Review the session for the most valuable extractable pattern (one per invocation — keep skills focused).

2. Draft the skill file and present it to the user via `AskUserQuestion`:

   - **Edit first** — user provides changes, re-present

   Do NOT save without user approval.

3. Once approved, use `AskUserQuestion` to choose where to save:

   - **Save globally** — `~/.claude/skills/learned/[pattern-name].md` (available in all projects)
   - **Save to project** — `.claude/skills/[pattern-name].md` (scoped to this repo)

   Rule of thumb: library/tool/technique patterns → global. Project architecture/conventions/domain patterns → project.

4. Save using this format:

```markdown
# [Descriptive Pattern Name]

**Extracted:** [today's date]
**Context:** [Brief description of when this applies]

## Problem
[What problem this solves - be specific]

## Solution
[The pattern/technique/workaround]

## Example
[Code example if applicable]

## When to Use
[Trigger conditions - what should activate this skill]
```

5. Confirm the saved path to the user. If there are additional patterns worth capturing, mention it — the user can run `/mine.capture_lesson` again.
