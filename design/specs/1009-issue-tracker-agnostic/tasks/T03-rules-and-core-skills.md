---
task_id: "T03"
title: "generalize git-workflow, mine-create-issue, issue-refiner, and mine-issues"
status: "done"
depends_on: ["T01"]
implements: ["FR#1", "FR#2", "FR#3", "FR#4", "FR#7", "FR#8", "AC#1", "AC#4"]
---

## Target Files

- modify: `rules/common/git-workflow.md` — Issue Creation Conventions section (lines 46-54)
- modify: `skills/mine-create-issue/SKILL.md` — remove "on GitHub" phrasing (line 9)
- modify: `skills/mine-create-issue/worker.md` — replace `gh-issue` commands with intent language (lines 3, 75, 90)
- modify: `agents/issue-refiner.md` — make description and body platform-neutral (lines 5, 10, 25, 100, 102)
- modify: `commands/mine-issues.md` — generalize dispatch specifics while keeping `$ISSUE_TRACKER` as platform signal

## Prompt

### git-workflow.md (lines 46-54)

The "Issue Creation Conventions" section currently says "When creating issues with `gh-issue create`..." and references `gh-issue overview` and `--milestone "name"` flags. Rewrite to use intent language:

- "When creating issues, match the conventions already in use in the repo"
- "Check the repo's milestones, labels, and usage patterns before creating issues" (instead of "Run `gh-issue overview`")
- "Assign a milestone if the repo uses them" / "Apply labels consistent with existing patterns"
- Keep the behavioral guidance (>50% threshold, don't invent labels, ask when in doubt) — just remove the tool-specific commands.

### mine-create-issue/SKILL.md (line 9)

Change "create it on GitHub" to "create it in the project's issue tracker" or similar platform-neutral language.

### mine-create-issue/worker.md

Line 3: "create it on GitHub" → "create it in the project's issue tracker"

Step 3 (lines 73-91): Currently prescribes `gh-issue overview`, `gh-issue create` with specific flags. Rewrite to intent:
- "Check the repo's issue conventions (milestones, labels, patterns)"
- "Create the issue with the title and body from Step 2"
- "Apply appropriate labels based on the issue type and what the tracker already uses"
- "Assign a milestone if the repo commonly uses them"
- Keep the tmpdir/body-file pattern as a suggestion ("write the issue body to a temp file to avoid shell escaping issues") but don't prescribe the exact command.

### agents/issue-refiner.md

- Line 5 (description): "Enriches GitHub issues" → "Enriches issues"
- Line 10: "refining vague or incomplete GitHub issues" → "refining vague or incomplete issues"
- Lines 25, 100, 102: Replace `gh-issue view`/`gh-issue edit` commands with intent language: "Read the issue" / "Update the issue body"

### commands/mine-issues.md

Keep `$ISSUE_TRACKER` as the platform detection signal. Keep the phase structure. Changes:
- Line 7: Keep "Supports GitHub (`gh`) and Jira (`jira`) via the `$ISSUE_TRACKER` env var" but also allow other values — or at minimum don't hard-reject non-gh/jira values. The skill should work with any tracker Claude has tools for.
- Line 7 description and line 11 arguments example: Update to not enumerate specific tracker names — keep `$ISSUE_TRACKER` as the signal but don't limit to `gh`/`jira`.
- Phase 1 (lines 15-18): Instead of hard-erroring on unknown values, allow any `$ISSUE_TRACKER` value — Claude will figure out the right tool. Only error if `$ISSUE_TRACKER` is completely unset. Update the error message text accordingly.
- Phase 3 (lines 29-53): Remove the `gh`/`jira` conditional branches that prescribe specific CLI commands. Instead, describe the intent: "fetch the full issue (title, body, comments, labels/tags, assignees, milestone/sprint)" and let the subagent use whatever tool matches `$ISSUE_TRACKER`. The output template stays the same.

## Verify

- [ ] FR#7: `git-workflow.md` Issue Creation Conventions section contains no `gh-issue` references
- [ ] FR#8: `issue-refiner.md` contains no "GitHub" in its description or instructions
- [ ] FR#1: `grep -n 'gh-issue\|gh issue' rules/common/git-workflow.md skills/mine-create-issue/ agents/issue-refiner.md commands/mine-issues.md` returns no matches
- [ ] FR#4: `$ISSUE_TRACKER` is still referenced in `commands/mine-issues.md`
- [ ] AC#4: Each modified file uses intent language instead of tool-specific commands
