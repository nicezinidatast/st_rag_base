"""노드: 검색 결과 정합성/컨텍스트 신뢰도 스코어링.

[Phase 5 — 그래프 골격용 경량 노드]
추가 LLM 호출 없이(동작/지연 변화 없이) 검색 점수만으로 신뢰도를 매긴다:
documents 의 최고 점수를 state["grade"] 로 둔다(없으면 0.0).

[추후] config/prompts/nodes/grader.yaml 로 LLM 관련성 채점 → 점수가 낮으면
rag_agent 에서 재검색/모드전환으로 분기(conditional edge)하는 품질 게이트.
"""
from __future__ import annotations

from app.services.workflow.state import AgentState
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def grade(state: AgentState) -> AgentState:
    documents = state.get("documents") or []
    score = max((d.get("score") or 0.0) for d in documents) if documents else 0.0
    logger.info("node_grade", grade=round(float(score), 4), n_documents=len(documents))
    return {"grade": float(score)}
