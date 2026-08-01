# Design: Port Pocock Skills

**Date:** 2026-08-01
**Status:** draft
**Mode:** sketch

## Problem

Six skills from Matt Pocock's `mattpocock/skills` repo fill genuine capability gaps: multi-session decision mapping (wayfinder), persistent domain vocabulary (domain-modeling), structured learning (teach), and a writing pipeline (fragments → shape/beats). None of these exist in the current Claudefiles setup.

## Goals

- Add 6 new skills adapted to existing conventions (naming, frontmatter, dependency wiring, trigger phrases)
- Remap Pocock's internal dependencies to existing equivalents (grilling → mine-grill, research → mine-research, prototype → mine-mockup)
- Wire trigger phrases into capabilities-core.md and update REFERENCE.md

## Non-Goals

- Porting Pocock's setup/bootstrap skill (setup-matt-pocock-skills) — existing gh-issue CLI and repo config cover this
- Porting his code-review, tdd, implement, triage, or diagnosing-bugs skills — existing skills are strictly better
- Porting codebase-design vocabulary as a standalone skill — useful concepts can be folded into mine-domain-model's reference material later
- Fetching Pocock's format side files from GitHub — create adapted versions that match our conventions

## Functional Requirements

- **FR#1** A `mine-domain-model` skill exists that maintains a CONTEXT.md glossary and ADRs in the current repo, challenging fuzzy language, cross-referencing code, and updating inline during design conversations
- **FR#2** A `mine-wayfinder` skill exists that creates a map issue on GitHub with decision tickets as child issues, using fog-of-war progressive discovery to chart multi-session efforts
- **FR#3** A `mine-teach` skill exists that creates a stateful learning workspace with mission, lessons, learning records, reference docs, and zone-of-proximal-development tracking
- **FR#4** A `mine-fragments` skill exists that mines raw writing fragments through grilling and appends them to a markdown file
- **FR#5** A `mine-shape` skill exists that takes raw material and shapes it into an article paragraph-by-paragraph with grounding discipline
- **FR#6** A `mine-beats` skill exists that takes raw material and assembles it into a journey of beats with choose-your-own-adventure branching
- **FR#7** All 6 skills have trigger phrases in `rules/common/capabilities-core.md`
- **FR#8** All 6 skills appear in the REFERENCE.md skills table
- **FR#9** All 6 skills use `user-invocable: true` frontmatter; mine-domain-model's description includes trigger phrases so the model can auto-invoke it during design conversations

## Acceptance Criteria

- **AC#1** Each skill directory exists under `skills/` with a valid SKILL.md (correct frontmatter: name, description, user-invocable)
- **AC#2** mine-wayfinder references `mine-grill`, `mine-research`, `mine-mockup`, `mine-domain-model`, and `gh-issue` — no references to Pocock's original skill names
- **AC#3** mine-domain-model includes format templates for CONTEXT.md and ADR as side files or inline sections
- **AC#4** mine-teach includes format templates for MISSION.md, learning records, resources, and glossary as side files or inline sections
- **AC#5** Trigger phrases in capabilities-core.md match the pattern of existing entries
- **AC#6** REFERENCE.md entries match the table format (| skill | description |)
- **AC#7** All 6 skill directories exist: `ls skills/mine-{domain-model,wayfinder,teach,fragments,shape,beats}/SKILL.md` succeeds

## Approach

Each skill is a new directory under `skills/` with a `SKILL.md` and optional side files. The adaptation follows these conventions drawn from existing skills:

**Frontmatter pattern** (from mine-grill, mine-define):
```yaml
---
name: mine-<name>
description: "Use when the user says: ..."
user-invocable: true
---
```

**Dependency remapping:**
- `/grilling` and `/grill-with-docs` → `mine-grill` (invoke via `/mine-grill`)
- `/research` → `mine-research` (invoke via `/mine-research`)
- `/prototype` → `mine-mockup` (invoke via `/mine-mockup`)
- `/domain-modeling` → `mine-domain-model` (invoke via `/mine-domain-model`)
- Issue tracker operations → `gh-issue` CLI preferred; raw `gh` acceptable for operations `gh-issue` doesn't cover (e.g., assignment)

**Side file strategy:**
- mine-domain-model: context-format.md, adr-format.md as side files (adapted from Pocock's, not fetched)
- mine-teach: mission-format.md, learning-record-format.md, resources-format.md as side files
- Others: single SKILL.md, no side files needed

**Grouping in capabilities-core.md:**
- mine-domain-model triggers: "domain model", "glossary", "sharpen terminology", "define this term", "what does X mean in this codebase"
- mine-wayfinder triggers: "wayfinder", "chart this effort", "too big for one session", "multi-session plan", "foggy effort"
- mine-teach triggers: "teach me", "learn about", "study", "lesson on", "help me learn"
- mine-fragments triggers: "mine fragments", "explore writing", "raw material", "capture fragments"
- mine-shape triggers: "shape this article", "write paragraph by paragraph", "shape this writing"
- mine-beats triggers: "write in beats", "beat by beat", "choose your own adventure writing"

## Changed Files

- create: `skills/mine-domain-model/SKILL.md` — main skill file
- create: `skills/mine-domain-model/context-format.md` — glossary format template
- create: `skills/mine-domain-model/adr-format.md` — ADR format template
- create: `skills/mine-wayfinder/SKILL.md` — main skill file
- create: `skills/mine-teach/SKILL.md` — main skill file
- create: `skills/mine-teach/mission-format.md` — mission format template
- create: `skills/mine-teach/learning-record-format.md` — learning record format template
- create: `skills/mine-teach/resources-format.md` — resources format template
- create: `skills/mine-fragments/SKILL.md` — main skill file
- create: `skills/mine-shape/SKILL.md` — main skill file
- create: `skills/mine-beats/SKILL.md` — main skill file
- modify: `rules/common/capabilities-core.md` — add trigger phrases for all 6 skills
- modify: `REFERENCE.md` — add all 6 skills to the core skills table
