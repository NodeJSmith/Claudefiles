# Coding Style

## Immutability (CRITICAL)

ALWAYS create new objects, NEVER mutate existing ones. Return new copies with changes, never modify in-place.

## File Organization

- 200-400 lines typical, 800 max
- Organize by feature/domain, not by type
- Functions <50 lines, nesting <4 levels
