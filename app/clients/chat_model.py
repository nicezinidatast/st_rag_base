"""[ChatModel 팩토리] "provider:model" 문자열 → LangChain BaseChatModel.

[왜 LangChain 모델인가] (Phase 5+)
- LangGraph `astream_events(v2)` 가 `on_chat_model_stream` 으로 토큰을 자동 포착한다 →
  generate 노드는 `ainvoke` 만 하면 되고 별도 스트리밍 배관(get_stream_writer)이 필요 없다.
- 콜백 하나(`config={"callbacks":[...]}`)로 Langfuse 등 트레이싱이 자동 계측된다.
- `bind_tools` / `with_structured_output` 등 생태계 기능을 그대로 쓴다.

[설계]
- provider 별 빌더 레지스트리 유지(새 프로바이더는 `@register` 만 추가).
- 키는 settings 에서 골라 **명시 주입**한다. `.env` 는 `os.environ` 이 아니라 Settings 로
  로드되므로, LangChain 모델이 환경변수에서 키를 자동으로 읽지 못한다.
- get_chat_model("anthropic:claude-...") 처럼 호출. provider 생략 시 openai 가정.
"""
from __future__ import annotations

from collections.abc import Callable

from langchain_core.language_models import BaseChatModel

from app.core.config import settings

# Anthropic 은 max_tokens 가 사실상 필수. 다른 프로바이더엔 적용하지 않는다.
_DEFAULT_MAX_TOKENS = 4096

# provider 이름 → BaseChatModel 을 만드는 빌더 함수
REGISTRY: dict[str, Callable[[str], BaseChatModel]] = {}


def register(
    provider: str,
) -> Callable[[Callable[[str], BaseChatModel]], Callable[[str], BaseChatModel]]:
    """새 프로바이더 빌더 등록 데코레이터."""

    def deco(fn: Callable[[str], BaseChatModel]) -> Callable[[str], BaseChatModel]:
        REGISTRY[provider] = fn
        return fn

    return deco


def get_chat_model(spec: str | None = None) -> BaseChatModel:
    """"provider:model" 스펙으로 LangChain BaseChatModel 을 생성한다.

    spec 이 None 이면 settings.DEFAULT_CHAT_MODEL 사용.
    예) "anthropic:claude-...", "openai:gpt-4o-mini".
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


@register("anthropic")
def _build_anthropic(model: str) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=model, api_key=settings.ANTHROPIC_API_KEY, max_tokens=_DEFAULT_MAX_TOKENS
    )


@register("openai")
def _build_openai(model: str) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=model, api_key=settings.OPENAI_API_KEY)
