"""[Embedding 팩토리] 임베딩 프로바이더를 바꿔 끼우는 틀.

[왜 필요한가]
- 임베딩 모델은 차원(dim)과 성능/비용이 제각각이고, 한국어 품질도 다르다
  (openai, voyage, cohere, upstage-solar, huggingface-bge ...).
- Vector DB 의 컬렉션 차원과 임베딩 dim 이 맞아야 하므로, 모델 교체를 한 곳에서
  통제해야 사고를 막는다.

[설계]
- Embedder: 공통 인터페이스.
    · aembed_documents(texts) -> list[list[float]]  (적재용: 여러 청크)
    · aembed_query(text) -> list[float]              (검색용: 단일 쿼리)
    · dim -> int                                     (컬렉션 생성 시 필요)
- get_embedder("openai:text-embedding-3-small") 로 생성.

[구현 상태] 팩토리/레지스트리 = 틀 완성. 프로바이더 본체 = TODO.
"""
from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

from app.core.config import settings


@runtime_checkable
class Embedder(Protocol):
    @property
    def dim(self) -> int:
        """임베딩 벡터 차원 수."""
        ...

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    async def aembed_query(self, text: str) -> list[float]:
        ...


REGISTRY: dict[str, Callable[[str], Embedder]] = {}


def register(provider: str):
    def deco(fn: Callable[[str], Embedder]):
        REGISTRY[provider] = fn
        return fn

    return deco


def get_embedder(spec: str | None = None) -> Embedder:
    """"provider:model" 스펙으로 Embedder 생성. None 이면 기본값 사용."""
    spec = spec or settings.DEFAULT_EMBEDDING_MODEL
    provider, _, model = spec.partition(":")
    if not model:
        provider, model = "openai", spec
    if provider not in REGISTRY:
        raise ValueError(f"등록되지 않은 embedding provider: '{provider}'")
    return REGISTRY[provider](model)


@register("openai")
def _build_openai(model: str) -> Embedder:
    # TODO: OpenAI 임베딩 래퍼 반환 (dim 은 모델별 상수 매핑 권장)
    raise NotImplementedError("openai Embedder 빌더 미구현")
