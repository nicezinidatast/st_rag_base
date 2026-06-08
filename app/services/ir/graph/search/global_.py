"""Global Search: 커뮤니티 요약 Map-Reduce 기반 거시적 검색.

[Phase 9 — 동작]
1. 질문 관련 커뮤니티 리포트 top-k 선택 (community_fulltext 인덱스).
2. Map: 리포트별 LLM 부분답변 (asyncio.gather 동시 실행, "관련 없음" 은 버림).
3. 부분답변들을 RetrievedChunk 로 반환 → Reduce 는 generate 노드가 수행
   (컨텍스트 통합 답변 = reduce. Retriever 인터페이스를 유지하는 절충).
- 비용: 질문당 LLM ≤ top_k 회 (+generate 1회).
- 파일명이 global_.py 인 이유: 'global' 은 파이썬 예약어라 import 불가.
"""

from __future__ import annotations

import asyncio

from app.core.graph_db import get_graph_driver
from app.services.ir.base import RetrievedChunk, Retriever
from app.services.ir.graph.search.local import sanitize_fulltext_query
from app.utils.logger import get_logger

logger = get_logger(__name__)

_NOT_RELEVANT = "관련 없음"

_REPORT_QUERY = """
CALL db.index.fulltext.queryNodes('community_fulltext', $q) YIELD node, score
RETURN node.id AS id, node.report AS report, score
ORDER BY score DESC LIMIT $top_k
"""

# 풀텍스트 0건 시 폴백: 전체 리포트를 균등 점수로 Map 에 투입.
_ALL_REPORTS_QUERY = """
MATCH (c:Community)
WHERE c.report IS NOT NULL
RETURN c.id AS id, c.report AS report, 1.0 AS score
ORDER BY c.id LIMIT $top_k
"""


def _is_relevant(partial: str) -> bool:
    """Map 부분답변이 실답변인지 판단(= '관련 없음' 센티넬이 아닌지).

    LLM 이 '관련 없음.' / '관련 없음 ' 처럼 구두점·공백을 붙여도 무관으로 본다.
    """
    cleaned = partial.strip().strip(" \t\n.。!?！？")
    return bool(cleaned) and cleaned != _NOT_RELEVANT


class GlobalGraphRetriever(Retriever):
    async def retrieve(self, query: str, top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        reports = await _fetch_reports(query, top_k)
        if not reports:
            return []
        # 리포트 하나의 Map(LLM) 호출이 실패해도 나머지로 답하도록 부분 실패를 허용한다.
        partials = await asyncio.gather(
            *(_map_one(query, r["report"]) for r in reports), return_exceptions=True
        )
        failures = sum(isinstance(p, BaseException) for p in partials)
        if failures:
            logger.warning("graph_global_map_partial_fail", failed=failures, total=len(reports))
        kept = [
            (r, p)
            for r, p in zip(reports, partials, strict=True)
            if isinstance(p, str) and _is_relevant(p)
        ]
        if not kept:
            return []
        max_score = max(float(r["score"]) for r, _ in kept) or 1.0
        return [
            RetrievedChunk(
                content=partial,
                score=float(report["score"]) / max_score,
                source_id=f"community:{report['id']}",
                metadata={"engine": "graph_global", "community_id": report["id"]},
            )
            for report, partial in kept
        ]


async def _fetch_reports(query: str, top_k: int) -> list[dict]:
    q = sanitize_fulltext_query(query)
    async with get_graph_driver().session() as session:
        rows: list[dict] = []
        if q:
            result = await session.run(_REPORT_QUERY, q=q, top_k=top_k)
            rows = [dict(rec) async for rec in result if rec["report"]]
        if not rows:
            # 거시 질문("전체 요약해줘")은 리포트 본문과 어휘가 안 겹쳐 풀텍스트가
            # 0건이 되기 쉽다 → 전체 리포트로 폴백 (MS GraphRAG 의 기본 동작).
            result = await session.run(_ALL_REPORTS_QUERY, top_k=top_k)
            rows = [dict(rec) async for rec in result if rec["report"]]
    return rows


async def _map_one(query: str, report: str) -> str:
    """Map 단계: 리포트 1개 → 질문에 대한 부분답변 (무관하면 '관련 없음')."""
    from app.clients.chat_model import get_chat_model
    from app.utils.prompts import load_prompt, render

    prompt = load_prompt("graphrag/global_search")
    resp = await get_chat_model().ainvoke(
        [
            ("system", prompt["system"]),
            ("user", render(prompt["user"], query=query, report=report)),
        ]
    )
    return resp.content if isinstance(resp.content, str) else str(resp.content)
