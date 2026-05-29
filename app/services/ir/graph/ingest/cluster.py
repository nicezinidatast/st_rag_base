"""Leiden 알고리즘 기반 계층적 커뮤니티 군집화.

[구현 가이드]
- 구축된 지식그래프에 Leiden(예: graspologic/igraph) 적용해 계층적 커뮤니티 도출.
- 각 커뮤니티에 level/구성 엔티티를 부여 → schemas.graph.Community 리스트 반환.
"""
from __future__ import annotations

from app.schemas.graph import Community


async def cluster(graph) -> list[Community]:
    raise NotImplementedError("community 군집화 미구현")
