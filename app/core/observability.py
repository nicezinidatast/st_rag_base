"""[관측성] Langfuse 기반 LLM 트레이싱 기본 틀.

[왜 필요한가]
- RAG 는 "왜 이런 답이 나왔는가"를 추적하기 어렵다. 어떤 청크를 검색했고, 어떤
  프롬프트로 LLM 을 불렀고, 토큰/지연/비용이 얼마였는지를 한 trace 안에 묶어
  시각화해야 품질을 개선할 수 있다. Langfuse 가 그 역할을 한다.
- 한 요청(trace) 안에 여러 span(검색, 리랭크, LLM 호출 등)을 중첩해 기록한다.

[어떻게 연결되나]
1. main.py lifespan 에서 init_langfuse() 1회 호출.
2. 노드/서비스 함수에 @observe() 데코레이터를 붙이거나, get_langfuse() 로 클라이언트를
   받아 수동 span 을 만든다.
3. LangGraph 를 쓸 경우 langfuse 의 CallbackHandler 를 graph 실행 config 에 넣으면
   노드 실행이 자동으로 trace 된다. (rag_agent.py 구현 시 연결)
4. trace 의 id 를 middleware 의 trace_id 와 맞춰두면 로그 ↔ 트레이스가 연결된다.

[구현 상태]
- 키가 없거나 LANGFUSE_ENABLED=false 면 전부 no-op (운영 안전).
- 실제 langfuse 패키지 연동부는 TODO. 지금은 인터페이스/안전가드만 잡아둔 틀이다.
"""
from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# 전역 클라이언트 핸들 (init 후 채워짐). 직접 접근하지 말고 get_langfuse() 사용.
_langfuse_client: Any | None = None


def init_langfuse() -> None:
    """Langfuse 클라이언트 초기화. main.py lifespan 에서 1회 호출.

    TODO(구현):
        from langfuse import Langfuse
        global _langfuse_client
        _langfuse_client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
    """
    global _langfuse_client
    if not settings.LANGFUSE_ENABLED:
        logger.info("langfuse_disabled")
        return
    if not (settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY):
        logger.warning("langfuse_enabled_but_keys_missing")
        return
    # TODO: 위 docstring 의 실제 초기화 코드를 여기에 작성
    logger.info("langfuse_init_placeholder")


def get_langfuse() -> Any | None:
    """초기화된 Langfuse 클라이언트 반환 (없으면 None → 호출부에서 no-op 처리)."""
    return _langfuse_client


def get_langgraph_callback() -> Any | None:
    """LangGraph 실행 config 에 넣을 Langfuse CallbackHandler 반환.

    TODO(구현):
        from langfuse.callback import CallbackHandler
        return CallbackHandler(...)  # 비활성화면 None
    사용 예 (rag_agent.py):
        cb = get_langgraph_callback()
        config = {"callbacks": [cb]} if cb else {}
        await graph.ainvoke(state, config=config)
    """
    return None


def shutdown_langfuse() -> None:
    """버퍼에 남은 트레이스를 flush. main.py shutdown 에서 호출.

    TODO(구현): if _langfuse_client: _langfuse_client.flush()
    """
    if _langfuse_client is not None:
        logger.info("langfuse_flush_placeholder")
