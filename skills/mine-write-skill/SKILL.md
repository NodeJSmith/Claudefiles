---
name: mine-write-skill
description: "Use when the user says: \"create a skill\", \"write a skill\", \"new skill\", or wants to author a new SKILL.md. Guided skill creation following Claudefiles conventions."
user-invocable: true
---

# Write Skill

Guided creation of a new skill for this repo. Gathers requirements, drafts the skill, validates against a quality checklist, and writes it to the correct location.

A good skill states its goal, why it matters, and what done looks like, and leaves the how to the agent. Exact steps belong only where something outside the agent depends on them (see `references/common/instruction-quality.md`). Lists of steps and cases get followed literally and miss whatever the author didn't picture.

## Arguments

$ARGUMENTS — optional skill name or description. If provided, use as starting context.

---

## Phase 1: Requirements

The purpose is the one thing only the user knows. If $ARGUMENTS doesn't already describe the task the skill should handle, ask:

```
AskUserQuestion:
  question: "What task should this skill handle? Describe the problem it solves."
  header: "Purpose"
```

Derive the rest from the purpose and the codebase, and present it in the draft for correction instead of asking up front:

- **Triggers** — phrases a user would say, in the style of the `description` of existing skills.
- **Output** — a file, a report, a question, or an action, whichever the purpose implies.
- **Invocability** — user-invocable unless the purpose is clearly a reference loaded by other skills.

Ask again only when the purpose is ambiguous between a new skill and an extension of an existing one.

Then explore the codebase for related skills, patterns, or existing work that should inform the new skill's design.

---

## Phase 2: Draft

### Determine the skill name

Derive from the purpose: `mine-<kebab-case-name>`. Max 30 chars total. Check that `skills/mine-<name>/` doesn't already exist.

### Write SKILL.md

Write to `skills/mine-<name>/SKILL.md` using the template in REFERENCE.md. Draft the goal, the why, and what done looks like first; then add only the contract steps. See REFERENCE.md for conventions, AskUserQuestion constraints (`header` ≤12 chars, max 4 options), and size guidance.

---

## Phase 3: Quality Checklist

Check the draft against the checklists in REFERENCE.md. The one that matters most: the draft states its goal, why, and what done looks like, with exact steps only where something outside the agent depends on them.

Report results. Fix any failures before presenting to the user.

---

## Phase 4: Wiring

After the user approves the skill:

1. Add a row to the matching skills table in `REFERENCE.md` (alphabetical order), and to `ONBOARDING.md` if a new adopter should know about the skill
2. Remind the user to run `uv run install.py` to create the symlink
