"""노드: rag_mode 에 따라 ir/ 의 특정 search 모듈을 매핑 호출.

[구현 가이드]
- state["rag_mode"] 로 VectorRetriever / LocalGraphRetriever / GlobalGraphRetriever 선택.
- 공통 Retriever.retrieve() 호출 → state["documents"] 채움.
- (vector 의 경우) rerank 까지 여기서 적용 가능.
"""
from __future__ import annotations

from app.services.workflow.state import AgentState


async def retrieve(state: AgentState) -> AgentState:
    raise NotImplementedError("retrieve 노드 미구현")
