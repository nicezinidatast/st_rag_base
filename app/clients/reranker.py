"""[Reranker 팩토리] 재정렬 프로바이더를 바꿔 끼우는 틀.

[왜 필요한가]
- 1차 검색(vector/BM25)은 recall 위주라 노이즈가 섞인다. cross-encoder 리랭커로
  쿼리-문서 쌍을 정밀 채점해 상위 N개만 추리면 답변 품질이 크게 오른다.
- 프로바이더가 다양하다: cohere rerank, BGE-reranker(huggingface), Voyage rerank ...

[설계]
- Reranker: 공통 인터페이스.
    · arerank(query, documents, top_n) -> list[RerankResult]
      (입력 문서들을 점수 내림차순으로 재정렬해 상위 top_n 반환)
- get_reranker("cohere:rerank-multilingual-v3.0") 로 생성.

[구현 상태] 팩토리/레지스트리 = 틀 완성. 프로바이더 본체 = TODO.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable

from app.core.config import settings


@dataclass
class RerankResult:
    index: int       # 입력 documents 에서의 원래 위치
    score: float
    document: str


@runtime_checkable
class Reranker(Protocol):
    async def arerank(
        self, query: str, documents: list[str], top_n: int = 5
    ) -> list[RerankResult]:
        ...


REGISTRY: dict[str, Callable[[str], Reranker]] = {}


def register(provider: str):
    def deco(fn: Callable[[str], Reranker]):
        REGISTRY[provider] = fn
        return fn

    return deco


def get_reranker(spec: str | None = None) -> Reranker:
    spec = spec or settings.DEFAULT_RERANK_MODEL
    provider, _, model = spec.partition(":")
    if not model:
        provider, model = "cohere", spec
    if provider not in REGISTRY:
        raise ValueError(f"등록되지 않은 rerank provider: '{provider}'")
    return REGISTRY[provider](model)


@register("cohere")
def _build_cohere(model: str) -> Reranker:
    # TODO: Cohere Rerank API 래퍼 반환
    raise NotImplementedError("cohere Reranker 빌더 미구현")
