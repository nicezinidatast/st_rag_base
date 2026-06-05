"""Phase 1: ChatModel 팩토리 + OpenAIChatModel.achat 단위 테스트.

실제 OpenAI 호출은 하지 않는다(키 불필요). 클라이언트 응답만 가짜로 끼운다.
"""
from __future__ import annotations

from app.clients.chat_model import get_chat_model
from app.clients.openai_client import OpenAIChatModel
from app.core.config import settings


def test_get_chat_model_returns_openai_instance(monkeypatch):
    """팩토리가 "openai:..." 스펙을 OpenAIChatModel 로 빌드하는지."""
    # AsyncOpenAI 는 키 없이는 생성되지 않으므로 더미 키를 주입.
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    model = get_chat_model("openai:gpt-4o-mini")
    assert isinstance(model, OpenAIChatModel)
    assert model.model == "gpt-4o-mini"


async def test_achat_extracts_message_content(monkeypatch):
    """achat 가 OpenAI 응답에서 message.content 를 뽑아 반환하는지."""
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    model = OpenAIChatModel("gpt-4o-mini")

    class _Msg:
        content = "안녕하세요"

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    async def _fake_create(**kwargs):
        return _Resp()

    monkeypatch.setattr(model._client.chat.completions, "create", _fake_create)

    out = await model.achat([{"role": "user", "content": "hi"}])
    assert out == "안녕하세요"


async def test_astream_yields_token_chunks(monkeypatch):
    """astream 이 OpenAI stream 청크의 delta.content 만 골라 yield 하는지."""
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    model = OpenAIChatModel("gpt-4o-mini")

    class _Delta:
        def __init__(self, content):
            self.content = content

    class _Choice:
        def __init__(self, content):
            self.delta = _Delta(content)

    class _Chunk:
        def __init__(self, content):
            self.choices = [_Choice(content)]

    async def _fake_create(**kwargs):
        async def _gen():
            for c in ["안", "녕", None, "!"]:  # None 조각은 건너뛰어야 한다
                yield _Chunk(c)

        return _gen()

    monkeypatch.setattr(model._client.chat.completions, "create", _fake_create)

    tokens = [t async for t in model.astream([{"role": "user", "content": "hi"}])]
    assert tokens == ["안", "녕", "!"]
