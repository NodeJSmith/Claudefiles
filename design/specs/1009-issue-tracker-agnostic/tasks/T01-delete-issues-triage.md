---
task_id: "T01"
title: "delete mine-issues-triage and remove all references"
status: "done"
depends_on: []
implements: ["FR#5", "AC#2"]
---

## Target Files

- delete: `skills/mine-issues-triage/SKILL.md`
- modify: `rules/common/capabilities-core.md` — remove triage routing entries from the skill routing table
- modify: `commands/mine-issues.md` — remove the triage fallback offer in Phase 2 step 4
- modify: `REFERENCE.md` — remove mine-issues-triage entry
- modify: `install.py` — remove mine-issues-triage bundle reference if present

## Prompt

Delete the `skills/mine-issues-triage/` directory entirely.

In `rules/common/capabilities-core.md`, find the skill routing table (the `| User says something like... | Invoke |` table near the top of the file). Remove the row that routes "scan issues", "triage issues", etc. to `/mine-issues-triage`.

In `commands/mine-issues.md`, Phase 2 step 4 currently offers a triage fallback: "or say 'triage' to run a batch scan instead" and "run `/mine-issues-triage` if they ask for it." Remove the triage offer from the `gh` branch. For the `jira` branch, the triage offer is already absent, so no change needed. The step should just ask which issue to look at, without mentioning triage.

Also check `install.py` for any bundle references to `mine-issues-triage` and remove them.

Remove the `mine-issues-triage` entry from `REFERENCE.md` (the skill tables section).

## Verify

- [ ] FR#5: `skills/mine-issues-triage/` directory does not exist
- [ ] AC#2: `grep -rn 'mine-issues-triage\|mine.issues.triage' skills/ rules/ agents/ commands/ install.py REFERENCE.md` returns no matches
