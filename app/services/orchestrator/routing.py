"""의도 파악 → 어떤 RAG 엔진(vector/graph-local/graph-global/hybrid)을 쓸지 결정.

[구현 가이드]
- 규칙기반(키워드/엔티티 수) 또는 LLM 분류기로 RagMode 반환.
- rag_mode 가 AUTO 일 때만 동작하고, 명시 지정 시엔 그대로 따른다.
"""
from __future__ import annotations

from app.schemas.chat import RagMode


async def route(query: str) -> RagMode:
    raise NotImplementedError("라우팅 미구현")
