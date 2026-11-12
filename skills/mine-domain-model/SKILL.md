---
name: mine-domain-model
description: "Use when the user says: \"domain model\", \"glossary\", \"sharpen terminology\", \"define this term\", \"what does X mean in this codebase\", \"ubiquitous language\", or wants to pin down domain terminology, or when another skill needs to maintain the domain model."
user-invocable: true
---

# Domain Model

Actively build and sharpen the project's domain model as you design. This is the *active* discipline — challenging terms, inventing edge-case scenarios, and writing the glossary down the moment terms crystallize. (Merely *reading* `CONTEXT.md` for vocabulary is not this skill — that's a one-line habit any skill can do. This skill is for when you're changing the model, not just consuming it.)

## Direct Invocation

Most of the time this skill runs ambient, layered onto whatever design conversation is already happening. It can also be invoked directly with a term to pin down — e.g. `/mine-domain-model "what does cancellation mean"`. In that case, treat the argument as the term in question and open with the relevant question from [Sharpen fuzzy language](#sharpen-fuzzy-language).

## File Structure

`CONTEXT.md` lives at the repo root. Create files lazily — only when you have something to write. If no `CONTEXT.md` exists, create one when the first term is resolved, using the format in [CONTEXT.md Format](#contextmd-format).

## CONTEXT.md Format

`CONTEXT.md` is a glossary of domain terms — the project's ubiquitous language. It is devoid of implementation details: no file paths, no class names, no framework mentions. Just what each term means in this project's domain.

```markdown
# Context: <Project Name>

## Glossary

### <Term>
<Definition — what it means in this project's domain. One or two sentences.>

### <Term>
<Definition>
```

### CONTEXT.md Rules

- One `###` entry per term, alphabetized is not required — order by relatedness or introduction order, whichever reads more naturally.
- Definitions are one or two sentences. If a term needs more than that to explain, it is probably two terms.
- Cross-reference related terms by name inline (e.g., "A **Refund** is a partial or full reversal of a **Payment**, distinct from a **Cancellation** which reverses an **Order** before fulfillment.") rather than nesting definitions inside each other.
- Do not describe how a term is implemented, stored, or validated — that belongs in code, not here.
- When a term's definition changes, edit the entry in place. Do not append a second entry for the same term or leave the old definition as a comment.

## During the Session

### Challenge against the glossary

When the user uses a term that conflicts with the existing language in `CONTEXT.md`, call it out immediately. "Your glossary defines 'cancellation' as X, but you seem to mean Y — which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. Ask one question at a time, and attach your recommended answer so the user can confirm or correct rather than starting from a blank page: "You're saying 'account' — do you mean the Customer or the User? Those are different things. Recommendation: Customer, since the code's billing module already uses that term."

### Discuss concrete scenarios

When domain relationships are being discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code agrees. If you find a contradiction, surface it: "Your code cancels entire Orders, but you just said partial cancellation is possible — which is right?"

### Update `CONTEXT.md` inline

When a term is resolved, update `CONTEXT.md` right there. Don't batch these up — capture them as they happen. Use the format in [CONTEXT.md Format](#contextmd-format).

`CONTEXT.md` should be totally devoid of implementation details. Do not treat `CONTEXT.md` as a spec, a scratch pad, or a repository for implementation decisions. It is a glossary and nothing else.

Concurrent sessions in separate worktrees can each resolve the same term differently; both entries can merge in cleanly with no conflict marker if they don't textually overlap. This is a known, self-correcting risk for a single-user glossary — not actively guarded against — so re-read a term's entry if it seems inconsistent with a session you don't remember writing.
