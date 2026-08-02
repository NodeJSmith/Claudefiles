---
task_id: "T02"
title: "create mine-wayfinder skill"
status: "done"
depends_on: ["T01"]
implements: ["FR#2", "FR#9", "AC#1", "AC#2", "AC#7"]
---

## Target Files

- create: `skills/mine-wayfinder/SKILL.md`

## Prompt

Create the mine-wayfinder skill — multi-session decision mapping for foggy efforts too big for one context window. Adapted from Pocock's `wayfinder` skill (search for `### 17. \`skills/engineering/wayfinder/SKILL.md\`` in the source material file).

This is the most complex adaptation. Key changes:

**Frontmatter:**
- `name: mine-wayfinder`
- `user-invocable: true` (user-invoked only — this is explicitly invoked for large efforts, not auto-triggered)
- Description: "Use when the user says: \"wayfinder\", \"chart this effort\", \"too big for one session\", \"multi-session plan\", \"foggy effort\", or has a large uncertain effort that needs progressive discovery before planning."

**Dependency remapping — CRITICAL:**
- Every `/grilling` reference → describe inline or say "run `/mine-grill`"
- Every `/domain-modeling` reference → "run `/mine-domain-model`"
- Every `/research` reference → "dispatch via `/mine-research`"
- Every `/prototype` reference → "dispatch via `/mine-mockup`"
- The setup reference (`/setup-matt-pocock-skills`) → remove entirely; state that the skill uses `gh-issue` for all tracker operations

**Issue tracker operations — use `gh-issue` CLI:**
- Create map issue: `gh-issue create --title "<map title>" --label "wayfinder:map" --body "<map body>"`
- Create child ticket: `gh-issue create --title "<ticket title>" --label "wayfinder:<type>" --body "<ticket body>"` then add as sub-issue
- Close ticket: `gh-issue close <number>`
- Assign ticket (claim): `gh issue edit <number> --add-assignee @me` (raw `gh` — `gh-issue` doesn't cover assignment)
- Query frontier (open, unblocked, unclaimed children): `gh-issue list` with appropriate filters
- Add blocking relationships: note blocking in the ticket body ("Blocked by: #N, #M") since GitHub's sub-issue/blocking features have limited CLI support
- The skill should handle the case where the repo doesn't have GitHub Issues enabled — fall back to local markdown under `.scratch/<effort>/issues/` (similar to Pocock's local-markdown tracker)

**Keep intact from the original:**
- The entire fog-of-war concept and Not-yet-specified section
- The out-of-scope section and scoping discipline
- The map body structure (Destination, Notes, Decisions so far, Not yet specified, Out of scope)
- Ticket types (research, prototype, grilling, task) with HITL/AFK distinction
- The "one ticket per session max" rule (except research)
- The two invocation modes (Chart the map / Work through the map)
- The "refer by name" principle (use issue titles, not bare numbers)
- The "plan don't do" default

**Adapt ticket type resolution:**
- Research (AFK): dispatch via `/mine-research` subagent
- Prototype (HITL): dispatch via `/mine-mockup`
- Grilling (HITL): run `/mine-grill` and `/mine-domain-model`
- Task (HITL or AFK): unchanged

## Verify

- [ ] FR#2: `skills/mine-wayfinder/SKILL.md` exists with fog-of-war, map structure, ticket types, and two invocation modes
- [ ] AC#1: Frontmatter includes `user-invocable: true` and correct name/description
- [ ] FR#9: Frontmatter uses `user-invocable: true`
- [ ] AC#2: grep for `/grilling`, `/research`, `/prototype`, `/domain-modeling`, `/setup-matt-pocock-skills` returns zero matches
- [ ] AC#2: grep for `mine-grill`, `mine-research`, `mine-mockup`, `mine-domain-model`, `gh-issue` returns matches
