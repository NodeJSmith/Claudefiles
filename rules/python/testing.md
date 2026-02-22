# Python Testing

> This file extends [common/testing.md](../common/testing.md) with Python specific content.

## Framework

Use **pytest** as the testing framework.

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
