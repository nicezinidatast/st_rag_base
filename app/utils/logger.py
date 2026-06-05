"""구조화 로그(structlog) + stdlib 통합 — 콘솔 + 회전 파일, 요청별 trace id 자동 포함.

[설계]
- structlog 를 **stdlib logging 위에** 얹는다(ProcessorFormatter). 그래서:
    · 우리 로그(get_logger)와 uvicorn 로그(uvicorn/uvicorn.access)가 **같은 핸들러**로 모인다.
    · 핸들러 = 콘솔(stdout) + 회전 파일(logs/app.log). 둘 다 같은 포맷 체인을 공유.
    · 콘솔은 사람이 읽기 좋은 컬러 렌더(개발), 파일은 JSON 한 줄(검색/적재용).
- middleware/request_context.py 가 trace_id 를 contextvars 에 bind 하면
  merge_contextvars 가 모든 라인에 자동으로 trace_id 를 끼운다(매번 넘길 필요 없음).
- configure_logging() 은 main.py lifespan 에서 1회 호출.
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

import structlog

from app.core.config import settings

# 포맷터 직전까지 공유하는 프로세서 체인(우리 로그 + 외부 stdlib 로그 공통).
_SHARED_PROCESSORS: list = [
    structlog.contextvars.merge_contextvars,   # trace_id 자동 병합
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]

_ROTATE_BYTES = 10 * 1024 * 1024  # 10MB
_ROTATE_BACKUPS = 5


def _level_int(level: str) -> int:
    return getattr(logging, level.upper(), logging.INFO)


def _make_formatter(json_output: bool) -> structlog.stdlib.ProcessorFormatter:
    """stdlib LogRecord(우리 + uvicorn) → 최종 렌더(JSON 또는 컬러 콘솔)."""
    renderer = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())
    )
    return structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_SHARED_PROCESSORS,  # structlog 를 안 거친 로그(uvicorn)용
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )


def configure_logging(level: str | None = None) -> None:
    """structlog+stdlib 로깅 설정. 시작 시 1회(main.py lifespan)."""
    lvl = _level_int(level or settings.LOG_LEVEL)

    # Windows 콘솔 한글 깨짐 방지(가능한 환경에서만).
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

    # 1) structlog: 메시지를 가공해 stdlib LogRecord 로 넘긴다(wrap_for_formatter).
    structlog.configure(
        processors=[
            *_SHARED_PROCESSORS,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 2) 핸들러: 콘솔(stdout) + 회전 파일.
    handlers: list[logging.Handler] = []

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(_make_formatter(json_output=settings.LOG_JSON_CONSOLE))
    handlers.append(console)

    if settings.LOG_FILE:
        path = Path(settings.LOG_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=_ROTATE_BYTES, backupCount=_ROTATE_BACKUPS, encoding="utf-8"
        )
        file_handler.setFormatter(_make_formatter(json_output=True))  # 파일은 항상 JSON
        handlers.append(file_handler)

    # 3) 루트 로거에 핸들러 부착(중복 방지 위해 기존 핸들러 제거).
    root = logging.getLogger()
    root.handlers.clear()
    for h in handlers:
        root.addHandler(h)
    root.setLevel(lvl)

    # 4) uvicorn 로거는 자체 핸들러를 떼고 루트로 흘려보낸다 → 콘솔+파일에 함께 기록.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True


def get_logger(name: str | None = None):
    return structlog.get_logger(name)
