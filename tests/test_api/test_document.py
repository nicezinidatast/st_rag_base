"""POST /api/v1/documents/ingest 엔드포인트 테스트. 실제 적재는 가짜로 끼운다."""
from __future__ import annotations

from fastapi.testclient import TestClient

import app.services.ir.vector.ingest as ingest_module
from app.main import app


def test_ingest_calls_vector_ingest(monkeypatch):
    async def _fake_ingest(source_id, content, metadata=None):
        return 3

    monkeypatch.setattr(ingest_module, "ingest", _fake_ingest)

    client = TestClient(app)
    resp = client.post(
        "/api/v1/documents/ingest",
        json={"source_id": "doc-1", "content": "hello", "targets": ["vector"]},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ingested"
    assert body["source_id"] == "doc-1"
    assert body["vector_chunks"] == 3


def test_ingest_without_content_returns_400():
    client = TestClient(app)
    resp = client.post(
        "/api/v1/documents/ingest",
        json={"source_id": "doc-1", "targets": ["vector"]},
    )
    assert resp.status_code == 400


def test_ingest_calls_graph_ingest(monkeypatch):
    import app.services.ir.graph.ingest as graph_ingest_module

    async def _fake_graph_ingest(source_id, content, metadata=None):
        return {"entities": 4, "relations": 2, "communities": 1}

    monkeypatch.setattr(graph_ingest_module, "ingest", _fake_graph_ingest)

    client = TestClient(app)
    resp = client.post(
        "/api/v1/documents/ingest",
        json={"source_id": "doc-1", "content": "hello", "targets": ["graph"]},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["graph_entities"] == 4
    assert body["graph_relations"] == 2
    assert body["graph_communities"] == 1
    assert "vector_chunks" not in body  # graph 만 지정 시 vector 는 건너뜀


def test_graph_ingest_failure_returns_503(monkeypatch):
    import app.services.ir.graph.ingest as graph_ingest_module

    async def _boom(source_id, content, metadata=None):
        raise RuntimeError("neo4j down")

    monkeypatch.setattr(graph_ingest_module, "ingest", _boom)

    client = TestClient(app)
    resp = client.post(
        "/api/v1/documents/ingest",
        json={"source_id": "doc-1", "content": "hello", "targets": ["graph"]},
    )
    assert resp.status_code == 503
