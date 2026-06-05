"""FastAPI 의존성 주입(Depends) 제공자: DB/Redis/Vector/Graph/인증.

[역할] 풀(core/*)에서 커넥션·세션을 꺼내 엔드포인트에 주입. 얇게 유지할 것.

[인증 의존성 두 가지 — Phase 7]
- get_current_user      : 항상 강제. 토큰 없거나 무효면 401. (/auth/me 등 인증 전용)
- get_optional_user     : AUTH_ENABLED=false 면 검사 없이 None 반환(기존 동작 유지),
                          true 면 get_current_user 와 동일하게 강제. (chat/document 용)
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_access_token
from app.models.user import User

# auto_error=False: 토큰이 없을 때 403 자동 응답 대신 None 을 받아 직접 401 을 던진다.
_bearer = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    from app.core.database import SessionLocal

    async with SessionLocal() as session:
        yield session


async def get_redis():
    # TODO: return redis_client
    raise NotImplementedError


async def get_vector_db():
    # TODO: return get_vector_client()
    raise NotImplementedError


async def get_graph_db():
    # TODO: return get_graph_driver()
    raise NotImplementedError


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Authorization: Bearer <token> 을 검증해 활성 사용자를 복원. 실패 시 401."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="유효한 인증 토큰이 필요합니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError:
        raise unauthorized from None

    email = payload.get("sub")
    if not email:
        raise unauthorized
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise unauthorized
    return user


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    """AUTH_ENABLED 토글형 인증. off 면 None(기존 무인증 동작), on 이면 강제.

    off 일 때도 get_db 가 걸려 있지만 SQLAlchemy 세션은 lazy 라
    실제 쿼리 전에는 DB 연결을 만들지 않는다(Postgres 미기동이어도 무해).
    """
    if not settings.AUTH_ENABLED:
        return None
    return await get_current_user(credentials, db)
