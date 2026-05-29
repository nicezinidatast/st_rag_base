"""AnthropicChatModel 단위 테스트. 실제 Anthropic 호출은 하지 않는다."""
from __future__ import annotations

from app.clients.anthropic_client import AnthropicChatModel, _split_system
from app.core.config import settings


def test_split_system_separates_system_role():
    system, convo = _split_system(
        [
            {"role": "system", "content": "ctx"},
            {"role": "user", "content": "hi"},
        ]
    )
    assert system == "ctx"
    assert convo == [{"role": "user", "content": "hi"}]


def test_split_system_none_when_absent():
    system, convo = _split_system([{"role": "user", "content": "hi"}])
    assert system is None
    assert convo == [{"role": "user", "content": "hi"}]


async def test_achat_joins_text_blocks(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    model = AnthropicChatModel("claude-haiku-4-5-20251001")

    class _Block:
        type = "text"
        text = "안녕하세요"

    class _Resp:
        content = [_Block()]

    captured = {}

    async def _fake_create(**kwargs):
        captured.update(kwargs)
        return _Resp()

    monkeypatch.setattr(model._client.messages, "create", _fake_create)

    out = await model.achat(
        [{"role": "system", "content": "ctx"}, {"role": "user", "content": "hi"}]
    )
    assert out == "안녕하세요"
    # system 은 별도 인자로 빠지고 messages 에는 user 만 남아야 한다.
    assert captured["system"] == "ctx"
    assert captured["messages"] == [{"role": "user", "content": "hi"}]
    assert "max_tokens" in captured


async def test_astream_yields_text(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    model = AnthropicChatModel("claude-haiku-4-5-20251001")

    class _FakeStream:
        def __init__(self, texts):
            self._texts = texts

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        @property
        def text_stream(self):
            async def _gen():
                for t in self._texts:
                    yield t

            return _gen()

    monkeypatch.setattr(
        model._client.messages, "stream", lambda **kw: _FakeStream(["안", "녕"])
    )

    tokens = [t async for t in model.astream([{"role": "user", "content": "hi"}])]
    assert tokens == ["안", "녕"]
