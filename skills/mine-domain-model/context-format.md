# CONTEXT.md Format

`CONTEXT.md` is a glossary of domain terms — the project's ubiquitous language. It is devoid of implementation details: no file paths, no class names, no framework mentions. Just what each term means in this project's domain.

```markdown
# Context: <Project Name>

## Glossary

### <Term>
<Definition — what it means in this project's domain. One or two sentences.>

### <Term>
<Definition>
```

## Rules

- One `###` entry per term, alphabetized is not required — order by relatedness or introduction order, whichever reads more naturally.
- Definitions are one or two sentences. If a term needs more than that to explain, it is probably two terms.
- Cross-reference related terms by name inline (e.g., "A **Refund** is a partial or full reversal of a **Payment**, distinct from a **Cancellation** which reverses an **Order** before fulfillment.") rather than nesting definitions inside each other.
- Do not describe how a term is implemented, stored, or validated — that belongs in code or an ADR, not here.
- When a term's definition changes, edit the entry in place. Do not append a second entry for the same term or leave the old definition as a comment.
