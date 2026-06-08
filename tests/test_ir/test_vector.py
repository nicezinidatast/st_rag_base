"""Vector ingest/search 단위 테스트. 임베딩과 Qdrant 클라이언트를 가짜로 끼운다."""
from __future__ import annotations

import app.services.ir.vector.ingest as ingest_module
import app.services.ir.vector.search as search_module


class _FakeEmbedder:
    dim = 3

    async def aembed_documents(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]

    async def aembed_query(self, text):
        return [0.1, 0.2, 0.3]


# ── ingest ────────────────────────────────────────────────────────
class _FakeIngestClient:
    def __init__(self):
        self.created = None
        self.upserted = None

    async def collection_exists(self, name):
        return False  # 없으면 생성 경로를 타게 한다

    async def create_collection(self, **kwargs):
        self.created = kwargs

    async def upsert(self, collection_name, points):
        self.upserted = points


async def test_ingest_chunks_embeds_and_upserts(monkeypatch):
    client = _FakeIngestClient()
    monkeypatch.setattr(ingest_module, "get_embedder", lambda spec=None: _FakeEmbedder())
    monkeypatch.setattr(ingest_module, "get_vector_client", lambda: client)

    n = await ingest_module.ingest("doc-1", "서울은 대한민국의 수도이다.", {"lang": "ko"})

    assert n == 1
    assert client.created is not None  # 컬렉션 생성됨
    assert len(client.upserted) == 1
    point = client.upserted[0]
    assert point.payload["content"] == "서울은 대한민국의 수도이다."
    assert point.payload["source_id"] == "doc-1"
    assert point.payload["metadata"] == {"lang": "ko"}


async def test_ingest_empty_content_returns_zero(monkeypatch):
    monkeypatch.setattr(ingest_module, "get_embedder", lambda spec=None: _FakeEmbedder())
    monkeypatch.setattr(ingest_module, "get_vector_client", lambda: _FakeIngestClient())

    assert await ingest_module.ingest("doc-1", "   ") == 0


# ── search ────────────────────────────────────────────────────────
class _Point:
    def __init__(self, payload, score):
        self.payload = payload
        self.score = score


class _QueryResp:
    def __init__(self, points):
        self.points = points


class _FakeSearchClient:
    def __init__(self, exists=True):
        self._exists = exists

    async def collection_exists(self, name):
        return self._exists

    async def query_points(self, **kwargs):
        return _QueryResp(
            [_Point({"content": "c1", "source_id": "doc-1", "metadata": {}}, 0.9)]
        )


async def test_search_returns_retrieved_chunks(monkeypatch):
    monkeypatch.setattr(search_module, "get_embedder", lambda spec=None: _FakeEmbedder())
    monkeypatch.setattr(search_module, "get_vector_client", lambda: _FakeSearchClient())

    chunks = await search_module.VectorRetriever().retrieve("질문", top_k=3)

    assert len(chunks) == 1
    assert chunks[0].content == "c1"
    assert chunks[0].source_id == "doc-1"
    assert chunks[0].score == 0.9


async def test_search_empty_when_collection_missing(monkeypatch):
    monkeypatch.setattr(search_module, "get_embedder", lambda spec=None: _FakeEmbedder())
    monkeypatch.setattr(
        search_module, "get_vector_client", lambda: _FakeSearchClient(exists=False)
    )

    assert await search_module.VectorRetriever().retrieve("질문") == []
