# Dependency Injection

## Principle

Functions and classes should **receive** their dependencies, not create or import them inline. If a collaborator is instantiated inside the function that uses it, testing requires `mock.patch` — which is brittle, couples tests to implementation, and obscures what the code actually depends on.

## The Smell

If a test needs `mock.patch` nested more than one level deep, the production code has a DI problem. Fix the code, not the test.

```python
# BAD — hidden dependency, requires patching
def get_user_summary(user_id: int) -> str:
    client = HttpClient()
    resp = client.get(f"/users/{user_id}")
    return format_summary(resp.json())

# test requires: @mock.patch("mymodule.HttpClient")
# and then: mock_client.return_value.get.return_value.json.return_value = {...}
```

```python
# GOOD — dependency is explicit, test passes a fake
def get_user_summary(user_id: int, client: HttpClient) -> str:
    resp = client.get(f"/users/{user_id}")
    return format_summary(resp.json())

# test: get_user_summary(1, FakeHttpClient(responses={...}))
```

## Rules

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

1. **Accept collaborators as parameters.** Clients, repositories, services, configuration — pass them in. Use `None` sentinel defaults for convenience at call sites (`client: HttpClient | None = None` → `client = client or HttpClient()`) — never use mutable or eagerly-constructed default arguments.
2. **One level of `mock.patch` max.** Patching a module-level constant or env var is fine. Patching a return value of a return value is a structural problem.
3. **Prefer protocols/interfaces over concrete types.** Accept `typing.Protocol` or ABC so tests can supply lightweight fakes instead of mocking concrete classes.
4. **Factory functions over inline construction.** When a class needs to build complex collaborators, use a factory or classmethod that wires dependencies — keep `__init__` a simple assignment.
5. **FastAPI: use `Depends()`.** FastAPI's dependency injection system exists for this purpose. Override dependencies in tests via `app.dependency_overrides` rather than patching.

## Where `mock.patch` Is Still Fine

- **Module-level constants** — `@mock.patch("mymodule.API_URL", "http://test")`
- **Time** — `@mock.patch("mymodule.datetime")` or `freezegun`
- **Environment variables** — `@mock.patch.dict(os.environ, ...)`
- **Thin boundary wrappers** that exist solely to be patched (rare — usually a sign the wrapper should accept a parameter instead)

## Refactoring Checklist

When writing new code or modifying existing code:

1. Does this function create any client, connection, or service object? → Accept it as a parameter
2. Does `__init__` call anything beyond simple assignment? → Extract a factory
3. Would testing this require `mock.patch` with `.return_value` chains? → Restructure
4. Does a module-level singleton make testing hard? → Accept it as a parameter with a default
