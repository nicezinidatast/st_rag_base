"""문서 재정렬: cross-encoder(BGE) 또는 Cohere Rerank.

1차 검색(vector/BM25)은 recall 위주라 노이즈가 섞인다. 리랭커로 쿼리-문서 쌍을 정밀
채점해 상위 top_n 만 남기면 답변 품질이 오른다. 재정렬은 *선택* 단계라:
- 기본 검색 파이프라인엔 끼우지 않았다(비용·지연 + 프로바이더 키가 필요해 배포별 선택).
  쓰려면 retrieve 결과에 rerank() 를 한 줄 덧대면 된다.
- 리랭커가 없거나(프로바이더 미구현/키 없음) 호출이 실패하면 입력을 그대로 돌려준다
  (없다고 검색을 막지 않는다 — 메모리/그래프의 우아한 강등과 같은 철학).

프로바이더 본체(cohere/BGE 등)는 clients/reranker.py 빌더에서 고른다(배포별 선택).
"""

from __future__ import annotations

from dataclasses import replace

from app.clients.reranker import get_reranker
from app.services.ir.base import RetrievedChunk
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def rerank(query: str, chunks: list[RetrievedChunk], top_n: int = 5) -> list[RetrievedChunk]:
    """검색 결과를 리랭커로 재정렬해 상위 top_n 만 남긴다(리랭커 없으면 원래 순서 유지)."""
    if not chunks:
        return []
    try:
        reranker = get_reranker()
        results = await reranker.arerank(query, [c.content for c in chunks], top_n=top_n)
    except Exception as e:  # noqa: BLE001  리랭커 부재/실패는 비치명 → 원래 순서 유지
        logger.warning("rerank_skip", error=str(e))
        return chunks[:top_n]
    # RerankResult.index 는 입력 documents(=chunks) 에서의 원래 위치 → 점수만 교체해 재배열.
    return [replace(chunks[r.index], score=r.score) for r in results]
