from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/login")
async def login(username: str, password: str) -> dict[str, str]:
    # TODO: implement real auth
    if username == "admin" and password == "admin":
        return {"token": "fake-jwt-token"}
    raise HTTPException(status_code=401, detail="Invalid credentials")
