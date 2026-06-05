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


def _initial_state(request: Any, spec: str) -> dict:
    """ChatRequest → LangGraph 입력 state. (rag_mode 는 StrEnum 이라 그대로 str 로 쓰임)"""
    return {
        "query": request.question,
        "rag_mode": request.rag_mode,
        "top_k": request.top_k,
        "model": spec,
    }


async def stream_chat(request: Any, user_id: int | None = None) -> AsyncIterator[dict]:
    """[스트리밍 응답용 generator — Phase 5+]

    LangGraph 를 astream_events(version="v2") 로 돌린다. LangChain 챗 모델 호출이
    이벤트로 흘러나오므로 별도 토큰 배관이 필요 없다:
      · on_chain_end(name="retrieve") → 그 출력의 citations 를 EVENT_META 로 먼저 송출.
      · on_chat_model_stream         → generate 의 LLM 토큰을 EVENT_TOKEN 으로 중계.
    노드가 analyze→retrieve→grade→generate 순으로 도므로 meta(출처)가 토큰보다 먼저 나간다.

    주의: 이 함수는 HTTP 를 몰라야 한다(헤더/상태코드 X). 오직 이벤트만 yield.
    스트림 도중 죽으면 HTTP 상태코드로 못 알리므로 에러도 이벤트로 알린다(EVENT_ERROR).
    """
    from app.core.config import settings
    from app.services import cache, memory, persistence

    # [개발 편의 가드] 챗 LLM 키가 없으면 안내 값을 토큰으로 흘리고 끝낸다. (run_chat_sync 와 동일)
    if not settings.ANTHROPIC_API_KEY:
        yield sse(NO_API_KEY_MESSAGE, EVENT_TOKEN)
        yield sse("[DONE]", EVENT_DONE)
        return

    spec = request.model or settings.DEFAULT_CHAT_MODEL
    session_id = request.session_id
    question = request.question

    # [캐시] 같은 질문이 캐시에 있으면 LLM 없이 저장된 답변을 토큰으로 흘린다.
    if settings.CACHE_ENABLED:
        cached = await cache.get_cached(question)
        if cached is not None:
            meta = {"model": spec, "citations": [], "session_id": session_id, "cached": True}
            yield sse(meta, EVENT_META)
            yield sse(cached, EVENT_TOKEN)
            yield sse("[DONE]", EVENT_DONE)
            if settings.MEMORY_ENABLED:
                await memory.append_message(session_id, "user", question)
                await memory.append_message(session_id, "assistant", cached)
            await persistence.save_exchange(session_id, user_id, question, cached)
            return

    from app.services.orchestrator.rag_agent import build_graph

    state = _initial_state(request, spec)
    if settings.MEMORY_ENABLED:
        state["history"] = await memory.get_history(session_id)

    graph = build_graph()
    parts: list[str] = []
    try:
        meta_sent = False
        async for ev in graph.astream_events(state, version="v2"):
            kind = ev["event"]
            if kind == "on_chat_model_stream":
                token = ev["data"]["chunk"].content
                if isinstance(token, str) and token:
                    parts.append(token)
                    yield sse(token, EVENT_TOKEN)
            elif kind == "on_chain_end" and ev.get("name") == "retrieve" and not meta_sent:
                citations = (ev["data"].get("output") or {}).get("citations", [])
                meta = {"model": spec, "citations": citations, "session_id": session_id}
                yield sse(meta, EVENT_META)
                meta_sent = True
        yield sse("[DONE]", EVENT_DONE)
    except Exception as e:  # noqa: BLE001  스트림 중 에러는 이벤트로만 알릴 수 있다
        yield sse(str(e), EVENT_ERROR)
        return

    answer = "".join(parts)
    if settings.MEMORY_ENABLED:
        await memory.append_message(session_id, "user", question)
        await memory.append_message(session_id, "assistant", answer)
    if settings.CACHE_ENABLED:
        await cache.set_cached(question, answer)
    await persistence.save_exchange(session_id, user_id, question, answer)


async def run_chat_sync(request: Any, user_id: int | None = None) -> dict:
    """[동기 응답용 — Phase 5]

    LangGraph 를 graph.ainvoke(state) 로 끝까지 돌려 최종 state 에서 답변/출처를 꺼낸다.
    endpoints/chat.py 에서 이 반환값을 ChatResponse 로 직렬화한다.
    """
    from app.core.config import settings
    from app.services import cache, memory, persistence

    spec = request.model or settings.DEFAULT_CHAT_MODEL
    session_id = request.session_id
    question = request.question

    # [개발 편의 가드] 챗 LLM 키가 없으면 난해한 인증 에러 대신
    # 안내 값을 answer 로 그대로 돌려준다. (키 채우면 자동 해제)
    if not settings.ANTHROPIC_API_KEY:
        return {
            "answer": NO_API_KEY_MESSAGE, "citations": [], "model": spec, "session_id": session_id,
        }

    # [캐시] 같은 질문이면 LLM 없이 캐시된 답변 반환(히트 시 citations 는 비움).
    if settings.CACHE_ENABLED:
        cached = await cache.get_cached(question)
        if cached is not None:
            if settings.MEMORY_ENABLED:
                await memory.append_message(session_id, "user", question)
                await memory.append_message(session_id, "assistant", cached)
            await persistence.save_exchange(session_id, user_id, question, cached)
            return {
                "answer": cached, "citations": [], "model": spec,
                "session_id": session_id, "cached": True,
            }

    from app.services.orchestrator.rag_agent import build_graph

    state = _initial_state(request, spec)
    if settings.MEMORY_ENABLED:
        state["history"] = await memory.get_history(session_id)

    final = await build_graph().ainvoke(state)
    answer = final.get("answer", "")
    citations = final.get("citations", [])

    if settings.MEMORY_ENABLED:
        await memory.append_message(session_id, "user", question)
        await memory.append_message(session_id, "assistant", answer)
    if settings.CACHE_ENABLED:
        await cache.set_cached(question, answer)
    await persistence.save_exchange(session_id, user_id, question, answer)

    return {
        "answer": answer,
        "citations": citations,
        "model": final.get("model", spec),
        "session_id": session_id,
    }
