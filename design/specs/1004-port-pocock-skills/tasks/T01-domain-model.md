---
task_id: "T01"
title: "create mine-domain-model skill with format side files"
status: "done"
depends_on: []
implements: ["FR#1", "FR#9", "AC#1", "AC#3", "AC#7"]
---

## Target Files

- create: `skills/mine-domain-model/SKILL.md`
- create: `skills/mine-domain-model/context-format.md`
- create: `skills/mine-domain-model/adr-format.md`

## Prompt

Create the mine-domain-model skill — an active domain glossary discipline that maintains `CONTEXT.md` and ADRs during design conversations.

**SKILL.md** — adapt from Pocock's `domain-modeling` skill (search for `### 5. \`skills/engineering/domain-modeling/SKILL.md\`` in the source material file). Key adaptations:

- Frontmatter: `name: mine-domain-model`, `user-invocable: true`, description with trigger phrases including "Use when..." with triggers like: "domain model", "glossary", "sharpen terminology", "define this term", "what does X mean in this codebase", "or when another skill needs to maintain the domain model"
- Remove all references to `/grilling` → describe the inline grilling behavior directly (one question at a time, recommended answer attached)
- Remove all references to `/codebase-design` — not being ported
- Remove references to `CONTEXT-MAP.md` multi-context layout — simplify to single-context only (one CONTEXT.md at repo root)
- Keep the core behaviors: challenge fuzzy language, cross-reference code, update CONTEXT.md inline, offer ADRs sparingly (hard-to-reverse + surprising + real tradeoff)
- Reference side files with relative paths: `[context-format.md](./context-format.md)`, `[adr-format.md](./adr-format.md)`

**context-format.md** — create a format template for CONTEXT.md. Based on what the SKILL.md describes: a glossary of domain terms, devoid of implementation details. Format:
```markdown
# Context: <Project Name>

## Glossary

### <Term>
<Definition — what it means in this project's domain. One or two sentences.>

### <Term>
<Definition>
```

**adr-format.md** — create an ADR format template. Standard lightweight ADR:
```markdown
# ADR-NNNN: <Title>

**Date:** YYYY-MM-DD
**Status:** accepted | superseded by ADR-NNNN | deprecated

## Context
<What forces are at play>

## Decision
<What we decided and why>

## Consequences
<What follows from this decision — good and bad>
```

## Verify

- [ ] FR#1: `skills/mine-domain-model/SKILL.md` exists with correct frontmatter (`user-invocable: true`, description with trigger phrases)
- [ ] AC#3: `skills/mine-domain-model/context-format.md` and `skills/mine-domain-model/adr-format.md` exist
- [ ] No references to `/grilling`, `/codebase-design`, `/domain-modeling`, or `CONTEXT-MAP.md` in any file
