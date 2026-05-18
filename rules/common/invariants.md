# Design Invariants

Named invariants that must hold across all code written in this setup. These are defined in their respective rule files — this file promotes them to a proactive checklist.

## When to Check

Scan this list at two points: **before writing code** (catch structural violations before they're written) and **before claiming completion** (catch process violations before they're committed). Not a gate requiring explicit confirmation — just a mental pass at each point.

## Invariant Library

### Immutability
Create new objects, never mutate existing ones. Return new copies with changes.
**Exception:** PySpark DataFrame reassignment is conventional and safe.
**Defined in:** `coding-style.md`

### No Future Annotations
Never add `from __future__ import annotations` — breaks Pydantic, FastAPI, dataclasses, and runtime type inspection.
**Defined in:** `python.md`

### No Optional[X]
Use `X | None`, not `Optional[X]`.
**Defined in:** `python.md`

### No Lazy Imports
All imports at the top of the file. Only exception: `TYPE_CHECKING` guards for circular import avoidance.
**Defined in:** `python.md`

### Mock at Boundaries Only
Mock external APIs, databases, time, filesystem. Use real instances for internal collaborators. Prefer dependency injection.
**Defined in:** `testing.md`

### Dependencies as Parameters
Functions and classes receive collaborators as parameters, not create them inline. If testing requires `mock.patch` more than one level deep, restructure the code.
**Defined in:** `dependency-injection.md`

### No Log Capture Tests
Test the behavior that produces the log, not the log output itself.
**Defined in:** `testing.md`

### Test Co-location
Code and its unit tests ship in the same commit. Integration tests may follow; unit tests may not be deferred.
**Exemptions:** generated code, type definitions, config files, constants, `__init__.py`, docs-only changes, migrations with no business logic.
**Defined in:** `testing.md`

### File Size Limits
200-400 lines typical, 800 max. Functions <50 lines, nesting <4 levels.
**Defined in:** `coding-style.md`

### No Default Underscore Prefixes
Don't prefix methods with `_` unless genuinely unsafe to call out of sequence, required by a framework, or part of a published library API.
**Defined in:** `coding-style.md`

### Evidence Before Claims
Never claim work is done without actual command output proving it.
**Defined in:** `verification.md`

## Adding Invariants

When a code review catches the same violation more than once, or a new rule is added to a rule file that should be checked proactively, add it here with a one-line summary and a `Defined in` pointer. Keep this list under 15 items — if it grows beyond that, the invariants are too granular.
