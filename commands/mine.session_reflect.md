---
description: End-of-session reflection grounded in git evidence. Captures decisions, techniques, friction points, and reusable patterns in a structured doc.
---

# Session Reflection

Reflect on a work session by combining objective git evidence with your experience of the session. Produces a reflection doc with specific, actionable insights — not generic retrospective fluff.

## Arguments

$ARGUMENTS — optional scope hint: a branch name, commit range (e.g. `abc123..HEAD`), time range (e.g. "last 2 hours"), or description of what to reflect on. If omitted, infer from conversation context.

## Phase 1: Scope

Determine what this reflection covers:

1. If $ARGUMENTS provides a commit range or branch, use it directly.
2. If $ARGUMENTS is a description, use it to guide scope detection.
3. If $ARGUMENTS is empty, infer from conversation context — look at what was discussed, what files were touched, what problems were solved.

Run `git log --oneline -20` to see recent commits and identify the relevant range.

Present the inferred scope to the user via `AskUserQuestion`:

- **Looks right** — proceed with this scope
- **Let me adjust** — user refines the scope

Do NOT proceed until scope is confirmed.

## Phase 2: Evidence

Launch a single **Task subagent** (`subagent_type: Explore`, `model: haiku`) to gather git evidence for the confirmed scope:

> Gather git evidence for a session reflection covering: [confirmed scope]
>
> Run these commands and return structured results:
>
> 1. `git log --format="%h %s" [range]` — list of commits
> 2. `git diff --stat [range]` — files changed with insertion/deletion counts
> 3. `git diff [range]` — full diff (summarize large diffs, don't paste thousands of lines)
>
> Return this structure:
>
> - **Commits**: list each commit hash and message
> - **Files Changed**: list with change magnitude (minor tweak / significant edit / new file / deleted)
> - **Notable Decisions**: anything visible in the code — architectural choices, pattern usage, dependency additions, config changes, things that were tried then reverted
> - **Scope of Impact**: how many files, what areas of the codebase, any cross-cutting concerns

Wait for the subagent to return before proceeding.

## Phase 3: Synthesis

Combine the subagent's git evidence with your own knowledge of the session (conversation context, problems encountered, approaches tried, user decisions). Draft the reflection using this structure:

```markdown
# Reflection: [short title]

**Date**: [today's date]
**Scope**: [what was covered]

## Decisions & Outcomes

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| [What was chosen] | [Why it was chosen] | [How it turned out — worked well / caused issues / TBD] |

## Techniques Worth Repeating

- [Specific method or approach that worked well and why — not vague praise like "good planning"]

## Friction Points

- [What slowed things down, with enough detail to act on — not just "tests were hard"]

## Patterns to Capture

- [Reusable insights from this session — specific enough to become skill files]
- [Only include if there are genuinely reusable patterns; omit this section if not]
```

Present the draft to the user via `AskUserQuestion`:

- **Save as-is** — proceed to save
- **I have edits** — user provides changes, then re-present

Incorporate any edits and re-confirm until the user approves.

## Phase 4: Next Steps

Save the approved reflection to `docs/reflections/YYYY-MM-DD-[slug].md` where `[slug]` is a short kebab-case summary (e.g. `2026-02-16-kimai-refactor.md`). Create the `docs/reflections/` directory if it doesn't exist.

Then use `AskUserQuestion` to offer next steps (include all that apply):

- **Capture patterns** — extract patterns as skill files (only offer if "Patterns to Capture" section is non-empty)
- **Commit the reflection** — stage and commit the reflection file
- **Done** — end the command

If **Capture patterns**: For each pattern listed in "Patterns to Capture", draft a skill file using the format from `/mine.capture_lesson`. Before saving each one, use `AskUserQuestion` to approve and choose where to save:

- **Save globally** — `~/.claude/skills/learned/[pattern-name].md` (available in all projects)
- **Save to project** — `.claude/skills/[pattern-name].md` (scoped to this repo)
- **Skip this pattern** — don't save it

Rule of thumb presented to user: if the pattern is about a library, tool, or technique you'd use anywhere, save globally. If it's about this project's architecture, conventions, or domain, save to project.

After processing all patterns, return to the next steps menu (user may also want to commit).

If **Commit the reflection**: run `git add docs/reflections/[filename]` then `git commit` with message `docs: add session reflection — [short title]`. Include any newly created skill files in the commit if patterns were captured (both global and project-level).

If **Done**: end.
