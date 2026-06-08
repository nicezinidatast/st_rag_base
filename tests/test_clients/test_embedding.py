"""OpenAIEmbedder 단위 테스트. 실제 OpenAI 호출은 하지 않는다."""
from __future__ import annotations

from app.clients.embedding import (
    OpenAIEmbedder,
    SentenceTransformerEmbedder,
    get_embedder,
)
from app.core.config import settings


def test_get_embedder_builds_local_bge_m3():
    """"st:BAAI/bge-m3" 스펙이 로컬 임베더로 빌드되는지(키 불필요)."""
    emb = get_embedder("st:BAAI/bge-m3")
    assert isinstance(emb, SentenceTransformerEmbedder)
    assert emb.model_name == "BAAI/bge-m3"
    assert emb.dim == 1024  # 모델 로드 없이 상수 매핑으로 결정


def test_get_embedder_returns_openai_instance(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    emb = get_embedder("openai:text-embedding-3-small")
    assert isinstance(emb, OpenAIEmbedder)
    assert emb.dim == 1536


async def test_st_embedder_encodes_via_model(monkeypatch):
    """sentence-transformers 모델을 가짜로 끼워 인코딩 경로를 검증(실모델 로드 X)."""
    import numpy as np

    emb = SentenceTransformerEmbedder("BAAI/bge-m3")

    class _FakeModel:
        def encode(self, texts, normalize_embeddings=False):
            return np.array([[0.1, 0.2, 0.3] for _ in texts])

    emb._model = _FakeModel()  # 지연 로드 우회

    docs = await emb.aembed_documents(["a", "b"])
    assert docs == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]

    query = await emb.aembed_query("q")
    assert query == [0.1, 0.2, 0.3]


async def test_aembed_documents_extracts_vectors(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    emb = OpenAIEmbedder("text-embedding-3-small")

    class _Item:
        def __init__(self, e):
            self.embedding = e

    class _Resp:
        data = [_Item([0.1, 0.2]), _Item([0.3, 0.4])]

    async def _fake_create(**kwargs):
        return _Resp()

    monkeypatch.setattr(emb._client.embeddings, "create", _fake_create)

    out = await emb.aembed_documents(["a", "b"])
    assert out == [[0.1, 0.2], [0.3, 0.4]]


async def test_aembed_query_returns_single_vector(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    emb = OpenAIEmbedder("text-embedding-3-small")

    class _Item:
        embedding = [0.5, 0.6]

    class _Resp:
        data = [_Item()]

    async def _fake_create(**kwargs):
        return _Resp()

    monkeypatch.setattr(emb._client.embeddings, "create", _fake_create)

    out = await emb.aembed_query("q")
    assert out == [0.5, 0.6]
