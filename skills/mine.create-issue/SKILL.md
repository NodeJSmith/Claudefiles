---
name: mine.create-issue
description: "Use when the user says: 'create an issue', 'file an issue', 'open an issue', 'write an issue', 'new issue for this'. Codebase-aware issue creation — investigates the code to produce well-structured issues with acceptance criteria, affected areas, and enough detail for automated triage."
user-invocable: true
---

# Create Issue

Codebase-aware issue creation. Investigates the code to produce well-structured issues that the triage skill can assess as "well-defined" — with concrete acceptance criteria, affected code areas, and testable outcomes.

Note: This skill creates new issues. To enrich an existing issue with acceptance criteria and technical detail, use the `issue-refiner` agent instead.

## Arguments

$ARGUMENTS — a description of the issue to create. Can be:
- A short description: `/mine.create-issue "add retry logic to the webhook sender"`
- A bug report: `/mine.create-issue "500 error when submitting empty form"`
- Empty: ask the user what they want to file

## Phase 1: Classify and Gather

If $ARGUMENTS is empty, ask the user: "What do you want to create an issue for?"

### Classify type

From the description, classify the issue type:

| Type | Signals |
|------|---------|
| bug | "error", "broken", "crash", "fails", "wrong", "500", reproduction context |
| feature | "add", "new", "support", "enable", "implement" |
| task | "refactor", "rename", "move", "split", "clean up", "remove", "update", "upgrade" |
| chore | "deps", "CI", "config", "version bump" |

When signals overlap (e.g., "upgrade" could be task or chore), prefer the type whose follow-up questions would extract the most useful detail. If genuinely ambiguous, default to task.

### Targeted follow-ups

Ask only what's missing from the description. Skip questions the user already answered.

**Bug** — ask for (if not already provided):
- What's happening vs what should happen
- How to reproduce (steps or trigger)

**Feature** — ask for (if not already provided):
- What problem this solves or what it enables
- Any constraints or non-goals

**Task / Chore** — usually self-contained from the description. Only ask if the scope is ambiguous.

Keep this to **1-2 questions max**. The codebase investigation (Phase 2) fills in the technical detail — don't ask the user for file paths or function names.

## Phase 2: Investigate

Launch an **Explore subagent** (`subagent_type: Explore`, `model: haiku`) to find affected code:

> Search the codebase for code relevant to this issue: "<user's description>"
>
> Find:
> - Files and functions that would need to change
> - Related tests
> - Any existing patterns to follow or constraints to respect
>
> Return a structured summary:
> - **Affected files**: list of file paths with brief reason each is relevant
> - **Key functions/classes**: names and what they do
> - **Existing patterns**: how similar things are done in this codebase
> - **Test files**: related test files that would need updates
> - **Constraints**: anything that limits how this should be implemented
>
> If you cannot find relevant code, return "No relevant code found" with what you searched for.

If the subagent found no relevant code, note this for Phase 3 — the Affected Areas section will use "TBD — investigation needed" and Confidence will be lower. Proceed to drafting regardless.

## Phase 3: Draft and Preview

Compose the issue using this template. Adapt section content to the issue type — not every section applies to every type.

### Issue title

Short, specific, imperative mood. Include the component/area when it helps:
- "Add retry with backoff to webhook sender"
- "Fix 500 error on empty form submission in /api/events"
- "Remove deprecated license classifier per PEP 639"

### Issue body template

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

[Include constraints, patterns, or related issues discovered during investigation. Omit only if Phase 2 found no constraints and the description is fully self-explanatory.]
```

**Acceptance criteria rules:**
- Every AC must be testable — "it works" is not an AC
- Include a tests-pass AC on every issue
- For bugs: include "the original error no longer occurs" as an AC
- For features: include both the happy path and at least one edge case
- 3-6 ACs is the sweet spot — fewer means underspecified, more means the issue should be split

**Affected areas rules:**
- Include actual file paths from the investigation (Phase 2)
- Include test files
- If the investigation couldn't identify specific files, set to "TBD — investigation needed"

### Preview

Display the full issue (title + body) to the user, then:

```
AskUserQuestion:
  question: "How does this look?"
  header: "Preview"
  multiSelect: false
  options:
    - label: "Create it"
      description: "File the issue on GitHub"
    - label: "Edit first"
      description: "I want to adjust something before creating"
    - label: "Cancel"
      description: "Don't create the issue"
```

If **"Edit first"**: ask what to change, revise, and re-preview. Repeat until the user selects "Create it" or "Cancel".

## Phase 4: Create

### Detect labels and milestones

Run `gh-issue overview` once to see available labels and milestones. Cache the result if creating multiple issues in the same session.

**Labels:** Match the issue type to existing labels:
- bug → "bug" label (if it exists)
- feature → "enhancement" label (if it exists)
- task/chore → no default label unless the repo has one

**Milestones:** If >50% of recent issues have milestones, pick the milestone that fits the work's scope. Add `--milestone "<name>"` to the create command.

### Create the issue

1. Run `get-skill-tmpdir mine-create-issue` — note the path
2. Write the issue body to `<tmpdir>/issue-body.md`
3. Run:

```bash
gh-issue create --title "<title>" --body-file <tmpdir>/issue-body.md [--label "<label>"] [--milestone "<name>"]
```

Display the issue URL and number.

### Offer next action

```
AskUserQuestion:
  question: "Issue created. What next?"
  header: "Next"
  multiSelect: false
  options:
    - label: "Create another"
      description: "File another issue"
    - label: "Start working on it"
      description: "Run /mine.build to implement this issue"
    - label: "Done"
      description: "Stop here"
```

If **"Create another"**: restart from Phase 1.
If **"Start working on it"**: run `/mine.build` with the issue context.
