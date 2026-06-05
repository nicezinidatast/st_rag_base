"""Phase 6: 응답 캐시(cache.py) 단위 테스트. fakeredis(conftest autouse) 사용."""
from __future__ import annotations

from app.services import cache


async def test_set_get_roundtrip():
    await cache.set_cached("질문이 있나요?", "네 있습니다")
    assert await cache.get_cached("질문이 있나요?") == "네 있습니다"


async def test_get_miss_returns_none():
    assert await cache.get_cached("캐시에 없는 질문") is None


async def test_normalized_key_hits():
    """공백/대소문자 정규화 후 같은 질문이면 히트."""
    await cache.set_cached("  Hello   World ", "hi")
    assert await cache.get_cached("hello world") == "hi"


async def test_blank_query_is_noop():
    await cache.set_cached("   ", "x")
    assert await cache.get_cached("   ") is None


async def test_empty_answer_not_cached():
    await cache.set_cached("질문", "")
    assert await cache.get_cached("질문") is None
