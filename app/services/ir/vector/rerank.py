"""문서 재정렬: cross-encoder(BGE) 또는 Cohere Rerank.

[구현 가이드] clients/reranker.get_reranker() 로 리랭커를 받아 arerank 호출,
상위 top_n 만 남긴다. search.py 결과를 입력으로 받는다.
"""
from __future__ import annotations

from app.services.ir.base import RetrievedChunk


async def rerank(query: str, chunks: list[RetrievedChunk], top_n: int = 5) -> list[RetrievedChunk]:
    raise NotImplementedError("rerank 미구현")
