"""요청 컨텍스트 미들웨어 — 요청마다 고유 trace id 를 발급/전파한다.

[왜 필요한가]
- 분산/비동기 환경에서 "이 로그가 어느 요청에서 나왔는지"를 묶어줄 키가 필요하다.
- contextvars 에 trace_id 를 심어두면, 같은 요청 흐름 안에서 호출되는 어떤
  함수(서비스/노드/클라이언트)든 인자로 넘기지 않고도 동일한 id 를 꺼내 쓸 수 있다.
- 응답 헤더(X-Request-ID)로도 돌려줘서, 클라이언트/프론트가 문제 신고 시 그 id 를
  첨부하면 서버 로그에서 바로 찾을 수 있다.

[어떻게 연결되나]
- main.py 에서 가장 바깥 미들웨어로 등록(가장 먼저 실행 → 모든 후속 로직이 id 공유).
- utils/logger.py 의 structlog 가 contextvars 를 자동 병합하므로, 한 번 bind 하면
  이후 모든 로그 라인에 trace_id 가 자동으로 찍힌다.

이 파일은 "동작하는 기본 틀"이다. 그대로 써도 되고, 헤더 이름/생성 규칙만 바꾸면 된다.
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# 요청 흐름 전역에서 공유되는 trace id. 어디서든 get_trace_id() 로 읽는다.
_trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="-")

REQUEST_ID_HEADER = "X-Request-ID"


def get_trace_id() -> str:
    """현재 요청의 trace id 를 반환 (요청 컨텍스트 밖이면 '-')."""
    return _trace_id_ctx.get()


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 클라이언트가 보낸 id 를 존중하고(엣지 게이트웨이 추적 연계), 없으면 새로 발급.
        trace_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        _trace_id_ctx.set(trace_id)

        # structlog 컨텍스트에 bind → 이후 모든 로그에 자동 포함.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(trace_id=trace_id)

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = trace_id
        return response
