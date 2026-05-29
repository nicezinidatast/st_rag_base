"""하이브리드 검색: Dense 벡터 + BM25 키워드 → 융합(RRF 등).

[구현 가이드]
- Dense: embedding.aembed_query → vector_db 유사도 검색.
- Sparse: utils/text.tokenize_ko 토큰화 → BM25(rank-bm25) 점수.
- 두 결과를 Reciprocal Rank Fusion 으로 합치고 RetrievedChunk 리스트 반환.
- 이후 rerank.py 로 재정렬하는 게 일반 파이프라인.
"""
from __future__ import annotations

from app.services.ir.base import RetrievedChunk, Retriever


class VectorRetriever(Retriever):
    async def retrieve(self, query: str, top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        # TODO: dense + BM25 → RRF 융합
        raise NotImplementedError("vector search 미구현")
