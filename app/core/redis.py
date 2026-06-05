"""Redis 클라이언트 — 대화 이력(memory.py)과 응답 캐시(cache.py)에서 사용.

[설계]
- 단일 전역 클라이언트를 재사용한다(매 요청 새 연결 금지).
- 짧은 연결 타임아웃: Redis 가 죽어 있을 때 각 op 가 오래 매달리지 않게 한다.
- 가용성 플래그: main.py lifespan 의 ping 으로 1회 확정한다. 미기동이면 memory/cache 가
  매번 연결을 재시도하지 않고 즉시 건너뛴다(요청 지연 0). Redis 를 띄운 뒤엔 재시작하면 반영.
"""
from __future__ import annotations

import redis.asyncio as redis

from app.core.config import settings

redis_client = redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=1.0,  # 미기동 시 빠르게 실패
    socket_timeout=1.0,
)

# 가용성 플래그(기본 True). lifespan ping 이 미기동을 감지하면 False 로 내려
# memory/cache 가 op 를 건너뛴다. 테스트는 lifespan 을 안 거치고 fakeredis 를 쓰므로 True 유지.
_available: bool = True


def set_available(value: bool) -> None:
    global _available
    _available = value


def is_available() -> bool:
    return _available
