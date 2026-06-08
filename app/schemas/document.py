"""문서 적재/검색 필터 스키마.

[구현 가이드] targets 로 vector/graph 중 어디에 적재할지 선택. content(인라인)
또는 uri(원격/오브젝트 스토리지) 중 하나로 본문 전달.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class IngestTarget(StrEnum):
    VECTOR = "vector"
    GRAPH = "graph"


class DocumentUpload(BaseModel):
    source_id: str = Field(
        description="문서 식별자(재적재 시 동일 id 면 멱등 갱신).",
        examples=["css-modeling-basic-day2"],
    )
    content: str | None = Field(
        default=None, description="인라인 본문. (Phase 3 는 content 만 지원)"
    )
    uri: str | None = Field(
        default=None, description="원격/오브젝트 스토리지 위치(인라인이 아닐 때)."
    )
    metadata: dict = Field(
        default_factory=dict, description="검색 시 함께 보존할 메타데이터."
    )
    targets: list[IngestTarget] = Field(
        default=[IngestTarget.VECTOR], description="적재 대상 저장소."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source_id": "css-modeling-basic-day2",
                "content": "모형 검증은 모형의 안정성과 변별력을 통계적으로 점검하는 과정이다. ...",
                "metadata": {"course": "CSS 모델링(Basic)", "day": 2},
                "targets": ["vector"],
            }
        }
    )


class FilterCondition(BaseModel):
    """검색 시 적용할 메타데이터 필터 (eq / in / range 등)."""

    field: str
    op: str = "eq"
    value: object
