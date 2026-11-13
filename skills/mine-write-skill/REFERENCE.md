# Write Skill — Reference

Template, conventions, and the quality checklist for SKILL.md authoring.

---

## SKILL.md Template

```markdown
---
name: mine-<name>
description: "Use when the user says: '<trigger 1>', '<trigger 2>', or <broader description>."
user-invocable: true|false
---

# mine-<name>

<What the skill is for and why it exists: the problem, who it's for, what they do with the result.>

## Arguments

$ARGUMENTS — <what arguments it accepts, or "none">

## Done looks like

<The output and the bar it has to clear. Concrete enough that the agent can tell when it's finished and when it's padding.>

## Contract
<Only the steps something outside the agent depends on (see `references/common/instruction-quality.md`). Omit the section otherwise.>
```

Add sections when the skill needs them (what makes this hard, known traps, a REFERENCE.md of recipes). Phases are for work whose order is part of the contract, not a default structure.

---

## Conventions

- `mine-*` prefix for first-party skills
- Frontmatter fields: `name`, `description`, `user-invocable`
- Description: starts with "Use when..." trigger phrases, ends with a summary of what it produces
- Use `AskUserQuestion` for every user interaction point
  - `header` ≤12 characters
  - Maximum 4 options per question
  - When the right options depend on what the skill just found (findings, open questions, whether anything changed), describe them as a menu the agent builds from: which options exist, when each fits, and what to recommend. Don't hardcode a fixed list with a pinned "(Recommended)". If the agent can already tell the question is pointless, let it skip the question. Example: "Ask what's next (header `Ship or fix?`): offer Ship when there are no CRITICAL/HIGH findings, lead with Fix and re-review (naming the findings) when there are, and always offer Stop." The header, `multiSelect`, and the labels that "On 'X'" handlers match still belong in the prose.
- Put temp files in a per-run `mktemp -d <scratchpad>/<skill-name>-XXXXXX` directory, and use `bin/` helpers where appropriate — don't reinvent
- If the skill needs scripts, add them to `bin/` (shared), not inside the skill directory

## Size

SKILL.md holds the goal, what done looks like, and any contract. Material the agent looks up only when it needs it (recipes, formats, extended examples) goes in a `REFERENCE.md` beside it.

---

## Quality Checklist — Structural Criteria

1. **Description includes trigger phrases** — frontmatter `description` must start with `"Use when the user says: '...'"`; include at least 2–3 specific user phrases
2. **Every line earns its place** — for each sentence, you can name what the agent would get wrong without it; lookup material lives in REFERENCE.md, not SKILL.md
3. **No time-sensitive info** — no hardcoded dates, library versions, or ephemeral references; use `$ARGUMENTS` or instruct the agent to look up current state
4. **Consistent terminology** — pick one term for each concept and use it everywhere; don't alternate between "task" and "item", "skill" and "command", etc.
5. **Examples where the goal is easy to misread** — where a reader could plausibly take the goal the wrong way, show it, preferably with an example of the failure it prevents; don't add examples to a goal that's already clear
6. **No reference chains** — SKILL.md links directly to every file the agent needs; a supporting file doesn't send the agent on to further supporting files, which get skimmed or missed. Pointing to a shared standard (like `references/common/instruction-quality.md`) is fine
7. **No unresolved overlap with an existing skill** — if the purpose overlaps one, the user chose a new skill over extending it
8. **User interaction points are explicit** — wherever the user's answer is actually needed, they see an interactive `AskUserQuestion` prompt, not an implicit wait for free text

## Quality Checklist — Instruction Quality Criteria

9. **Goal first, steps only for contracts** — passes the standard in `references/common/instruction-quality.md`.
