---
task_id: "T05"
title: "generalize mine-wayfinder tracker operations and mine-why evidence search"
status: "done"
depends_on: []
implements: ["FR#1", "FR#3", "FR#9", "AC#1", "AC#4"]
---

## Target Files

- modify: `skills/mine-wayfinder/SKILL.md` — Tracker Operations section (lines 105-165), platform gate (line 27), and scattered `gh-issue`/`gh` references throughout
- modify: `skills/mine-why/SKILL.md` — evidence search step (lines 88-89)

## Prompt

### mine-wayfinder/SKILL.md

This is the most complex file. The "Tracker Operations" section (lines 105-165) is a GitHub API cookbook with exact `gh`/`gh-issue` commands for every operation: label creation, issue creation, sub-issue wiring, claim-race detection, frontier queries.

**Replace the cookbook with intent descriptions.** Keep the section header and the operation list, but describe what each operation does rather than how:

Current operations to preserve as intents:
- **Check tracker availability:** Currently checks `gh api repos/{owner}/{repo} --jq .has_issues`. Replace with: "Confirm the project has an issue tracker configured (`$ISSUE_TRACKER` is set). If not, stop and ask the user how to track the effort."
- **Labels:** Currently creates `wayfinder:*` labels via `gh label create`. Replace with: "Ensure these labels/tags exist in the tracker: `wayfinder:map`, `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, `wayfinder:task`. Create any that are missing."
- **Create the map:** Currently uses `gh-issue create`. Replace with intent: "Create an issue with the map body, labeled `wayfinder:map`."
- **Create a child ticket:** Currently uses `gh-issue create --parent`. Replace with: "Create a child issue of the map issue, labeled with the ticket type."
- **Wire blocking edges:** Currently uses `gh-issue edit --add-blocked-by`. Replace with: "Add blocking relationships between tickets where dependencies exist."
- **Claim a ticket:** Currently uses `gh issue edit --add-assignee @me` with a race-detection pattern. Replace with: "Assign yourself to the ticket. Verify you're the first assignee — if someone else claimed it first, pick a different ticket." Keep the behavioral instruction (verify after claiming) without prescribing the specific commands.
- **Record resolution and close:** Currently uses `gh-issue comment` + `gh-issue close`. Replace with: "Add the resolution as a comment, then close the ticket."
- **Query the frontier:** Currently uses a complex `gh-issue list` + `jq` pipeline. Replace with: "Query open, unblocked, unclaimed child issues of the map."

**Platform gate (line 27):** Change from "If the repo has no GitHub remote or Issues disabled, stop" to "If `$ISSUE_TRACKER` is not set, stop and ask the user how to track the effort."

**Scattered references:** Search the rest of the file for any remaining `gh-issue`, `gh issue`, `gh label`, `gh api` references and replace with intent language.

The note about `gh-issue` using bot-token auth vs personal auth for claims (line 140) should be removed — that's a tool implementation detail that Claude can handle on its own.

### mine-why/SKILL.md (lines 88-89)

Currently says:
```
2. Search issues: gh-issue list -R <repo> --state all --search "<keywords>" --limit 20
```

Replace with intent: "Search the project's issues and PRs for relevant keywords." Don't prescribe the specific command.

## Verify

- [ ] FR#9: `mine-wayfinder/SKILL.md` no longer contains `gh-issue`, `gh issue`, `gh label`, or `gh api`
- [ ] FR#9: The platform gate checks `$ISSUE_TRACKER` instead of GitHub remote presence
- [ ] FR#3: `mine-why/SKILL.md` uses intent language for issue/PR search
- [ ] AC#1: `grep -n 'gh-issue\|gh issue\|gh label\|gh api\|gh pr list' skills/mine-wayfinder/SKILL.md skills/mine-why/SKILL.md` returns no matches
- [ ] AC#4: Each modified file uses intent language instead of tool-specific commands
