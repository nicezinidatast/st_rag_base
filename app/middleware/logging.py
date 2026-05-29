"""접근 로그 + 처리 시간 측정 미들웨어.

[왜 필요한가]
- 모든 요청의 method/path/status/소요시간을 일관된 형식(JSON)으로 남겨야
  관측성(observability)이 생긴다. 엔드포인트마다 직접 찍으면 누락/불일치가 생김.

[어떻게 연결되나]
- main.py 에서 RequestContext 다음(안쪽)에 등록 → trace_id 가 이미 bind 된 상태라
  로그에 자동으로 trace_id 가 붙는다.

[스트리밍 주의]
- 여기서는 응답 *본문*을 절대 읽지 않는다(SSE 버퍼링 방지). 상태코드/시간만 측정.
- 단, SSE 는 응답이 "시작"되는 시점과 "끝나는" 시점이 다르다. 여기서 재는 시간은
  "첫 응답까지의 시간"이 아니라 "핸들러가 StreamingResponse 객체를 반환하기까지의
  시간"이다. 토큰 단위 지연(TTFT 등)은 generate 노드/스트림 제너레이터 안에서 따로
  측정해 Langfuse 로 보내는 것을 권장.

이 파일도 "동작하는 기본 틀"이다.

NOTE: time.perf_counter() 는 표준 라이브러리라 사용 가능하지만, 일부 샌드박스에서
실행이 막힐 수 있으니 그 경우 monotonic 대체 구현으로 바꾸면 된다.
"""
from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.utils.logger import get_logger

logger = get_logger(__name__)


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            elapsed_ms=round(elapsed_ms, 2),
        )
        response.headers["X-Process-Time-ms"] = str(round(elapsed_ms, 2))
        return response
