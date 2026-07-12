---
tool: claude, antigravity
---

# Pause Safely

For planned session boundaries, use `mine-end-of-day`. This covers **unplanned mid-task interruptions**: going offline unexpectedly, context about to compact, system restart, process killed mid-run.

The problem: unlike end-of-day (which runs while context is intact), a mid-task interruption may happen while you're inside an iteration — partial disk state, uncommitted work, context about to summarize away everything you know.

## Playbook

When an unplanned stop is imminent:

**1. Stop at an atomic boundary.** Finish the current unit of work (the current file edit, the current test cycle). Do not stop mid-edit with a broken file.

**2. Commit everything on disk** with a `wip:` prefix:

```bash
git add -A && git commit -m "wip: <what this incomplete state represents>"
```

This ensures nothing is lost if context compacts or the process dies.

**3. Write a resume note to `/tmp/<slug>-resume.md`.** This file lives off-context — it survives even if the conversation is fully summarized. Write it before reporting back to the user.

```markdown
# Resume: <task description>

**Branch:** <branch>
**Last completed action:** <what you just finished>
**Position in plan/loop:** <step N of M, or which task in mine-orchestrate>
**What's in memory but not on disk:** <anything important not captured in commits or files>
**First action on resume:** <specific enough to start without re-reading the full context>
```

**4. Report your position.** Reply with:
- Where you stopped in the plan/loop
- What's committed vs. still only in memory
- The path to the resume note (`/tmp/<slug>-resume.md`)
- The exact first action on resume

## Why the /tmp File

`mine-end-of-day` writes a handoff while context is intact. The `/tmp` resume note is written as the last act before interruption, specifically to survive context window summarization. Different mechanism, different failure mode.

The `/tmp` path is intentional — it doesn't need to be in the repo, just available for the next session on the same machine.
