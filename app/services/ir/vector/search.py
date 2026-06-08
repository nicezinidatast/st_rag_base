"""Vector 검색.

[Phase 3 — dense 단독]
- embedding.aembed_query → vector_db 유사도 검색 → RetrievedChunk 리스트.
- 컬렉션이 아직 없으면(적재 전) 빈 리스트를 반환한다.

[Phase 4] utils/text.tokenize_ko + BM25(rank-bm25) 점수를 dense 와 Reciprocal Rank
Fusion 으로 융합한다(HybridRetriever). 재정렬(rerank.py)은 후속 작업.
"""

from __future__ import annotations

from dataclasses import replace

from app.clients.embedding import get_embedder
from app.core.config import settings
from app.core.vector_db import get_vector_client
from app.services.ir.base import RetrievedChunk, Retriever
from app.utils.text import tokenize_ko


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
    """여러 랭킹(dense / BM25)을 RRF 로 융합. (순수 함수 — 단위 테스트 대상)

    각 청크 점수 = Σ 1/(k + 순위). 같은 청크((source_id, 내용) 기준)면 양쪽 점수를
    더해 내림차순 정렬한다 → 두 방식이 다 찾은 청크가 위로 올라온다.
    (문서가 아니라 청크 단위로 합친다 — 같은 문서의 다른 청크를 뭉개지 않으려고.)
    """
    fused: dict[tuple[str, str], list] = {}
    for ranking in rankings:
        for rank, chunk in enumerate(ranking, start=1):
            key = (chunk.source_id, chunk.content)
            if key not in fused:
                fused[key] = [0.0, chunk]
            fused[key][0] += 1.0 / (k + rank)
    merged = [replace(chunk, score=score) for score, chunk in fused.values()]
    merged.sort(key=lambda c: c.score, reverse=True)
    return merged


class HybridRetriever(Retriever):
    """dense + BM25 → RRF 융합. (VectorRetriever 와 동일 시그니처)

    한국어는 형태소 단위 BM25 가 dense 임베딩이 놓치는 정확매칭(고유명사·드문 용어)을
    잡아준다. tokenize_ko 로 토큰화한 BM25 점수와 dense 점수를 RRF 로 합친다.
    재정렬(rerank.py)은 후속 작업이라 아직 끼우지 않았다.
    """

    async def retrieve(self, query: str, top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        dense = await VectorRetriever().retrieve(query, top_k=top_k)
        sparse = await self._bm25_search(query, top_k)
        return reciprocal_rank_fusion([dense, sparse])[:top_k]

    async def _bm25_search(self, query: str, top_k: int) -> list[RetrievedChunk]:
        """전체 청크를 읽어 BM25 점수 상위 top_k 반환.

        작은~중간 코퍼스 기준 — 질의마다 전체 청크를 읽어 BM25 를 새로 만든다. 코퍼스가
        아주 커지면 영구 BM25 색인이나 Qdrant 스파스벡터로 옮긴다(배포별 선택, base 아님).
        """
        from rank_bm25 import BM25Okapi

        client = get_vector_client()
        if not await client.collection_exists(settings.VECTOR_COLLECTION):
            return []
        corpus = await _scroll_all(client, settings.VECTOR_COLLECTION)
        if not corpus:
            return []
        bm25 = BM25Okapi([tokenize_ko(c.content) for c in corpus])
        scores = bm25.get_scores(tokenize_ko(query))
        ranked = sorted(zip(corpus, scores, strict=True), key=lambda cs: cs[1], reverse=True)
        # 겹치는 단어가 없으면 BM25 점수 0 → 무관하니 버린다.
        return [replace(c, score=float(s)) for c, s in ranked[:top_k] if s > 0]


async def _scroll_all(client, collection: str) -> list[RetrievedChunk]:
    """컬렉션의 모든 청크를 RetrievedChunk(점수 0)로 읽어온다(BM25 코퍼스용)."""
    corpus: list[RetrievedChunk] = []
    offset = None
    while True:
        points, offset = await client.scroll(
            collection_name=collection,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for p in points:
            payload = p.payload or {}
            corpus.append(
                RetrievedChunk(
                    content=payload.get("content", ""),
                    score=0.0,
                    source_id=payload.get("source_id", ""),
                    metadata=payload.get("metadata", {}),
                )
            )
        if offset is None:
            break
    return corpus
