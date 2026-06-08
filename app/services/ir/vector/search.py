"""Vector 검색.

[Phase 3 — dense 단독]
- embedding.aembed_query → vector_db 유사도 검색 → RetrievedChunk 리스트.
- 컬렉션이 아직 없으면(적재 전) 빈 리스트를 반환한다.

[Phase 4 예정] utils/text.tokenize_ko + BM25(rank-bm25) 점수를 dense 와
Reciprocal Rank Fusion 으로 융합하고, rerank.py 로 재정렬.
"""
from __future__ import annotations

from app.clients.embedding import get_embedder
from app.core.config import settings
from app.core.vector_db import get_vector_client
from app.services.ir.base import RetrievedChunk, Retriever


class VectorRetriever(Retriever):
    async def retrieve(self, query: str, top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        client = get_vector_client()
        if not await client.collection_exists(settings.VECTOR_COLLECTION):
            return []  # 아직 아무것도 적재되지 않음

        embedder = get_embedder()
        query_vector = await embedder.aembed_query(query)
        resp = await client.query_points(
            collection_name=settings.VECTOR_COLLECTION,
            query=query_vector,
            limit=top_k,
            with_payload=True,
            score_threshold=0.5,  # 유사도 0.5 이상만 반환 (실험적, 필요시 조정)
        )
        chunks = []
        for p in resp.points:
            payload = p.payload or {}
            chunks.append(
                RetrievedChunk(
                    content=payload.get("content", ""),
                    score=p.score,
                    source_id=payload.get("source_id", ""),
                    metadata=payload.get("metadata", {}),
                )
            )
        return chunks


def reciprocal_rank_fusion(
    rankings: list[list[RetrievedChunk]], k: int = 60
) -> list[RetrievedChunk]:
    """[Phase 4 — 스켈레톤] 여러 랭킹(dense / BM25)을 RRF 로 융합.

    각 청크 점수 = Σ 1/(k + rank). source_id 기준으로 합산해 내림차순 정렬한다.
    본체 구현은 정확도 개선 단계에서 채운다(현재는 슬롯만).
    """
    raise NotImplementedError("RRF 융합 미구현 (Phase 4)")


class HybridRetriever(Retriever):
    """[Phase 4 — 스켈레톤] dense + BM25 → RRF 융합 → rerank.

    tokenize_ko 형태소 분리 후 BM25 점수와 VectorRetriever 의 dense 점수를
    reciprocal_rank_fusion 으로 합치고, ir/vector/rerank.rerank 로 재정렬한다.
    VectorRetriever 와 동일 시그니처(외부 동작 동일, 검색 정확도만 향상).
    본체 구현은 정확도 개선 단계에서 채운다(현재는 슬롯만).
    """

    async def retrieve(self, query: str, top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        raise NotImplementedError("하이브리드 검색 미구현 (Phase 4)")
