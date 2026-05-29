"""Anthropic 구체 래퍼 (Claude).

[구현 가이드]
- chat_model.py 의 ChatModel 인터페이스(achat/astream)를 만족한다.
- Anthropic 은 OpenAI 와 두 가지가 다르다:
    1) system 프롬프트는 messages 배열이 아니라 별도 `system=` 인자로 넘긴다.
       (그래서 _split_system 으로 system 역할 메시지를 분리한다.)
    2) max_tokens 가 필수다.
- 키는 settings.ANTHROPIC_API_KEY 사용.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from app.core.config import settings

# Anthropic 은 max_tokens 가 필수. 호출 시 kwargs 로 덮어쓸 수 있다.
_DEFAULT_MAX_TOKENS = 4096


def _split_system(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """system 역할 메시지를 분리한다 → (system 문자열|None, 대화 메시지 목록).

    Anthropic 은 system 을 messages 에 넣지 못하므로 별도 인자로 빼야 한다.
    """
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    convo = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m["role"] != "system"
    ]
    system = "\n\n".join(system_parts) if system_parts else None
    return system, convo


class AnthropicChatModel:
    """Anthropic Messages API 를 ChatModel 인터페이스로 감싼 래퍼."""

    def __init__(self, model: str) -> None:
        from anthropic import AsyncAnthropic

        self.model = model
        self._client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def achat(self, messages: list[dict], **kwargs) -> str:
        """동기형: 전체 답변을 한 번에 반환."""
        system, convo = _split_system(messages)
        params: dict = {
            "model": self.model,
            "max_tokens": kwargs.pop("max_tokens", _DEFAULT_MAX_TOKENS),
            "messages": convo,
            **kwargs,
        }
        if system is not None:
            params["system"] = system
        resp = await self._client.messages.create(**params)
        return "".join(b.text for b in resp.content if b.type == "text")

    async def astream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        """스트리밍형: 토큰 조각을 yield."""
        system, convo = _split_system(messages)
        params: dict = {
            "model": self.model,
            "max_tokens": kwargs.pop("max_tokens", _DEFAULT_MAX_TOKENS),
            "messages": convo,
            **kwargs,
        }
        if system is not None:
            params["system"] = system
        async with self._client.messages.stream(**params) as stream:
            async for text in stream.text_stream:
                yield text
