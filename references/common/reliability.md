# Reliability

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->
## Timeouts on External Calls

Every call to an external service — HTTP, database, queue, file I/O over network — must have an explicit timeout. No implicit "wait forever" defaults.

If a library doesn't accept a timeout parameter, wrap it with `asyncio.wait_for` or `asyncio.timeout`.

```python
async with asyncio.timeout(10):
    result = await some_library_call()
```

## Transient vs Permanent Failures

Distinguish transient failures (network blips, rate limits, 429/502/503/504) from permanent ones (auth failures, bad requests, missing resources). Only retry transient failures — a 400 or 401 will never succeed on retry.

## Retry with Backoff

When retrying, use exponential backoff with jitter. Fixed-interval retries amplify thundering herd problems.

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->
## Errors Surfaced Not Swallowed

Every error path should be explicitly handled or propagated. Bare `except: pass` and silent catch-and-ignore hide real failures — handle the specific exception, propagate the rest.

When intentionally suppressing an exception, use `contextlib.suppress` with a specific type and make the intent obvious.

```python
# acceptable: explicit, scoped, intentional
with contextlib.suppress(FileNotFoundError):
    path.unlink()
```

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->
## Shared State Protection

Concurrent access to shared mutable state must be protected — but first ask whether the actors truly need the same mutable object. If not, eliminate the sharing: give each actor its own owned file, key, or state, and merge only at the read boundary. Two workers writing their own field into one `state.json` is still shared mutation; `worker-a-state.json` + `worker-b-state.json` is not.

When sharing is a real invariant, use locks, queues, or atomic operations — not hope. If you're tempted to skip a lock because "it's probably fine," add the lock.

## Async Awaiting

Every coroutine call must be awaited. Forgetting `await` returns a coroutine object instead of the result — and the operation silently never happens. If you intentionally want fire-and-forget, make it explicit with `asyncio.create_task` and handle the result.

## Idempotent Operations

Operations that may be retried (queue consumers, webhook handlers, scheduled tasks) should be idempotent. Every state-mutating operation should answer three questions: What happens if this runs twice? What if the previous run crashed halfway? Does re-execution converge to the same end state? If any answer is "it depends on what state was left behind," the operation needs a reconciliation step.

Use idempotency keys, upserts, or check-before-write patterns.
