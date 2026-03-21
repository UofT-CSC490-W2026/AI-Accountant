from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.db.dao import UserDAO

router = APIRouter(prefix="/users", tags=["users"])


class UserCreateRequest(BaseModel):
    email: EmailStr
    password_hash: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("/", response_model=UserResponse, status_code=201)
def create_user(payload: UserCreateRequest, db: Session = Depends(get_db)) -> UserResponse:
    existing = UserDAO.get_by_email(db, payload.email)
    if existing is not None:
        raise HTTPException(status_code=409, detail="user already exists")
    user = UserDAO.create(db, payload.email, payload.password_hash)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: uuid.UUID, db: Session = Depends(get_db)) -> UserResponse:
    user = UserDAO.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return UserResponse.model_validate(user)


@router.get("/by-email/{email}", response_model=UserResponse)
def get_user_by_email(email: EmailStr, db: Session = Depends(get_db)) -> UserResponse:
    user = UserDAO.get_by_email(db, str(email))
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return UserResponse.model_validate(user)
