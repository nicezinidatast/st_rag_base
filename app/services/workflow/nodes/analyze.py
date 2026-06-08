"""노드: 질문 의도 및 타겟 엔티티 파악.

[Phase 5 — 그래프 골격용 경량 노드]
지금은 동작을 바꾸지 않는다(외부 결과는 Phase 3/4 와 동일). query 만 정규화하고
rag_mode 는 요청값을 그대로 통과시킨다.

[추후] config/prompts/nodes/analyzer.yaml + chat_model 로 의도/엔티티 추출 →
state["entities"] 채움. rag_mode 자동 라우팅(AUTO 해소)은 Phase 10(routing.py).
"""
from __future__ import annotations

from app.services.workflow.state import AgentState
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def analyze(state: AgentState) -> AgentState:
    query = (state.get("query") or "").strip()
    logger.info("node_analyze", rag_mode=state.get("rag_mode"), query_chars=len(query))
    return {"query": query}
