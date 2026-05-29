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
from typing import Any, AsyncIterator

# SSE 표준 이벤트 이름 컨벤션 (프론트와 합의해 고정해두면 좋다)
EVENT_TOKEN = "token"   # 답변 토큰 조각
EVENT_META = "meta"     # 검색 출처/단계 등 메타데이터
EVENT_DONE = "done"     # 스트림 종료 신호
EVENT_ERROR = "error"   # 에러 발생


def sse(data: Any, event: str = EVENT_TOKEN) -> dict:
    """sse-starlette 의 EventSourceResponse 가 받는 이벤트 dict 로 변환.

    EventSourceResponse 는 {"event": ..., "data": ...} 형태를 yield 받으면
    `event: ...\\n data: ...\\n\\n` SSE 프레임으로 자동 포맷한다.
    data 가 문자열이 아니면 JSON 직렬화한다.
    """
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return {"event": event, "data": payload}


async def stream_chat(request: Any) -> AsyncIterator[dict]:
    """[스트리밍 응답용 generator — 구현 가이드]

    여기가 'EventSourceResponse 로 감쌀 내용물'이다. 아래 순서로 구현하면 된다:

        1. graph = build_graph()
        2. (선택) yield sse({"stage": "retrieving"}, EVENT_META)
        3. async for ev in graph.astream_events(state, version="v2"):
               # ev 에서 LLM 토큰만 골라:
               #   if ev["event"] == "on_chat_model_stream":
               #       yield sse(ev["data"]["chunk"].content, EVENT_TOKEN)
        4. 출처/인용은 EVENT_META 로 따로 흘려보낸다.
        5. 마지막에 yield sse("[DONE]", EVENT_DONE)
        6. try/except 로 감싸 에러 시 yield sse(str(e), EVENT_ERROR)
           (스트림 도중 죽으면 HTTP 상태코드로 못 알리므로 이벤트로 알려야 한다)

    주의: 이 함수는 HTTP 를 몰라야 한다(헤더/상태코드 X). 오직 이벤트만 yield.
    """
    raise NotImplementedError("stream_chat generator 미구현")
    yield  # pragma: no cover  (async generator 로 만들기 위한 표식)


async def run_chat_sync(request: Any) -> dict:
    """[동기 응답용 — Phase 1 임시 구현]

    원래는 LangGraph 를 돌려야 하지만(아래 주석), Phase 1 에는 아직 graph 가 없다.
    그래서 검색/노드 없이 ChatModel 을 직접 호출해 답변만 만든다. (RAG 없음)

        result = await graph.ainvoke(state)                          # ← Phase 5 에서 이렇게 교체
        return {"answer": result["answer"], "citations": result.get("citations", [])}

    endpoints/chat.py 에서 이 반환값을 ChatResponse 로 직렬화한다.
    """
    from app.clients.chat_model import get_chat_model

    chat_model = get_chat_model()  # settings.DEFAULT_CHAT_MODEL 사용
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    answer = await chat_model.achat(messages)
    return {"answer": answer, "citations": []}
