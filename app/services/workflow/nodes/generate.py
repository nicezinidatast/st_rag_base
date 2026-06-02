"""노드: 최종 컨텍스트 조립 후 답변 생성.

[Phase 5] Phase 3 의 _build_messages + ChatModel 호출을 노드로 옮겼다(동작 동일).
- *** 스트리밍 핵심: chat_model.astream() 으로 토큰을 받아 get_stream_writer 로
  흘려보낸다. streaming.py 가 graph.astream(stream_mode="custom") 으로 이 토큰을
  SSE 로 중계한다. graph.ainvoke(동기) 일 때 writer 는 자동 no-op 이라 같은 코드가
  양쪽을 커버한다. ***
- state["answer"], state["model"] 채워 반환(citations 는 retrieve 노드가 채움).

[추후] config/prompts/nodes/generator.yaml 로 system 프롬프트 외부화.
"""
from __future__ import annotations

from app.services.workflow.state import AgentState


def _build_messages(question: str, context: str) -> list[dict]:
    """질문(+검색 컨텍스트)을 LLM 메시지 목록으로 만든다.

    컨텍스트가 있으면 system 메시지로 앞에 끼운다(없으면 질문만).
    """
    messages: list[dict] = []
    if context:
        messages.append(
            {
                "role": "system",
                "content": (
                    "다음 컨텍스트를 근거로 답하라. 컨텍스트에 없으면 모른다고 답하라.\n\n"
                    f"{context}"
                ),
            }
        )
    messages.append({"role": "user", "content": question})
    return messages


async def generate(state: AgentState) -> AgentState:
    from langgraph.config import get_stream_writer

    from app.clients.chat_model import get_chat_model
    from app.core.config import settings

    spec = state.get("model") or settings.DEFAULT_CHAT_MODEL
    messages = _build_messages(state.get("query", ""), state.get("context", ""))

    chat_model = get_chat_model(spec)
    writer = get_stream_writer()
    parts: list[str] = []
    async for token in chat_model.astream(messages):
        parts.append(token)
        writer({"token": token})
    return {"answer": "".join(parts), "model": spec}
