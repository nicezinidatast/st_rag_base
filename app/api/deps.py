"""FastAPI 의존성 주입(Depends) 제공자: DB/Redis/Vector/Graph/인증.

[역할] 풀(core/*)에서 커넥션·세션을 꺼내 엔드포인트에 주입. 얇게 유지할 것.

[구현 가이드]
- get_db: SessionLocal() 로 세션 열고 yield, finally 에서 close.
- get_redis/get_vector_db/get_graph_db: 전역 클라이언트(또는 app.state) 반환.
- get_current_user: Authorization 헤더의 토큰을 core.security 로 검증해 주체 복원.
"""
from __future__ import annotations

from typing import AsyncGenerator


async def get_db() -> AsyncGenerator:
    # TODO: async with SessionLocal() as session: yield session
    raise NotImplementedError


async def get_redis():
    # TODO: return redis_client
    raise NotImplementedError


async def get_vector_db():
    # TODO: return get_vector_client()
    raise NotImplementedError


async def get_graph_db():
    # TODO: return get_graph_driver()
    raise NotImplementedError


async def get_current_user():
    # TODO: 토큰 추출 → core.security.decode_access_token → 사용자 조회
    raise NotImplementedError
