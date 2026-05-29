"""Global Search: 커뮤니티 요약 Map-Reduce 기반 거시적 검색.

[구현 가이드]
- Map: 각 커뮤니티 리포트로 부분 답변 생성 → Reduce: 통합 답변.
- "전체 주제/요지" 같은 광범위 질문에 강하다. Retriever 인터페이스 구현.
- 파일명이 global_.py 인 이유: 'global' 은 파이썬 예약어라 import 불가.
"""
from __future__ import annotations

from app.services.ir.base import RetrievedChunk, Retriever


class GlobalGraphRetriever(Retriever):
    async def retrieve(self, query: str, top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        raise NotImplementedError("graph global search 미구현")
