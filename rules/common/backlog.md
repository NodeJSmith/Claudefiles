# Backlog Convention

When analysis skills produce multiple work items, **save the full list before asking which to tackle**. This prevents findings from being lost to context compaction or session boundaries.

## When to Invoke

Any time you present **3 or more actionable findings or work items** from an analysis skill (audit, challenge, brainstorm, etc.), invoke this flow before asking which to address first.

For fewer than 3 items, you may skip this flow **only if** the originating skill already provides a per-finding "Create an issue" or "Save" option that doesn't route through this convention. If it doesn't, use this flow anyway so findings aren't lost.

## Backlog Save Flow

```
AskUserQuestion:
  question: "Before we start, how would you like to save these findings so the rest aren't lost?"
  header: "Save backlog"
  multiSelect: false
  options:
    - label: "Save all to .claude/backlog.md"
      description: "Append all findings to a local backlog file in this repo"
    - label: "Create all as issues"
      description: "File each finding as a tracked issue (GitHub via gh-issue; ADO: not yet automated)"
    - label: "Let me split — I'll say which go to issues"
      description: "You name which items to file as issues; the rest go to .claude/backlog.md"
```

### If "Save all to .claude/backlog.md"

Ensure the `.claude/` directory exists (create it if needed), then append to `.claude/backlog.md` (create the file if it doesn't exist). Do not overwrite previous entries — each session appends a new dated section.

### If "Create all as issues"

Run `git-platform` to detect the hosting platform.

- **GitHub**: Create one issue per finding using `gh-issue create`. This wrapper uses bot-token authentication when available, otherwise falls back to your personal token. Use the issue body format defined by the originating skill (each skill documents its own issue format).
- **Azure DevOps**: Automated work item creation is not yet supported. Tell the user: "ADO work item creation isn't automated yet — saving to `.claude/backlog.md` instead." Fall back to the backlog file flow.

### If "Let me split"

Ask the user to specify which items go to issues (e.g. "items 1 and 3 as issues, the rest to backlog"). Then run `git-platform`:

- **GitHub**: Create issues for the specified items using `gh-issue create`. Append remaining items to `.claude/backlog.md`.
- **Azure DevOps**: Tell the user ADO work item creation isn't automated yet. Append all items to `.claude/backlog.md`.

## After Saving

Confirm what was saved (file path and/or issue URLs), then ask which finding to address in this session.

## Backlog File Format

`.claude/backlog.md` is append-only. Each session adds a dated section:

```markdown
## [Skill name] — YYYY-MM-DD

### 1. [Finding title] — [label]
[One-sentence description]

### 2. [Finding title] — [label]
[One-sentence description]
```

The label comes from whatever the originating skill produces — severity for audit and challenge (CRITICAL / HIGH / MEDIUM / LOW), ranking tier or score for brainstorm. Preserve whatever label the skill used so the backlog stays actionable on its own.

## Gitignore

`.claude/backlog.md` is a local workspace file. If you want it out of version control:

```
.claude/backlog.md
```

Do not gitignore the entire `.claude/` directory — it may contain committed config files (agents, settings).
