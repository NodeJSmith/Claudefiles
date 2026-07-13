---
tool: claude, antigravity
---

# Coding Style

## Immutability (CRITICAL)

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

ALWAYS create new objects, NEVER mutate existing ones. Return new copies with changes, never modify in-place.

**PySpark exception**: PySpark DataFrame reassignment (`df = df.filter(...)`) is the project convention and does not violate this rule — DataFrames are lazy and immutable per transform, so reassigning `df` rebinds the name to a new immutable object.

## File Organization

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

- 200-400 lines typical, 800 max
- Organize by feature/domain, not by type
- Functions <50 lines, nesting <4 levels

## No Default Underscore Prefixes

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

Do not prefix methods with `_` unless there is a concrete reason. Claude's instinct is to mark anything not called in the same method as `_private` — resist this.

`_` is appropriate when:
- The method is genuinely unsafe to call outside its intended sequence (e.g., `_commit_transaction` that assumes locks are held)
- A framework convention requires it (e.g., `_meta` in Django models)
- The class is part of a published library with a stable API contract

`_` is not appropriate just because:
- Only one other method calls it
- It's a "helper" or "internal" method
- It "feels like an implementation detail"

Most application code has no consumers beyond the same codebase. Underscore prefixes add noise, make testing harder (signaling "don't call this directly"), and create a false sense of encapsulation.

## Early Returns

Prefer early returns to reduce nesting. Guard clauses at the top, happy path at the bottom.

## Variable Naming

Short, contextually obvious names inside methods (`resp`, `total`, `rows`). Longer names for module-level constants and config fields where context is absent (`DEFAULT_RETRY_DELAY_SECONDS`).

## Method Decomposition

Extract methods when they make the code testable or when logic appears twice. Don't extract every 3-line block into its own method. One-liner checks stay inline.

```python
# good: inline check, not a dedicated method
if cache.get(throttle_key) is not None:
    return

# good: extracted because it's called from two places and is independently testable
def resolve_priority(ticket: Ticket) -> Priority:
    if ticket.is_escalated:
        return Priority.CRITICAL
    for rule in PRIORITY_RULES:
        if rule.matches(ticket):
            return rule.priority
    return Priority.LOW
```

## Boolean Comparisons

When a value is known to be a `bool`, use it directly (`if not user.is_active:`). Only use `is True`/`is False` when the value can also be `None` and `None` is semantically different from `False`.

## Constants at the Top

All module-level constants go at the top of the file, after imports. Never define a constant inline next to the code that uses it.

## No Section Divider Comments

Don't add decorated comment blocks between methods. If the class needs section headers to be readable, it needs fewer methods.

## Logging

Log at decision points and actions, not at every step. Use warnings for unexpected state, info for actions taken. Don't log routine state reads or echo every variable.

## Data Structures First

Get the data shape right before writing logic. The right shape makes downstream code obvious. Define core types early, trace every access pattern, and choose structures that match the dominant paths. A data-structure change late is a rewrite; early, it is a one-line diff. See also `model-the-domain.md` for which structure to reach for when conditionals are the smell.

Use dataclasses when a structure is passed between multiple methods or stored. Don't introduce them for intermediate values within a single method.

## Migrate Callers Then Delete Legacy APIs

When introducing a new internal API, migrate all callers and remove the old API in the same refactor wave. Do not keep legacy paths alive only because internal callers still exist. No compatibility shims, no parallel old-and-new paths waiting for cleanup later.

## Functions Over Methods

Logic that doesn't need `self` should be a module-level function, not a method. This makes it easier to test and reuse. Place helper functions below the class.
