# Coding Style

## Immutability (CRITICAL)

ALWAYS create new objects, NEVER mutate existing ones. Return new copies with changes, never modify in-place.

**PySpark exception**: PySpark DataFrame reassignment (`df = df.filter(...)`) is the project convention and does not violate this rule — DataFrames are lazy and immutable per transform, so reassigning `df` rebinds the name to a new immutable object.

## File Organization

- 200-400 lines typical, 800 max
- Organize by feature/domain, not by type
- Functions <50 lines, nesting <4 levels
