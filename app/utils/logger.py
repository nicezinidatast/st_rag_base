"""구조화 JSON 로그 + 요청별 trace id 자동 포함 (structlog).

[연결 관계]
- configure_logging() 은 main.py lifespan 에서 1회 호출.
- middleware/request_context.py 가 trace_id 를 contextvars 에 bind 하면,
  아래 merge_contextvars 프로세서가 모든 로그 라인에 자동으로 trace_id 를 끼워준다.
  → 즉 로그를 찍을 때 trace_id 를 매번 넘길 필요가 없다.
"""
from __future__ import annotations

import logging

import structlog


def configure_logging(level: int = logging.INFO) -> None:
    """structlog 를 JSON 출력으로 설정. 시작 시 1회."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,   # trace_id 자동 병합
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name)
