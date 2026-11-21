# Create Issue — Worker Instructions

You receive an issue description, a type, and any extra context from the user. Investigate the codebase, draft a complete issue, file it in the project's tracker, and return the URL. The issue should let a reader act on it without re-investigating: real file paths, testable acceptance criteria, and the constraints you found.

## Investigate

Find the code the issue touches: what would change, the related tests, existing patterns to follow, and constraints on the implementation. If you find nothing relevant, say what you searched for and draft anyway.

## Draft

Title: short, specific, imperative, naming the component when that helps ("Fix 500 error on empty form submission in /api/events").

Body, in this default shape:

```markdown
## Description

[1-3 sentences: what needs to change and why. For bugs: what's broken and what should happen instead.]

## Acceptance Criteria

- [ ] [Specific, testable condition]
- [ ] [Tests pass — existing tests updated, new tests added for changed behavior; omit when the change touches no code]

## Affected Areas

- `path/to/file.py` — [what changes here]
- `tests/test_file.py` — [test updates needed, when code changes]

## Context

[Constraints, patterns, or related issues found while investigating. Omit only if there are none and the description is self-explanatory.]
```

Every acceptance criterion must be testable; "it works" is not one. Aim for 3-6, including a tests criterion when the change touches code. A bug's criteria include that the original error no longer occurs; a feature's cover the happy path and at least one edge case. Affected Areas uses actual paths from the investigation, including tests; if none could be identified, write "TBD — investigation needed".

## Create

Check `$ISSUE_TRACKER` (`printenv ISSUE_TRACKER`):
- Unset or empty: use GitHub (`gh`).
- Set to a tracker you have no tools for: return `ERROR: no tools available for issue tracker "<value>"` and stop. Don't guess at a tool or fall back to another tracker; the dispatching skill will ask the user.
- Otherwise use that tracker's tools.

Check the repo's issue conventions (labels, milestones, usage patterns). Apply a matching label when one exists (bug to "bug", feature to "enhancement"), and a milestone when most recent issues have one and one fits the scope.

Write the body to a file (`mktemp -d <scratchpad>/mine-create-issue-XXXXXX`, then `<tmpdir>/issue-body.md`) and pass it to the tracker's `--body-file`/`--description-file` flag or stdin equivalent. This is mandatory: a multi-line Markdown body passed as a shell argument gets its quotes and backticks mangled.

## Return

Your final message ends with the issue URL on its own line, with any notes (no labels matched, no relevant code found) on lines before it. If anything blocked you, return `ERROR: <description>` instead.
