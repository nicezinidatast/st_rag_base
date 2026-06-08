"""[관측성] Langfuse 기반 LLM 트레이싱 (Phase 11).

[왜 필요한가]
- RAG 는 "왜 이런 답이 나왔는가"를 추적하기 어렵다. 어떤 청크를 검색했고, 어떤
  프롬프트로 LLM 을 불렀고, 토큰/지연/비용이 얼마였는지를 한 trace 안에 묶어
  시각화해야 품질을 개선할 수 있다. Langfuse 가 그 역할을 한다.
- 한 요청(trace) 안에 여러 span(검색, 리랭크, LLM 호출 등)이 중첩 기록된다.

[어떻게 연결되나]
1. main.py lifespan 에서 init_langfuse() 1회 호출 (키 없거나 비활성화면 no-op).
2. utils/streaming.py 가 graph 실행 config 에 get_langgraph_callback() 핸들러를 넣으면
   LangGraph 노드(analyze→retrieve→grade→generate)와 LLM 호출이 자동으로 trace 된다.
3. trace id 를 middleware 의 trace_id(X-Request-ID)와 맞춰 로그 ↔ 트레이스가 연결된다.
   (uuid4().hex 가 W3C trace id 형식(32 hex)과 같아 그대로 쓸 수 있다.)
4. session_id/user_id 는 config metadata 의 langfuse_session_id/langfuse_user_id 로 전달
   → Langfuse 대시보드에서 세션/사용자 단위로 묶여 보인다.

[SDK 주의] langfuse v3+(OTel 기반) API 를 쓴다 — v2 의 `langfuse.callback` 모듈은 없다.
"""
from __future__ import annotations

import re
from typing import Any

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# 전역 클라이언트 핸들 (init 후 채워짐). 직접 접근하지 말고 get_langfuse() 사용.
_langfuse_client: Any | None = None

# W3C trace id = 32자리 소문자 hex. middleware 의 uuid4().hex 가 정확히 이 형식.
_TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def init_langfuse() -> None:
    """Langfuse 클라이언트 초기화. main.py lifespan 에서 1회 호출."""
    global _langfuse_client
    if not settings.LANGFUSE_ENABLED:
        logger.info("langfuse_disabled")
        return
    if not (settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY):
        logger.warning("langfuse_enabled_but_keys_missing")
        return

    from langfuse import Langfuse

    _langfuse_client = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        base_url=settings.LANGFUSE_HOST,
        environment=settings.ENV,
    )
    logger.info("langfuse_initialized", host=settings.LANGFUSE_HOST)


def get_langfuse() -> Any | None:
    """초기화된 Langfuse 클라이언트 반환 (없으면 None → 호출부에서 no-op 처리)."""
    return _langfuse_client


def get_langgraph_callback() -> Any | None:
    """LangGraph 실행 config 에 넣을 Langfuse CallbackHandler 반환 (비활성화면 None).

    요청 미들웨어의 trace_id 가 W3C 형식이면 Langfuse trace id 로 그대로 사용해
    `X-Request-ID` ↔ Langfuse trace 가 1:1 로 연결된다. (클라이언트가 임의 형식의
    X-Request-ID 를 보낸 경우엔 Langfuse 가 자체 발급하도록 둔다.)
    """
    if _langfuse_client is None:
        return None

    from langfuse.langchain import CallbackHandler

    from app.middleware.request_context import get_trace_id

    trace_id = get_trace_id()
    if _TRACE_ID_RE.match(trace_id):
        return CallbackHandler(trace_context={"trace_id": trace_id})
    return CallbackHandler()


def build_graph_config(session_id: str | None, user_id: int | None = None) -> dict:
    """graph.ainvoke/astream_events 에 넘길 config 생성 (트레이싱 꺼져 있으면 {}).

    metadata 의 langfuse_* 키는 CallbackHandler 가 trace 속성으로 승격한다.
    """
    callback = get_langgraph_callback()
    if callback is None:
        return {}
    metadata: dict[str, str] = {}
    if session_id:
        metadata["langfuse_session_id"] = session_id
    if user_id is not None:
        metadata["langfuse_user_id"] = str(user_id)
    return {"callbacks": [callback], "metadata": metadata}


def shutdown_langfuse() -> None:
    """버퍼에 남은 트레이스를 flush. main.py shutdown 에서 호출."""
    if _langfuse_client is not None:
        _langfuse_client.flush()
        logger.info("langfuse_flushed")
