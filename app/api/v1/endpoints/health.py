"""헬스체크 — 로드밸런서/쿠버네티스 probe 용. (현재 동작하는 엔드포인트)

- /health (liveness): 프로세스 살아있음.
- /ready  (readiness): 다운스트림(DB/Redis/Vector/Graph) 연결 가능 여부.
  [구현 가이드] 각 커넥션에 ping 을 보내 하나라도 죽으면 503 반환하도록 확장.
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> dict[str, str]:
    # TODO: DB/Redis/Vector/Graph 핑 후 실패 시 503
    return {"status": "ready"}
