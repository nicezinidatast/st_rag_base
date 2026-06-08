"""그래프 전체에서 공유되는 컨텍스트 객체(AgentState).

[구현 가이드] LangGraph 는 각 노드가 이 dict 를 받아 일부 키를 갱신해 반환하면
자동 병합한다. 필요한 필드를 늘려가되, 노드 간 계약을 명확히 유지할 것.
"""
from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict, total=False):
    query: str
    rag_mode: str
    top_k: int                 # 검색할 청크 수 (요청에서 전달)
    model: str                 # 답변 생성에 쓸 "provider:model"
    entities: list[str]
    history: list[dict]        # 이전 대화 턴 [{"role","content"}, ...] (Phase 6)
    documents: list[dict]      # 검색/리랭크된 청크
    context: str               # documents 를 LLM 입력용으로 합친 문자열
    grade: float               # 컨텍스트 신뢰도 점수
    answer: str
    citations: list[dict]
