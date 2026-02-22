# Testing Requirements

## Minimum Test Coverage: 80%

Test Types (ALL required):
1. **Unit Tests** - Individual functions, utilities, components
2. **Integration Tests** - API endpoints, database operations
3. **E2E Tests** - Critical user flows (framework chosen per language)

## Test-Driven Development

MANDATORY workflow:
1. Write test first (RED)
2. Run test - it should FAIL
3. Write minimal implementation (GREEN)
4. Run test - it should PASS
5. Refactor (IMPROVE)
6. Verify coverage (80%+)

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
