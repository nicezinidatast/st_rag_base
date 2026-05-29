"""Local Search: 특정 엔티티 주변 이웃 노드 기반 미시적 검색.

[구현 가이드]
- 질문에서 앵커 엔티티 식별 → graph_db 에서 이웃 노드/관계 확장 → 컨텍스트 조립.
- 특정 사실/관계를 묻는 질문에 강하다. Retriever 인터페이스 구현.
"""
from __future__ import annotations

from app.services.ir.base import RetrievedChunk, Retriever


class LocalGraphRetriever(Retriever):
    async def retrieve(self, query: str, top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        raise NotImplementedError("graph local search 미구현")
