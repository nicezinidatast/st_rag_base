"""ir/graph/ingest: 파이프라인 오케스트레이션(전부 가짜) 테스트."""
from __future__ import annotations

import app.services.ir.graph.ingest as ingest_module
import app.services.ir.graph.ingest.cluster as cluster_module
import app.services.ir.graph.ingest.extractor as extractor_module
import app.services.ir.graph.ingest.summarizer as summarizer_module
from app.schemas.graph import Community, Entity, Relation, Subgraph


async def _fake_ensure_schema():
    return None


def _patch_common(monkeypatch, communities):
    async def _fake_cluster():
        return communities

    monkeypatch.setattr(ingest_module, "ensure_schema", _fake_ensure_schema)
    monkeypatch.setattr(cluster_module, "cluster", _fake_cluster)


async def test_ingest_pipeline_counts_and_flow(monkeypatch):
    calls = {"upsert": 0, "summarize": []}

    async def _fake_extract(text, model=None):
        return Subgraph(
            entities=[Entity(id="서울", name="서울", type="LOCATION")],
            relations=[Relation(source="서울", target="대한민국", type="CAPITAL_OF")],
        )

    async def _fake_upsert(sub, source_id):
        calls["upsert"] += 1

    async def _fake_summarize(com):
        calls["summarize"].append(com.id)
        return "리포트"

    _patch_common(monkeypatch, [Community(id="c0", level=0, entity_ids=["서울", "대한민국"])])
    monkeypatch.setattr(extractor_module, "extract", _fake_extract)
    monkeypatch.setattr(ingest_module, "_upsert_subgraph", _fake_upsert)
    monkeypatch.setattr(summarizer_module, "summarize", _fake_summarize)

    out = await ingest_module.ingest("doc-1", "서울은 대한민국의 수도이다.")

    assert out == {"entities": 1, "relations": 1, "communities": 1}
    assert calls["upsert"] == 1
    assert calls["summarize"] == ["c0"]


async def test_ingest_skips_failed_chunk(monkeypatch):
    async def _boom(text, model=None):
        raise RuntimeError("llm down")

    _patch_common(monkeypatch, [])
    monkeypatch.setattr(extractor_module, "extract", _boom)

    out = await ingest_module.ingest("doc-1", "본문")
    assert out == {"entities": 0, "relations": 0, "communities": 0}


def test_chunk_uses_graph_sizes():
    text = "가" * 3000
    chunks = ingest_module._chunk(text)
    assert len(chunks[0]) == 1200
    assert chunks[1][:100] == chunks[0][-100:]  # 오버랩 100
