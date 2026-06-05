"""Phase 6: 대화 이력(memory.py) 단위 테스트. fakeredis(conftest autouse) 사용."""
from __future__ import annotations

from app.core.config import settings
from app.services import memory


async def test_append_and_get_history():
    await memory.append_message("s1", "user", "안녕")
    await memory.append_message("s1", "assistant", "안녕하세요")
    hist = await memory.get_history("s1")
    assert hist == [
        {"role": "user", "content": "안녕"},
        {"role": "assistant", "content": "안녕하세요"},
    ]


async def test_get_history_empty_session():
    assert await memory.get_history("does-not-exist") == []


async def test_blank_session_is_noop():
    await memory.append_message("", "user", "x")  # 예외 없이 무시
    assert await memory.get_history("") == []


async def test_history_trimmed_to_max(monkeypatch):
    monkeypatch.setattr(settings, "HISTORY_MAX_MESSAGES", 2)
    for i in range(5):
        await memory.append_message("s2", "user", f"m{i}")
    hist = await memory.get_history("s2")
    assert len(hist) == 2
    assert hist[-1]["content"] == "m4"
