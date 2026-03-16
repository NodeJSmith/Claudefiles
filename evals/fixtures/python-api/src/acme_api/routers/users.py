from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from acme_api.db import get_db
from acme_api.models import User
from acme_api.schemas import UserCreate, UserResponse

router = APIRouter()


@router.get("/", response_model=list[UserResponse])
async def list_users(db: Session = Depends(get_db)) -> list[User]:
    return db.query(User).all()


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    user = User(name=payload.name, email=payload.email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
