"""노드: 검색 결과 정합성/컨텍스트 신뢰도 스코어링.

[구현 가이드] config/prompts/nodes/grader.yaml 로 관련성 채점.
점수가 낮으면 rag_agent 에서 재검색/모드전환으로 분기(conditional edge)하도록 설계.
"""
from __future__ import annotations

from app.services.workflow.state import AgentState


async def grade(state: AgentState) -> AgentState:
    raise NotImplementedError("grade 노드 미구현")
