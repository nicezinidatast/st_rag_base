"""커뮤니티별 요약(Community Report) 생성.

[Phase 9]
- 커뮤니티 구성 엔티티/내부 관계를 Neo4j 에서 모아 텍스트로 펼친 뒤 LLM 요약.
- Global Search 가 이 리포트를 Map 입력으로 쓰므로 요약 품질 = 거시검색 품질.
- 생성된 리포트는 Community.report 에 저장된다.
"""
from __future__ import annotations

from app.core.graph_db import get_graph_driver
from app.schemas.graph import Community

_FETCH_MEMBERS = """
MATCH (e:Entity)-[:IN_COMMUNITY]->(c:Community {id: $id})
OPTIONAL MATCH (e)-[r:RELATED]-(o:Entity)-[:IN_COMMUNITY]->(c)
RETURN e.name AS name, e.type AS type, e.description AS description,
       collect(DISTINCT e.name + ' -[' + r.type + ']-> ' + o.name) AS relations
"""
_SAVE_REPORT = "MATCH (c:Community {id: $id}) SET c.report = $report"


async def summarize(community: Community) -> str:
    from app.clients.chat_model import get_chat_model
    from app.utils.prompts import load_prompt, render

    entities_text, relations_text = await _fetch_members(community.id)
    prompt = load_prompt("graphrag/community_report")
    resp = await get_chat_model().ainvoke(
        [
            ("system", prompt["system"]),
            ("user", render(prompt["user"], entities=entities_text, relations=relations_text)),
        ]
    )
    report = resp.content if isinstance(resp.content, str) else str(resp.content)
    async with get_graph_driver().session() as session:
        await session.run(_SAVE_REPORT, id=community.id, report=report)
    return report


async def _fetch_members(community_id: str) -> tuple[str, str]:
    """커뮤니티 구성원을 '엔티티 목록 텍스트'와 '관계 목록 텍스트'로 펼친다."""
    entity_lines: list[str] = []
    relation_lines: set[str] = set()
    async with get_graph_driver().session() as session:
        result = await session.run(_FETCH_MEMBERS, id=community_id)
        async for rec in result:
            entity_lines.append(f"- {rec['name']} ({rec['type']}): {rec['description'] or ''}")
            relation_lines.update(r for r in rec["relations"] if r)
    return "\n".join(entity_lines), "\n".join(sorted(relation_lines))
