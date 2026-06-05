"""ir/graph/search: local(엔티티 카드 조립) + global(map-reduce) 테스트."""
from __future__ import annotations

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

import app.clients.chat_model as chat_model_module
import app.services.ir.graph.search.global_ as global_module
from app.services.ir.graph.search.global_ import GlobalGraphRetriever
from app.services.ir.graph.search.local import (
    LocalGraphRetriever,
    build_chunks,
    sanitize_fulltext_query,
)


def _row(name, score, neighbors=None, source_ids=None):
    return {
        "name": name,
        "type": "LOCATION",
        "description": f"{name} 설명",
        "source_ids": source_ids or ["doc-1"],
        "score": score,
        "neighbors": neighbors or [],
    }


def test_sanitize_strips_lucene_specials():
    assert sanitize_fulltext_query('서울+수도 AND "관계"?') == "서울 수도 AND  관계"


def test_build_chunks_normalizes_scores_and_formats_neighbors():
    rows = [
        _row(
            "서울",
            4.0,
            neighbors=[
                {"type": "CAPITAL_OF", "desc": "수도 관계", "other": "대한민국", "other_desc": None}
            ],
        ),
        _row("부산", 2.0),
    ]
    chunks = build_chunks(rows, top_k=5)
    assert chunks[0].score == 1.0 and chunks[1].score == 0.5
    assert "서울 -[CAPITAL_OF]- 대한민국" in chunks[0].content
    assert chunks[0].source_id == "doc-1"
    assert chunks[0].metadata["entity"] == "서울"


def test_build_chunks_respects_top_k():
    chunks = build_chunks([_row("a", 2.0), _row("b", 1.0)], top_k=1)
    assert len(chunks) == 1


async def test_local_retriever_blank_after_sanitize_returns_empty():
    # lucene 특수문자만 있는 질의 → 드라이버 접근 전에 빈 결과
    assert await LocalGraphRetriever().retrieve("?:!*") == []


# ── Global Search ────────────────────────────────────────────────────


async def test_global_retriever_maps_filters_and_normalizes(monkeypatch):
    reports = [
        {"id": "c0", "report": "리포트0", "score": 2.0},
        {"id": "c1", "report": "리포트1", "score": 1.0},
    ]
    answers = {"리포트0": "부분답변0", "리포트1": "관련 없음"}

    async def _fake_fetch(query, top_k):
        return reports

    async def _fake_map(query, report):
        return answers[report]

    monkeypatch.setattr(global_module, "_fetch_reports", _fake_fetch)
    monkeypatch.setattr(global_module, "_map_one", _fake_map)

    chunks = await GlobalGraphRetriever().retrieve("전체 주제는?")

    assert len(chunks) == 1  # "관련 없음" 은 버려진다
    assert chunks[0].content == "부분답변0"
    assert chunks[0].score == 1.0  # 최댓값 정규화
    assert chunks[0].source_id == "community:c0"
    assert chunks[0].metadata["engine"] == "graph_global"


async def test_global_retriever_empty_without_reports(monkeypatch):
    async def _fake_fetch(query, top_k):
        return []

    monkeypatch.setattr(global_module, "_fetch_reports", _fake_fetch)
    assert await GlobalGraphRetriever().retrieve("질문") == []


async def test_map_one_calls_llm_with_prompt(monkeypatch):
    monkeypatch.setattr(
        chat_model_module,
        "get_chat_model",
        lambda spec=None: GenericFakeChatModel(messages=iter([AIMessage(content="부분답변")])),
    )
    assert await global_module._map_one("질문", "리포트") == "부분답변"
