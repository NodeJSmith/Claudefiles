# Decomposition Discipline

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

Before implementing a feature, answer four decomposition questions. A dimension that genuinely does not apply keeps its entry with a brief reason rather than being silently dropped.

## The Four Questions

1. **Blocking first steps.** What gates must run before any parallel work begins? Shared types, schema migrations, CI setup, and foundational data structures are blockers. Sequence them first.

2. **Independent workstreams.** Which slices touch disjoint files, services, or layers and can proceed in parallel? Which share write targets and must serialize? Parallel work on shared files is not parallelism; it is a merge conflict.

3. **Shared mutable state.** Do any workstreams write to the same file, branch, key, or state object? Default to splitting the target so each workstream owns its output. Serialize structurally (locks, sequential phases, exclusive ownership) only when one shared write target is a real invariant. See `reliability.md`.

4. **Smallest safe decomposition.** Can this be split into smaller independently-landable units? If one worker is best, name why. If multiple workers make sense, each gets a specific scope (file paths, named data shape, success criteria).

## When to Write It

Any feature that touches more than one module or has a non-trivial implementation path. Skip for single-file changes where the decomposition is obvious.

