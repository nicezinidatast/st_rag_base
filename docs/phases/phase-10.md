# Phase 10 — 자동 라우팅 (하이브리드 융합 모드는 보류)

- **커밋:** _(미커밋, 작업 트리)_
- **목표:** `rag_mode="auto"` 면 질문을 보고 어떤 검색 엔진을 쓸지 시스템이 고른다.
  (이전엔 auto 가 그냥 일반 벡터 검색으로 조용히 넘어갔다.)
- **검증:** 전체 `pytest` 99 passed(신규 5 + 그래프 견고성 3). ruff / mypy 통과.
  수동: 같은 질문을 `auto` 로 던지고 로그 `node_route_auto` 의 선택 모드를 확인.

---

## A. 라우터 (`orchestrator/routing.py`)

`route(query)`: 질문을 보고 검색 모드를 돌려준다. **기본은 규칙 기반**(LLM 안 부름):

- "요약/전체/주요/개요…" → `graph_global` (전체를 훑는 거시 질문)
- "관계/관련/누구/누가/연결…" → `graph_local` (특정 대상의 이웃·관계)
- 그 외 → `vector` (= dense+BM25 혼합 검색)

규칙 기반은 빠르고, 같은 질문이면 항상 같은 결과라 디버깅이 쉽다. 키워드 목록만 바꾸면 조정된다.

## B. LLM 라우터는 주석으로

더 똑똑하게 고르고 싶으면 같은 파일 아래쪽 `_llm_route` 주석을 살리고 `route()` 한 줄만 바꾼다.
질문마다 LLM 을 1회 더 부르므로(비용·지연) 기본은 꺼 둔다.

## C. 연결 (`workflow/nodes/retrieve.py`)

`rag_mode=auto` 면 검색 직전에 `route()` 로 실제 모드를 정한 뒤 기존 분기를 탄다.
MOCK 검색기일 땐 의미가 없어 건너뛴다. graph 데이터가 없어 graph 모드가 빈 결과를 줘도
retrieve 가 컨텍스트 없이 답을 만들도록 이미 처리돼 있어 안전하다.

## D. 보류한 것 — vector × graph 융합 모드

`rag_mode="hybrid"`(벡터 + 그래프 결과를 합치는 모드)는 만들지 않았다. graph 를 쓰는 것
자체가 모든 배포에서 필요한 게 아니고, 융합 방식·가중치는 배포마다 달라지는 부분이기 때문이다.
필요해지면 Phase 4 의 `reciprocal_rank_fusion` 을 그대로 재사용하면 된다.

## E. 함께 처리 — GraphRAG 검색 견고성 (Phase 9 백로그)

- `ir/graph/search/global_.py` — Map(LLM) 호출을 부분 실패 허용으로 바꿔, 리포트 하나가
  실패해도 나머지로 답한다(`_is_relevant`). "관련 없음" 센티넬은 구두점이 붙어도 무관 처리.
- `ir/graph/search/local.py` — 풀텍스트 질의의 대문자 `AND/OR/NOT`(Lucene 연산자)을
  소문자로 낮춰 파스 에러를 막는다.
