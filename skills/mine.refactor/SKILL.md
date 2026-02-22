---
name: mine.refactor
description: Interactive code refactoring with strategy selection, dependency analysis, and incremental verification. Uses AskUserQuestion for naming, scope, and approach decisions throughout.
user-invokable: true
---

# Refactor

Interactive, incremental code refactoring. Analyzes the target code, presents strategy options, builds a plan, and executes with tests between each step.

## Arguments

$ARGUMENTS — what to refactor. Can be:
- A file path: `/refactor src/services/user_service.py`
- A function/class name: `/refactor UserManager`
- A smell description: `/refactor "the auth module is doing too much"`
- A specific technique: `/refactor extract-function handle_payment in checkout.py`
- Empty: analyze the most recently edited files for refactoring opportunities

## How to Analyze Code

**Read the code and reason about it directly.** Use the Read tool, Grep, and Glob to examine files. Use Explore subagents to read multiple files in parallel. Do NOT write or execute Python/shell scripts to perform analysis — no AST parsing scripts, no custom complexity calculators, no throwaway code to count imports or detect feature envy. You can read code and identify these patterns yourself.

The only commands to execute during analysis are:
- `git log` / `git diff` — for churn and history data
- `pytest --cov` or equivalent — for actual test coverage numbers
- Project linters (`ruff`, `eslint`) — for existing lint configuration output

Everything else — identifying smells, mapping dependencies, assessing coupling, spotting duplication — comes from reading the files.

## Phase 1: Discover Scope

### If target is specific (file, function, class)

1. Read the target code
2. Identify its dependencies — use Grep to find imports and call sites
3. Measure size (lines, complexity) to gauge effort
4. Check for existing test coverage — this determines how aggressive we can safely be

### If target is vague or empty

1. If empty, check `git diff --name-only HEAD~5` for recently changed files
2. Read candidate files and look for code smells:
   - Functions > 50 lines
   - Files > 400 lines
   - Deep nesting (> 4 levels)
   - God classes / modules doing too many things
   - Duplicated logic across files
   - Long parameter lists
   - Feature envy (function uses another module's data more than its own)
3. Rank findings by impact (how much cleaner the code would be) and risk (how many call sites, how much test coverage)

### Present findings with AskUserQuestion

```
AskUserQuestion:
  question: "I found these refactoring opportunities. Which would you like to tackle?"
  header: "Target"
  multiSelect: false
  options:
    - label: "user_service.py (210 lines)"
      description: "3 functions over 50 lines, low test coverage — split into focused modules"
    - label: "auth.py:handle_login (85 lines)"
      description: "Deep nesting, mixed concerns — extract validation and token logic"
    - label: "models/ duplication"
      description: "serialize_response() duplicated in 4 files — consolidate"
```

## Phase 2: Analyze & Choose Strategy

Once the target is identified, analyze it deeply:

1. **Read the full target code** and all files it touches
2. **Map dependencies**: what imports it, what it imports, where it's called from
3. **Check test coverage**: run tests with coverage on the target file/module
4. **Architecture check**: assess whether the problems are structural (fixable by rearranging code) or architectural (the design itself is wrong)
5. **Identify the applicable refactoring techniques** (see catalogue below)

### Refactor vs. rearchitect

If the code's problems run deeper than structure — e.g., wrong abstraction boundaries, missing layers, responsibilities that belong in a different part of the system — surface this before presenting strategies:

```
AskUserQuestion:
  question: "The auth module mixes HTTP handling, business logic, and data access in one layer. Refactoring can clean up the long functions, but the tangling will come back without a proper separation of concerns. How would you like to proceed?"
  header: "Approach"
  multiSelect: false
  options:
    - label: "Refactor now (Recommended)"
      description: "Improve structure within the current design. Practical, lower risk, shippable today."
    - label: "Rearchitect"
      description: "Redesign with proper layer separation. Bigger scope — will use /mine.adrs to plan it."
    - label: "Refactor now, plan rearchitecture"
      description: "Do the quick structural win, then create an ADR capturing the longer-term design."
    - label: "Create an issue"
      description: "File a GitHub issue capturing the architectural concern — come back to it later."
```

If the user chooses **Rearchitect**, hand off to `/mine.adrs` to record the decision and then plan the larger change — that's outside this skill's scope. If they choose **Refactor now, plan rearchitecture**, complete the refactoring first, then create the ADR at the end as a follow-up artifact. If they choose **Create an issue**, file it with `gh issue create` (include the analysis as the body), confirm the URL, and continue with a structural refactor within the current design.

If no architectural concerns exist, skip this question and go straight to strategy.

### Present strategy with AskUserQuestion

Always present at least 2 approaches — a conservative one and a more thorough one.

```
AskUserQuestion:
  question: "How would you like to refactor auth.py:handle_login (85 lines)?"
  header: "Strategy"
  multiSelect: false
  options:
    - label: "Extract functions (Recommended)"
      description: "Pull validation, token creation, and audit logging into separate functions in the same file. Low risk, keeps the public API identical."
    - label: "Extract module"
      description: "Move auth helpers into auth_helpers.py. Cleaner separation but changes import paths at 12 call sites."
    - label: "Decompose class"
      description: "Split AuthManager into AuthValidator + TokenService + AuditLogger. Most thorough but highest churn."
```

### Naming decisions

When the chosen strategy requires new names (functions, files, classes, variables), **always ask**:

```
AskUserQuestion:
  question: "What should the extracted validation function be called?"
  header: "Naming"
  multiSelect: false
  options:
    - label: "validate_login_request (Recommended)"
      description: "Matches existing naming convention in the codebase"
    - label: "check_credentials"
      description: "Shorter, but less specific"
```

Names are one of the hardest parts of refactoring and the user knows their domain best. Don't guess — ask.

## Phase 3: Plan

**Enter plan mode** using the `EnterPlanMode` tool.

### Build the plan

For the chosen strategy, write a step-by-step plan where each step is:
1. A single, atomic edit (one function extracted, one file split, one rename)
2. Independently testable — tests should pass after each step, not just at the end
3. Reversible — if a step breaks something, we can revert just that step

### Plan format

```markdown
## Refactor Plan: [target] — [strategy]

### Pre-flight
- [ ] All tests currently passing
- [ ] No uncommitted changes (or stash first)

### Step 1: Extract validate_login_request()
- **File**: src/auth.py
- **Action**: Extract lines 15-42 into `validate_login_request(username, password) -> LoginCredentials`
- **Call sites**: Update handle_login() to call the new function
- **Tests**: Existing tests should pass unchanged (same public API)
- **New tests**: Add unit test for validate_login_request() edge cases

### Step 2: Extract create_auth_token()
- **File**: src/auth.py
- **Action**: Extract lines 55-78 into `create_auth_token(user: User) -> str`
- **Call sites**: Update handle_login() to call the new function
- **Tests**: Existing tests should pass unchanged

### Step 3: Simplify handle_login()
- **File**: src/auth.py
- **Action**: handle_login() is now a thin orchestrator calling the extracted functions
- **Verify**: Function is under 20 lines, reads top-to-bottom

### Post-flight
- [ ] All tests passing
- [ ] Coverage same or improved
- [ ] No new linting warnings
```

Use `ExitPlanMode` to present for user approval.

### Handle scope change

If during planning you discover the refactoring is bigger than expected (e.g., a rename touches 30 files), pause and ask:

```
AskUserQuestion:
  question: "This rename affects 30 files across 4 modules. How would you like to scope it?"
  header: "Scope"
  multiSelect: false
  options:
    - label: "Full rename (Recommended)"
      description: "Rename everywhere for consistency. I'll do it in one atomic step."
    - label: "Partial — this module only"
      description: "Rename in src/auth/ only, add a re-export alias for other modules"
    - label: "Abort rename"
      description: "Keep the old name, continue with other refactoring steps"
```

## Phase 4: Execute

Apply the plan step by step. **Mechanical fixes** (updating import paths, adjusting test helpers to match moved code, fixing linter complaints) should be done automatically — don't ask the user about obvious cascading changes. Reserve AskUserQuestion for genuine ambiguity.

After EACH step:

1. **Apply the edit(s)** for that step
2. **Run tests** — fix mechanical breakage (updated imports, adjusted paths) automatically. Only ask the user when a failure reveals an **actual ambiguity**:
   ```
   AskUserQuestion:
     question: "Tests failed after extracting validate_login_request(). test_handle_login_empty_password now fails — the original function was silently returning None for empty passwords, but the extracted version raises ValueError. This looks like a latent bug. How should I handle it?"
     header: "Test failure"
     multiSelect: false
     options:
       - label: "Keep the ValueError (Recommended)"
         description: "The new behavior is safer. Update the test to expect the exception."
       - label: "Preserve the old behavior"
         description: "Match the original — return None for empty passwords. Fix the bug separately."
       - label: "Revert this step"
         description: "Undo the extraction and move on to the next step"
   ```
3. **Run linter/formatter** if configured (ruff, eslint, etc.)
4. Move to next step

### During execution — stay interactive

If you encounter something unexpected (circular import, surprising coupling, test you didn't anticipate), **ask rather than assume**:

```
AskUserQuestion:
  question: "Extracting this function creates a circular import between auth.py and users.py. How should I resolve it?"
  header: "Circular import"
  multiSelect: false
  options:
    - label: "Create a shared types module (Recommended)"
      description: "Move the shared types to a types.py that both modules import"
    - label: "Use TYPE_CHECKING guard"
      description: "Import only for type checking, not at runtime"
    - label: "Skip this extraction"
      description: "Leave the function where it is"
```

## Phase 5: Verify & Summarize

After all steps are complete:

1. **Run full test suite** — not just the files we touched
2. **Run linter** on all modified files
3. **Compare before/after**:
   - Lines of code (target file)
   - Max function length
   - Nesting depth
   - Number of responsibilities per module

### Present summary

```
## Refactor Complete: auth.py — Extract Functions

### Changes
- Extracted validate_login_request() (28 lines) from handle_login()
- Extracted create_auth_token() (24 lines) from handle_login()
- handle_login() reduced from 85 → 18 lines

### Files Modified
- src/auth.py — restructured
- tests/test_auth.py — added 4 tests for extracted functions

### Metrics
- Max function length: 85 → 28 lines
- Test coverage: 72% → 89%
- All 47 tests passing

### What I didn't touch
- Token refresh logic (lines 90-140) — works fine as-is
- The AuthManager class — handle_login was the only oversized method
```

## Refactoring Catalogue

Reference for identifying which technique applies:

| Smell | Technique | Risk |
|-------|-----------|------|
| Long function (> 50 lines) | Extract function | Low |
| Long file (> 400 lines) | Extract module / split file | Medium |
| Deep nesting (> 4 levels) | Early returns, extract conditions | Low |
| Duplicated logic | Extract shared function/utility | Low-Medium |
| God class (too many responsibilities) | Split into focused classes | Medium-High |
| Long parameter list (> 4 params) | Introduce parameter object / dataclass | Low |
| Feature envy | Move function to the class it envies | Medium |
| Primitive obsession | Introduce value objects | Medium |
| Shotgun surgery (1 change = many files) | Consolidate related logic | Medium |
| Middle man (class just delegates) | Inline / remove wrapper | Low |
| Data clump (same group of params everywhere) | Extract dataclass / NamedTuple | Low |
| Divergent change (1 file, many reasons to change) | Split by responsibility | Medium |

## What This Skill Does NOT Do

- **Dead code removal** — not in scope for this skill
- **Major architecture changes** — use `/mine.adrs` to decide, then this skill to execute
- **Performance optimization** — refactoring is about structure, not speed
- **Rewriting from scratch** — incremental improvement, not replacement

## Principles

1. **Tests are the safety net** — never refactor without them. If coverage is low, write tests first.
2. **Small steps** — each step should independently leave the code in a working state.
3. **Same behavior** — refactoring changes structure, not behavior. If behavior needs to change, that's a separate task.
4. **Ask, don't guess** — names, scope, and strategy are user decisions. Present options, don't assume.
5. **Know when to stop** — not every smell needs fixing. Refactor what's in the way, leave the rest.
