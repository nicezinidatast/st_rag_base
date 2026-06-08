"""그래프 저장소 드라이버 (기본 Neo4j, NebulaGraph 등으로 교체 가능).

[Phase 9]
- get_graph_driver(): 프로세스당 1회 생성되는 비동기 드라이버. 생성만으로는 접속하지
  않고 첫 쿼리에서 붙는다(지연 연결 — vector_db 의 Qdrant 클라이언트와 같은 철학).
- ensure_schema(): 유니크 제약 + 풀텍스트 인덱스를 IF NOT EXISTS 로 생성(이미 있으면 건너뜀).
  graph ingest 진입 시마다 호출해도 안전하다.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from neo4j import AsyncDriver

# 스키마(제약/인덱스) — 전부 IF NOT EXISTS 라 이미 있으면 건너뜀(여러 번 실행해도 안전)
SCHEMA_STATEMENTS = [
    "CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE",
    "CREATE CONSTRAINT community_id IF NOT EXISTS FOR (c:Community) REQUIRE c.id IS UNIQUE",
    "CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS "
    "FOR (e:Entity) ON EACH [e.name, e.description]",
    "CREATE FULLTEXT INDEX community_fulltext IF NOT EXISTS FOR (c:Community) ON EACH [c.report]",
]


@lru_cache
def get_graph_driver() -> AsyncDriver:
    from neo4j import AsyncGraphDatabase

    return AsyncGraphDatabase.driver(
        settings.GRAPH_DB_URI, auth=(settings.GRAPH_DB_USER, settings.GRAPH_DB_PASSWORD)
    )


async def ensure_schema() -> None:
    """엔티티/커뮤니티 제약과 풀텍스트 인덱스를 보장한다.

    이미 있으면 건너뛰므로 여러 번 호출해도 안전하다.
    """
    driver = get_graph_driver()
    async with driver.session() as session:
        for stmt in SCHEMA_STATEMENTS:
            await session.run(stmt)
