---
task_id: "T03"
title: "create mine-teach skill with format side files"
status: "done"
depends_on: []
implements: ["FR#3", "FR#9", "AC#1", "AC#4", "AC#7"]
---

## Target Files

- create: `skills/mine-teach/SKILL.md`
- create: `skills/mine-teach/mission-format.md`
- create: `skills/mine-teach/learning-record-format.md`
- create: `skills/mine-teach/resources-format.md`

## Prompt

Create the mine-teach skill — structured learning over multiple sessions with a stateful workspace. Adapted from Pocock's `teach` skill (search for `### 21. \`skills/productivity/teach/SKILL.md\`` in the source material file).

**Frontmatter:**
- `name: mine-teach`
- `user-invocable: true`
- Description: "Use when the user says: \"teach me\", \"learn about\", \"study\", \"lesson on\", \"help me learn\", \"tutorial on\", or wants structured learning over multiple sessions."

**Key adaptations:**
- Remove the Tailwind CDN reference for lesson HTML — lessons must be self-contained (no CDN, same constraint as Artifacts). Use inline CSS.
- The `./assets/` shared component library concept is good — keep it
- Keep the full philosophy section (knowledge, skills, wisdom; fluency vs storage strength)
- Keep zone-of-proximal-development tracking via learning records
- Keep the NOTES.md scratchpad concept
- The glossary format from Pocock references a `GLOSSARY-FORMAT.md` — fold glossary guidance into the SKILL.md directly (it's a simple format: term → definition pairs) rather than adding another side file
- Reference side files with relative paths: `[mission-format.md](./mission-format.md)`, `[learning-record-format.md](./learning-record-format.md)`, `[resources-format.md](./resources-format.md)`

**mission-format.md** — create from the SKILL.md description. The mission captures WHY the user wants to learn this. Format:
```markdown
# Mission

## Why I'm Learning This
<The reason — what goal this serves, what problem it solves>

## Current Level
<Where the user is now — beginner, some exposure, practitioner switching domains>

## Target
<What "done" looks like — what the user wants to be able to do>

## Constraints
<Time budget, preferred learning style, tools available>
```

**learning-record-format.md** — capture non-obvious lessons and key insights. Format:
```markdown
# NNNN — <Title>

**Date:** YYYY-MM-DD
**Lesson:** <which lesson this came from>
**Status:** active | revised by NNNN | deprecated

## Insight
<What was learned — the non-obvious takeaway>

## Evidence
<What demonstrated this — the exercise, example, or experience>

## Implications
<What this changes about future learning — what to do differently>
```

**resources-format.md** — track high-quality learning resources. Format:
```markdown
# Resources

## Primary Sources
<Official docs, canonical textbooks, first-party references>

| Resource | Type | Trust | Notes |
|----------|------|-------|-------|
| <name + URL> | docs/book/video/course | high/medium | <why it's useful> |

## Community
<Forums, subreddits, Discord servers, local groups>

## To Evaluate
<Resources found but not yet vetted>
```

## Verify

- [ ] FR#3: `skills/mine-teach/SKILL.md` exists with workspace model (MISSION.md, learning-records/, lessons/, reference/, assets/), zone-of-proximal-development tracking, and lesson creation guidance
- [ ] AC#4: Side files exist: `skills/mine-teach/mission-format.md`, `skills/mine-teach/learning-record-format.md`, `skills/mine-teach/resources-format.md`
- [ ] AC#1: Frontmatter includes `user-invocable: true`
