"""의도 파악 → 어떤 RAG 엔진(vector/graph_local/graph_global)을 쓸지 결정.

[Phase 10] rag_mode 가 AUTO 일 때만 이 함수가 동작한다(명시 지정 시엔 그대로 따른다).
- 기본은 규칙 기반(질문 속 키워드)으로 고른다 — LLM 을 부르지 않아 빠르고, 같은 질문이면
  항상 같은 결과라 디버깅이 쉽다. 비율/키워드를 바꾸려면 아래 목록만 손보면 된다.
- 더 똑똑하게 고르고 싶으면 맨 아래 _llm_route 주석을 살려서 route() 본문만 바꿔 끼운다
  (질문마다 LLM 을 1회 더 부르므로 비용·지연이 늘어 기본은 꺼 둔다).
- graph 데이터가 없어 graph 모드가 빈 결과를 줘도, retrieve 노드가 컨텍스트 없이 답을
  만들도록 이미 처리한다(검색 실패는 비치명) → auto 가 graph 로 가도 안전하다.
"""

from __future__ import annotations

from app.schemas.chat import RagMode

# 질문에 이 말들이 있으면 "전체를 훑는" 거시 질문 → 커뮤니티 요약 검색(graph_global).
_GLOBAL_HINTS = (
    "요약",
    "전체",
    "전반",
    "주요",
    "한눈",
    "개요",
    "정리",
    "통틀어",
    "overview",
    "summary",
    "summarize",
)
# 특정 대상의 "관계/연결"을 묻는 질문 → 엔티티 이웃 검색(graph_local).
_LOCAL_HINTS = (
    "관계",
    "관련",
    "사이",
    "연결",
    "누구",
    "누가",
    "relationship",
    "related",
    "between",
)


async def route(query: str) -> RagMode:
    """rag_mode=AUTO 일 때 질문을 보고 검색 모드를 고른다(기본: 규칙 기반)."""
    return _rule_route(query)


def _rule_route(query: str) -> RagMode:
    """질문 속 키워드로 모드 결정. (순수 함수 — 단위 테스트 대상)"""
    q = query.lower()  # 영어 키워드 대소문자 무시 (한글은 영향 없음)
    if any(h in q for h in _GLOBAL_HINTS):
        return RagMode.GRAPH_GLOBAL
    if any(h in q for h in _LOCAL_HINTS):
        return RagMode.GRAPH_LOCAL
    # 기본: 일반 검색. (1번 작업으로 dense+BM25 혼합 검색이 들어오면 VECTOR 가 그걸 쓴다)
    return RagMode.VECTOR


# ── LLM 분류기 버전 (선택) ───────────────────────────────────────────
# 규칙 기반이 부족하면 아래를 살리고 route() 를 `return await _llm_route(query)` 로 바꾼다.
# config/prompts/routing/classify.yaml 에 system/user 프롬프트를 만들어야 한다.
#
# async def _llm_route(query: str) -> RagMode:
#     from app.clients.chat_model import get_chat_model
#     from app.utils.prompts import load_prompt, render
#
#     prompt = load_prompt("routing/classify")
#     resp = await get_chat_model().ainvoke(
#         [("system", prompt["system"]), ("user", render(prompt["user"], query=query))]
#     )
#     raw = (resp.content if isinstance(resp.content, str) else str(resp.content)).strip()
#     try:
#         return RagMode(raw)
#     except ValueError:
#         return RagMode.VECTOR  # 모델이 엉뚱한 값을 주면 안전하게 일반 검색으로
