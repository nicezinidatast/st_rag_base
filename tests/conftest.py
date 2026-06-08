"""Shared test fixtures."""
from __future__ import annotations

import asyncio

import fakeredis.aioredis
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.core.database as database_module
import app.core.redis as redis_module
from app.core.config import settings
from app.models import Base


@pytest.fixture(autouse=True)
def auth_disabled_by_default(monkeypatch):
    """개발자 .env 의 AUTH_ENABLED 값과 무관하게 테스트는 항상 off 에서 시작.

    인증이 필요한 테스트는 각자 monkeypatch 로 True 를 켠다(ANTHROPIC_API_KEY 와 같은 패턴).
    """
    monkeypatch.setattr(settings, "AUTH_ENABLED", False)


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """모든 테스트에서 Redis 를 in-memory fakeredis 로 대체.

    memory.py/cache.py 는 함수 안에서 `from app.core.redis import redis_client` 하므로
    여기서 모듈 속성을 교체하면 호출 시점에 가짜 클라이언트를 집어온다(라이브 Redis 불필요).
    함수 스코프라 테스트마다 깨끗한 상태로 격리된다.
    """
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(redis_module, "redis_client", fake)
    yield


@pytest.fixture
def sqlite_db(tmp_path, monkeypatch):
    """Postgres 대신 임시 파일 SQLite 로 SessionLocal 을 교체 (Phase 7 인증/영속화 테스트용).

    deps.py/persistence.py 는 호출 시점에 `from app.core.database import SessionLocal`
    하므로 모듈 속성 교체로 충분하다(fake_redis 와 같은 패턴, 라이브 Postgres 불필요).
    NullPool: 커넥션을 풀에 보관하지 않아 pytest 루프 ↔ TestClient 루프 간 공유 문제가 없다.
    """
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'test.db'}", poolclass=NullPool
    )

    async def _create_all() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_all())
    monkeypatch.setattr(
        database_module, "SessionLocal", async_sessionmaker(engine, expire_on_commit=False)
    )
    yield
    asyncio.run(engine.dispose())
