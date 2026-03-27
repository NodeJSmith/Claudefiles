# Design: Test Coverage Enforcement in the Caliper v2 Workflow

**Date:** 2026-03-27
**Status:** approved
**Research:** /tmp/claude-mine-design-research-test-coverage/brief.md

## Problem

New code can ship through the caliper v2 pipeline without tests. Three gaps exist:

1. **WPs can defer unit tests to later WPs.** The draft-plan template says "at least one test per WP" but doesn't require unit tests to live in the same WP as the code they cover. A WP can add a new module and say "tests in WP05."
2. **Implementation review doesn't catch cross-WP test gaps.** The spec reviewer already FAILs per-WP on missing tests (`spec-reviewer-prompt.md:29-41`), but the implementation review (item 7) is a soft check that can't catch gaps across WPs — modules added as side effects, integration coverage holes, or overall test adequacy.
3. **mine.ship only checks that existing tests pass.** It never checks whether the diff contains test changes for new code. Ad-hoc work that bypasses the caliper pipeline has no test-presence gate at all.

Additionally, there is no top-level principle in the caliper workflow that says "code ships with its tests." The TDD requirement only appears deep in the execution layer (orchestrate's tdd.md), where it's instruction-based rather than structurally enforced.

## Non-Goals

- Programmatic coverage measurement (pytest-cov, istanbul, etc.) — this is about structural enforcement in skill prompts, not tooling
- Changes to mine.commit-push — it's not a strong enough gate to warrant this check
- Changes to the code-reviewer or integration-reviewer agents — they have different responsibilities
- Blocking ship for caliper-pipeline work that already passed implementation review

## Architecture

### Change 1: Test Co-location Principle in `rules/common/testing.md`

Add a new top-level section after "Coverage: 80%+" that establishes the canonical rule:

```markdown
## Test Co-location

Code and its unit tests ship together. In any repo with test infrastructure, every change that introduces or modifies functional code must include corresponding unit tests in the same commit (or the same WP in the caliper workflow). Integration tests may follow in a subsequent WP, but unit tests may not be deferred.

Exemptions: generated code, pure type definitions, configuration files, constants, `__init__.py` / module init files, documentation-only changes, migrations with no business logic.
```

This is the canonical policy. All downstream skills inherit it via the rules system.

### Change 2: Test Strategy Section in `mine.design` Design Doc Template

Add a `## Test Strategy` section to the design doc template in `skills/mine.design/SKILL.md` Phase 4, between `## Alternatives Considered` and `## Open Questions`:

```markdown
## Test Strategy

[High-level approach to testing this change. Which layers need tests (unit, integration, E2E)? Are there test infrastructure changes needed (new fixtures, test utilities, mock services)? What are the key behaviors that must be verified? For repos with no test infrastructure (e.g., prompt/config repos), state "N/A — no test infrastructure in this repo."]
```

This forces thinking about tests at architecture time, before WPs are generated. When mine.draft-plan runs, it uses this section to inform per-WP test strategies.

**Downstream consumer changes:**
- Add `- **Test Strategy** — high-level testing approach and infrastructure needs` to mine.draft-plan Phase 1's extraction list (`SKILL.md:46-52`) so the WP generator reads this section.
- In mine.draft-plan Phase 3, when writing per-WP Test Strategy sections, reference the design doc's Test Strategy for high-level guidance (test layers, infrastructure needs) while making the WP-level strategy concrete (specific files, functions).

**Freeze-gate note:** Per-WP Test Strategies are authoritative once WPs are written. This design-level section provides initial context for draft-plan and is not updated after plan-review freeze.

### Change 3: Strengthen WP Rules in `mine.draft-plan`

Two changes in `skills/mine.draft-plan/SKILL.md`:

**a) WP ordering rules** (after line 128): Add a unit-test co-location rule.

Replace:
```
- WPs that write integration tests come after the units they test
```

With two explicit rules:
```
- Unit tests must live in the same WP as the code they test — never in a separate WP
- Integration tests may live in a subsequent WP, but that WP must come after all WPs containing the units under test
```

**b) Test Strategy field rules** (line 183): Strengthen from advisory to structural.

Current:
```
- **Test Strategy**: At least one test per WP. Name the file and function. Follow TDD: test first.
```

Replace with:
```
- **Test Strategy**: Required for every WP that introduces or modifies functional code. Must name specific test files and test functions. Follow TDD: write the test first. If the WP's subtasks include code changes, the Test Strategy must include at least one unit test in a named test file. "Tests deferred to a later WP" is only acceptable for integration tests, never for unit tests. WPs that are exempt per the Test Co-location rule in `testing.md` (generated code, pure type definitions, configuration files, constants, module init files, documentation-only changes, migrations with no business logic) may state "N/A — no testable code changes."
```

### Change 4: Upgrade Implementation Review Test Check

In `skills/mine.implementation-review/reviewer-prompt.md`, replace item 7 (lines 63-67).

Current:
```markdown
### 7. Test coverage

Does the test suite actually cover the implementation? Are critical paths tested?

Look for: new modules with no corresponding test file; happy-path-only tests with no edge cases; tests that import code but never assert meaningful state; coverage gaps on error paths or branching logic.
```

Replace with:
```markdown
### 7. Test coverage (CRITICAL)

Does the test suite actually cover the implementation? This is a high-severity check — missing tests for new code should be treated as a CRITICAL finding.

**FAIL-level findings (these MUST be FAIL, not WARN — they are blocking):**
- New module (`.py`, `.ts`, `.js`, etc.) containing public functions or classes with no corresponding test file (excluding generated code and pure type definitions)
- WP Test Strategy names specific tests that don't exist in the codebase
- Core business logic paths with zero test coverage

**WARN-level findings:**
- Happy-path-only tests with no edge cases
- Tests that import code but never assert meaningful state
- Coverage gaps on error paths or branching logic
- Generated code or pure type definitions without tests (acceptable but worth noting)

**Verdict rule:** A FAIL on item 7 (test coverage) always produces REQUEST_FIXES, never APPROVE, regardless of whether the reviewer considers the gap minor.
```

### Change 5: Test-Presence Check in `mine.ship`

In `skills/mine.ship/SKILL.md`, add a new sub-step to Phase 1 step 6 (LOCAL VERIFICATION), between the current sub-step 1 ("Determine the project's test command") and sub-step 2 ("Run the test suite locally").

New sub-step:
```markdown
   2. **TEST PRESENCE CHECK (skip if sub-step 1 found no test command — this signals the repo has no test infrastructure. Also skip for changes exempt per the Test Co-location rule in `testing.md`):**
      Review the branch diff (`git diff --name-only` against the default branch). If the diff contains new or changed source files but zero changes in test files (no files matching common test patterns like `test_*`, `*_test.*`, `*_spec.*`, `__tests__/`), mention this to the user and ask whether to proceed or stop to write tests.
      This is advisory, not a hard block — the user decides.
```

Renumber subsequent sub-steps (current 2→3, 3→4, 4→5).

## Alternatives Considered

### Hard-block in mine.ship

Rejected because mine.ship serves both caliper and ad-hoc workflows. A hard block would be too aggressive for hotfixes, config changes, and other cases where tests genuinely follow in a separate commit. The advisory approach with judgment respects the user's context.

### Programmatic enforcement via spec-helper

Could extend `spec-helper wp-validate` to check that Test Strategy sections are non-empty and contain test file names when subtasks reference code files. Rejected for now — the prompt-level enforcement is sufficient and avoids adding Python logic for content validation. Could be a follow-up if the prompt-level check proves unreliable.

### Add test checking to code-reviewer agent

The code-reviewer focuses on code quality, security, and style. Adding test-presence checking would blur its responsibility. The implementation review is the right place for this — it already has a test coverage item.

## Test Strategy

This change is to markdown skill/rule files in a configuration repo with no test infrastructure. Verification is manual:
- After implementation, run a dry walkthrough of each affected skill with a sample feature to confirm the new language is picked up correctly.
- Verify that mine.draft-plan generates WPs with concrete Test Strategy sections (not deferral language).
- Verify that mine.ship's test-presence check fires when the diff has source changes but zero test file changes.

## Open Questions

None — all questions resolved during design interrogation.

## Impact

**Files changed:**

| File | Change |
|------|--------|
| `rules/common/testing.md` | Add "Test Co-location" section (~5 lines) |
| `skills/mine.design/SKILL.md` | Add `## Test Strategy` to design doc template (~3 lines) |
| `skills/mine.draft-plan/SKILL.md` | Strengthen WP ordering rule + Test Strategy field rule (~8 lines changed) |
| `skills/mine.implementation-review/reviewer-prompt.md` | Replace item 7 with CRITICAL-severity version (~12 lines changed) |
| `skills/mine.ship/SKILL.md` | Add test-presence check sub-step to Phase 1 step 6 (~8 lines added) |

**Blast radius:** Narrow surface, broad behavioral impact. All changes are prompt text in skill/rule files — no code, no dependencies, no infrastructure. However, the changes affect the strictness of automated review gates in the orchestration pipeline, which will change the pass/fail rate of future orchestration runs. This is the intent — stricter enforcement — but is not "zero impact."

**Dependencies:** None.
