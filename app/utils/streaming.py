"""[스트리밍 유틸] SSE 스트리밍 ↔ 동기 응답을 다루는 공통 틀 + LangGraph 가이드.

이 파일은 NICECHAT_BASE 의 응답 철학을 코드 주석으로 못박는 곳이다.
*** 기본은 SSE 스트리밍, 그러나 동기(sync) 응답도 항상 가능해야 한다. ***

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
■ 꼭 이해할 개념: "StreamingResponse" vs "generator"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
이 둘은 다른 계층이다. 헷갈리면 안 된다.

  • generator (async generator)
      - "데이터를 한 조각씩 만들어 내보내는 함수". `async def ... : yield ...`
      - 우리 도메인 로직(LangGraph 실행 → 토큰 조각)이 사는 곳.
      - 순수하게 '무엇을 내보낼지'만 책임진다. HTTP 를 모른다.

  • StreamingResponse / EventSourceResponse
      - "그 generator 를 HTTP 응답으로 감싸는 어댑터". HTTP 헤더/전송을 책임진다.
      - StreamingResponse: 임의 바이트/텍스트 청크 스트리밍 (raw).
      - EventSourceResponse (sse-starlette): SSE 규격(`data: ...\n\n`, event/ id)에
        맞춰 자동 포맷팅. 프론트가 EventSource/fetch-stream 으로 받기 쉽다.
        → 챗 토큰 스트리밍에는 EventSourceResponse 를 권장(이 프로젝트 기본).

  관계:  [도메인 generator]  →  [EventSourceResponse 로 감싼다]  →  [클라이언트]
  즉 generator 가 '내용물', StreamingResponse 류가 '포장지'다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
■ LangGraph 와 어떻게 연결하나 (구현 시 가이드)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LangGraph 컴파일된 graph(=app.services.orchestrator.rag_agent.build_graph()) 는
세 가지 실행 메서드를 준다. 용도별로 구분해서 써라:

  1) await graph.ainvoke(state)        → [동기 응답용]
       전체 워크플로를 끝까지 돌려 최종 state 를 한 번에 반환. ChatResponse 로 직렬화.

  2) graph.astream(state)              → [노드 단위 스트리밍]
       각 노드 실행이 끝날 때마다 중간 state 를 yield. "검색중… 생성중…" 같은
       단계 진행 표시(progress)에 적합.

  3) graph.astream_events(state, version="v2")  → [토큰 단위 스트리밍]  ★기본
       LLM 토큰까지 이벤트로 흘려준다. 진짜 'ChatGPT 처럼 한 글자씩' 출력.
       generate 노드의 LLM 호출이 streaming 으로 설정돼 있어야 토큰 이벤트가 나온다.

  → 따라서 ChatModel.astream() (clients/chat_model.py) 가 반드시 필요한 이유가 이것.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
■ 동기 vs 스트리밍 분기 (endpoints/chat.py 에서)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ChatRequest.stream 플래그로 분기한다.
    if request.stream:  return EventSourceResponse( stream_chat(...) )   # generator 포장
    else:               result = await run_chat_sync(...);  return ChatResponse(...)
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

# SSE 표준 이벤트 이름 컨벤션 (프론트와 합의해 고정해두면 좋다)
EVENT_TOKEN = "token"   # 답변 토큰 조각
EVENT_META = "meta"     # 검색 출처/단계 등 메타데이터
EVENT_DONE = "done"     # 스트림 종료 신호
EVENT_ERROR = "error"   # 에러 발생

# 챗 LLM(=Anthropic) 키가 없을 때 동기/스트리밍 양쪽에서 그대로 result 로 내보내는 안내 값.
NO_API_KEY_MESSAGE = "Anthropic API key 가 없습니다."


def sse(data: Any, event: str = EVENT_TOKEN) -> dict:
    """sse-starlette 의 EventSourceResponse 가 받는 이벤트 dict 로 변환.

    EventSourceResponse 는 {"event": ..., "data": ...} 형태를 yield 받으면
    `event: ...\\n data: ...\\n\\n` SSE 프레임으로 자동 포맷한다.
    data 가 문자열이 아니면 JSON 직렬화한다.
    """
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return {"event": event, "data": payload}


async def _retrieve_context(question: str, top_k: int) -> tuple[str, list[dict]]:
    """[Phase 3] 질문으로 vector 검색 → (컨텍스트 문자열, citations).

    적재 전(컬렉션 없음)이거나 결과가 없으면 ("", []) 을 돌려준다 → 컨텍스트 없이 답변.
    검색 인프라(Qdrant/임베딩)가 없거나 실패해도 채팅 자체는 막지 않는다(검색만 건너뜀).
    """
    from app.services.ir.vector import search as vsearch
    from app.utils.logger import get_logger

    if not question.strip():
        return "", []

    try:
        chunks = await vsearch.VectorRetriever().retrieve(question, top_k=top_k)
    except Exception as e:  # noqa: BLE001  검색 실패는 치명적이지 않다 → 컨텍스트 없이 진행
        get_logger(__name__).warning("vector retrieve skipped", error=str(e))
        return "", []
    if not chunks:
        return "", []

    context = "\n\n".join(f"[{i + 1}] {c.content}" for i, c in enumerate(chunks))
    citations = [
        {"source_id": c.source_id, "snippet": c.content[:200], "score": c.score}
        for c in chunks
    ]
    return context, citations


def _build_messages(question: str, context: str) -> list[dict]:
    """질문(+검색 컨텍스트)을 LLM 메시지 목록으로 만든다.

    클라이언트는 question 만 보내고, user 메시지 변환은 여기서 한다.
    컨텍스트가 있으면 system 메시지로 앞에 끼운다.
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


async def stream_chat(request: Any) -> AsyncIterator[dict]:
    """[스트리밍 응답용 generator — Phase 2~3 임시 구현]

    원래는 LangGraph 의 astream_events 로 토큰을 흘려야 하지만(아래 미래 가이드),
    아직 graph 가 없다(Phase 5). 그래서 run_chat_sync 와 대칭으로, vector 검색으로
    컨텍스트를 만든 뒤(Phase 3) ChatModel.astream 을 직접 호출해 토큰을 흘린다.

        graph = build_graph()                                    # ← Phase 5 에서 이렇게 교체
        async for ev in graph.astream_events(state, version="v2"):
            if ev["event"] == "on_chat_model_stream":
                yield sse(ev["data"]["chunk"].content, EVENT_TOKEN)
        # 출처/인용은 EVENT_META 로 따로 흘려보낸다.

    주의: 이 함수는 HTTP 를 몰라야 한다(헤더/상태코드 X). 오직 이벤트만 yield.
    스트림 도중 죽으면 HTTP 상태코드로 못 알리므로 에러도 이벤트로 알린다(EVENT_ERROR).
    """
    from app.clients.chat_model import get_chat_model
    from app.core.config import settings

    # [개발 편의 가드] 챗 LLM 키가 없으면 안내 값을 토큰으로 흘리고 끝낸다. (run_chat_sync 와 동일)
    if not settings.ANTHROPIC_API_KEY:
        yield sse(NO_API_KEY_MESSAGE, EVENT_TOKEN)
        yield sse("[DONE]", EVENT_DONE)
        return

    spec = request.model or settings.DEFAULT_CHAT_MODEL
    chat_model = get_chat_model(spec)
    try:
        context, citations = await _retrieve_context(request.question, request.top_k)
        # 사용 모델 + 출처를 먼저 meta 로 알려준다(프론트가 헤더처럼 받음).
        yield sse({"model": spec, "citations": citations}, EVENT_META)
        messages = _build_messages(request.question, context)
        async for token in chat_model.astream(messages):
            yield sse(token, EVENT_TOKEN)
        yield sse("[DONE]", EVENT_DONE)
    except Exception as e:  # noqa: BLE001  스트림 중 에러는 이벤트로만 알릴 수 있다
        yield sse(str(e), EVENT_ERROR)


async def run_chat_sync(request: Any) -> dict:
    """[동기 응답용 — Phase 1~3 임시 구현]

    원래는 LangGraph 를 돌려야 하지만(아래 주석), 아직 graph 가 없다(Phase 5).
    그래서 vector 검색으로 컨텍스트를 만든 뒤(Phase 3) ChatModel 을 직접 호출해
    답변을 만든다.

        result = await graph.ainvoke(state)                          # ← Phase 5 에서 이렇게 교체
        return {"answer": result["answer"], "citations": result.get("citations", [])}

    endpoints/chat.py 에서 이 반환값을 ChatResponse 로 직렬화한다.
    """
    from app.clients.chat_model import get_chat_model
    from app.core.config import settings

    spec = request.model or settings.DEFAULT_CHAT_MODEL

    # [개발 편의 가드] 챗 LLM 키가 없으면 난해한 인증 에러 대신
    # 안내 값을 answer 로 그대로 돌려준다. (키 채우면 자동 해제)
    if not settings.ANTHROPIC_API_KEY:
        return {"answer": NO_API_KEY_MESSAGE, "citations": [], "model": spec}

    chat_model = get_chat_model(spec)
    context, citations = await _retrieve_context(request.question, request.top_k)
    messages = _build_messages(request.question, context)
    answer = await chat_model.achat(messages)
    return {"answer": answer, "citations": citations, "model": spec}
