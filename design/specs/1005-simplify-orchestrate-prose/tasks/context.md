# Context: Simplify Mine-Orchestrate Prose

## Problem & Motivation

The mine-orchestrate instruction surface repeats contracts and rationale across orchestrator files and composed subagent prompts. The cleanup must lower context and maintenance cost without changing any observable workflow behavior.

## Key Decisions

1. Treat this as instruction refactoring: process behavior is frozen.
2. Give shared contracts a canonical owner and keep call sites limited to invocation-specific details.
3. Preserve necessary repetition across isolated subagent contexts, but remove duplication inside a single composed prompt.
4. Preserve PR #496's content-fingerprint no-op route exactly while expressing the fixer passes once.
5. Use a contract inventory, repository checks, and line-count target to verify equivalence.

## Constraints

- Do not add, remove, reorder, or weaken phases, gates, reviewer passes, retry limits, user choices, state transitions, artifacts, or telemetry.
- Do not alter command syntax, known-issue schema, verdict vocabulary, canonical verdict lines, or sentinel behavior.
- Do not remove instructions solely because another orchestrator file states them when an isolated subagent still needs them in its prompt.
- Do not optimize for line count by creating unreadably long lines or vague references.
- Work with the merged PR #496 version of `findings-fix-loop.md`.
