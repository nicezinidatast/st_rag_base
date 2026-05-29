"""채팅 엔드포인트 — 오케스트레이터(LangGraph) 호출. SSE 스트리밍 + 동기 둘 다 지원.

[이 엔드포인트의 책임]
- 오직 "HTTP 계층 분기"만 한다: request.stream 값에 따라
    · True  → EventSourceResponse 로 generator(stream_chat) 를 감싸 SSE 스트리밍
    · False → run_chat_sync 결과를 ChatResponse(JSON) 로 반환
- 실제 검색/생성 로직은 여기 두지 말 것. orchestrator/ 와 utils/streaming.py 가 담당.

[구현 가이드]
- stream_chat / run_chat_sync 본체는 app/utils/streaming.py 에 작성.
- 인증이 필요하면 Depends(get_current_user) 추가.
- StreamingResponse vs generator 의 차이는 utils/streaming.py 상단 주석 참고.
"""
from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from app.schemas.chat import ChatRequest, ChatResponse
from app.utils.streaming import run_chat_sync, stream_chat

router = APIRouter()


@router.post("")
async def chat(request: ChatRequest):
    """기본은 스트리밍(SSE). request.stream=False 면 동기 JSON 응답.

    *** 동작 흐름 ***
      스트리밍: [LangGraph astream_events] → stream_chat(generator) → EventSourceResponse
      동기:     [LangGraph ainvoke]        → run_chat_sync(dict)    → JSONResponse
    """
    if request.stream:
        # generator 를 SSE 포장지로 감싼다. media_type 은 sse-starlette 가 자동 설정.
        return EventSourceResponse(stream_chat(request))

    # 동기 경로: 전체 답변을 만들어 한 번에 반환.
    result = await run_chat_sync(request)
    response = ChatResponse(
        session_id=request.session_id or str(uuid4()),
        answer=result["answer"],
        citations=result.get("citations", []),
        rag_mode=request.rag_mode,
        model=result["model"],
    )
    return JSONResponse(response.model_dump())
