"""그래프 저장소 드라이버 (기본 Neo4j, NebulaGraph 등으로 교체 가능).

[구현 가이드]
- get_graph_driver() 가 드라이버를 반환. GraphRAG 적재(ir/graph/ingest)와
  검색(ir/graph/search)에서 사용.
- 엔티티/관계 노드 스키마, 커뮤니티 계층 인덱스 설계를 먼저 정하고 시작할 것.
"""
from __future__ import annotations

from app.core.config import settings


def get_graph_driver():
    # TODO: from neo4j import AsyncGraphDatabase
    #       return AsyncGraphDatabase.driver(settings.GRAPH_DB_URI,
    #                                         auth=(settings.GRAPH_DB_USER, settings.GRAPH_DB_PASSWORD))
    raise NotImplementedError("graph_db 드라이버 미구현")
