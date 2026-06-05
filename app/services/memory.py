"""Redis 기반 대화 히스토리 관리 (Phase 6).

세션(session_id)별 메시지 목록을 Redis 리스트로 저장/조회한다.
- 키: chat:history:{session_id}, 각 원소 = JSON {"role","content"}.
- 최근 HISTORY_MAX_MESSAGES 개만 유지(LTRIM) + TTL 갱신.
- Redis 가 없거나 죽어도 채팅을 막지 않는다(append=no-op, get=[]).
  vector 검색 실패와 동일한 비치명 정책.
"""
from __future__ import annotations

import json

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _key(session_id: str) -> str:
    return f"chat:history:{session_id}"


async def append_message(session_id: str, role: str, content: str) -> None:
    """세션 이력 끝에 메시지 1건 추가 + 최근 N개로 trim + TTL 갱신."""
    if not session_id:
        return
    from app.core import redis as _redis

    if not _redis.is_available():
        return
    redis_client = _redis.redis_client

    try:
        key = _key(session_id)
        await redis_client.rpush(
            key, json.dumps({"role": role, "content": content}, ensure_ascii=False)
        )
        await redis_client.ltrim(key, -settings.HISTORY_MAX_MESSAGES, -1)
        await redis_client.expire(key, settings.HISTORY_TTL_SECONDS)
    except Exception as e:  # noqa: BLE001  메모리 실패는 비치명 → 채팅 계속
        logger.warning("memory_append_skipped", error=str(e))


async def get_history(session_id: str, limit: int | None = None) -> list[dict]:
    """세션의 최근 메시지 목록을 [{"role","content"}, ...] 로 반환(오래된→최신)."""
    if not session_id:
        return []
    from app.core import redis as _redis

    if not _redis.is_available():
        return []
    redis_client = _redis.redis_client

    n = limit or settings.HISTORY_MAX_MESSAGES
    try:
        raw = await redis_client.lrange(_key(session_id), -n, -1)
    except Exception as e:  # noqa: BLE001
        logger.warning("memory_get_skipped", error=str(e))
        return []

    history: list[dict] = []
    for item in raw:
        try:
            history.append(json.loads(item))
        except (json.JSONDecodeError, TypeError):
            continue
    return history
