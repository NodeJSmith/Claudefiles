# ADR Format

Architecture Decision Records live directly under `design/`, one file per decision, named `adr-NNNN-slug.md` (4-digit sequential number, kebab-case slug).

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

## Rules

- **Title** is the decision itself, not the topic ("Use Postgres for the write model", not "Database choice").
- **Context** states the forces at play — constraints, competing concerns, the question that needed an answer — without yet revealing the decision.
- **Decision** states what was chosen and the reasoning, including the alternatives that were considered and rejected.
- **Consequences** are honest about tradeoffs — what gets easier, what gets harder, what the decision forecloses.
- Never edit a decided ADR's Decision section to reflect a later change of mind. Write a new ADR and set the old one's **Status** to `superseded by ADR-NNNN`.
- Keep ADRs short. A page is generous. If it runs longer, the decision was probably several decisions bundled together.
