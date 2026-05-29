"""노드: 최종 컨텍스트 조립 후 답변 생성.

[구현 가이드]
- config/prompts/nodes/generator.yaml + chat_model 로 답변 생성.
- *** 스트리밍 핵심: 여기서 LLM 을 streaming 으로 호출해야 astream_events 가
  토큰 이벤트를 흘려보낸다(utils/streaming.py 참고). chat_model.astream() 사용. ***
- state["answer"], state["citations"] 채워 반환.
"""
from __future__ import annotations

from app.services.workflow.state import AgentState


async def generate(state: AgentState) -> AgentState:
    raise NotImplementedError("generate 노드 미구현")
