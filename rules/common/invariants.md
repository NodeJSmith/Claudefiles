---
tool: claude, codex, antigravity
---

# Design Invariants

Named invariants that must hold across all code written in this setup. These are defined in their respective rule files — this file promotes them to a proactive checklist.

## When to Check

Scan this list at two points: **before writing code** (catch structural violations before they're written) and **before claiming completion** (catch process violations before they're committed). Not a gate requiring explicit confirmation — just a mental pass at each point.

## Severity Tiers

- **Must** — no exceptions. Always a violation. Fix before committing.
- **Should** — wrong unless there's a documented, deliberate reason. If you're violating this, you can articulate why.
- **Consider** — worth a quick check. Neither right nor wrong — context decides.

## Invariant Library

### Must

#### Immutability
Create new objects, never mutate existing ones. Return new copies with changes. (PySpark DataFrame reassignment is exempt — see coding-style.md.)
**Defined in:** `rules/common/coding-style.md`

#### No Future Annotations
Never add `from __future__ import annotations` — breaks Pydantic, FastAPI, dataclasses, and runtime type inspection.
**Defined in:** `rules/common/python.md`

#### No Optional[X]
Use `X | None`, not `Optional[X]`.
**Defined in:** `rules/common/python.md`

#### No Lazy Imports
All imports at the top of the file. Only exception: `TYPE_CHECKING` guards for circular import avoidance.
**Defined in:** `rules/common/python.md`

#### Mock at Boundaries Only
Mock external APIs, databases, time, filesystem. Use real instances for internal collaborators. Prefer dependency injection.
**Defined in:** `references/common/testing.md`

#### Dependencies as Parameters
Functions and classes receive collaborators as parameters, not create them inline. If testing requires `mock.patch` more than one level deep, restructure the code.
**Defined in:** `references/common/dependency-injection.md`

#### No Log Capture Tests
Test the behavior that produces the log, not the log output itself.
**Defined in:** `references/common/testing.md`

#### Evidence Before Claims
Never claim work is done without actual command output proving it.
**Defined in:** `rules/common/verification.md`

#### No `any`
Do not use `any` in TypeScript. Use `unknown` for external data and narrow before use.
**Defined in:** `references/common/typescript.md`

#### No `as` Casts
Do not use `as` casts in TypeScript. Exceptions: after full validation at system boundaries, and branded type constructors where the preceding validation is the only path to the type.
**Defined in:** `references/common/typescript.md`

#### No Enums
Do not use TypeScript `enum`. Use `as const` objects or union types instead.
**Defined in:** `references/common/typescript.md`

#### Functional Components Only
No class components in React/Preact. Use function components with hooks.
**Defined in:** `references/common/frontend.md`

#### Effect Cleanup
Every `useEffect` that subscribes, listens, or opens a connection must return a cleanup function.
**Defined in:** `references/common/frontend.md`

#### Input Validation at Boundaries
External data (user input, API responses, file reads, env vars) validated and parsed at system boundaries. Internal code trusts what the boundary already validated.
**Defined in:** `references/common/security.md`

#### Timeouts on External Calls
Every call to an external service has an explicit timeout. No implicit "wait forever."
**Defined in:** `references/common/reliability.md`

#### Shared State Protection
Concurrent access to shared mutable state: first ask whether sharing is necessary — if not, give each actor its own state. When sharing is a real invariant, protect with locks, queues, or atomic operations.
**Defined in:** `references/common/reliability.md`

#### Parallel Executor Isolation
When launching 2+ subagents that write to the git working directory in parallel, each must use `isolation: "worktree"`. A shared working directory with concurrent writers destroys changes via index races and pre-commit hook stash collisions.
**Defined in:** `references/common/agents.md`

### Should

#### Test Co-location
Code and its unit tests ship in the same commit. Integration tests may follow; unit tests may not be deferred.
**Exemptions:** generated code, type definitions, config files, constants, `__init__.py`, docs-only changes, migrations with no business logic.
**Defined in:** `references/common/testing.md`

#### File Size Limits
200-400 lines typical, 800 max. Functions <50 lines, nesting <4 levels.
**Defined in:** `rules/common/coding-style.md`

#### Errors Surfaced Not Swallowed
Every error path is explicitly handled or propagated. Silent catch-and-ignore hides real failures — use `contextlib.suppress` with a specific exception type when intentional.
**Defined in:** `references/common/reliability.md`

#### Reproduce Before Fixing
A bug you cannot reproduce, you cannot prove fixed. Reproduce it yourself before designing a fix.
**Defined in:** `rules/common/debugging-discipline.md`

#### Pin Behavior Before Refactoring
Before restructuring, capture current behavior with a characterization test. Type checks and lint are not a pin.
**Defined in:** `rules/common/refactoring-discipline.md`

#### Exit Condition Before Iterating
Define done as a checkable predicate before the first iteration of a long-running task.
**Defined in:** `rules/common/autonomous-run-discipline.md`

#### Verify Review Findings Before Accepting
When code review findings arrive, verify each against the actual code before implementing. Reviewers make mistakes. Grep for suggested abstractions — if no callers exist outside the changed files, skip it.
**Defined in:** `references/common/receiving-code-review.md`

### Consider

These principles are defined in `rules/common/` files that are themselves always loaded — their full text is already in context, so this tier is just the scan list: **Laziness Protocol, Reader Load, Subtract Before You Add, Redesign from First Principles, Outcome-Oriented Execution, Encode Lessons in Structure, Exhaust the Design Space, Experience First, Baseline Before Optimizing, Decompose Before Implementing, No Default Underscore Prefixes, Build the Lever**.

Three more are defined in `references/common/` files, which load only on demand (via the Domain References table below) — so their summaries stay here as the always-present surface:

#### AI Prose Self-Audit
After writing non-code text (PR descriptions, docs, skill files, rules), ask: "What makes this obviously AI-generated?" Fix whatever comes to mind. Em dashes, hedging, significance inflation, and synonym cycling are the common tells.
**Defined in:** `references/common/writing-quality.md`

#### Screenshot Before and After UI Changes
Before changing any UI, screenshot the affected pages and sibling pages. After implementing, screenshot again to verify. Visual bugs only appear in screenshots.
**Defined in:** `references/common/frontend.md`

#### Instruction Quality Checks
When writing rules or skill files, apply proportionally: diagnostic questions over thresholds, named failure modes, AI-specific bias acknowledgment, a generative value, and "why" before "what."
**Defined in:** `references/common/instruction-quality.md`

## Domain References

**BLOCKING REQUIREMENT**: Before starting work that matches a row below, Read the reference file. Do NOT proceed with domain work without loading the relevant guidance first.

| When working with... | Read |
|----------------------|------|
| `.ts`, `.tsx`, `.js`, `.jsx` files | `${CLAUDE_HOME:-~/.claude}/references/common/typescript.md` |
| Frontend components, CSS, UI | `${CLAUDE_HOME:-~/.claude}/references/common/frontend.md` |
| Backend services, async code, retries | `${CLAUDE_HOME:-~/.claude}/references/common/reliability.md`, `${CLAUDE_HOME:-~/.claude}/references/common/dependency-injection.md` |
| Tests, TDD, pytest | `${CLAUDE_HOME:-~/.claude}/references/common/testing.md` |
| Prose: PR descriptions, docs, skills, rules | `${CLAUDE_HOME:-~/.claude}/references/common/writing-quality.md` |
| Subagent orchestration, parallel executors | `${CLAUDE_HOME:-~/.claude}/references/common/agents.md` |
| Processing code review findings | `${CLAUDE_HOME:-~/.claude}/references/common/receiving-code-review.md` |
| Writing rules or skill files | `${CLAUDE_HOME:-~/.claude}/references/common/instruction-quality.md` |
| API endpoints, auth handlers, user input | `${CLAUDE_HOME:-~/.claude}/references/common/security.md` |

## Adding Invariants

When a code review catches the same violation more than once, or a new rule is added to a rule file that should be checked proactively, add it here with a one-line summary, a tier, and a `Defined in` pointer. Keep Must items tight — they're the "never violate" set. Should and Consider can be more inclusive.
