"""PostgreSQL 비동기 SQLAlchemy 엔진/세션 팩토리.

[구현 가이드]
- get_db() 의존성(deps.py)에서 SessionLocal() 로 세션을 열고 yield, finally 에서 close.
- 모델 정의는 app/models/, 스키마 변경은 Alembic(migration/)로.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
