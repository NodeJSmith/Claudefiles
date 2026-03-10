# Error Tracking

## Purpose

Track non-trivial errors during multi-step work so failed approaches survive context compaction and aren't repeated.

## Error File

**Path:** `/tmp/claude-errors-$CLAUDE_SESSION_ID.md`

- Per-session, append-only
- Auto-cleaned by OS
- No gitignore needed

## When to Track

**Track these** (errors that cost real effort):
- Wrong API usage discovered after building against it
- Architectural dead-ends that required backtracking
- Dependency conflicts that needed investigation
- Configuration mysteries that took multiple attempts
- Approaches that silently produced wrong results

**Do NOT track** (noise):
- Typos, lint errors, missing imports
- Expected test failures during TDD red phase
- First-attempt errors that are immediately obvious
- Permission or path errors fixed in one try

## Entry Format

Append to the error file using Write tool:

```markdown
### [short description] — Attempt N
- **Tried:** what approach was taken
- **Result:** why it failed
- **Next:** what to try differently (or "Resolved: [how]")
```

## Workflow

1. Hit a non-trivial error during multi-step work
2. Append an entry to the error file
3. On subsequent attempts, increment the attempt number
4. When resolved, update the last entry's **Next** line to "Resolved: [how]"
5. Before retrying a failed approach, read the error file to check what's already been tried

## Reading the Error File

Before retrying approaches on a complex problem, read `/tmp/claude-errors-$CLAUDE_SESSION_ID.md` to avoid repeating failed strategies. Reference it in `/status` output.
