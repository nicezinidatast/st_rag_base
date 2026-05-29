"""백그라운드 태스크: 무거운 적재 + GraphRAG 인덱싱.

[왜 워커로 빼는가]
- GraphRAG 인덱싱(엔티티 추출 → Leiden 군집 → 커뮤니티 요약)과 대형문서 임베딩은
  수 초~수 분 걸린다. HTTP 요청 안에서 돌리면 타임아웃/리소스 고갈이 난다.
- 그래서 document 엔드포인트는 '작업을 큐에 넣기만' 하고 즉시 202 를 반환,
  실제 처리는 여기(ARQ/Celery 워커 프로세스)서 비동기로 한다.

[구현 가이드]
- ingest_document: targets 에 따라 ir/vector/ingest.py 와/또는
  ir/graph/ingest/* 파이프라인을 호출. 진행상황/실패는 DB 나 Redis 에 기록.
"""
from __future__ import annotations


async def ingest_document(document_id: str, targets: list[str]) -> None:
    raise NotImplementedError("적재 태스크 미구현")
