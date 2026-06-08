"""ir/graph/cluster: Leiden 군집화 순수 함수 테스트 (Neo4j 불필요)."""
from __future__ import annotations

from app.services.ir.graph.ingest.cluster import compute_communities


def _clique(names):
    """완전그래프 엣지 목록 (서로 빽빽하게 연결된 무리)."""
    return [(a, b, 1.0) for i, a in enumerate(names) for b in names[i + 1 :]]


def test_two_cliques_with_weak_bridge_split_into_two_communities():
    edges = _clique(["a1", "a2", "a3"]) + _clique(["b1", "b2", "b3"]) + [("a1", "b1", 0.1)]
    comms = compute_communities(edges)
    groups = sorted(sorted(c.entity_ids) for c in comms)
    assert groups == [["a1", "a2", "a3"], ["b1", "b2", "b3"]]
    assert all(c.level == 0 for c in comms)
    assert sorted(c.id for c in comms) == ["c0", "c1"]


def test_empty_graph_returns_no_communities():
    assert compute_communities([]) == []
