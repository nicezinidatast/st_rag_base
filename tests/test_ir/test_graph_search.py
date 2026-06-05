"""ir/graph/search: local(엔티티 카드 조립) + global(map-reduce) 테스트."""
from __future__ import annotations

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
