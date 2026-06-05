"""Leiden 알고리즘 기반 커뮤니티 군집화 (단일 레벨 MVP).

[Phase 9 — 동작]
1. Neo4j 에서 (source, target, weight) 엣지 목록을 읽는다.
2. igraph 무방향 그래프 → leidenalg 모듈러리티 파티션 (seed 고정 → 결정적).
   계층형(level>0)은 후속 확장 — 지금은 전부 level=0.
3. 기존 Community 노드를 전부 지우고 새로 만든 뒤 IN_COMMUNITY 로 연결한다.
   (군집은 전역 개념이라 적재 때마다 전체 재계산 — 느려지면 Phase 8 워커로)
"""
from __future__ import annotations

from app.core.graph_db import get_graph_driver
from app.schemas.graph import Community

_LOAD_EDGES = (
    "MATCH (s:Entity)-[r:RELATED]->(t:Entity) "
    "RETURN s.name AS s, t.name AS t, r.weight AS w"
)
_DELETE_COMMUNITIES = "MATCH (c:Community) DETACH DELETE c"
_SAVE_COMMUNITIES = """
UNWIND $communities AS com
CREATE (c:Community {id: com.id, level: com.level})
WITH c, com
UNWIND com.entity_ids AS name
MATCH (e:Entity {name: name})
MERGE (e)-[:IN_COMMUNITY]->(c)
"""


def compute_communities(edges: list[tuple[str, str, float]]) -> list[Community]:
    """엣지 목록 → Leiden 파티션. (순수 함수 — 단위 테스트 대상)"""
    import igraph as ig
    import leidenalg

    if not edges:
        return []
    names = sorted({n for s, t, _ in edges for n in (s, t)})
    index = {n: i for i, n in enumerate(names)}
    g = ig.Graph(
        n=len(names), edges=[(index[s], index[t]) for s, t, _ in edges], directed=False
    )
    part = leidenalg.find_partition(
        g,
        leidenalg.ModularityVertexPartition,
        weights=[w or 1.0 for _, _, w in edges],
        seed=42,
    )
    return [
        Community(id=f"c{i}", level=0, entity_ids=[names[v] for v in members])
        for i, members in enumerate(part)
    ]


async def cluster() -> list[Community]:
    """Neo4j 그래프 전체를 군집화하고 Community 노드로 저장한다."""
    driver = get_graph_driver()
    async with driver.session() as session:
        result = await session.run(_LOAD_EDGES)
        edges = [(rec["s"], rec["t"], rec["w"]) async for rec in result]
    communities = compute_communities(edges)
    async with driver.session() as session:
        await session.run(_DELETE_COMMUNITIES)
        if communities:
            await session.run(
                _SAVE_COMMUNITIES,
                communities=[
                    c.model_dump(include={"id", "level", "entity_ids"}) for c in communities
                ],
            )
    return communities
