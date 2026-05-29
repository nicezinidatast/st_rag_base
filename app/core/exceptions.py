"""도메인 예외 + FastAPI 예외 핸들러(main 에서 등록).

[구현 가이드]
- AppError 하위로 상황별 예외를 늘리고, main.py 에서 app.add_exception_handler 로
  일관된 JSON 에러 응답(예: {"error": ..., "trace_id": ...})으로 변환.
- *** 스트리밍 주의: SSE 응답은 이미 200 으로 시작됐을 수 있어 HTTP 상태코드로
  에러를 못 알린다. 스트림 도중 에러는 streaming.py 의 EVENT_ERROR 이벤트로 전달. ***
"""
from __future__ import annotations


class AppError(Exception):
    status_code: int = 500

    def __init__(self, message: str = "internal error") -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404


class UnauthorizedError(AppError):
    status_code = 401
