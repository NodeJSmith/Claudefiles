---
description: Deep-dive an issue, plan the implementation, and create a worktree ready to go.
---

# Tackle Command

Takes an issue key, researches it, plans the approach, and creates a worktree with a complete plan handoff. One command from "I want to work on this" to `cd <path> && claude`.

## Arguments

$ARGUMENTS — one issue key (required). GitHub: `123`. Jira: `PROJ-123`.

## Phase 1: Validate

1. If no argument provided, tell the user: `Usage: /mine.tackle <issue-key>` and **stop**.
2. Read `$ISSUE_TRACKER`:
   - If **unset or empty**: tell the user `$ISSUE_TRACKER is not configured. Set it to "gh" or "jira" in your context var file.` and **stop**.
   - If not `gh` or `jira`: tell the user `Unsupported ISSUE_TRACKER value: "$ISSUE_TRACKER". Expected "gh" or "jira".` and **stop**.

## Phase 2: Deep Dive

Launch a **Task subagent** (`subagent_type: Explore`, `model: haiku`) to research the issue:

> **If `$ISSUE_TRACKER` is `gh`:**
> Run `gh issue view <N> --json title,body,comments,labels,assignees,milestone` to get the full issue.
>
> **If `$ISSUE_TRACKER` is `jira`:**
> Run `jira issue view <KEY> --comments 5 --plain` to get the full issue.
>
> Then scan the codebase for files and areas mentioned in or related to the issue (grep for keywords, check referenced file paths, look at relevant modules).
>
> Return this structured summary and nothing else:
>
> ```
> ## Issue <KEY> — Title
> - **Description**: [condensed from body, 2-3 sentences max]
> - **Key comments**: [relevant discussion points, or "None"]
> - **Affected areas**: [files/modules identified from codebase scan]
> - **Estimated scope**: [small/medium/large with brief reasoning]
> - **Suggested approach**: [1-2 sentences]
> ```

Display the summary to the user.

## Phase 3: Confirm Direction

Use `AskUserQuestion` to ask:

- **Plan & create worktree** — Design an implementation plan in plan mode, then create a worktree with the plan as handoff
- **Quick worktree** — Skip detailed planning, create a worktree with just the issue summary as handoff (good for small/obvious issues)
- **Just explore** — Keep researching in this session, no worktree yet

If "Just explore", continue researching and **stop** — do not proceed to later phases.

## Phase 4: Plan (if "Plan & create worktree")

Enter plan mode (`EnterPlanMode`). While in plan mode:

1. Explore the affected areas identified in Phase 2
2. Understand the current architecture and patterns
3. Design an implementation approach
4. Write the plan, then use `ExitPlanMode` for user approval

After approval, proceed to Phase 5.

## Phase 4b: Quick Handoff (if "Quick worktree")

Skip plan mode entirely. The issue summary from Phase 2 will be used directly as the basis for the worktree handoff. Proceed to Phase 5.

## Phase 5: Create Worktree

1. **Derive branch name** from the issue:
   - GitHub: `<issue-number>-<slugified-title>` (e.g., `123-fix-auth-bug`)
   - Jira: `<issue-key>-<slugified-title>` (e.g., `PROJ-123-fix-auth-bug`)
   - Kebab-case, max ~50 chars
2. **Get git info**:
   ```bash
   git rev-parse --show-toplevel   # source worktree
   git branch --show-current       # base branch
   ```
3. **Worktree path**: `$(dirname "$(git rev-parse --show-toplevel)")/<branch-name>`
4. **Create the worktree**: `git worktree add -b <branch> <path> <base-branch>`
5. **Set up shared config**:
   ```bash
   setup-worktree.sh <source-worktree> <new-worktree>
   ```
6. **Write plan handoff** to `<worktree-path>/.claude/plan.md`:

   If full plan (Phase 4): reformat the approved plan into the handoff structure below.
   If quick (Phase 4b): build the handoff from the issue summary.

   Handoff format:
   ```markdown
   # Plan: <Issue KEY> — <Title>

   ## Goal
   What needs to be done (tied to the issue).

   ## Context
   Issue details and why this work is needed. Include relevant discussion
   from issue comments.

   ## Relevant files
   - `path/to/file.py` — what to do here
   - `path/to/other.py` — what to do here

   ## Approach
   Step-by-step implementation plan.

   ## Acceptance criteria
   - [ ] Criterion 1
   - [ ] Criterion 2
   ```

   Write this as a clear, actionable document that a fresh Claude session can execute with **zero additional context**. Include enough detail that the new session doesn't need to re-discover what this session already knows.

7. **Report**:
   ```
   Worktree ready at <path>
   To start:
     cd <path> && claude
   Or, if using tmux:
     tmux new-session -d -s "<branch-name>" -c "<path>" && tmux attach -t "<branch-name>"
   Then accept the project trust prompt, and use /mine.start to begin.
   ```

## Error Handling

- Issue not found → inform user and stop
- Worktree path already exists → inform user, ask how to proceed
- Branch already exists locally → ask whether to use it or pick a new name
- `setup-worktree.sh` not found → warn but continue (config can be set up manually)
