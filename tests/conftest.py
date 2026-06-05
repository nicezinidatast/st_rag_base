"""Shared test fixtures."""
from __future__ import annotations

import fakeredis.aioredis
import pytest

import app.core.redis as redis_module


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
