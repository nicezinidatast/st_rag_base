"""Phase 5: LangGraph 워크플로(노드 단위 + 그래프 e2e) 테스트.

실제 LLM/Qdrant 없이 VectorRetriever/get_chat_model 을 가짜로 끼워
analyze→retrieve→grade→generate 흐름과 토큰 스트리밍을 검증한다.
"""
from __future__ import annotations

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

import app.clients.chat_model as chat_model_module
import app.services.ir.vector.search as search_module
from app.services.ir.base import RetrievedChunk
from app.services.orchestrator.rag_agent import build_graph
from app.services.workflow.nodes.generate import generate
from app.services.workflow.nodes.grade import grade
from app.services.workflow.nodes.retrieve import retrieve


def _fake_chat_model(content="fake answer"):
    """LangChain BaseChatModel 대역. 공백 기준으로 토큰이 쪼개진다."""
    return GenericFakeChatModel(messages=iter([AIMessage(content=content)]))


class _FakeRetriever:
    def __init__(self, chunks=None):
        self._chunks = chunks or []

    async def retrieve(self, query, top_k=5, **kwargs):
        return self._chunks


def _chunk():
    return RetrievedChunk(
        content="서울은 대한민국의 수도이다.", score=0.9, source_id="doc-1", metadata={}
    )


# ── 노드 단위 ────────────────────────────────────────────────────────


async def test_retrieve_node_populates_context_and_citations(monkeypatch):
    monkeypatch.setattr(search_module, "VectorRetriever", lambda: _FakeRetriever([_chunk()]))
    out = await retrieve({"query": "수도?", "top_k": 5})
    assert out["context"].startswith("[1] 서울")
    assert out["citations"][0]["source_id"] == "doc-1"
    assert out["documents"][0]["score"] == 0.9


async def test_retrieve_node_empty_on_no_results(monkeypatch):
    monkeypatch.setattr(search_module, "VectorRetriever", lambda: _FakeRetriever([]))
    out = await retrieve({"query": "x", "top_k": 5})
    assert out == {"documents": [], "context": "", "citations": []}


async def test_retrieve_node_blank_query_skips_search():
    out = await retrieve({"query": "   ", "top_k": 5})
    assert out == {"documents": [], "context": "", "citations": []}


async def test_retrieve_node_routes_graph_local(monkeypatch):
    import app.services.ir.graph.search.local as local_module

    monkeypatch.setattr(local_module, "LocalGraphRetriever", lambda: _FakeRetriever([_chunk()]))
    out = await retrieve({"query": "수도?", "top_k": 5, "rag_mode": "graph_local"})
    assert out["citations"][0]["source_id"] == "doc-1"


async def test_retrieve_node_routes_graph_global(monkeypatch):
    import app.services.ir.graph.search.global_ as global_module

    monkeypatch.setattr(global_module, "GlobalGraphRetriever", lambda: _FakeRetriever([_chunk()]))
    out = await retrieve({"query": "요지?", "top_k": 5, "rag_mode": "graph_global"})
    assert out["documents"][0]["score"] == 0.9


async def test_grade_node_uses_top_document_score():
    out = await grade({"documents": [{"score": 0.3}, {"score": 0.8}]})
    assert out["grade"] == 0.8


async def test_grade_node_zero_without_documents():
    assert (await grade({}))["grade"] == 0.0


async def test_generate_node_produces_answer(monkeypatch):
    monkeypatch.setattr(chat_model_module, "get_chat_model", lambda spec=None: _fake_chat_model())
    out = await generate({"query": "안녕?", "context": "", "model": "anthropic:x"})
    assert out["answer"] == "fake answer"
    assert out["model"] == "anthropic:x"


# ── 그래프 e2e ───────────────────────────────────────────────────────


async def test_graph_end_to_end_sync(monkeypatch):
    build_graph.cache_clear()
    monkeypatch.setattr(search_module, "VectorRetriever", lambda: _FakeRetriever([_chunk()]))
    monkeypatch.setattr(chat_model_module, "get_chat_model", lambda spec=None: _fake_chat_model())

    final = await build_graph().ainvoke(
        {"query": "수도?", "rag_mode": "auto", "top_k": 5, "model": "anthropic:x"}
    )
    assert final["answer"] == "fake answer"
    assert final["citations"][0]["source_id"] == "doc-1"
    assert final["grade"] == 0.9


async def test_graph_streams_tokens_via_astream_events(monkeypatch):
    build_graph.cache_clear()
    monkeypatch.setattr(search_module, "VectorRetriever", lambda: _FakeRetriever([_chunk()]))
    monkeypatch.setattr(chat_model_module, "get_chat_model", lambda spec=None: _fake_chat_model())

    tokens = []
    citations = None
    async for ev in build_graph().astream_events(
        {"query": "수도?", "rag_mode": "auto", "top_k": 5, "model": "anthropic:x"},
        version="v2",
    ):
        if ev["event"] == "on_chat_model_stream":
            tokens.append(ev["data"]["chunk"].content)
        elif ev["event"] == "on_chain_end" and ev.get("name") == "retrieve":
            citations = ev["data"]["output"]["citations"]
    assert "".join(tokens) == "fake answer"
    assert citations[0]["source_id"] == "doc-1"
