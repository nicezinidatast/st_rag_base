"""GraphRAG 검증 스키마: 엔티티/관계/서브그래프/커뮤니티.

[구현 가이드] extractor 가 Subgraph 를 반환, cluster/summarizer 가 Community 를 채운다.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Entity(BaseModel):
    id: str
    name: str
    type: str
    description: str | None = None


class Relation(BaseModel):
    """지식 트리플렛: (source) -[type]-> (target)."""

    source: str
    target: str
    type: str
    description: str | None = None
    weight: float = 1.0


class Subgraph(BaseModel):
    entities: list[Entity] = []
    relations: list[Relation] = []


class Community(BaseModel):
    id: str
    level: int = 0
    entity_ids: list[str] = Field(default_factory=list)
    report: str | None = None  # 커뮤니티 요약 리포트
