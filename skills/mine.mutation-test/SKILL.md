---
name: mine.mutation-test
description: "Use when the user says: \"mutation test\", \"do my tests actually catch bugs\", or wants to verify test quality. Intentionally breaks code to check if tests catch real bugs. No framework needed."
user-invokable: true
---

# Mutation Testing

Intentionally introduce bugs into source code and verify that tests catch them. Each surviving mutation is a concrete, demonstrable gap in test coverage. Claude-driven — no external framework needed.

## Arguments

$ARGUMENTS — what to mutation-test. Can be:
- A file path: `/mine.mutation-test src/services/payment.py`
- A function name: `/mine.mutation-test calculate_total`
- A module: `/mine.mutation-test src/auth/`
- Empty: auto-detect from git diff or recent test context

## Phase 0: Pre-flight

A clean working tree is the safety net under the safety net. If an Edit-based revert fails, `git checkout -- <file>` must be available.

1. Run `git status` to check for uncommitted changes
2. If the working tree is dirty:

```
AskUserQuestion:
  question: "The working tree has uncommitted changes. Mutation testing needs a clean tree as a safety net for reverting mutations. How should we proceed?"
  header: "Dirty tree"
  multiSelect: false
  options:
    - label: "Stash changes (Recommended)"
      description: "Run git stash, proceed with mutation testing, then git stash pop when done"
    - label: "Commit first"
      description: "Commit the current changes before starting"
    - label: "Proceed anyway"
      description: "Skip the safety net — I'll handle reverting manually if needed"
```

If the user chose stash, run `git stash` and remember to `git stash pop` at the end.

## Phase 1: Target Discovery

### If $ARGUMENTS provided

1. Resolve the target — file path, function, or module
2. Read the target source code
3. Find corresponding test files using Grep and Glob:
   - Check `tests/test_<module>.py`, `tests/<module>/test_*.py`
   - Search for imports of the target module in test files
4. Read the test files to understand what's already covered

### If $ARGUMENTS is empty

1. Check `git diff --name-only HEAD~3` for recently changed source files (exclude test files)
2. If no recent changes, run `git diff --name-only @{upstream}...HEAD 2>/dev/null` to get branch changes (respects non-default PR targets); if that fails (no upstream), fall back to `git-default-branch | xargs -I {} git diff --name-only "origin/{}...HEAD" 2>/dev/null || git-default-branch | xargs -I {} git diff --name-only "{}...HEAD"`
3. If multiple candidates, present them:

```
AskUserQuestion:
  question: "Which file should I mutation-test?"
  header: "Target"
  multiSelect: false
  options:
    - label: "src/services/payment.py (Recommended)"
      description: "Changed in 3 recent commits, has test_payment.py"
    - label: "src/auth/tokens.py"
      description: "Changed in 1 recent commit, has test_tokens.py"
```

4. If a single clear candidate exists, proceed without asking

### Validate test baseline

Before mutating anything, run the relevant tests and confirm they all pass. If tests are already failing, stop:

> Tests are failing before any mutations. Fix the failing tests first — mutation testing requires a green baseline.

## Phase 2: Mutation Planning

Read the target code carefully. Identify mutation points that represent **real bugs a developer might introduce** — not every possible character swap.

### Mutation categories

| Category | Example | Severity |
|----------|---------|----------|
| Guard removal | Delete an `if not user:` early return | Critical |
| Logic flip | `and` to `or`, negate a condition | Critical |
| Exception removal | Remove a `raise ValueError(...)` | Critical |
| Return value | `return True` to `return False`, `return x` to `return None` | High |
| Boundary | `>` to `>=`, `<` to `<=`, `==` to `!=` | High |
| Off-by-one | `range(n)` to `range(n-1)`, `[1:]` to `[2:]` | High |
| Arithmetic | `+` to `-`, `*` to `/` | Medium |
| Constant | Change a string literal, numeric constant | Low |

### What to skip

- Logging statements (`logger.info(...)`, `print(...)`)
- Comments and docstrings
- Debug-only code (`if DEBUG:`, `assert` statements)
- Type annotations
- Imports (removing imports just causes ImportError, not a meaningful test)
- Trivial `__repr__` / `__str__` methods

### Present the plan

After identifying mutation points, present the plan:

```
## Mutation Plan: src/services/payment.py

| # | Line | Category | Mutation |
|---|------|----------|----------|
| 1 | 23 | Guard removal | Remove `if not amount > 0: raise ValueError` |
| 2 | 31 | Logic flip | `and` → `or` in discount eligibility check |
| 3 | 45 | Boundary | `>=` → `>` in minimum order threshold |
| 4 | 52 | Return value | `return total` → `return None` |
| 5 | 67 | Exception removal | Remove `raise InsufficientFunds` |
| 6 | 78 | Arithmetic | `price * quantity` → `price + quantity` |
| 7 | 89 | Off-by-one | `items[1:]` → `items[2:]` |

**7 mutations planned** — running tests/test_payment.py per mutation.
```

```
AskUserQuestion:
  question: "Here's the mutation plan. Proceed with all 7, or narrow the scope?"
  header: "Scope"
  multiSelect: false
  options:
    - label: "Run all 7 (Recommended)"
      description: "Full mutation testing pass"
    - label: "Critical + High only"
      description: "Skip Medium/Low severity — focus on the mutations that matter most"
    - label: "Let me pick"
      description: "I'll choose specific mutations from the list"
```

## Phase 3: Mutation Execution

For each mutation, follow this exact sequence:

### Per-mutation protocol

1. **Record** the exact original code (the `old_string` that will be used to revert)
2. **Apply** the mutation via Edit tool
3. **Run** the relevant test file(s) — not the full suite
4. **Record** the result:
   - **Killed** — at least one test failed (good: the test suite caught the bug)
   - **Survived** — all tests passed (bad: this bug would go undetected)
5. **Revert** immediately via Edit tool (swap `old_string` and `new_string`)
6. **Verify** the revert — the file must match its pre-mutation state

### Safety constraints

- **One mutation at a time** — never apply two mutations simultaneously
- **Always revert before the next mutation** — no exceptions
- **If Edit-based revert fails** — fall back to `git checkout -- <file>`
- **If both fail** — STOP immediately and alert the user. Do not continue.
- **Never leave a mutated file** — verify the revert succeeded before proceeding

### Results tracking

Maintain a running results table:

```
| # | Mutation | Result | Details |
|---|----------|--------|---------|
| 1 | Remove guard (L23) | Killed | test_negative_amount caught it (ValueError) |
| 2 | Logic flip (L31) | Survived | No test checks discount eligibility edge case |
| 3 | Boundary >= → > (L45) | Killed | test_minimum_order caught it |
| ...
```

## Phase 4: Report + Fix

### Present the mutation score

```
## Mutation Testing Results: src/services/payment.py

**Score: 5/7 killed (71%)**

### Killed (tests caught the bug)
| # | Mutation | Caught by |
|---|----------|-----------|
| 1 | Remove guard (L23) | test_negative_amount |
| 3 | Boundary >= → > (L45) | test_minimum_order |
| 4 | Return None (L52) | test_calculate_total_returns_value |
| 5 | Remove raise (L67) | test_insufficient_funds |
| 6 | price * qty → price + qty (L78) | test_multi_item_order |

### Survived (tests missed the bug)
| # | Mutation | Severity | Why it matters |
|---|----------|----------|----------------|
| 2 | `and` → `or` in discount check (L31) | Critical | A logic flip in eligibility could give discounts to ineligible users |
| 7 | `items[1:]` → `items[2:]` (L89) | High | Off-by-one would silently skip the second item in processing |
```

### Ask which survivors to fix

```
AskUserQuestion:
  question: "2 mutations survived — these are gaps in your test coverage. Which should I write tests for?"
  header: "Fix"
  multiSelect: true
  options:
    - label: "Discount logic flip (Recommended)"
      description: "Critical severity — and/or flip could give unauthorized discounts"
    - label: "Off-by-one in item processing"
      description: "High severity — would silently skip items"
    - label: "Skip all"
      description: "I'll address these later"
```

### For each chosen survivor

1. Explain what the mutation changed and why the current tests miss it
2. Write a test (or strengthen an existing one) that would catch the mutation
3. Run the new test to confirm it passes on the **original** code
4. Re-apply the mutation to verify the new test **fails** (kills the mutant)
5. Revert the mutation
6. Confirm the test passes again on the original code

This is a mini TDD cycle: the mutation is the "bug" and the new test is the "fix."

## Phase 5: Summary

```
## Mutation Testing Summary: src/services/payment.py

### Score
- **Before**: 5/7 killed (71%)
- **After**: 7/7 killed (100%)

### Tests added
- `test_discount_ineligible_user` — verifies discount logic rejects users who don't meet all criteria
- `test_process_all_items` — verifies no items are skipped during processing

### Remaining survivors
None — all mutations killed.

### Confidence assessment
The test suite for payment.py now covers guard clauses, boundary conditions, return values, exception paths, and logic branches. The main remaining risk area is integration behavior (payment gateway responses), which mutation testing can't cover — integration tests are needed for that.
```

If the working tree was stashed in Phase 0, run `git stash pop` now.

## What This Skill Does NOT Do

- **Replace integration or E2E tests** — mutation testing validates unit test quality, not system behavior
- **Use external frameworks** (mutmut, cosmic-ray, etc.) — Claude picks semantically meaningful mutations instead of mechanical ones
- **Mutate test code** — only source code is mutated; tests are the judges
- **Fix production bugs** — this finds gaps in test coverage, not bugs in the code itself

## Principles

1. **Semantic over mechanical** — Claude picks mutations that represent real bugs a developer might introduce, not every possible character swap
2. **Always revert** — the codebase must never be left in a mutated state
3. **Targeted test runs** — run only relevant tests per mutation for speed
4. **Interactive** — user chooses scope, confirms plan, picks which survivors to fix
5. **Evidence-based** — every surviving mutation is a concrete, demonstrable gap in test coverage
