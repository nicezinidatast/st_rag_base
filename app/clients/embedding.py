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

[구현 상태]
- 기본 = "st:BAAI/bge-m3" (로컬 sentence-transformers, 무료/키 불필요).
- "openai:..." 등 다른 프로바이더는 spec 으로 선택 가능.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

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


# OpenAI 임베딩 모델별 차원(dim). 컬렉션 생성 시 이 값과 맞춰야 한다.
_OPENAI_EMBED_DIMS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


class OpenAIEmbedder:
    """OpenAI Embeddings 를 Embedder 인터페이스로 감싼 래퍼."""

    def __init__(self, model: str) -> None:
        from openai import AsyncOpenAI

        self.model = model
        self._dim = _OPENAI_EMBED_DIMS.get(model, 1536)
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    @property
    def dim(self) -> int:
        return self._dim

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        resp = await self._client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]

    async def aembed_query(self, text: str) -> list[float]:
        resp = await self._client.embeddings.create(model=self.model, input=[text])
        return resp.data[0].embedding


@register("openai")
def _build_openai(model: str) -> Embedder:
    return OpenAIEmbedder(model)


# sentence-transformers(HF) 모델별 차원. 미등록 모델은 로드 후 실측한다.
_ST_EMBED_DIMS = {
    "BAAI/bge-m3": 1024,
}


class SentenceTransformerEmbedder:
    """로컬 sentence-transformers 임베더 (무료, API 키 불필요).

    기본값 BAAI/bge-m3 는 한국어 포함 다국어에 강하다. 모델은 무겁기 때문에
    최초 사용 시점에 한 번만 로드(지연)하고, 인코딩은 스레드풀에서 돌려
    이벤트 루프를 막지 않는다. bge-m3 권장대로 임베딩을 정규화한다(코사인 거리용).
    """

    def __init__(self, model: str) -> None:
        self.model_name = model
        self._model = None  # 지연 로드

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            from app.core.config import settings

            self._model = SentenceTransformer(
                self.model_name, token=settings.HF_TOKEN
            )
        return self._model

    @property
    def dim(self) -> int:
        known = _ST_EMBED_DIMS.get(self.model_name)
        if known is not None:
            return known
        return self._ensure_model().get_sentence_embedding_dimension()

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        import anyio

        model = self._ensure_model()
        vectors = await anyio.to_thread.run_sync(
            lambda: model.encode(texts, normalize_embeddings=True)
        )
        return [v.tolist() for v in vectors]

    async def aembed_query(self, text: str) -> list[float]:
        import anyio

        model = self._ensure_model()
        vectors = await anyio.to_thread.run_sync(
            lambda: model.encode([text], normalize_embeddings=True)
        )
        return vectors[0].tolist()


@register("st")
def _build_sentence_transformer(model: str) -> Embedder:
    return SentenceTransformerEmbedder(model)
