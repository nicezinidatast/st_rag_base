"""문서 적재/검색 필터 스키마.

[구현 가이드] targets 로 vector/graph 중 어디에 적재할지 선택. content(인라인)
또는 uri(원격/오브젝트 스토리지) 중 하나로 본문 전달.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class IngestTarget(str, Enum):
    VECTOR = "vector"
    GRAPH = "graph"


class DocumentUpload(BaseModel):
    source_id: str
    content: str | None = None
    uri: str | None = None  # 원격/오브젝트 스토리지 위치 (인라인이 아닐 때)
    metadata: dict = Field(default_factory=dict)
    targets: list[IngestTarget] = [IngestTarget.VECTOR]


class FilterCondition(BaseModel):
    """검색 시 적용할 메타데이터 필터 (eq / in / range 등)."""

    field: str
    op: str = "eq"
    value: object
