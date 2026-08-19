# Design: Issue Tracker Agnostic

**Date:** 2026-08-19
**Status:** archived
**Mode:** sketch

## Problem

Skills, rules, and agents hardcode specific issue tracker CLI commands (`gh-issue create`, `gh label list`, etc.) instead of describing intent. This creates two problems: it locks instructions to GitHub when the user also works in Azure DevOps and Jira, and it over-specifies what Claude should do when Claude is smart enough to pick the right tool from a general instruction like "create an issue in the project's tracker."

## Goals

- Remove hardcoded `gh-issue` / `gh` CLI invocations from skill instructions, replacing them with intent-level language
- Keep `$ISSUE_TRACKER` as the "which system" signal so skills know what platform they're on
- Delete `mine-issues-triage` (the entire skill)
- Preserve platform-specific tool implementations in `bin/` and `packages/` untouched

## Non-Goals

- Adding ADO/Jira support to `mine-wayfinder` (it currently requires GitHub's sub-issue model; generalizing that is a separate design problem)
- Changing `mine-eval-repo` (inherently about public open-source GitHub repos)
- Changing `mine-create-pr` or `mine-address-pr-issues` (already platform-agnostic)
- Changing `bin/` tool implementations or `REFERENCE.md` tool documentation

## Functional Requirements

- **FR#1** No skill, rule, or agent file references `gh-issue`, `gh issue`, `gh label`, `gh api repos`, or `gh pr list` as a command to run (except `mine-eval-repo`, `mine-create-pr`, `mine-address-pr-issues`, files under `bin/`, and the tool-reference documentation section of `capabilities-core.md`).
- **FR#2** Skills that create issues (mine-create-issue, mine-challenge, mine-orchestrate, mine-brainstorm, mine-decompose, mine-audit, mine-tool-gaps) use intent language ("create an issue in the project's issue tracker") rather than tool-specific commands.
- **FR#3** Skills that search/query issues (mine-why, mine-issues) use intent language ("search the project's issues and PRs") rather than tool-specific commands.
- **FR#4** `$ISSUE_TRACKER` remains referenced where skills need to know which platform they're on, but is not used to dispatch to specific CLI commands within the skill text.
- **FR#5** `mine-issues-triage/` skill directory and all routing references to it are removed.
- **FR#6** `capabilities-core.md` routing table merges GitHub and ADO issue/PR rows into unified intent-based entries where the trigger phrases are platform-neutral.
- **FR#7** `git-workflow.md` Issue Creation Conventions section uses intent language instead of `gh-issue` commands.
- **FR#8** `issue-refiner` agent description and instructions are platform-neutral (not GitHub-specific).
- **FR#9** `mine-wayfinder` replaces `gh-issue` commands with intent language and removes the "no GitHub remote → stop" gate, replacing it with a check that the project has an issue tracker configured (`$ISSUE_TRACKER` is set).

## Acceptance Criteria

- **AC#1** `grep -rn 'gh-issue\|gh issue\|gh label\|gh api repos\|gh pr list' skills/ rules/ agents/ commands/` returns zero matches outside the excluded files (mine-eval-repo, mine-create-pr, mine-address-pr-issues) and outside the tool-reference documentation section of `capabilities-core.md`. Maps to FR#1.
- **AC#2** `mine-issues-triage` directory does not exist and is not referenced in any capabilities file or routing table. Maps to FR#5.
- **AC#3** `capabilities-core.md` has no duplicate trigger phrases (e.g., "create issue" appearing in both a GitHub and ADO section). Maps to FR#6.
- **AC#4** Every file that previously referenced `gh-issue create` now uses intent language that works regardless of `$ISSUE_TRACKER` value. Maps to FR#2, FR#3.

## Approach

### Intent language pattern

Replace specific commands with descriptions of what to do. The key shift: skills describe the *what*, Claude figures out the *how*.

**Before:**
```
Create the issue:
gh-issue create --title "<title>" --body-file <tmpdir>/issue-body.md --label "<label>"
```

**After:**
```
Create the issue in the project's issue tracker with the title and body above.
Match labels/tags to the issue type using whatever labeling conventions the tracker already has.
```

Skills still reference `$ISSUE_TRACKER` to know the platform context (e.g., "if `$ISSUE_TRACKER` is `jira`, issue keys look like `PROJ-123`"), but don't prescribe CLI invocations.

### Routing table consolidation

`capabilities-core.md` currently has separate sections: generic trigger phrases → `gh-issue` (lines 76), and ADO-prefixed phrases → `ado-api` (lines 96-105). Merge into one set of intent-based rows:

| User says... | Run |
|---|---|
| "view issue", "create issue", "list issues" | Use the appropriate issue tracker CLI based on `$ISSUE_TRACKER` / `git-platform` |
| "list PR threads", "unresolved comments" | Use the appropriate PR thread tool |

The ADO-specific rows for builds (`ado-api builds`, `ado-api logs`, `ado-api builds approve`, etc.) stay — those are CI/CD operations unique to ADO with no GitHub equivalent in the CLI tools. Same for `ado-api pipeline`.

The "GitHub tool notes" section stays but is renamed to clarify it's tool-specific documentation, not a general workflow instruction.

### mine-wayfinder special handling

Wayfinder is the most complex case. Its "Tracker Operations" section (lines 105-165) is essentially a GitHub API cookbook — label creation, sub-issue wiring, claim-race detection, frontier queries via `jq`. This level of detail is exactly what we want to stop prescribing. Replace the entire section with intent-level descriptions of what operations the wayfinder needs (create a map issue, create child tickets, wire blocking edges, claim tickets, query the frontier). Claude knows how to do these with `gh-issue` when on GitHub.

The "no GitHub remote → stop" gate becomes "if `$ISSUE_TRACKER` is not set, stop and ask the user how to track the effort."

### mine-issues-triage deletion

Delete the skill directory and remove its references from:
- `capabilities-core.md` (skill routing table and CLI tools table)
- `commands/mine-issues.md` (the triage fallback offer in Phase 2)
- `install.py` if it's referenced in a bundle

### Files that need "file as issue" label changes

These all have AskUserQuestion options labeled "Create a GitHub issue" or "File as GitHub issue" — change to "Create an issue" or "File as issue":
- `skills/mine-challenge/findings-protocol.md` (lines 188, 193, 209)
- `skills/mine-orchestrate/post-execution-pipeline.md` (lines 404-405, 416)
- `skills/mine-decompose/SKILL.md` (lines 130, 137)
- `skills/mine-audit/SKILL.md` (lines 152, 168)
- `skills/mine-brainstorm/SKILL.md` (line 247)
- `skills/mine-tool-gaps/SKILL.md` (lines 227, 252)

## Changed Files

- delete: `skills/mine-issues-triage/SKILL.md` — entire skill removed
- modify: `REFERENCE.md` — remove mine-issues-triage entry
- modify: `install.py` — remove mine-issues-triage bundle reference if present
- modify: `rules/common/capabilities-core.md` — merge GitHub/ADO rows, remove triage routing, consolidate tool notes
- modify: `rules/common/git-workflow.md` — rewrite Issue Creation Conventions to use intent language
- modify: `commands/mine-issues.md` — remove `$ISSUE_TRACKER` dispatch specifics and triage fallback, keep `$ISSUE_TRACKER` as platform signal
- modify: `skills/mine-create-issue/SKILL.md` — remove "create it on GitHub" phrasing
- modify: `skills/mine-create-issue/worker.md` — replace `gh-issue` commands with intent language
- modify: `agents/issue-refiner.md` — make description and instructions platform-neutral
- modify: `skills/mine-wayfinder/SKILL.md` — replace Tracker Operations cookbook with intent descriptions, change platform gate
- modify: `skills/mine-challenge/findings-protocol.md` — "File as issue" label and resolution
- modify: `skills/mine-orchestrate/post-execution-pipeline.md` — "File as issue" label and resolution
- modify: `skills/mine-brainstorm/SKILL.md` — issue creation step
- modify: `skills/mine-decompose/SKILL.md` — "File as issues" label and resolution
- modify: `skills/mine-audit/SKILL.md` — "File as issue" option
- modify: `skills/mine-tool-gaps/SKILL.md` — issue creation step
- modify: `skills/mine-why/SKILL.md` — issue/PR search step
