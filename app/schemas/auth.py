"""인증 엔드포인트 입출력 스키마 (Phase 7)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, examples=["user@example.com"])
    password: str = Field(min_length=8, examples=["s3cret-password"])


class LoginRequest(BaseModel):
    email: str = Field(examples=["user@example.com"])
    password: str = Field(examples=["s3cret-password"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    """비밀번호 해시를 제외한 사용자 공개 정보."""

    id: int
    email: str
    role: str
    is_active: bool
