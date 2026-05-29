"""채팅 엔드포인트 입출력 스키마.

[설계 원칙]
- 이건 *애플리케이션* API 다. LLM 을 직접 부르는 게 아니라, 클라이언트는 질문 하나만
  던지면 된다 → `question` 만 필수. 서버가 알아서 user 메시지로 변환하고 검색/생성한다.
- 멀티턴 이력은 `session_id` 로 서버가 관리한다(Phase 6 메모리). 클라이언트가 messages
  배열을 직접 쌓아 보내지 않는다.

Swagger("/docs")에서 바로 Execute 할 수 있도록 example 을 달아둔다.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class RagMode(StrEnum):
    """오케스트레이터가 사용할 검색 엔진."""

    AUTO = "auto"          # 라우터가 자동 결정
    VECTOR = "vector"      # dense + BM25 하이브리드
    GRAPH_LOCAL = "graph_local"   # 엔티티 이웃 기반 미시 검색
    GRAPH_GLOBAL = "graph_global"  # 커뮤니티 요약 맵리듀스 거시 검색
    HYBRID = "hybrid"      # vector + graph 융합


class ChatRequest(BaseModel):
    question: str = Field(
        description="사용자 질문. 서버가 user 메시지로 변환해 검색/생성에 사용한다.",
        examples=["CSS 모델링 과정에서 모형 검증 방법론을 요약해줘."],
    )
    session_id: str | None = Field(
        default=None,
        description="대화 세션 ID. 없으면 새로 발급한다. 멀티턴 이력의 키로 쓰인다(Phase 6).",
    )
    user_meta: dict = Field(
        default_factory=dict,
        description="호출 컨텍스트 메타(user_id, tenant, locale 등). 로깅/멀티테넌시/개인화용.",
        examples=[{"user_id": "u-123", "tenant": "acme", "locale": "ko-KR"}],
    )
    rag_mode: RagMode = Field(
        default=RagMode.AUTO, description="검색 엔진 선택. auto 면 서버가 결정."
    )
    top_k: int = Field(
        default=5, ge=1, le=50, description="검색 컨텍스트로 가져올 청크 수."
    )
    stream: bool = Field(
        default=True,
        description="true=SSE 토큰 스트리밍, false=동기 JSON 응답.",
    )
    model: str | None = Field(
        default=None,
        description='"provider:model" 오버라이드. 미지정 시 서버 기본 모델.',
        examples=[None],
    )

    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "question": "CSS 모델링 과정에서 모형 검증 방법론을 요약해줘.",
                "session_id": None,
                "user_meta": {"user_id": "u-123", "tenant": "acme"},
                "rag_mode": "auto",
                "top_k": 5,
                "stream": False,
            }
        },
    )


class Citation(BaseModel):
    source_id: str = Field(description="출처 문서 ID.", examples=["css-modeling-basic-day2"])
    snippet: str = Field(description="근거가 된 청크 일부.")
    score: float | None = Field(default=None, description="검색 유사도 점수.")


class ChatResponse(BaseModel):
    """동기 응답(stream=False)일 때 직렬화되는 스키마."""

    session_id: str = Field(description="대화 세션 ID(요청에 없으면 새로 발급).")
    answer: str = Field(description="생성된 답변.")
    citations: list[Citation] = Field(
        default=[], description="답변 근거가 된 출처 목록."
    )
    rag_mode: RagMode = Field(description="이번 응답에 사용된 검색 모드.")
    model: str = Field(description='실제 답변을 생성한 "provider:model".')

    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "session_id": "0f5c2d3a-1b2c-4d5e-8f90-112233445566",
                "answer": "모형 검증 방법론은 크게 ...",
                "citations": [
                    {
                        "source_id": "css-modeling-basic-day2",
                        "snippet": "모형 검증은 ...",
                        "score": 0.82,
                    }
                ],
                "rag_mode": "auto",
                "model": "anthropic:claude-haiku-4-5-20251001",
            }
        },
    )
