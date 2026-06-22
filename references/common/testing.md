# Testing

## Coverage: 80%+

Unit, integration, and E2E tests all required.

## Test Co-location

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

Code and its unit tests ship together. In any repo with test infrastructure, every change that introduces or modifies functional code must include corresponding unit tests in the same commit (or the same WP in the caliper workflow). Integration tests may follow in a subsequent WP, but unit tests may not be deferred.

Exemptions: generated code, pure type definitions, configuration files, constants, `__init__.py` / module init files, documentation-only changes, migrations with no business logic.

<!-- SYNC: This exemption list is inlined in skills/mine-implementation-review/reviewer-prompt.md (item 7 FAIL criteria). Update both when changing. skills/mine-plan/SKILL.md and skills/mine-ship/SKILL.md reference this list by name. -->

## Test-Driven Development

### Anti-Pattern: Horizontal Slicing

DO NOT write all tests first, then all implementation. One test at a time:

```
WRONG:  RED: test1,test2,test3 → GREEN: impl1,impl2,impl3
RIGHT:  RED→GREEN: test1→impl1 → RED→GREEN: test2→impl2
```

### Workflow

1. **Plan** — confirm which behaviors to test with the user
2. **Tracer bullet** — ONE test, RED, minimal code to GREEN
3. **Incremental loop** — one test at a time, only enough code to pass
4. **Refactor** — only after all tests pass. Never refactor while RED
5. **Verify coverage** (80%+)

### Mocking

<!-- SYNC: rules/common/invariants.md and references/common/dependency-injection.md — update both when changing this rule. -->

Mock only at system boundaries (external APIs, databases, time, filesystem). Prefer real instances for internal collaborators. Structure code for dependency injection so tests can supply fakes directly — see `references/common/dependency-injection.md` for the full rule.

### Avoid Log Capture Tests

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

Do not write tests that assert on log output (e.g., `caplog`, `capfd`, checking `logger.warning` was called). These tests are brittle — they break when log messages are reworded, reformatted, or when log levels change. Test the *behavior* that produces the log, not the log itself.

## Pytest on Resource-Constrained Machines

On low-RAM, small-CPU machines (e.g., the laptop), avoid `-n auto` — it spawns one worker per core, and overlapping or leaked parallel runs can fill swap and freeze the box. Pin a small worker count instead (e.g., `-n 2`) to cap the blast radius.

## Test Execution

**NEVER run tests without understanding how the project expects them to run.**

### Discovery Order

1. **CLAUDE.md** — "Test Execution" section; if found, use that command
2. **CI configuration** — `.github/workflows/`, `.gitlab-ci.yml`; use CI's exact commands
3. **Task runners** — `noxfile.py`, `tox.ini`, `Makefile`, `pyproject.toml` scripts
4. **Documentation** — README, CONTRIBUTING
5. **Ask the user** — store answer in CLAUDE.md
6. **Fallback** — `pytest` or equivalent as last resort

**Golden rule**: If CI uses a specific command, you should too.

## Handling Test Failures

**YOU OWN IT.** Fix all test failures — even pre-existing ones. Do not dismiss, skip, or move on.

Only escalate if genuinely out of scope (infrastructure changes, external services down).

**Retry limit:** 3 attempts, then present failures to the user.
