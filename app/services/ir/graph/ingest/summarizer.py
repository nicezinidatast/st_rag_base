"""커뮤니티별 요약(Community Report) 생성.

[구현 가이드]
- config/prompts/graphrag/community_report.yaml + chat_model 로 각 커뮤니티 요약.
- Global Search 가 이 리포트들을 맵리듀스로 활용하므로, 요약 품질이 거시검색 품질을 좌우.
"""
from __future__ import annotations

from app.schemas.graph import Community


async def summarize(community: Community) -> str:
    raise NotImplementedError("community 요약 미구현")
