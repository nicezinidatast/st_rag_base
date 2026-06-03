"""Redis 기반 응답 캐시 (Phase 6).

[현재 — 완전일치 MVP]
정규화한 질문 텍스트의 해시를 키로 답변을 캐싱한다 → 같은 질문 재호출 시 LLM 을 건너뛴다.
- 키: chat:cache:{sha256(normalized_query)}, 값 = 답변 문자열, TTL.
- Redis 가 없거나 죽어도 비치명(get=None=미스, set=no-op).

[후속 — 진짜 "시맨틱" 캐시]
임베딩 유사도 ≥ 임계치 매칭은 RediSearch 벡터 인덱스(or O(n) 스캔)가 필요해 미룬다.
지금은 완전일치(같은 질문)만 히트한다.

[주의] 질문 텍스트만으로 캐시하므로 멀티턴 맥락은 반영하지 않는다(히트 시 citations 없음).
"""
from __future__ import annotations

import hashlib
from typing import cast

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _key(query: str) -> str:
    norm = " ".join(query.strip().lower().split())
    digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()
    return f"chat:cache:{digest}"


async def get_cached(query: str) -> str | None:
    """질문에 대한 캐시된 답변. 미스/오류면 None."""
    if not query.strip():
        return None
    from app.core import redis as _redis

    if not _redis.is_available():
        return None

    try:
        # decode_responses=True 라 str 이 온다(redis 타입 스텁은 bytes|str 로 봄).
        return cast("str | None", await _redis.redis_client.get(_key(query)))
    except Exception as e:  # noqa: BLE001  캐시 실패는 비치명 → 정상 생성 경로로
        logger.warning("cache_get_skipped", error=str(e))
        return None


async def set_cached(query: str, answer: str, ttl: int | None = None) -> None:
    """질문→답변을 TTL 과 함께 캐싱."""
    if not query.strip() or not answer:
        return
    from app.core import redis as _redis

    if not _redis.is_available():
        return

    try:
        await _redis.redis_client.set(_key(query), answer, ex=ttl or settings.CACHE_TTL_SECONDS)
    except Exception as e:  # noqa: BLE001
        logger.warning("cache_set_skipped", error=str(e))
