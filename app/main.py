"""[ASGI 진입점] FastAPI 인스턴스 생성 + 미들웨어/CORS/라우터 연결.

*** 이 파일은 "실제로 동작하는" 유일한 부분이다. ***
나머지 서비스 로직은 전부 한글 주석으로 가이드만 있고 NotImplementedError 상태다.
지금 상태로도 `uvicorn app.main:app` 로 서버가 뜨고 /api/v1/health 가 응답한다.

[구현 가이드 — lifespan]
- startup 에서 DB/Redis/Vector/Graph 커넥션 풀을 열고 app.state 에 보관,
  shutdown 에서 정리한다. (지금은 TODO 주석만)
- Langfuse 클라이언트도 여기서 init_langfuse() 로 1회 초기화한다.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.observability import init_langfuse, shutdown_langfuse
from app.middleware.logging import AccessLogMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.utils.logger import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 훅. 여기서 인프라 커넥션을 열고 닫는다."""
    configure_logging()
    init_langfuse()  # Langfuse 트레이싱 초기화 (키 없거나 비활성화면 no-op)
    logger.info("startup", env=settings.ENV, app=settings.APP_NAME)

    # 임베딩 모델 워밍업: 첫 질문에서 14초 로드 대기가 걸리지 않도록 부팅 때 미리 로드.
    # MOCK_RETRIEVER 면 임베딩을 안 쓰므로 스킵(개발 중 reload 빠르게).
    if settings.EMBEDDING_WARMUP and not settings.MOCK_RETRIEVER:
        from app.clients.embedding import get_embedder

        try:
            await get_embedder().aembed_query("warmup")
            logger.info("embedding_warmup_done")
        except Exception as e:  # noqa: BLE001  워밍업 실패가 부팅을 막아선 안 됨
            logger.warning("embedding_warmup_failed", error=str(e))

    # Redis 연결 확인(대화 이력/캐시용). 미기동이어도 부팅은 막지 않고, 가용성 플래그를 내려
    # 이후 memory/cache 가 매 요청 연결 재시도 없이 즉시 건너뛰게 한다(요청 지연 0).
    if settings.MEMORY_ENABLED or settings.CACHE_ENABLED:
        from app.core import redis as _redis

        try:
            await _redis.redis_client.ping()
            _redis.set_available(True)
            logger.info("redis_connected")
        except Exception as e:  # noqa: BLE001  Redis 미기동이어도 채팅은 동작(이력/캐시만 스킵)
            _redis.set_available(False)
            logger.warning("redis_unavailable", error=str(e))

    # TODO(구현): DB/Vector/Graph 풀을 열어 app.state 에 저장
    #   app.state.db = ...
    #   app.state.vector = ...
    #   app.state.graph = ...

    yield

    logger.info("shutdown")
    shutdown_langfuse()  # 버퍼에 남은 트레이스 flush
    try:
        from app.core.redis import redis_client

        await redis_client.aclose()
    except Exception as e:  # noqa: BLE001
        logger.warning("redis_close_skipped", error=str(e))


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    # ─────────────────────────────────────────────────────────────
    # 미들웨어 등록 — *** 순서 주의: 나중에 add 한 것이 더 바깥(=먼저 실행) ***
    # 실행 순서(요청 기준): RequestContext → AccessLog → CORS → 엔드포인트
    # 따라서 add 는 "안쪽 → 바깥쪽" 역순으로 한다.
    # ─────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AccessLogMiddleware)        # 접근 로그/시간 측정
    app.add_middleware(RequestContextMiddleware)   # trace id 발급 (가장 바깥)

    # 라우터 연결
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # 테스트 UI — 빌드 없는 단일 HTML. http://localhost:8000/ui 로 접속.
    app.mount("/ui", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="ui")
    return app


app = create_app()
