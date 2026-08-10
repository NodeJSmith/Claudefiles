# TDD Reference

Reference for the executor subagent. Follow this during every task that involves code changes.

## Canonical Commands

Use the test and lint commands supplied by the orchestrator from `<dir>/test-command.txt` and
`<dir>/lint-command.txt`; do not rediscover or guess alternatives. `no test suite` and
`no lint tools` are canonical skip sentinels: record the corresponding check as `SKIPPED` and
continue. If a required command file is missing, empty, or another command is unrunnable, report
`BLOCKED`.

## Test Co-location

**Unit tests must ship in the same WP as the code they test.** Do not defer unit tests to a later WP. If the WP's Test Strategy names specific tests, those tests must exist when the WP is complete. Integration tests may follow in a subsequent WP.

## TDD Cycle

For every function, class, or behavior change, complete this cycle before moving to the next:

```
1. Write failing test (RED)
   → Run it. Confirm it FAILS with a meaningful error, not a setup error.

2. Write minimal implementation (GREEN)
   → Run the test. It must PASS.
   → Do not add code beyond what makes the test pass.

3. Refactor (IMPROVE)
   → Clean up while keeping the test green.
   → Run the test again. Still passing.
```

Do not skip the RED confirmation. A test that passes before any implementation either:
- Tests something that already existed (not new behavior)
- Has a bug (always returns true, tests the wrong thing)

If the test passes vacuously, fix the test before proceeding.

## Boundary Patterns

When no project test layout is established, follow this default structure:

| What you're testing | Test type | Where it lives |
|---------------------|-----------|----------------|
| Pure function, no I/O | Unit | `tests/unit/` |
| Function with mocked dependencies | Unit | `tests/unit/` |
| Database reads/writes | Integration | `tests/integration/` |
| HTTP API calls | Integration | `tests/integration/` |
| User-visible flows end-to-end | E2E | `tests/e2e/` |

If the project already has a test directory structure, follow existing conventions instead of these defaults.

When in doubt: if the test needs a real database, real HTTP, or real filesystem → integration. Otherwise → unit.

## Failure Modes to Fix (Not Ignore)

- **Test isolation bug**: test passes alone but fails with xdist (`-n auto`) → fix shared state, don't drop to serial
- **Flaky test**: passes sometimes → find the nondeterminism (time, order, randomness) and fix it
- **Fixture leakage**: state from one test bleeds into another → add teardown or use function-scope fixtures
- **Vacuous pass**: test passes before implementation → test is testing the wrong thing; fix it

None of these are acceptable permanent states. Fix them.

## Parallel Execution

Use the orchestrator-supplied canonical test command unchanged. If parallel execution
exposes an isolation bug, fix shared state rather than weakening the test command.
