---
name: mine-domain-model
description: "Use when the user says: \"domain model\", \"glossary\", \"sharpen terminology\", \"define this term\", \"what does X mean in this codebase\", \"ubiquitous language\", or wants to pin down domain terminology, or when another skill needs to maintain the domain model."
user-invocable: true
---

# Domain Model

Keep the project's domain language sharp while the design is changing. When the user says something vague, overloaded, or at odds with the glossary or the code, resolve it into a precise term and write it down in `CONTEXT.md` right then, so the project's vocabulary stays one shared thing rather than whatever each conversation happened to mean.

This is the *active* discipline, for when the model is changing. Merely reading `CONTEXT.md` for vocabulary is a habit any skill can have without this one. The skill usually runs ambient, layered on a design conversation; invoked directly with a term (`/mine-domain-model "what does cancellation mean"`), treat the argument as the term in question and start by pinning it down.

## What good looks like

- When the user states how something works, check the code rather than taking it on faith. Terms in conversation match `CONTEXT.md`. When the user's usage conflicts with a definition ("your glossary says 'cancellation' is X, but you seem to mean Y"), or with how the code behaves ("your code cancels entire Orders, but you just said partial cancellation is possible"), say so immediately and get the user to say which is right.
- Fuzzy words get a canonical term. Ask one question at a time and attach a recommendation the user can confirm or correct ("'account': Customer or User? Recommendation: Customer, since the billing module already uses that term").
- Relationships are stress-tested with concrete invented scenarios that probe edge cases, which force the user to be precise about where one concept ends and another begins.
- Resolved terms go into `CONTEXT.md` as they resolve, not batched at the end.

## `CONTEXT.md`

It lives at the repo root, and is created only when the first term is resolved. It is a glossary, the project's ubiquitous language, and nothing else: not a spec, scratch pad, or home for implementation decisions. No file paths, class names, framework mentions, or notes on how a term is stored or validated; that belongs in code.

```markdown
# Context: <Project Name>

## Glossary

### <Term>
<Definition: what it means in this project's domain.>
```

- One `###` entry per term, in whatever order reads naturally.
- A definition is one or two sentences; if it needs more, it is probably two terms.
- Cross-reference related terms by name inline ("A **Refund** is a partial or full reversal of a **Payment**, distinct from a **Cancellation** which reverses an **Order** before fulfillment") instead of nesting definitions.
- When a definition changes, edit the entry in place; don't add a second entry or leave the old one as a comment.

Concurrent sessions in separate worktrees can resolve the same term differently, and both entries can merge in without a conflict marker. That risk is accepted for a single-user glossary, so re-read a term's entry if it looks inconsistent with a session you don't remember.
