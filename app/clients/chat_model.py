"""[ChatModel 팩토리] 여러 LLM 프로바이더를 런타임에 바꿔 끼우는 틀.

[왜 필요한가]
- common backend 라서 프로젝트/요청마다 다른 모델을 써야 한다(gpt-4o, claude,
  gemini, solar...). 호출부가 특정 SDK 에 묶이면 교체가 지옥이 된다.
- "provider:model" 문자열 하나로 어떤 모델이든 동일한 인터페이스로 받게 한다.

[설계]
- ChatModel: 모든 챗 모델이 만족해야 하는 공통 인터페이스(Protocol).
    · achat(messages) -> str            (동기형: 전체 답변 한 번에)
    · astream(messages) -> AsyncIterator[str]  (스트리밍형: 토큰 조각)
  *** 반드시 동기형/스트리밍형 둘 다 제공할 것. ***
  (이유: SSE 응답은 astream 을, 일반 JSON 응답은 achat 를 쓴다. streaming.py 참고)
- REGISTRY: provider 이름 → 빌더 함수. 새 프로바이더는 @register 로 추가만 하면 됨.
- get_chat_model("openai:gpt-4o-mini"): 파싱 후 해당 빌더로 인스턴스 생성.

[구현 상태]
- 팩토리/파싱/레지스트리 = 동작하는 틀.
- 각 프로바이더 빌더 본체 = TODO (실제 SDK 연동은 직접 구현).
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Protocol, runtime_checkable

from app.core.config import settings


@runtime_checkable
class ChatModel(Protocol):
    """모든 챗 모델 구현이 만족해야 하는 공통 인터페이스."""

    async def achat(self, messages: list[dict], **kwargs) -> str:
        """동기형: 전체 답변을 한 번에 반환."""
        ...

    def astream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        """스트리밍형: 토큰/조각을 비동기로 yield."""
        ...


# provider 이름 → ChatModel 인스턴스를 만드는 빌더 함수
REGISTRY: dict[str, Callable[[str], ChatModel]] = {}


def register(provider: str) -> Callable[[Callable[[str], ChatModel]], Callable[[str], ChatModel]]:
    """새 프로바이더 빌더 등록 데코레이터.

    사용 예:
        @register("openai")
        def _build_openai(model: str) -> ChatModel:
            return OpenAIChatModel(model=model)
    """
    def deco(fn: Callable[[str], ChatModel]) -> Callable[[str], ChatModel]:
        REGISTRY[provider] = fn
        return fn

    return deco


def get_chat_model(spec: str | None = None) -> ChatModel:
    """"provider:model" 스펙으로 ChatModel 인스턴스를 생성한다.

    spec 이 None 이면 settings.DEFAULT_CHAT_MODEL 사용.
    예) "openai:gpt-4o-mini", "anthropic:claude-3-5-sonnet", "upstage:solar-pro"
    """
    spec = spec or settings.DEFAULT_CHAT_MODEL
    provider, _, model = spec.partition(":")
    if not model:  # "gpt-4o-mini" 처럼 provider 생략 시 openai 기본 가정
        provider, model = "openai", spec
    if provider not in REGISTRY:
        raise ValueError(
            f"등록되지 않은 chat provider: '{provider}'. "
            f"clients/chat_model.py 에 @register('{provider}') 빌더를 추가하세요."
        )
    return REGISTRY[provider](model)


# ─────────────────────────────────────────────────────────────────
# 프로바이더 빌더 — 본체는 TODO. 아래 형태로 채워나가면 된다.
# (지금은 등록만 하고 호출 시 NotImplementedError 를 던지는 틀)
# ─────────────────────────────────────────────────────────────────
@register("openai")
def _build_openai(model: str) -> ChatModel:
    from app.clients.openai_client import OpenAIChatModel

    return OpenAIChatModel(model)


@register("anthropic")
def _build_anthropic(model: str) -> ChatModel:
    from app.clients.anthropic_client import AnthropicChatModel

    return AnthropicChatModel(model)
