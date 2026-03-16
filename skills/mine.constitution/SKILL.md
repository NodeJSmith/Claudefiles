---
name: mine.constitution
description: "Use when the user says: \"create a constitution\", \"project constraints\", or \"architecture rules\". Guided interview that produces .claude/constitution.md with constraints that mine.design validates against."
user-invocable: true
---

# mine.constitution

Creates or updates `.claude/constitution.md` in the project root. This file captures project-level constraints that `mine.design` validates new designs against. Its absence is handled gracefully — this file is optional but valuable for large or long-lived projects.

---

## Phase 1: Check for Existing Constitution

Check if `.claude/constitution.md` exists in the project root.

If it exists:
```
AskUserQuestion:
  question: "A constitution already exists at .claude/constitution.md. What would you like to do?"
  header: "Constitution exists"
  multiSelect: false
  options:
    - label: "Review and update it"
      description: "Walk through each section and update as needed"
    - label: "Replace it entirely"
      description: "Start fresh with a new interview"
    - label: "View it without changes"
      description: "Just show me what's there"
```

If "View it without changes": read and display the file, then stop.

If "Review and update it": read the existing file, show it to the user, then proceed through Phase 2 with existing answers pre-filled. Only ask about sections the user wants to change.

If "Replace it entirely" or the file doesn't exist: proceed through Phase 2 fresh.

---

## Phase 2: Guided Interview

Ask one question at a time. All sections are optional — the user may answer "skip" or "none" to leave a section empty.

### Architecture Principles

> "What are the guiding architecture principles for this project? (e.g., 'prefer server-side rendering', 'event-driven with async consumers', 'monorepo with shared domain types', 'all external I/O behind repository interfaces')"

### Technology Constraints

> "Are there any mandatory or forbidden technologies? (e.g., 'must use PostgreSQL', 'no ORM — raw SQL only', 'Python 3.12+', 'no Redis dependency')"

### Testing Standards

> "What are your testing requirements? (e.g., 'minimum 80% coverage', 'no mocking of the database layer', 'integration tests must run against a real DB', 'property-based testing for core domain logic')"

### Performance Targets

> "Any performance or scale targets to keep in mind? (e.g., 'API p95 < 200ms', 'handle 1000 concurrent users', 'no N+1 queries in hot paths', 'batch jobs must complete within 1 hour')"

### Security Requirements

> "What security constraints apply? (e.g., 'all endpoints require auth', 'PII must be encrypted at rest', 'no secrets in env vars — use Vault', 'RBAC with explicit deny-by-default')"

### Operational Constraints

> "Any deployment or operational constraints? (e.g., 'must be stateless for horizontal scaling', 'no breaking changes to public APIs without versioning', 'all schema migrations must be backwards-compatible', 'zero-downtime deploys only')"

### Code Style and Review

> "Any code style or review conventions beyond the defaults? (e.g., 'all public APIs must have docstrings', 'functions > 50 lines require justification', 'no PR merges without two approvals')"

### Other Constraints

> "Anything else — project-specific rules, team agreements, or constraints that don't fit the above categories?"

---

## Phase 3: Confirm and Write

Present a one-paragraph summary of everything collected:

```
AskUserQuestion:
  question: "Here's a summary of your constitution:\n\n<summary>\n\nDoes this look right?"
  header: "Confirm constitution"
  multiSelect: false
  options:
    - label: "Yes — write it"
    - label: "No — let me adjust"
      description: "Tell me what to change"
```

If "No": ask what to change and update the summary, then confirm again.

---

## Phase 4: Write .claude/constitution.md

Ensure `.claude/` exists in the project root, then write:

```markdown
# Project Constitution

This file captures project-level constraints that `mine.design` validates new designs against.
Updated: <ISO date>

## Architecture Principles

<content or "None specified.">

## Technology Constraints

<content or "None specified.">

## Testing Standards

<content or "None specified.">

## Performance Targets

<content or "None specified.">

## Security Requirements

<content or "None specified.">

## Operational Constraints

<content or "None specified.">

## Code Style and Review

<content or "None specified.">

## Other Constraints

<content or "None specified.">
```

For each section, if the user said "skip" or "none", write `None specified.`

After writing, confirm:
> Constitution written to `.claude/constitution.md`. `mine.design` will validate new designs against it automatically.

If the file already existed and was updated, note which sections changed.
