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
