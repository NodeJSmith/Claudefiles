---
name: mine.backend-patterns
description: "Use when building or reviewing backend services. Backend architecture patterns, API design, database optimization, and server-side best practices for Python and FastAPI."
user-invocable: false
---

# Backend Development Patterns

Backend architecture patterns and best practices for scalable Python server-side applications.

## API Design Patterns

### RESTful API Structure

```python
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/markets", tags=["markets"])


@router.get("/")
async def list_markets(
    status: str | None = None,
    sort: str = "created_at",
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    ...


@router.get("/{market_id}")
async def get_market(market_id: str) -> dict:
    ...


@router.post("/", status_code=201)
async def create_market(data: CreateMarketRequest) -> dict:
    ...


@router.put("/{market_id}")
async def replace_market(market_id: str, data: CreateMarketRequest) -> dict:
    ...


@router.patch("/{market_id}")
async def update_market(market_id: str, data: UpdateMarketRequest) -> dict:
    ...


@router.delete("/{market_id}", status_code=204)
async def delete_market(market_id: str) -> None:
    ...
```

### Repository Pattern

```python
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class MarketRepository(Protocol):
    async def find_all(self, filters: MarketFilters | None = None) -> list[Market]: ...
    async def find_by_id(self, id: str) -> Market | None: ...
    async def create(self, data: CreateMarketRequest) -> Market: ...
    async def update(self, id: str, data: UpdateMarketRequest) -> Market: ...
    async def delete(self, id: str) -> None: ...


class SqlAlchemyMarketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_all(self, filters: MarketFilters | None = None) -> list[Market]:
        stmt = select(MarketModel)

        if filters and filters.status:
            stmt = stmt.where(MarketModel.status == filters.status)

        if filters and filters.limit:
            stmt = stmt.limit(filters.limit).offset(filters.offset or 0)

        result = await self._session.execute(stmt)
        return [row.to_entity() for row in result.scalars().all()]

    async def find_by_id(self, id: str) -> Market | None:
        result = await self._session.get(MarketModel, id)
        return result.to_entity() if result else None
```

### Service Layer Pattern

```python
class MarketService:
    def __init__(self, repo: MarketRepository) -> None:
        self._repo = repo

    async def search_markets(self, query: str, limit: int = 10) -> list[Market]:
        embedding = await generate_embedding(query)
        results = await self._vector_search(embedding, limit)

        markets = await self._repo.find_by_ids([r.id for r in results])

        score_map = {r.id: r.score for r in results}
        return sorted(markets, key=lambda m: score_map.get(m.id, 0), reverse=True)

    async def _vector_search(self, embedding: list[float], limit: int) -> list[SearchResult]:
        ...


# Wire up with FastAPI dependency injection
async def get_market_service(
    session: AsyncSession = Depends(get_session),
) -> MarketService:
    repo = SqlAlchemyMarketRepository(session)
    return MarketService(repo)


@router.get("/search")
async def search(
    q: str,
    limit: int = 10,
    service: MarketService = Depends(get_market_service),
) -> list[Market]:
    return await service.search_markets(q, limit)
```

### Middleware Pattern

```python
import time

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware


class RequestTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Response-Time"] = f"{elapsed_ms:.1f}ms"
        return response


app = FastAPI()
app.add_middleware(RequestTimingMiddleware)
```

Use `Depends()` for per-request processing (auth, DB sessions, etc.):

```python
from fastapi import Depends, Header, HTTPException


async def verify_api_key(x_api_key: str = Header()) -> str:
    if x_api_key != os.environ["EXPECTED_API_KEY"]:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


@router.get("/internal/stats")
async def stats(_key: str = Depends(verify_api_key)) -> dict:
    ...
```

## Database Patterns

### Query Optimization

```python
from sqlalchemy import select

# Select only needed columns
stmt = (
    select(MarketModel.id, MarketModel.name, MarketModel.status, MarketModel.volume)
    .where(MarketModel.status == "active")
    .order_by(MarketModel.volume.desc())
    .limit(10)
)
result = await session.execute(stmt)
rows = result.all()

# AVOID: loading entire models when you only need a few fields
# stmt = select(MarketModel)  # loads all columns
```

### N+1 Prevention

```python
from sqlalchemy.orm import selectinload, joinedload

# selectinload — issues a second IN query (good for collections)
stmt = (
    select(MarketModel)
    .options(selectinload(MarketModel.positions))
    .where(MarketModel.status == "active")
)

# joinedload — single JOIN query (good for one-to-one / many-to-one)
stmt = (
    select(MarketModel)
    .options(joinedload(MarketModel.creator))
    .where(MarketModel.status == "active")
)

# Batch fetch pattern for manual resolution
markets = await repo.find_all()
creator_ids = {m.creator_id for m in markets}
creators = await user_repo.find_by_ids(list(creator_ids))
creator_map = {c.id: c for c in creators}
```

### Transaction Pattern

```python
from sqlalchemy.ext.asyncio import AsyncSession


async def create_market_with_position(
    session: AsyncSession,
    market_data: CreateMarketRequest,
    position_data: CreatePositionRequest,
) -> Market:
    async with session.begin():
        market = MarketModel(**market_data.model_dump())
        session.add(market)
        await session.flush()  # get market.id before commit

        position = PositionModel(market_id=market.id, **position_data.model_dump())
        session.add(position)

    return market.to_entity()
    # session.begin() commits on success, rolls back on exception
```

## Caching Strategies

### Redis Cache-Aside Pattern

```python
import json

import redis.asyncio as redis

_redis = redis.from_url(os.environ["REDIS_URL"])

CACHE_TTL_SECONDS = 300  # 5 minutes


async def get_market_cached(market_id: str) -> Market | None:
    cache_key = f"market:{market_id}"

    # Try cache first
    cached = await _redis.get(cache_key)
    if cached:
        return Market.model_validate_json(cached)

    # Cache miss — fetch from DB
    market = await repo.find_by_id(market_id)
    if market:
        await _redis.setex(cache_key, CACHE_TTL_SECONDS, market.model_dump_json())

    return market


async def invalidate_market_cache(market_id: str) -> None:
    await _redis.delete(f"market:{market_id}")
```

## Error Handling Patterns

### Centralized Error Handler

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


class NotFoundError(AppError):
    def __init__(self, resource: str, id: str) -> None:
        super().__init__(404, f"{resource} '{id}' not found")


class ConflictError(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(409, detail)


app = FastAPI()


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"},
    )
```

### Retry with Exponential Backoff

```python
from tenacity import retry, stop_after_attempt, wait_exponential


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def call_external_api(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
```

## Background Jobs

### FastAPI BackgroundTasks

```python
from fastapi import BackgroundTasks


async def send_welcome_email(email: str) -> None:
    # Long-running task — runs after the response is sent
    ...


@router.post("/users", status_code=201)
async def create_user(
    data: CreateUserRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    user = await user_service.create(data)
    background_tasks.add_task(send_welcome_email, user.email)
    return {"id": user.id}
```

For heavier workloads, use **Celery** with a Redis or RabbitMQ broker:

```python
from celery import Celery

celery_app = Celery("tasks", broker=os.environ["CELERY_BROKER_URL"])


@celery_app.task
def generate_report(report_id: str) -> None:
    ...


# Dispatch from FastAPI
@router.post("/reports")
async def request_report(data: ReportRequest) -> dict:
    task = generate_report.delay(data.report_id)
    return {"task_id": task.id, "status": "queued"}
```

## Structured Logging

```python
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()


@router.get("/{market_id}")
async def get_market(market_id: str) -> dict:
    log = logger.bind(market_id=market_id)
    log.info("fetching_market")

    market = await repo.find_by_id(market_id)
    if not market:
        log.warning("market_not_found")
        raise NotFoundError("Market", market_id)

    log.info("market_fetched", status=market.status)
    return market.model_dump()
```

## Security

For authentication (JWT), authorization (RBAC), rate limiting, and input validation patterns, see skill: **mine.security-review**.

---

**Remember**: Backend patterns enable scalable, maintainable server-side applications. Choose patterns that fit your complexity level — start simple and add layers only when needed.
