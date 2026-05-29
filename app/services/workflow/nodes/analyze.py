"""노드: 질문 의도 및 타겟 엔티티 파악.

[구현 가이드] config/prompts/nodes/analyzer.yaml + chat_model 로 의도/엔티티 추출,
state["entities"], state["rag_mode"] 등을 채워 반환.
"""
from __future__ import annotations

from app.services.workflow.state import AgentState


async def analyze(state: AgentState) -> AgentState:
    raise NotImplementedError("analyze 노드 미구현")
