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
Create new objects, never mutate existing ones. Return new copies with changes.
**Note:** PySpark DataFrame reassignment (`df = df.filter(...)`) does not violate this — DataFrames are immutable per transform; reassignment rebinds the name to a new object.
**Defined in:** `coding-style.md`

#### No Future Annotations
Never add `from __future__ import annotations` — breaks Pydantic, FastAPI, dataclasses, and runtime type inspection.
**Defined in:** `python.md`

#### No Optional[X]
Use `X | None`, not `Optional[X]`.
**Defined in:** `python.md`

#### No Lazy Imports
All imports at the top of the file. Only exception: `TYPE_CHECKING` guards for circular import avoidance.
**Defined in:** `python.md`

#### Mock at Boundaries Only
Mock external APIs, databases, time, filesystem. Use real instances for internal collaborators. Prefer dependency injection.
**Defined in:** `testing.md`

#### Dependencies as Parameters
Functions and classes receive collaborators as parameters, not create them inline. If testing requires `mock.patch` more than one level deep, restructure the code.
**Defined in:** `dependency-injection.md`

#### No Log Capture Tests
Test the behavior that produces the log, not the log output itself.
**Defined in:** `testing.md`

#### Evidence Before Claims
Never claim work is done without actual command output proving it.
**Defined in:** `verification.md`

#### No `any`
Do not use `any` in TypeScript. Use `unknown` for external data and narrow before use.
**Defined in:** `typescript.md`

#### No `as` Casts
Do not use `as` casts in TypeScript. Exceptions: after full validation at system boundaries, and branded type constructors where the preceding validation is the only path to the type.
**Defined in:** `typescript.md`

#### No Enums
Do not use TypeScript `enum`. Use `as const` objects or union types instead.
**Defined in:** `typescript.md`

#### Functional Components Only
No class components in React/Preact. Use function components with hooks.
**Defined in:** `frontend.md`

#### Effect Cleanup
Every `useEffect` that subscribes, listens, or opens a connection must return a cleanup function.
**Defined in:** `frontend.md`

#### Input Validation at Boundaries
External data (user input, API responses, file reads, env vars) validated and parsed at system boundaries. Internal code trusts what the boundary already validated.
**Defined in:** `security.md`

#### Timeouts on External Calls
Every call to an external service has an explicit timeout. No implicit "wait forever."
**Defined in:** `reliability.md`

#### Shared State Protection
Concurrent access to shared mutable state: first ask whether sharing is necessary — if not, give each actor its own state. When sharing is a real invariant, protect with locks, queues, or atomic operations.
**Defined in:** `reliability.md`

#### Parallel Executor Isolation
When launching 2+ subagents that write to the git working directory in parallel, each must use `isolation: "worktree"`. A shared working directory with concurrent writers destroys changes via index races and pre-commit hook stash collisions.
**Defined in:** `agents.md`

### Should

#### Test Co-location
Code and its unit tests ship in the same commit. Integration tests may follow; unit tests may not be deferred.
**Exemptions:** generated code, type definitions, config files, constants, `__init__.py`, docs-only changes, migrations with no business logic.
**Defined in:** `testing.md`

#### File Size Limits
200-400 lines typical, 800 max. Functions <50 lines, nesting <4 levels.
**Defined in:** `coding-style.md`

#### Errors Surfaced Not Swallowed
Every error path is explicitly handled or propagated. Silent catch-and-ignore hides real failures — use `contextlib.suppress` with a specific exception type when intentional.
**Defined in:** `reliability.md`

#### Reproduce Before Fixing
A bug you cannot reproduce, you cannot prove fixed. Reproduce it yourself before designing a fix.
**Defined in:** `debugging-discipline.md`

#### Pin Behavior Before Refactoring
Before restructuring, capture current behavior with a characterization test. Type checks and lint are not a pin.
**Defined in:** `refactoring-discipline.md`

#### Exit Condition Before Iterating
Define done as a checkable predicate before the first iteration of a long-running task.
**Defined in:** `autonomous-run-discipline.md`

### Consider

#### Laziness Protocol
If tracing a value requires more than 3 files or layers, flatten the hierarchy. Prefer deletion over addition; minimize the diff.
**Defined in:** `laziness-protocol.md`

#### Reader Load
Code is readable when a new reader can answer "where does X come from?" in under 30 seconds. Collapse one-caller wrappers; shrink mutable state scope.
**Defined in:** `reader-load.md`

#### Subtract Before You Add
When evolving a system, remove complexity first, then build on the simpler base. Sequence removal before construction.
**Defined in:** `subtract-first.md`

#### Redesign from First Principles
When integrating a new requirement, redesign as if it had been there from the start. The result should have no bolt-on seams.
**Defined in:** `redesign-from-first-principles.md`

#### Outcome-Oriented Execution
During planned rewrites and migrations, optimize for the end state. Intermediate breakage is acceptable when planned, scoped, and reversible.
**Defined in:** `outcome-oriented-execution.md`

#### Encode Lessons in Structure
When the same instruction appears twice, encode it as a lint rule, metadata flag, runtime check, or script. The instruction is the symptom.
**Defined in:** `encode-lessons-in-structure.md`

#### Exhaust the Design Space
When the right answer is not obvious and no precedent exists, build 2-3 competing prototypes and compare before committing.
**Defined in:** `exhaust-the-design-space.md`

#### Experience First
When implementation convenience conflicts with user delight, choose delight. Every feature must earn its place.
**Defined in:** `experience-first.md`

#### Baseline Before Optimizing
Capture a trace or measurement before changing anything. "It feels faster" is not verification.
**Defined in:** `performance-discipline.md`

#### Decompose Before Implementing
For multi-module features, answer the four blocking/parallel/shared-state/decomposition questions before writing logic.
**Defined in:** `decomposition-discipline.md`

#### No Default Underscore Prefixes
Don't prefix methods with `_` unless genuinely unsafe to call out of sequence, required by a framework, or part of a published library API.
**Defined in:** `coding-style.md`

## Adding Invariants

When a code review catches the same violation more than once, or a new rule is added to a rule file that should be checked proactively, add it here with a one-line summary, a tier, and a `Defined in` pointer. Keep Must items tight — they're the "never violate" set. Should and Consider can be more inclusive.
