"""Redis 기반 시맨틱 캐싱.

[구현 가이드] 쿼리 임베딩 유사도가 임계치 이상이면 캐시된 답변 반환(LLM 호출 절약).
키 설계/TTL/유사도 임계치를 신중히. core/redis.redis_client 사용.
"""
from __future__ import annotations


async def get_cached(query: str) -> str | None:
    raise NotImplementedError


async def set_cached(query: str, answer: str, ttl: int = 3600) -> None:
    raise NotImplementedError
