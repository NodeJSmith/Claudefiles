# Testing Requirements

## Minimum Test Coverage: 80%

Test Types (ALL required):
1. **Unit Tests** - Individual functions, utilities, components
2. **Integration Tests** - API endpoints, database operations
3. **E2E Tests** - Critical user flows (framework chosen per language)

## Test-Driven Development

### Anti-Pattern: Horizontal Slicing

DO NOT write all tests first, then all implementation. This is "horizontal slicing" and produces bad tests that verify imagined behavior instead of actual behavior.

```
WRONG (horizontal):
  RED:   test1, test2, test3, test4, test5
  GREEN: impl1, impl2, impl3, impl4, impl5

RIGHT (vertical):
  RED→GREEN: test1→impl1
  RED→GREEN: test2→impl2
  RED→GREEN: test3→impl3
```

### Workflow

1. **Plan** — Confirm which behaviors to test with the user. You can't test everything. Identify the behaviors that matter most.
2. **Tracer bullet** — Write ONE test for ONE behavior. Run it (RED). Write minimal code to pass (GREEN). This proves the path works.
3. **Incremental loop** — For each remaining behavior: write one test (RED), implement just enough to pass (GREEN). One test at a time. Only enough code to pass the current test. Do not anticipate future tests.
4. **Refactor** — Only after all tests pass. Never refactor while RED.
5. **Verify coverage** (80%+)

### Per-Cycle Checklist

After each RED→GREEN cycle, verify:
- [ ] Test describes behavior, not implementation
- [ ] Test uses public interface only
- [ ] Test would survive an internal refactor
- [ ] Code is minimal for this test
- [ ] No speculative features added

### Mocking

Mock only at system boundaries:
- External APIs, databases, time, filesystem — mock these
- Your own classes and internal collaborators — prefer real instances. Mock only when they wrap a system boundary (e.g., an email sender, a file writer) or require expensive setup
- Use dependency injection for testability
- Prefer SDK-style interfaces over generic fetchers

## Test Execution

**NEVER run tests without understanding how the project expects them to run.** Running tests with the wrong command, environment, or dependencies leads to false positives that waste time and break trust in the test suite.

### Discovery Process

Before executing tests:

1. **Check project-specific guidance** - CLAUDE.md
   - Look for "Test Execution" or "Testing" section
   - If documented, use that command (skip further discovery)

2. **Check CI configuration** - the authoritative source
   - `.github/workflows/`, `.gitlab-ci.yml`, CI pipeline files
   - Use the exact commands CI uses

3. **Check task runners and build tools**
   - Project-specific orchestration (language-dependent)
   - May handle environment setup, dependencies, and isolation

4. **Check documentation**
   - README, CONTRIBUTING, or docs/ may specify test commands

5. **Ask the user** - if no configuration found
   - Use AskUserQuestion to ask how tests should be run
   - Store the answer in CLAUDE.md to prevent asking again
   - This creates project-specific guidance for future sessions

6. **Fallback carefully** - only if user doesn't know
   - Only use default test commands if no other information available
   - Verify environment setup requirements first

### Why This Matters

- **Environment mismatch**: Missing dependencies, wrong Python version, incorrect env vars
- **Scope mismatch**: CI might run only unit tests, or specific test markers
- **Isolation issues**: Task runners may provide test isolation that raw commands don't
- **False confidence**: Passing tests locally that fail in CI (or vice versa)

**Golden rule**: If CI uses a specific command, you should too.

## Handling Test Failures

**Default stance: YOU OWN IT.** When tests fail, your job is to fix them — not explain why they're not your problem.

### What NOT to do

- Do NOT dismiss failures as "pre-existing" or "unrelated to my changes"
- Do NOT say "this was already failing before I started"
- Do NOT skip failing tests or mark them as expected failures
- Do NOT move on and leave tests broken

### What to do

1. **Investigate the failure** — read the error, understand what the test expects
2. **Determine the cause** — is it your change, a flaky test, or a genuine pre-existing bug?
3. **Fix it regardless** — even if you didn't cause it, fix it or flag it explicitly:
   - If your change broke it → fix your change or update the test
   - If the test is wrong → fix the test and explain why
   - If it's a pre-existing bug → fix the bug (you found it, you own it)
   - If it's flaky/environment-specific → fix the flakiness, don't ignore it
4. **Only escalate to the user** if the fix is genuinely out of scope (e.g., requires infrastructure changes, external service is down, or fixing it would be a major unrelated refactor)

### Debugging steps

1. Check test isolation
2. Verify mocks are correct
3. Fix implementation, not tests (unless tests are wrong)
4. Track non-trivial failures in the error file (see error-tracking rules)
