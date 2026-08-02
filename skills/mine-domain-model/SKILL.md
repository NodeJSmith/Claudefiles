---
name: mine-domain-model
description: "Use when the user says: \"domain model\", \"glossary\", \"sharpen terminology\", \"define this term\", \"what does X mean in this codebase\", \"ubiquitous language\", or wants to pin down domain terminology, record an architectural decision, or when another skill needs to maintain the domain model."
user-invocable: true
---

# Domain Model

Actively build and sharpen the project's domain model as you design. This is the *active* discipline — challenging terms, inventing edge-case scenarios, and writing the glossary and decisions down the moment they crystallize. (Merely *reading* `CONTEXT.md` for vocabulary is not this skill — that's a one-line habit any skill can do. This skill is for when you're changing the model, not just consuming it.)

## File Structure

```
/
├── CONTEXT.md
└── design/
    ├── adr-001-event-sourced-orders.md
    └── adr-002-postgres-for-write-model.md
```

`CONTEXT.md` lives at the repo root. Create files lazily — only when you have something to write. If no `CONTEXT.md` exists, create one when the first term is resolved, using the format in [context-format.md](./context-format.md). If no `design/` directory exists, create it when the first ADR is needed, using the format in [adr-format.md](./adr-format.md).

## During the Session

### Challenge against the glossary

When the user uses a term that conflicts with the existing language in `CONTEXT.md`, call it out immediately. "Your glossary defines 'cancellation' as X, but you seem to mean Y — which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. Ask one question at a time, and attach your recommended answer so the user can confirm or correct rather than starting from a blank page: "You're saying 'account' — do you mean the Customer or the User? Those are different things. Recommendation: Customer, since the code's billing module already uses that term."

### Discuss concrete scenarios

When domain relationships are being discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code agrees. If you find a contradiction, surface it: "Your code cancels entire Orders, but you just said partial cancellation is possible — which is right?"

### Update CONTEXT.md inline

When a term is resolved, update `CONTEXT.md` right there. Don't batch these up — capture them as they happen. Use the format in [context-format.md](./context-format.md).

`CONTEXT.md` should be totally devoid of implementation details. Do not treat `CONTEXT.md` as a spec, a scratch pad, or a repository for implementation decisions. It is a glossary and nothing else.

### Offer ADRs sparingly

Only offer to create an ADR when all three are true:

1. **Hard to reverse** — the cost of changing your mind later is meaningful
2. **Surprising without context** — a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off** — there were genuine alternatives and you picked one for specific reasons

If any of the three is missing, skip the ADR. Use the format in [adr-format.md](./adr-format.md).
