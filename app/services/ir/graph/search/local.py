"""Local Search: 특정 엔티티 주변 이웃 노드 기반 미시적 검색.

[Phase 9 — 동작]
1. 질문을 풀텍스트 인덱스(entity_fulltext)에 던져 앵커 엔티티 top-N 매칭.
   검색 경로 LLM 0회 — 빠르고 저렴 (LLM 엔티티 인식은 Phase 10 analyze 고도화 때).
2. 앵커의 1-hop 이웃/관계를 모아 "엔티티 카드" 텍스트로 RetrievedChunk 조립.
3. score 는 lucene 점수를 최댓값으로 정규화(0~1), 출처는 엔티티 source_ids.
"""
from __future__ import annotations

import re

from app.core.graph_db import get_graph_driver
from app.services.ir.base import RetrievedChunk, Retriever

_ANCHORS = 3  # 질문당 앵커 엔티티 수

# lucene 쿼리 파싱 에러를 막기 위한 특수문자 제거
_LUCENE_SPECIALS = re.compile(r'[+\-&|!(){}\[\]^"~*?:\\/]')

_LOCAL_QUERY = """
CALL db.index.fulltext.queryNodes('entity_fulltext', $q) YIELD node, score
WITH node, score ORDER BY score DESC LIMIT $anchors
OPTIONAL MATCH (node)-[r:RELATED]-(nb:Entity)
RETURN node.name AS name, node.type AS type, node.description AS description,
       node.source_ids AS source_ids, score,
       collect({type: r.type, desc: r.description, other: nb.name,
                other_desc: nb.description}) AS neighbors
ORDER BY score DESC
"""


def sanitize_fulltext_query(query: str) -> str:
    """lucene 특수문자를 공백으로 치환 (global_ 도 같이 쓴다)."""
    return _LUCENE_SPECIALS.sub(" ", query).strip()


class LocalGraphRetriever(Retriever):
    async def retrieve(self, query: str, top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        q = sanitize_fulltext_query(query)
        if not q:
            return []
        async with get_graph_driver().session() as session:
            result = await session.run(_LOCAL_QUERY, q=q, anchors=_ANCHORS)
            rows = [dict(rec) async for rec in result]
        return build_chunks(rows, top_k)


def build_chunks(rows: list[dict], top_k: int) -> list[RetrievedChunk]:
    """앵커별 '엔티티 카드' 텍스트 조립. (순수 함수 — 단위 테스트 대상)"""
    if not rows:
        return []
    max_score = max(r["score"] for r in rows) or 1.0
    chunks = []
    for row in rows[:top_k]:
        lines = [f"{row['name']} ({row['type']}): {row['description'] or ''}"]
        for nb in row["neighbors"]:
            if nb.get("other"):
                lines.append(
                    f"- {row['name']} -[{nb['type']}]- {nb['other']}: "
                    f"{nb.get('desc') or nb.get('other_desc') or ''}"
                )
        source_ids = row.get("source_ids") or []
        chunks.append(
            RetrievedChunk(
                content="\n".join(lines),
                score=float(row["score"]) / float(max_score),
                source_id=source_ids[0] if source_ids else row["name"],
                metadata={"engine": "graph_local", "entity": row["name"]},
            )
        )
    return chunks
