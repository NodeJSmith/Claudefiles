# Implementation Reviewer Checklist

You are reviewing a completed caliper plan implementation against the original plan and design doc.

For each checklist item, output: PASS, WARN (minor issue), or FAIL (blocking issue) followed by a one-line note.

## Checklist

### 1. Cross-task boundaries

Did tasks stay within their assigned files? Are there unexpected side effects?

Look for: files modified that weren't in any task's `files` field; changes that bleed across task boundaries (task 2 modifying something task 1 was supposed to own); side effects in unrelated modules.

### 2. Duplication

Were DRY violations introduced across tasks?

Look for: the same logic appearing in multiple files that were worked on separately; helpers that should have been shared but were each copy-pasted into two task outputs; near-identical test setup blocks across test files.

### 3. Dead code

Were unused functions, classes, or unreachable branches added?

Look for: functions defined but never called; imports that are unused; branches that can never be reached given the current code; scaffolding left behind from TDD red phases.

### 4. Documentation

Are public APIs documented? Are existing docstrings still accurate?

Look for: new public functions or classes with no docstring; parameters that changed but docstrings weren't updated; module-level docstrings that describe the old behavior; README or inline comments that are now outdated.

### 5. Error handling

Are all error paths implemented, not just the happy path?

Look for: functions that can raise but callers don't handle; API responses that include error fields but code only checks success; missing validation at system boundaries (user input, external API responses, file I/O); exceptions caught and re-raised without context.

### 6. Integration gaps

Do the tasks wire together correctly? Are there missing glue pieces?

Look for: a function defined in task 2 that task 3 was supposed to call, but the call isn't present; config values that task 1 added but task 4 never reads; module-level registration (adding to `__all__`, registering a handler) that was deferred and forgotten.

### 7. Test coverage

Does the test suite actually cover the implementation? Are critical paths tested?

Look for: new modules with no corresponding test file; happy-path-only tests with no edge cases; tests that import code but never assert meaningful state; coverage gaps on error paths or branching logic.

## Output Format

For each item: `N. <name>: PASS|WARN|FAIL — <one-line note>`

Then:

```
## Verdict: APPROVE | REQUEST_FIXES | ABANDON

### Summary
[2-3 sentences on overall implementation quality and completeness]

### Blocking issues (if any)
- [Issue 1 — which category, which files]
- [Issue 2]

### Suggestions (non-blocking)
- [Suggestion 1]
```

APPROVE: no FAIL ratings; minor WARNs may remain
REQUEST_FIXES: one or more FAIL ratings that can be addressed without re-architecting
ABANDON: fundamental implementation gaps that require starting over or significant plan changes
