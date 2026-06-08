"""Phase 4: 재정렬(rerank) 테스트. 리랭커 클라이언트를 가짜로 끼운다."""

from __future__ import annotations

import app.services.ir.vector.rerank as rerank_module
from app.clients.reranker import RerankResult
from app.services.ir.base import RetrievedChunk


def _chunk(content, source_id="d"):
    return RetrievedChunk(content=content, score=0.1, source_id=source_id, metadata={})


class _FakeReranker:
    """입력을 역순으로 재정렬했다고 가정하는 가짜 리랭커."""

    async def arerank(self, query, documents, top_n=5):
        order = list(range(len(documents)))[::-1][:top_n]
        return [
            RerankResult(index=i, score=1.0 - n * 0.1, document=documents[i])
            for n, i in enumerate(order)
        ]


async def test_rerank_reorders_and_truncates(monkeypatch):
    monkeypatch.setattr(rerank_module, "get_reranker", lambda spec=None: _FakeReranker())
    chunks = [_chunk("a", "d1"), _chunk("b", "d2"), _chunk("c", "d3")]
    out = await rerank_module.rerank("q", chunks, top_n=2)
    assert [c.content for c in out] == ["c", "b"]  # 역순 상위 2개
    assert out[0].score == 1.0  # 리랭커 점수로 교체됨


async def test_rerank_graceful_when_no_provider(monkeypatch):
    def _boom(spec=None):
        raise NotImplementedError("provider 미구현")

    monkeypatch.setattr(rerank_module, "get_reranker", _boom)
    chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
    out = await rerank_module.rerank("q", chunks, top_n=2)
    assert [c.content for c in out] == ["a", "b"]  # 원래 순서 유지, top_n 만


async def test_rerank_empty_input():
    assert await rerank_module.rerank("q", []) == []
