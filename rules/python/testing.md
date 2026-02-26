# Python Testing

> This file extends [common/testing.md](../common/testing.md) with Python specific content.

## Framework

Use **pytest** as the testing framework.

## Test Execution Discovery

**NEVER run tests blindly.** Before executing `pytest` or `uv run pytest`, check how the project is configured to run tests. Running tests incorrectly leads to false positives (missing dependencies, wrong scope, incorrect environment).

### Discovery Order

1. **Project-specific guidance** — CLAUDE.md
   - Check for "Test Execution" or "Testing" section in CLAUDE.md
   - If documented there, use that command (skip further discovery)

2. **CI configuration** — the source of truth for how tests should run
   - `.github/workflows/*.yml` → check `pytest` commands in workflow steps
   - `.gitlab-ci.yml`, `azure-pipelines.yml`, etc.
   - Look for test matrix configurations (multiple Python versions, different environments)

3. **Task runners** — project-specific test orchestration
   - `noxfile.py` → check session names and pytest invocations (`nox -s test`)
   - `tox.ini` → check test environment commands (`tox -e py311`)
   - `Makefile` → check test targets (`make test`)
   - `pyproject.toml` → `[tool.pytest.ini_options]` or script definitions

4. **Project documentation** — README, CONTRIBUTING, docs/
   - May specify exact commands or prerequisites

5. **Ask user** — if no configuration found in steps 1-4
   - Use AskUserQuestion to ask how tests should be run
   - Store answer in CLAUDE.md "Test Execution" section
   - This prevents asking again in future sessions

6. **Fallback** — only if user doesn't know
   - Check for virtual environment activation needed
   - Use `pytest` or `uv run pytest` as last resort

### Examples

**Good** — checked CI first, found command in .github/workflows/test.yml:
```bash
nox -s test
```

**Good** — no CI file, found noxfile.py with session named "tests":
```bash
nox -s tests
```

**Good** — no CI or task runners, project uses uv (from uv.lock):
```bash
uv run pytest -n auto --cov=src --cov-report=term-missing
```

**Bad** — saw uv.lock and ran tests without checking for noxfile.py:
```bash
uv run pytest  # missed that noxfile.py exists and CI uses nox
```

**Bad** — running blindly without ANY discovery:
```bash
pytest  # might be missing deps, wrong env, or wrong scope
```

### Common Patterns

**IMPORTANT**: The presence of a package manager (uv, poetry) does NOT mean you skip discovery. Always follow the discovery order above.

**Example**: A project using uv for dependencies might still use nox for tests:
- ❌ Wrong: "I see uv.lock, so I'll run `uv run pytest`"
- ✅ Right: "I see uv.lock AND noxfile.py. Check noxfile.py first → use `nox -s test`"

**Fallback commands** (only when no CI/task runner found):

| Tool Found | Command | When to Use |
|------------|---------|-------------|
| noxfile.py | `nox -s test` (or check session names) | Task runner - use this first |
| tox.ini | `tox -e py311` (or check env names) | Task runner - use this first |
| Makefile | `make test` (or check target name) | Task runner - use this first |
| uv.lock | `uv run pytest` | Package manager fallback only |
| poetry.lock | `poetry run pytest` | Package manager fallback only |
| Plain venv | activate venv, then `pytest` | Manual fallback only |

## Parallel Execution (xdist)

**Use pytest-xdist by default.** Do NOT run tests serially when the test suite is non-trivial.

Rules of thumb:
- **50+ tests** → use `-n auto` (let xdist pick worker count)
- **< 50 tests** → serial is fine
- **Single test file or debugging** → serial is fine

```bash
# Default for full suite
pytest -n auto

# With coverage
pytest -n auto --cov=src --cov-report=term-missing

# Serial only when needed (debugging, <50 tests, or known isolation issues)
pytest tests/test_specific.py
```

If tests fail under xdist but pass serially, that's a **test isolation bug** — fix it, don't drop back to serial permanently.

## Coverage

```bash
pytest -n auto --cov=src --cov-report=term-missing
```

## Test Organization

Use `pytest.mark` for test categorization:

```python
import pytest

@pytest.mark.unit
def test_calculate_total():
    ...

@pytest.mark.integration
def test_database_connection():
    ...
```

## Reference

See skill: `mine.python-testing` for detailed pytest patterns and fixtures.
