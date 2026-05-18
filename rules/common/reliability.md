# Reliability

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->
## Timeouts on External Calls

Every call to an external service — HTTP, database, queue, file I/O over network — must have an explicit timeout. No implicit "wait forever" defaults.

```python
# good: explicit timeout
resp = await client.get("/api/data", timeout=10)

# good: database query timeout
with engine.connect() as conn:
    conn.execute(text("SET statement_timeout = '5s'"))
    result = conn.execute(query)
```

If a library doesn't accept a timeout parameter, wrap it with `asyncio.wait_for` or `asyncio.timeout`.

```python
async with asyncio.timeout(10):
    result = await some_library_call()
```

## Transient vs Permanent Failures

Distinguish transient failures (network blips, rate limits, temporary unavailability) from permanent ones (auth failures, bad requests, missing resources). Only retry transient failures.

```python
TRANSIENT_STATUS_CODES = {429, 502, 503, 504}

async def fetch_with_retry(client: httpx.AsyncClient, url: str) -> httpx.Response:
    for attempt in range(3):
        resp = await client.get(url, timeout=10)
        if resp.status_code not in TRANSIENT_STATUS_CODES:
            return resp
        if attempt < 2:
            await asyncio.sleep(2 ** attempt)
    resp.raise_for_status()
    return resp  # unreachable, satisfies type checker
```

A 400 or 401 will never succeed on retry. Don't waste time retrying them.

## Retry with Backoff

When retrying, use exponential backoff with jitter. Fixed-interval retries amplify thundering herd problems.

```python
import random

async def retry_with_backoff(fn, max_attempts: int = 3):
    for attempt in range(max_attempts):
        try:
            return await fn()
        except TransientError:
            if attempt == max_attempts - 1:
                raise
            delay = (2 ** attempt) + random.uniform(0, 1)
            await asyncio.sleep(delay)
```

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->
## Errors Surfaced Not Swallowed

Every error path should be explicitly handled or propagated. Bare `except: pass` and silent catch-and-ignore hide real failures.

```python
# BAD — swallows everything, including bugs
try:
    sync_inventory(warehouse)
except Exception:
    pass

# GOOD — handle specifically, propagate the rest
try:
    sync_inventory(warehouse)
except StaleDataError:
    logger.warning("Stale data for %s, will retry next cycle", warehouse.id)
except Exception:
    raise
```

When intentionally suppressing an exception, use `contextlib.suppress` with a specific type and make the intent obvious.

```python
# acceptable: explicit, scoped, intentional
with contextlib.suppress(FileNotFoundError):
    path.unlink()
```

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->
## Shared State Protection

Concurrent access to shared mutable state must be protected. Use locks, queues, or atomic operations — not hope.

```python
# good: lock protects shared state
class RateLimiter:
    def __init__(self, max_per_second: int):
        self.max_per_second = max_per_second
        self.tokens = max_per_second
        self.lock = asyncio.Lock()

    async def acquire(self) -> bool:
        async with self.lock:
            if self.tokens > 0:
                self.tokens -= 1
                return True
            return False
```

If you're tempted to skip a lock because "it's probably fine," add the lock.

## Async Awaiting

Every coroutine call must be awaited. Forgetting `await` returns a coroutine object instead of the result — and the operation silently never happens.

```python
# BAD — silently does nothing (returns a coroutine object)
client.post("/webhook", json=payload)

# GOOD
await client.post("/webhook", json=payload)
```

If you intentionally want fire-and-forget, make it explicit with `asyncio.create_task` and handle the result.

## Idempotent Operations

Operations that may be retried (queue consumers, webhook handlers, scheduled tasks) should be idempotent. Use idempotency keys, upserts, or check-before-write patterns.

```python
async def handle_webhook(event: WebhookEvent):
    if await already_processed(event.idempotency_key):
        return
    await process_event(event)
    await mark_processed(event.idempotency_key)
```
