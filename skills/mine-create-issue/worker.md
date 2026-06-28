# Create Issue — Worker Instructions

You receive an issue description, type, and any additional context the user provided. Your job: investigate the codebase, draft a complete issue, create it on GitHub, and return the URL.

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

## Step 3: Create

1. Run `gh-issue overview` to see available labels and milestones.

2. **Labels:** Match the issue type to existing labels:
   - bug → "bug" label (if it exists)
   - feature → "enhancement" label (if it exists)
   - task/chore → no default label unless the repo has one

3. **Milestones:** If >50% of recent issues have milestones, pick the milestone that fits the work's scope.

4. Run `get-skill-tmpdir mine-create-issue` — note the path.

5. Write the issue body to `<tmpdir>/issue-body.md`.

6. Create the issue:
   ```bash
   gh-issue create --title "<title>" --body-file <tmpdir>/issue-body.md [--label "<label>"] [--milestone "<name>"]
   ```

## Step 4: Return

Your final message must end with the issue URL on its own line. If you have notes (e.g., no labels matched, no relevant code found), put them on lines before the URL. If you encountered an error at any step, return `ERROR: <description>` instead.
