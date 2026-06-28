# Create Issue — Worker Instructions

You receive an issue description, type, and any additional context the user provided. Your job: investigate the codebase and draft a complete, well-structured issue. Return the title and body as your final output.

## Step 1: Investigate

Search the codebase for code relevant to the issue description.

Find:
- Files and functions that would need to change
- Related tests
- Existing patterns to follow or constraints to respect

Produce a structured summary:
- **Affected files**: file paths with brief reason each is relevant
- **Key functions/classes**: names and what they do
- **Existing patterns**: how similar things are done in this codebase
- **Test files**: related test files that would need updates
- **Constraints**: anything that limits how this should be implemented

If you cannot find relevant code, note "No relevant code found" with what you searched for. Proceed to drafting regardless.

## Step 2: Draft

Compose the issue using this template. Adapt section content to the issue type.

### Title

Short, specific, imperative mood. Include the component/area when it helps:
- "Add retry with backoff to webhook sender"
- "Fix 500 error on empty form submission in /api/events"
- "Remove deprecated license classifier per PEP 639"

### Body

```markdown
## Description

[1-3 sentences: what needs to change and why. For bugs: what's broken and what should happen instead.]

## Acceptance Criteria

- [ ] [Specific, testable condition 1]
- [ ] [Specific, testable condition 2]
- [ ] [Specific, testable condition 3]
- [ ] [Tests pass — existing tests updated, new tests added for changed behavior]

## Affected Areas

- `path/to/file.py` — [what changes here]
- `path/to/other.py` — [what changes here]
- `tests/test_file.py` — [test updates needed]

## Context

[Constraints, patterns, or related issues discovered during investigation. Omit only if the investigation found no constraints and the description is fully self-explanatory.]
```

### Acceptance criteria rules

- Every AC must be testable — "it works" is not an AC
- Include a tests-pass AC on every issue
- For bugs: include "the original error no longer occurs" as an AC
- For features: include both the happy path and at least one edge case
- 3-6 ACs is the sweet spot

### Affected areas rules

- Include actual file paths from the investigation
- Include test files
- If the investigation couldn't identify specific files, use "TBD — investigation needed"

## Step 3: Return

Your final message must be exactly this format (no other text):

```
TITLE: <issue title>
---
BODY:
<full issue body in markdown>
```
