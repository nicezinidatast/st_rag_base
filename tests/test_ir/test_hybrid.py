"""Phase 4: dense + BM25 혼합 검색(RRF 융합) 테스트.

임베딩/Qdrant 를 가짜로 끼워 RRF 순수 함수와 HybridRetriever 흐름을 검증한다.
"""

from __future__ import annotations

import app.services.ir.vector.search as search_module
from app.services.ir.base import RetrievedChunk
from app.services.ir.vector.search import HybridRetriever, reciprocal_rank_fusion


def _chunk(content, source_id="d"):
    return RetrievedChunk(content=content, score=0.0, source_id=source_id, metadata={})


# ── RRF 순수 함수 ────────────────────────────────────────────────────


def test_rrf_ranks_items_found_by_both_engines_highest():
    dense = [_chunk("A", "d1"), _chunk("B", "d2"), _chunk("C", "d3")]
    sparse = [_chunk("C", "d3"), _chunk("A", "d1"), _chunk("D", "d4")]
    fused = reciprocal_rank_fusion([dense, sparse])
    assert {c.content for c in fused[:2]} == {"A", "C"}  # 양쪽에 다 나온 게 위로
    assert fused[0].content == "A"  # dense1 + sparse2 가 최고점


def test_rrf_empty_inputs():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


# ── HybridRetriever 흐름 ─────────────────────────────────────────────


class _Point:
    def __init__(self, payload, score=0.0):
        self.payload = payload
        self.score = score


class _QueryResp:
    def __init__(self, points):
        self.points = points


class _FakeEmbedder:
    dim = 3

    async def aembed_query(self, text):
        return [0.1, 0.2, 0.3]


class _FakeClient:
    async def collection_exists(self, name):
        return True

    async def query_points(self, **kwargs):  # dense 후보
        return _QueryResp(
            [
                _Point({"content": "alpha", "source_id": "d1", "metadata": {}}, 0.9),
                _Point({"content": "beta", "source_id": "d2", "metadata": {}}, 0.7),
            ]
        )

    async def scroll(self, collection_name, limit, offset=None, **kwargs):  # BM25 코퍼스
        if offset is None:
            return (
                [
                    _Point({"content": "alpha", "source_id": "d1", "metadata": {}}),
                    _Point({"content": "gamma", "source_id": "d3", "metadata": {}}),
                ],
                None,
            )
        return ([], None)


async def test_hybrid_fuses_dense_and_bm25(monkeypatch):
    monkeypatch.setattr(search_module, "get_embedder", lambda spec=None: _FakeEmbedder())
    monkeypatch.setattr(search_module, "get_vector_client", lambda: _FakeClient())

    chunks = await HybridRetriever().retrieve("alpha", top_k=5)
    contents = [c.content for c in chunks]
    assert "alpha" in contents  # dense + BM25 양쪽에 나옴
    assert chunks[0].content == "alpha"  # 양쪽이 찾은 청크가 최상위


async def test_hybrid_empty_when_collection_missing(monkeypatch):
    class _Missing(_FakeClient):
        async def collection_exists(self, name):
            return False

    monkeypatch.setattr(search_module, "get_embedder", lambda spec=None: _FakeEmbedder())
    monkeypatch.setattr(search_module, "get_vector_client", lambda: _Missing())

    assert await HybridRetriever().retrieve("alpha") == []
