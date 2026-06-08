"""사용자 인증 엔드포인트 (Phase 7).

- POST /register : email+password 가입 (중복 email 은 409)
- POST /token    : 자격증명 검증 → JWT 발급
- GET  /me       : Bearer 토큰의 주체 반환 (AUTH_ENABLED 와 무관하게 항상 토큰 필요)

API 키 발급/회수가 필요해지면 여기에 추가.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter()

DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: DbDep) -> UserOut:
    exists = (
        await db.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="이미 가입된 email 입니다."
        )

    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user, from_attributes=True)


@router.post("/token")
async def login(payload: LoginRequest, db: DbDep) -> TokenResponse:
    user = (
        await db.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="email 또는 비밀번호가 올바르지 않습니다.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="비활성화된 계정입니다."
        )
    return TokenResponse(access_token=create_access_token(user.email))


@router.get("/me")
async def me(user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    return UserOut.model_validate(user, from_attributes=True)
