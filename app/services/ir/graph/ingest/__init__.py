"""[GraphRAG 컴포넌트] ingest 파이프라인: 청킹 → 추출 → 적재 → 군집 → 요약.

[Phase 9 — 비용 주의] 청크 수 + 커뮤니티 수만큼 LLM 호출이 발생한다.
무거우면 Phase 8 에서 workers/tasks.py 로 옮긴다(vector ingest 와 동일 계획).
"""
from __future__ import annotations

from app.core.graph_db import ensure_schema, get_graph_driver
from app.schemas.graph import Subgraph
from app.utils.logger import get_logger
from app.utils.text import clean_text

logger = get_logger(__name__)

# 추출엔 넓은 문맥이 유리해 vector(800)보다 큰 청크를 쓴다.
_CHUNK_SIZE = 1200
_CHUNK_OVERLAP = 100

_UPSERT_ENTITIES = """
UNWIND $entities AS ent
MERGE (e:Entity {name: ent.name})
SET e.type = ent.type,
    e.description = CASE
        WHEN size(coalesce(ent.description, '')) > size(coalesce(e.description, ''))
        THEN ent.description ELSE e.description END,
    e.source_ids = CASE
        WHEN $source_id IN coalesce(e.source_ids, []) THEN e.source_ids
        ELSE coalesce(e.source_ids, []) + $source_id END
"""

_UPSERT_RELATIONS = """
UNWIND $relations AS rel
MERGE (s:Entity {name: rel.source})
MERGE (t:Entity {name: rel.target})
MERGE (s)-[r:RELATED {type: rel.type}]->(t)
SET r.description = coalesce(rel.description, r.description),
    r.weight = coalesce(rel.weight, 1.0),
    r.source_ids = CASE
        WHEN $source_id IN coalesce(r.source_ids, []) THEN r.source_ids
        ELSE coalesce(r.source_ids, []) + $source_id END
"""


def _chunk(text: str, size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """고정 길이 슬라이딩 윈도우 (vector/ingest 와 동일 방식, 크기만 다름)."""
    if not text:
        return []
    step = max(1, size - overlap)
    return [text[i : i + size] for i in range(0, len(text), step)]


async def _upsert_subgraph(sub: Subgraph, source_id: str) -> None:
    """추출 결과를 MERGE 로 멱등 적재. 관계의 미선언 엔티티도 MERGE 로 생성된다."""
    async with get_graph_driver().session() as session:
        if sub.entities:
            await session.run(
                _UPSERT_ENTITIES,
                entities=[
                    e.model_dump(include={"name", "type", "description"}) for e in sub.entities
                ],
                source_id=source_id,
            )
        if sub.relations:
            await session.run(
                _UPSERT_RELATIONS,
                relations=[r.model_dump() for r in sub.relations],
                source_id=source_id,
            )


async def ingest(source_id: str, content: str, metadata: dict | None = None) -> dict:
    """문서를 지식그래프로 적재. 반환: 엔티티/관계/커뮤니티 수."""
    from app.services.ir.graph.ingest import cluster as cluster_module
    from app.services.ir.graph.ingest import extractor, summarizer

    await ensure_schema()

    chunks = _chunk(clean_text(content))
    n_entities = n_relations = 0
    for i, chunk in enumerate(chunks):
        try:
            sub = await extractor.extract(chunk)
        except Exception as e:  # noqa: BLE001  한 청크 실패가 전체 적재를 막지 않는다
            logger.warning("graph_extract_skip", chunk_index=i, error=str(e))
            continue
        await _upsert_subgraph(sub, source_id)
        n_entities += len(sub.entities)
        n_relations += len(sub.relations)

    communities = await cluster_module.cluster()
    for com in communities:
        await summarizer.summarize(com)

    logger.info(
        "graph_ingest_done",
        source_id=source_id,
        chunks=len(chunks),
        entities=n_entities,
        relations=n_relations,
        communities=len(communities),
    )
    return {"entities": n_entities, "relations": n_relations, "communities": len(communities)}
