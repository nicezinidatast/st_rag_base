"""통합 적재(Ingest) 엔드포인트 — Vector / Graph 저장소에 동시/선택 적재.

[구현 가이드]
- 실제 적재는 여기서 하지 말 것. app/workers/tasks.ingest_document 로 enqueue 하고
  즉시 202(Accepted) + 작업ID 반환 (무거운 작업이므로). workers/tasks.py 주석 참고.
- targets(vector/graph)에 따라 워커가 분기 처리한다.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.schemas.document import DocumentUpload

router = APIRouter()


@router.post("/ingest")
async def ingest(payload: DocumentUpload) -> dict:
    # TODO: 워커 큐에 적재 작업 enqueue
    return {"status": "queued", "targets": [t.value for t in payload.targets]}
