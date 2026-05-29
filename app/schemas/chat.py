"""채팅 엔드포인트 입출력 스키마.

[핵심 필드]
- rag_mode : 어떤 검색 엔진을 쓸지 (AUTO 면 orchestrator/routing 이 결정)
- stream   : True 면 SSE 스트리밍, False 면 동기 JSON 응답 (기본 True)
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RagMode(str, Enum):
    """오케스트레이터가 사용할 검색 엔진."""

    AUTO = "auto"          # 라우터가 자동 결정
    VECTOR = "vector"      # dense + BM25 하이브리드
    GRAPH_LOCAL = "graph_local"   # 엔티티 이웃 기반 미시 검색
    GRAPH_GLOBAL = "graph_global" # 커뮤니티 요약 맵리듀스 거시 검색
    HYBRID = "hybrid"      # vector + graph 융합


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    messages: list[ChatMessage]
    rag_mode: RagMode = RagMode.AUTO
    top_k: int = Field(default=5, ge=1, le=50)
    stream: bool = True   # 기본은 스트리밍(SSE). False 면 동기 응답.


class Citation(BaseModel):
    source_id: str
    snippet: str
    score: float | None = None


class ChatResponse(BaseModel):
    """동기 응답(stream=False)일 때 직렬화되는 스키마."""

    conversation_id: str
    answer: str
    citations: list[Citation] = []
    rag_mode: RagMode
