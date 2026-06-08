"""Phase 10: rag_mode=AUTO 자동 라우팅(규칙 기반) 테스트.

route() 는 질문 텍스트만 보는 순수 함수라 LLM/DB 없이 검증한다.
retrieve 노드가 auto 일 때 route() 결과대로 엔진을 고르는지도 함께 본다.
"""

from __future__ import annotations

import app.services.orchestrator.routing as routing_module
from app.core.config import settings
from app.schemas.chat import RagMode
from app.services.ir.base import RetrievedChunk
from app.services.workflow.nodes.retrieve import retrieve

# ── route() 규칙 단위 ────────────────────────────────────────────────


async def test_route_summary_question_to_global():
    assert await routing_module.route("문서 전체를 요약해줘") == RagMode.GRAPH_GLOBAL


async def test_route_english_overview_to_global():
    assert await routing_module.route("give me an overview") == RagMode.GRAPH_GLOBAL


async def test_route_relationship_question_to_local():
    assert await routing_module.route("서울과 한강의 관계는?") == RagMode.GRAPH_LOCAL


async def test_route_plain_question_defaults_to_vector():
    assert await routing_module.route("모형 검증 방법론 알려줘") == RagMode.VECTOR


# ── retrieve 노드 연결 (auto → route → 해당 엔진) ────────────────────


class _FakeRetriever:
    def __init__(self, chunks=None):
        self._chunks = chunks or []

    async def retrieve(self, query, top_k=5, **kwargs):
        return self._chunks


async def test_retrieve_auto_follows_router_choice(monkeypatch):
    """rag_mode=auto 면 retrieve 가 route() 가 고른 엔진을 쓴다."""
    import app.services.ir.graph.search.global_ as global_module

    monkeypatch.setattr(settings, "MOCK_RETRIEVER", False)

    async def _fake_route(query):
        return RagMode.GRAPH_GLOBAL

    monkeypatch.setattr(routing_module, "route", _fake_route)
    chunk = RetrievedChunk(content="요지", score=0.7, source_id="community:c0", metadata={})
    monkeypatch.setattr(global_module, "GlobalGraphRetriever", lambda: _FakeRetriever([chunk]))

    out = await retrieve({"query": "전체 요약", "top_k": 5, "rag_mode": "auto"})
    assert out["citations"][0]["source_id"] == "community:c0"
