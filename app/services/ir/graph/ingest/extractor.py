"""LLM 기반 엔티티 & 관계(지식 트리플렛) 추출.

[구현 가이드]
- config/prompts/graphrag/entity_extraction.yaml 프롬프트 + clients/chat_model 사용.
- 텍스트 청크에서 (엔티티, 타입, 설명) 과 (source, target, type) 추출 → schemas.graph.Subgraph.
- 결과를 core/graph_db 에 노드/엣지로 적재.
"""
from __future__ import annotations

from app.schemas.graph import Subgraph


async def extract(text: str) -> Subgraph:
    raise NotImplementedError("entity 추출 미구현")
