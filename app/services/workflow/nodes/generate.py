"""노드: 최종 컨텍스트 조립 후 답변 생성.

[Phase 5+] LangChain BaseChatModel 을 ainvoke 로 호출하기만 한다.
- *** 스트리밍 핵심: 토큰 스트리밍은 여기서 신경 쓸 게 없다. streaming.py 가
  graph.astream_events(v2) 로 돌리면 LangChain 모델 호출이 on_chat_model_stream
  이벤트로 토큰을 자동으로 흘려보낸다(ainvoke 든 astream 이든 무관). ***
- state["answer"], state["model"] 채워 반환(citations 는 retrieve 노드가 채움).

[추후] config/prompts/nodes/generator.yaml 로 system 프롬프트 외부화.
"""
from __future__ import annotations

from app.services.workflow.state import AgentState
from app.utils.logger import get_logger

logger = get_logger(__name__)


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
    from app.clients.chat_model import get_chat_model
    from app.core.config import settings

    spec = state.get("model") or settings.DEFAULT_CHAT_MODEL
    has_context = bool(state.get("context"))
    messages = _build_messages(state.get("query", ""), state.get("context", ""))

    logger.info("node_generate_start", model=spec, has_context=has_context)
    resp = await get_chat_model(spec).ainvoke(messages)
    content = resp.content
    answer = content if isinstance(content, str) else str(content)
    logger.info("node_generate_done", model=spec, answer_chars=len(answer))
    return {"answer": answer, "model": spec}
