# Write Skill — Reference

Extended guidance for SKILL.md authoring. Referenced by SKILL.md — do not reference further files from here.

---

## SKILL.md Template

```markdown
---
name: mine-<name>
description: "Use when the user says: '<trigger 1>', '<trigger 2>', or <broader description>."
user-invocable: true|false
---

# mine-<name>

<One-paragraph summary: what it does, when to use it, what it produces.>

## Arguments

$ARGUMENTS — <what arguments it accepts, or "none">

---

## Phase 1: <First phase name>
...

## Phase N: <Last phase name>
...
```

---

## Conventions

- `mine-*` prefix for first-party skills
- Frontmatter fields: `name`, `description`, `user-invocable`
- Description: starts with "Use when..." trigger phrases, ends with a summary of what it produces
- Phases are numbered with descriptive names
- Use `AskUserQuestion` for every user interaction point — explicit header and options
  - `header` ≤12 characters
  - Maximum 4 options per question
- Use `spec-helper`, `get-skill-tmpdir`, and other `bin/` helpers where appropriate — don't reinvent
- If the skill needs scripts, add them to `bin/` (shared), not inside the skill directory

## Size Target

Keep SKILL.md under ~100 lines. If the skill needs detailed reference material (examples, templates, extended guidance), split into:
- `SKILL.md` — workflow and phases (the "what to do")
- `REFERENCE.md` — detailed guidance, templates, examples (the "how to do it well")

---

## Quality Checklist — Structural Criteria

1. **Description includes trigger phrases** — frontmatter `description` must start with `"Use when the user says: '...'"`; include at least 2–3 specific user phrases
2. **SKILL.md under ~100 lines** — if longer, split reference material (templates, extended examples) into REFERENCE.md; procedural phases stay in SKILL.md
3. **No time-sensitive info** — no hardcoded dates, library versions, or ephemeral references; use `$ARGUMENTS` or instruct the agent to look up current state
4. **Consistent terminology** — pick one term for each concept and use it everywhere; don't alternate between "task" and "item", "skill" and "command", etc.
5. **Concrete examples** — at least one example of expected behavior, output format, or invocation; abstract guidance without examples is harder to follow
6. **References at most one level deep** — SKILL.md may reference REFERENCE.md; REFERENCE.md should not reference further files (prevents infinite chains)
7. **No duplication with existing skills** — grep `skills/` for similar functionality; if overlap exists, consider extending an existing skill rather than creating a new one
8. **User interaction points are explicit** — every place the user must respond uses `AskUserQuestion`; no implicit "wait for user input" or free-text assumptions

## Quality Checklist — Instruction Quality Criteria

See `references/common/instruction-quality.md` for the full framework. Apply proportionally — simple factual rules need only the rule itself; behavioral and principle-level guidance should hit most of these.

9. **Diagnostic questions over thresholds** — where the skill sets a standard, include a question the agent can ask itself in the moment ("can a reader answer X in 30 seconds?") not just a number to check against ("max 800 lines"). The question generalizes to novel situations.
10. **Named failure modes** — each behavioral rule should name the specific trap it guards against, not just the desired behavior. "Agents tend to X because Y — counter it by Z" fires at the right moment. "Don't do X" gets skimmed.
11. **AI-specific bias acknowledgment** — where the skill addresses a domain where AI agents have a known tendency (over-engineering, sycophantic agreement, bolting on instead of integrating), call it out directly. "You have a bias toward X" gets more attention than generic advice.
12. **A generative value** — one sentence that would produce correct behavior even if the rest of the skill were deleted. "If a human developer would find the code exhausting to maintain, it is a bad solution." If the skill is only a checklist with no underlying principle, it will be applied literally and miss edge cases.
13. **"Why" before "what"** — each major rule explains the trap it guards against before stating the rule. Understanding why makes agents apply the spirit in edge cases rather than following the letter and missing the point.
