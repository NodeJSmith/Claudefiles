---
name: mine-write-skill
description: "Use when the user says: \"create a skill\", \"write a skill\", \"new skill\", or wants to author a new SKILL.md. Guided skill creation following Claudefiles conventions."
user-invocable: true
---

# Write Skill

Write a new skill for this repo that a current model can run well, and wire it in so it installs.

A good skill states its goal, why it matters, and what done looks like, and leaves the how to the agent. Exact steps belong only where something outside the agent depends on them (see `references/common/instruction-quality.md`). Lists of steps and cases get followed literally and miss whatever the author didn't picture. Hold your draft to the same standard as this file.

## Arguments

$ARGUMENTS — optional skill name or description, used as starting context.

## Done looks like

- `skills/mine-<name>/SKILL.md` exists, drafted from the template and conventions in this skill's `REFERENCE.md`, and passes its quality checklist. Fix failures before showing the draft; don't report them as caveats.
- The user approved the draft, having seen the triggers, output, and invocability you inferred, and had the chance to correct them.
- The skill is wired in: a row in the matching skills table of the repo-root `REFERENCE.md` (alphabetical), an `ONBOARDING.md` entry if a new adopter should know about it, and a reminder to run `uv run install.py` so the symlink gets created.

## What makes this go well

The purpose is the one thing only the user knows. If $ARGUMENTS doesn't describe what task the skill handles, ask. Infer the trigger phrases, output, and whether it's user-invocable from the purpose and the codebase, and put them in the draft for correction rather than interviewing up front.

Before drafting, look at related skills. The usual mistake is writing a new skill when an existing one should be extended; if the purpose overlaps one, say so and ask which way to go.

Name it `mine-<kebab-case>`, short enough to type as a slash command.

## Contract

- `skills/mine-<name>/` must not already exist.
- Get the user's approval of the draft through `AskUserQuestion` before any wiring. Edit the repo-root `REFERENCE.md` and `ONBOARDING.md` only after they approve.
