"""Redis 클라이언트 — 대화 이력 메모리(memory.py)와 시맨틱 캐시(cache.py)에서 사용.

[구현 가이드] 단일 전역 클라이언트를 재사용한다(매 요청 새 연결 금지).
시맨틱 캐시는 임베딩 유사도 키, 대화 이력은 list/hash 자료구조 권장.
"""
from __future__ import annotations

import redis.asyncio as redis

from app.core.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
