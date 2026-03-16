from fastapi import FastAPI

from acme_api.routers import users, auth

app = FastAPI(title="Acme API", version="0.1.0")

app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
