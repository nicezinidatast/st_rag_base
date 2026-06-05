"""통합 적재(Ingest) 엔드포인트 — Vector / Graph 저장소에 동시/선택 적재.

[Phase 3 — 임시: 엔드포인트에서 직접 적재]
- 원래는 무거운 작업이라 워커 큐로 보내야 하지만(Phase 8), 지금은 단순함을 위해
  vector ingest 를 직접 await 한다. content(인라인)만 지원(uri 적재는 추후).
- graph target 은 Phase 9 에서 연결.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.document import DocumentUpload, IngestTarget

router = APIRouter()


@router.post("/ingest")
async def ingest(payload: DocumentUpload) -> dict:
    if payload.content is None:
        raise HTTPException(
            status_code=400, detail="content 가 필요합니다 (Phase 3 는 인라인 content 만 지원)."
        )

    result: dict = {"status": "ingested", "source_id": payload.source_id}
    if IngestTarget.VECTOR in payload.targets:
        from app.services.ir.vector.ingest import ingest as vector_ingest

        result["vector_chunks"] = await vector_ingest(
            payload.source_id, payload.content, payload.metadata
        )
    # IngestTarget.GRAPH → Phase 9
    return result
