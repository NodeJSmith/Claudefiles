---
name: mine.write-skill
description: "Use when the user says: \"create a skill\", \"write a skill\", \"new skill\", or wants to author a new SKILL.md. Guided skill creation following Claudefiles conventions."
user-invocable: true
---

# Write Skill

Guided creation of a new skill for this repo. Gathers requirements, drafts the skill, validates against a quality checklist, and writes it to the correct location.

## Arguments

$ARGUMENTS — optional skill name or description. If provided, use as starting context.

---

## Phase 1: Requirements

Ask these one at a time. Skip any already answered by $ARGUMENTS.

```
AskUserQuestion:
  question: "What task should this skill handle? Describe the problem it solves."
  header: "Skill purpose"
```

```
AskUserQuestion:
  question: "What trigger phrases should invoke it? (e.g., when the user says 'audit the codebase')"
  header: "Trigger phrases"
```

```
AskUserQuestion:
  question: "What does the output look like? (e.g., a file, a report, a question, an action)"
  header: "Output"
```

```
AskUserQuestion:
  question: "Should this be user-invocable (slash command) or a reference skill (loaded by other skills only)?"
  header: "Invocability"
  multiSelect: false
  options:
    - label: "User-invocable"
      description: "Can be called directly via /mine.<name>"
    - label: "Reference only"
      description: "Loaded by other skills, not directly callable"
```

Then explore the codebase for related skills, patterns, or existing work that should inform the new skill's design.

---

## Phase 2: Draft

### Determine the skill name

Derive from the purpose: `mine.<kebab-case-name>`. Max 30 chars total. Check that `skills/mine.<name>/` doesn't already exist.

### Write SKILL.md

Write to `skills/mine.<name>/SKILL.md`. Follow this structure:

```markdown
---
name: mine.<name>
description: "Use when the user says: '<trigger 1>', '<trigger 2>', or <broader description>."
user-invocable: true|false
---

# mine.<name>

<One-paragraph summary: what it does, when to use it, what it produces.>

## Arguments

$ARGUMENTS — <what arguments it accepts, or "none">

---

## Phase 1: <First phase name>
...

## Phase N: <Last phase name>
...
```

**Conventions:**
- `mine.*` prefix for first-party skills
- Frontmatter: `name`, `description`, `user-invocable`
- Description: starts with "Use when..." trigger phrases, ends with a summary of what it produces
- Phases are numbered with descriptive names
- Use `AskUserQuestion` for user interaction points with explicit header and options
- Use `spec-helper`, `get-skill-tmpdir`, and other `bin/` helpers where appropriate — don't reinvent
- If the skill needs scripts, add them to `bin/` (shared), not inside the skill directory

**Size target:** Keep SKILL.md under ~100 lines. If the skill needs detailed reference material (examples, templates, extended guidance), split into:
- `SKILL.md` — workflow and phases (the "what to do")
- `REFERENCE.md` — detailed guidance, templates, examples (the "how to do it well")

---

## Phase 3: Quality Checklist

Validate the drafted skill against this checklist:

1. **Description includes trigger phrases** — "Use when..." with specific user phrases
2. **SKILL.md under ~100 lines** — or split with REFERENCE.md if longer
3. **No time-sensitive info** — no dates, versions, or ephemeral references
4. **Consistent terminology** — same term used throughout, no synonyms for the same concept
5. **Concrete examples** — at least one example of expected behavior or output
6. **References at most one level deep** — SKILL.md can reference REFERENCE.md, but REFERENCE.md should not reference further files
7. **No duplication with existing skills** — check that this doesn't overlap significantly with an existing skill
8. **User interaction points are explicit** — every place the user must respond uses AskUserQuestion

Report results. Fix any failures before presenting to the user.

---

## Phase 4: Wiring

After the user approves the skill:

1. Add a routing entry to `rules/common/capabilities.md` using the trigger phrases from Phase 1
2. Add a row to the Skills table in `README.md` (alphabetical order) and update the skill count in the section header
3. Remind the user to run `./install.sh` to create the symlink
